"""Terminus-2 agent with host intervention and verification.

Extends HarborTerminus2WithSkills to add:
- Pre-task: inject meta-skills (skill-creator) into container
- Intra-task: host intervention loop (independent verifier, progress checklist, GT oracle)
- Post-task: export verifier scripts, read evolution summary, write detailed logs
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import tempfile
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from harbor.environments.base import BaseEnvironment
from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.task.config import TaskConfig
from harbor.models.trial.paths import TrialPaths

from libs.terminus_agent.evolution.independent_verifier import IndependentVerifier
from libs.terminus_agent.evolution.models import VerificationResult
from libs.terminus_agent.evolution.self_verifier import SelfVerifier

from .harbor_terminus_2_skills import EpisodeExitResult, HarborTerminus2WithSkills
from .skill_docs import is_shell_warning

logger = logging.getLogger(__name__)


def _evo_print(msg: str) -> None:
    """Print evolution status to stdout, silently ignoring BrokenPipeError."""
    try:
        print(msg, flush=True)
    except BrokenPipeError:
        pass


class HarborTerminus2Evolution(HarborTerminus2WithSkills):
    """Terminus-2 agent with host intervention and verification."""

    _IDLE_EPISODE_LIMIT: int = 3  # consecutive empty-command episodes before forced intervention
    _STALE_EPISODE_LIMIT: int = 10  # episodes without task_complete before forced intervention

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        sequential_run: int = 1,
        gt_oracle_model: str | None = None,
        max_host_interventions: int = 5,
        independent_verifier_model: str | None = None,
        gt_oracle_agent: str | None = None,
        timeout_multiplier: float = 1.0,
        skip_surrogate_verifier: bool = False,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, timeout_multiplier=timeout_multiplier, **kwargs)
        self._skip_surrogate_verifier = skip_surrogate_verifier

        self._sequential_run = sequential_run
        self._gt_oracle_model = gt_oracle_model
        self._gt_oracle_agent = gt_oracle_agent or "terminus-2"

        # Evolution components
        self._verifier = SelfVerifier()  # Used to read pytest results after independent verifier runs
        self._independent_verifier = IndependentVerifier(
            model_name=independent_verifier_model or model_name or "",
            temperature=0.3,
        )

        # Runtime state
        self._environment: BaseEnvironment | None = None
        self._instruction: str = ""
        self._meta_skills_injected: list[str] = []

        # Host intervention state (reset at start of each run())
        self._host_intervention_count: int = 0  # only surrogate_pass increments this
        self._max_host_interventions: int = max_host_interventions
        self._surrogate_retry_count: int = 0  # surrogate_fail / verifier errors
        self._max_surrogate_retries: int = 15  # fixed cap for surrogate retries
        self._exit_reason: str = ""
        self._intervention_history: list[dict] = []
        self._pre_existing_skills: set[str] = set()
        self._best_gt_snapshot: dict | None = None  # best GT skills snapshot for rollback
        self._surrogate_tests_locked: bool = False  # lock surrogate tests after first valid generation
        self._checklist_fail_count: int = 0  # consecutive checklist failures (enforce once, then advisory)
        self._frontmatter_fix_requested: bool = False  # whether we already asked agent to fix frontmatter

        # Idle detection state
        self._consecutive_idle_episodes: int = 0  # consecutive episodes with no commands
        self._episodes_since_last_complete: int = 0  # episodes since last task_complete signal

    @staticmethod
    def name() -> str:
        return "terminus-2-evolution"

    def version(self) -> str | None:
        return "2.2.0"

    def _get_prompt_template_path(self) -> Path:
        """Return the evolution-specific prompt template for JSON parser, else delegate to parent."""
        if self._parser_name != "json":
            return super()._get_prompt_template_path()
        root = os.environ.get("SKILLSBENCH_ROOT")
        candidates = [Path(root)] if root else []
        candidates.append(Path.cwd())
        for c in candidates:
            p = c / "libs/terminus_agent/agents/prompt-templates/terminus-evolution-json.txt"
            if p.exists():
                return p
        return Path(__file__).resolve().parent.parent / "prompt-templates" / "terminus-evolution-json.txt"

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _resolve_evolution_dir(self) -> Path:
        """Return the ``environment/.evolution/`` directory for storing evolution artifacts."""
        env_dir = getattr(self._environment, "environment_dir", None)
        if env_dir:
            return Path(env_dir) / ".evolution"
        return self.logs_dir / ".evolution"

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)
        self._environment = environment

        # Inject meta-skills into container
        self._meta_skills_injected = await self._inject_meta_skills(environment)

        # Inject previous verifier script into container (from prior runs)
        await self._inject_previous_verifier(environment)

    # ------------------------------------------------------------------
    # Meta-skill injection
    # ------------------------------------------------------------------

    def _find_meta_skills_dir(self) -> Path | None:
        """Locate the .claude/skills directory on the host."""
        # Try common locations
        candidates = [
            Path(__file__).resolve().parents[4] / ".claude" / "skills",  # repo root
        ]
        # Also check SKILLSBENCH_ROOT env
        root = os.environ.get("SKILLSBENCH_ROOT")
        if root:
            candidates.insert(0, Path(root) / ".claude" / "skills")

        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return None

    async def _inject_meta_skills(self, environment: BaseEnvironment) -> list[str]:
        """Inject meta-skills into the container.

        Only skill-creator is injected. Verification is handled by the
        independent verifier agent (separate LLM session) — skill-verifier
        is no longer needed in the evolution agent's context.
        """
        meta_dir = self._find_meta_skills_dir()
        if not meta_dir:
            logger.warning("Meta-skills directory not found")
            return []

        name = "skill-creator"
        src = meta_dir / name
        if not src.exists():
            logger.info("Meta-skill %s not found at %s", name, src)
            return []

        success = await self._inject_skill_dir_to_container(name, src, environment)
        if success:
            logger.info("Injected meta-skill: %s", name)
            return [name]

        return []

    async def _inject_previous_verifier(self, environment: BaseEnvironment) -> None:
        """Inject the most recent exported verifier script into a new container.

        Looks for ``environment/verifier/generated_scripts/test_outputs_v*.py``
        on the host, takes the highest version, and injects it into the container
        at ``/root/verifier/test_outputs.py``.  This ensures manual reruns benefit
        from the verifier built during a prior run.
        """
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir:
            return

        scripts_dir = Path(env_dir) / "verifier" / "generated_scripts"
        if not scripts_dir.is_dir():
            return

        candidates = sorted(
            scripts_dir.glob("test_outputs_v*.py"),
            key=lambda p: int(re.search(r"_v(\d+)\.py$", p.name).group(1)),
        )
        if not candidates:
            return

        latest = candidates[-1]
        logger.info("Injecting previous verifier script: %s", latest.name)

        raw = latest.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        result = await environment.exec(
            command=(f"mkdir -p /root/verifier && echo '{encoded}' | base64 -d > /root/verifier/test_outputs.py"),
            timeout_sec=30,
        )
        if result.return_code != 0:
            logger.warning("Failed to inject previous verifier: %s", result.stderr)
        else:
            logger.info("Previous verifier injected into container at /root/verifier/test_outputs.py")

    async def _inject_skill_dir_to_container(
        self,
        name: str,
        skill_dir: Path,
        environment: BaseEnvironment,
    ) -> bool:
        """Copy a skill directory (SKILL.md, scripts/, references/) into the container.

        All file content is transferred via base64 encoding to avoid heredoc
        delimiter collisions with arbitrary skill content.
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return False

        container_dir = f"/app/environment/skills/{name}"

        # Write SKILL.md via base64
        encoded = base64.b64encode(skill_md.read_bytes()).decode("ascii")
        result = await environment.exec(
            command=f"mkdir -p '{container_dir}' && echo '{encoded}' | base64 -d > '{container_dir}/SKILL.md'",
            timeout_sec=30,
        )
        if result.return_code != 0:
            logger.warning("Failed to inject skill %s: %s", name, result.stderr)
            return False

        # Copy scripts/ via base64
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            for script_file in sorted(scripts_dir.iterdir()):
                if script_file.is_file():
                    encoded = base64.b64encode(script_file.read_bytes()).decode("ascii")
                    await environment.exec(
                        command=(
                            f"mkdir -p '{container_dir}/scripts' && "
                            f"echo '{encoded}' | base64 -d > '{container_dir}/scripts/{script_file.name}' && "
                            f"chmod +x '{container_dir}/scripts/{script_file.name}'"
                        ),
                        timeout_sec=15,
                    )

        # Copy references/ via base64
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            for ref_file in sorted(refs_dir.iterdir()):
                if ref_file.is_file():
                    encoded = base64.b64encode(ref_file.read_bytes()).decode("ascii")
                    await environment.exec(
                        command=(
                            f"mkdir -p '{container_dir}/references' && "
                            f"echo '{encoded}' | base64 -d > '{container_dir}/references/{ref_file.name}'"
                        ),
                        timeout_sec=15,
                    )

        # Restore app_files/ to /app/ — these are agent-created task files
        # (e.g. solution.py) that live outside /app/environment/ and would
        # otherwise be lost when a new container is created.
        app_files_dir = skill_dir / "app_files"
        if app_files_dir.is_dir():
            for app_file in sorted(app_files_dir.iterdir()):
                if app_file.is_file():
                    encoded = base64.b64encode(app_file.read_bytes()).decode("ascii")
                    await environment.exec(
                        command=f"echo '{encoded}' | base64 -d > '/app/{app_file.name}'",
                        timeout_sec=15,
                    )
            logger.info("Restored %d app_files to /app/ for skill %s", len(list(app_files_dir.iterdir())), name)

        return True

    async def _validate_skill_frontmatter(self, environment: BaseEnvironment) -> list[str]:
        """Check evolved skills in container for missing or broken YAML frontmatter.

        Returns list of (skill_path, issue) tuples for skills with frontmatter problems.
        Checks for:
        1. Missing frontmatter entirely (no --- delimiter)
        2. Missing name: or description: fields
        3. YAML syntax errors (e.g. unquoted colons in description values)
        """
        # Find all evo-* SKILL.md files in the container
        result = await environment.exec(
            command="find /app/environment/skills/evo-* -name 'SKILL.md' 2>/dev/null",
            timeout_sec=10,
        )
        if result.return_code != 0 or not result.stdout.strip():
            return []

        # Use a Python one-liner in the container to validate YAML frontmatter
        # This catches both missing frontmatter and YAML syntax errors (unquoted colons etc.)
        validate_script = r"""
import yaml, sys, glob
issues = []
for path in sys.argv[1:]:
    try:
        content = open(path).read()
    except Exception:
        continue
    if not content.strip().startswith('---'):
        issues.append(f'{path}: missing frontmatter')
        continue
    parts = content.split('---', 2)
    if len(parts) < 3:
        issues.append(f'{path}: malformed frontmatter delimiters')
        continue
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        issues.append(f'{path}: YAML syntax error (likely unquoted colon in description)')
        continue
    if not isinstance(data, dict):
        issues.append(f'{path}: frontmatter is not a mapping')
        continue
    if 'name' not in data:
        issues.append(f'{path}: missing name field')
    if 'description' not in data:
        issues.append(f'{path}: missing description field')
for issue in issues:
    print(issue)
"""
        skill_paths = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
        if not skill_paths:
            return []

        paths_arg = " ".join(f"'{p}'" for p in skill_paths)
        validate_result = await environment.exec(
            command=f"python3 -c {validate_script!r} {paths_arg}",
            timeout_sec=15,
        )

        if validate_result.return_code != 0 or not validate_result.stdout.strip():
            return []

        return [line.strip() for line in validate_result.stdout.strip().split("\n") if line.strip()]

    # ------------------------------------------------------------------
    # Intra-run host intervention
    # ------------------------------------------------------------------

    async def _check_episode_exit(
        self,
        episode: int,
        result: Any,
        environment: BaseEnvironment,
        terminal_output: str,
    ) -> EpisodeExitResult:
        """Override: host-level verification between episodes.

        Cascade:
        1. Token budget > 70% → record intervention + force stop
        2. Idle/stale detection (when NOT task_complete):
           → consecutive empty episodes >= 3 OR episodes since last complete >= 10:
             force task_complete to trigger surrogate verification
           → otherwise: keep going
        3. Intervention cap exceeded → record intervention + accept and stop
        4. Independent surrogate verifier (separate LLM session):
           → fails or pass_rate < 1.0: record intervention, reset checklist (P2-P6), feed failures back
           → no script / script error: record intervention, feed back to agent
        5. Progress checklist → enforce once (first fail returns agent), then advisory (proceed to GT oracle)
        6. Record intervention (surrogate result + skills snapshot)
        7. Full GT oracle (always, default to same model):
           → pass: early stop + write oracle_stop.json
           → fail: feed back to agent
           → error/timeout: trust surrogate, accept
        """
        # ── 1. Token budget check (always) ──
        if self._chat is not None:
            max_tokens = self._get_max_context_tokens()
            if self._chat.last_input_tokens >= max_tokens * 0.9:
                self._exit_reason = "token_budget"
                _evo_print(f"[evolution] Exit: token_budget ({self._chat.last_input_tokens}/{max_tokens} tokens)")
                logger.info(
                    "Token budget exceeded: %d / %d (%.0f%%), force stopping (intervention_count=%d)",
                    self._chat.last_input_tokens,
                    max_tokens,
                    self._chat.last_input_tokens / max_tokens * 100,
                    self._host_intervention_count,
                )
                await self._record_intervention(environment, trigger="token_budget")
                return EpisodeExitResult(should_exit=True, exit_reason="token_budget")

        # ── 2. Idle / stale detection (only when agent did NOT signal task_complete) ──
        if not result.is_task_complete:
            has_commands = len(result.commands) > 0 and any(c.keystrokes.strip() for c in result.commands)
            if has_commands:
                self._consecutive_idle_episodes = 0
            else:
                self._consecutive_idle_episodes += 1
            self._episodes_since_last_complete += 1

            idle_triggered = self._consecutive_idle_episodes >= self._IDLE_EPISODE_LIMIT
            stale_triggered = self._episodes_since_last_complete >= self._STALE_EPISODE_LIMIT

            if idle_triggered or stale_triggered:
                trigger = "idle_agent" if idle_triggered else "stale_agent"
                logger.info(
                    "Agent appears stuck (%s): idle=%d, stale=%d — forcing surrogate verification",
                    trigger,
                    self._consecutive_idle_episodes,
                    self._episodes_since_last_complete,
                )
                # Force into the surrogate verification flow below
                result.is_task_complete = True
            else:
                return EpisodeExitResult(should_exit=False)

        # Agent signalled task_complete (or was forced by idle detection) — reset stale counters
        self._consecutive_idle_episodes = 0
        self._episodes_since_last_complete = 0

        # ── 3. Intervention cap → prevent infinite loop ──
        cap_hit = self._host_intervention_count >= self._max_host_interventions
        retry_cap_hit = self._surrogate_retry_count >= self._max_surrogate_retries
        if cap_hit or retry_cap_hit:
            self._exit_reason = "max_interventions" if cap_hit else "max_surrogate_retries"
            _evo_print(
                f"[evolution] Intervention cap reached ({self._exit_reason}): "
                f"oracle={self._host_intervention_count}/{self._max_host_interventions}, "
                f"retries={self._surrogate_retry_count}/{self._max_surrogate_retries}"
            )
            logger.info(
                "Intervention cap reached (oracle=%d/%d, surrogate_retries=%d/%d), running final GT oracle before accepting",
                self._host_intervention_count,
                self._max_host_interventions,
                self._surrogate_retry_count,
                self._max_surrogate_retries,
            )
            intervention = await self._record_intervention(environment, trigger="max_interventions")

            # Final GT oracle — record result for analysis, then always stop
            oracle_model = self._gt_oracle_model or self._model_name
            evolved_skills_dir = await self._export_evolved_skills_to_host(environment)
            try:
                gt_oracle_result = await self._run_gt_oracle_check(
                    self._instruction,
                    environment,
                    oracle_model=oracle_model,
                    evolved_skills_dir=evolved_skills_dir,
                    oracle_label=f"gt-oracle-max-{self._host_intervention_count}",
                )
            except Exception as oracle_exc:
                logger.warning("Final GT oracle check failed: %s", oracle_exc)
                gt_oracle_result = {"passed": None, "error": str(oracle_exc)}
            finally:
                if evolved_skills_dir:
                    shutil.rmtree(evolved_skills_dir, ignore_errors=True)

            gt_error = gt_oracle_result.get("error") if gt_oracle_result else None
            if gt_error:
                intervention["gt_result"] = {
                    "source": "gt_oracle",
                    "passed": None,
                    "error": gt_error,
                }
            elif gt_oracle_result is not None:
                gt_passed = gt_oracle_result.get("passed")
                raw = gt_oracle_result.get("raw_output") or ""
                intervention["gt_result"] = {
                    "source": "gt_oracle",
                    "passed": gt_passed,
                    "pass_rate": gt_oracle_result.get("pass_rate"),
                    "tests_passed": gt_oracle_result.get("tests_passed"),
                    "total_tests": gt_oracle_result.get("total_tests"),
                    "test_details": gt_oracle_result.get("test_details"),
                    "failure_reasons": gt_oracle_result.get("failure_reasons"),
                    "raw_output": raw[-5000:] if len(raw) > 5000 else raw,
                }
                await self._maybe_save_best_snapshot(environment, gt_oracle_result, self._host_intervention_count)
                if gt_passed is True:
                    self._exit_reason = "gt_oracle_pass"
                    task_name = self._extract_task_name(environment)
                    self._write_oracle_stop_signal(task_name, gt_result=gt_oracle_result)
                    return EpisodeExitResult(should_exit=True, exit_reason="gt_oracle_pass")

            return EpisodeExitResult(should_exit=True, exit_reason=self._exit_reason)

        _evo_print(
            f"[evolution] Running surrogate verifier (oracle={self._host_intervention_count}/{self._max_host_interventions}, "
            f"retries={self._surrogate_retry_count}/{self._max_surrogate_retries}, locked={self._surrogate_tests_locked})"
        )
        logger.info(
            "Running independent verifier (oracle=%d/%d, surrogate_retries=%d/%d, locked=%s)",
            self._host_intervention_count,
            self._max_host_interventions,
            self._surrogate_retry_count,
            self._max_surrogate_retries,
            self._surrogate_tests_locked,
        )

        # ── 4. Independent surrogate verifier ──
        # When skip_surrogate_verifier is set, bypass entirely and go straight to GT oracle.
        if self._skip_surrogate_verifier:
            logger.info("Surrogate verifier skipped (--skip-surrogate-verifier flag)")
            surrogate_dict: dict = {"tests_passed": 0, "tests_failed": 0, "total_tests": 0, "pass_rate": 1.0}
            await self._record_intervention(environment, trigger="surrogate_skipped", surrogate_result=surrogate_dict)
        # When locked, re-run the existing pytest script without spawning a new LLM.
        # When unlocked, launch a separate LLM session to generate + run pytest.
        elif self._surrogate_tests_locked:
            # Re-run existing surrogate tests (no new LLM session)
            logger.info("Surrogate tests locked — re-running existing script via SelfVerifier")
            try:
                verification = await self._verifier.verify(environment=environment)
            except Exception as exc:
                logger.warning("Locked surrogate re-run failed: %s", exc)
                self._surrogate_retry_count += 1
                logger.info("Surrogate retry %d/%d (trigger=locked_rerun_exception)", self._surrogate_retry_count, self._max_surrogate_retries)
                await self._record_intervention(environment, trigger="locked_rerun_exception")
                feedback = (
                    "Verification could not be completed due to an infrastructure error. "
                    "Please verify your output manually — re-read the task instruction, "
                    "check all output files, and signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

            if verification.source in ("no_script", "script_error"):
                self._surrogate_retry_count += 1
                error_detail = verification.error or verification.reasoning
                trigger = "locked_" + verification.source
                logger.warning("Locked surrogate issue (%s): %s", trigger, error_detail)
                logger.info("Surrogate retry %d/%d (trigger=%s)", self._surrogate_retry_count, self._max_surrogate_retries, trigger)
                await self._record_intervention(environment, trigger=trigger)
                feedback = (
                    f"Verification could not be completed ({error_detail}). "
                    "Please verify your output manually — re-read the task instruction, "
                    "check all output files, and signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)
        else:
            # Unlocked: launch independent verifier LLM to generate + run tests
            try:
                verification = await self._independent_verifier.generate_and_run(
                    environment=environment,
                    instruction=self._instruction,
                    logs_dir=self.logs_dir,
                )
            except Exception as exc:
                logger.warning("Independent verification failed: %s", exc)
                self._surrogate_retry_count += 1
                logger.info("Surrogate retry %d/%d (trigger=verifier_exception)", self._surrogate_retry_count, self._max_surrogate_retries)
                await self._record_intervention(environment, trigger="verifier_exception")
                feedback = (
                    "Verification could not be completed due to an infrastructure error. "
                    "Please verify your output manually — re-read the task instruction, "
                    "check all output files, and signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

            if verification.source in ("no_script", "script_error"):
                self._surrogate_retry_count += 1
                error_detail = verification.error or verification.reasoning
                trigger = {
                    "script_error": "verifier_script_error",
                    "no_script": "verifier_no_script",
                }.get(verification.source, "verifier_no_script")
                logger.warning("Verifier issue (%s): %s", trigger, error_detail)
                logger.info("Surrogate retry %d/%d (trigger=%s)", self._surrogate_retry_count, self._max_surrogate_retries, trigger)
                await self._record_intervention(environment, trigger=trigger)
                feedback = (
                    f"Verification could not be completed ({error_detail}). "
                    "Please verify your output manually — re-read the task instruction, "
                    "check all output files, and signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

            # Valid script generated — lock surrogate tests
            self._surrogate_tests_locked = True
            logger.info("Surrogate tests locked after valid generation #%d", self._independent_verifier._generation_count)

        if not self._skip_surrogate_verifier:
            surrogate_dict = {
                "tests_passed": verification.tests_passed,
                "tests_failed": verification.tests_failed,
                "total_tests": verification.total_tests,
                "pass_rate": verification.tests_passed / verification.total_tests if verification.total_tests > 0 else 0.0,
            }

        surrogate_pass_rate = surrogate_dict["pass_rate"]
        if not self._skip_surrogate_verifier:
            _evo_print(
                f"[evolution] Surrogate: {verification.tests_passed}/{verification.total_tests} passed ({surrogate_pass_rate:.0%})"
            )
        if not self._skip_surrogate_verifier and (verification.tests_failed > 0 or surrogate_pass_rate < 1.0):
            self._surrogate_retry_count += 1
            trigger = "surrogate_fail" if verification.tests_failed > 0 else "surrogate_incomplete"
            logger.info("Surrogate retry %d/%d (trigger=%s)", self._surrogate_retry_count, self._max_surrogate_retries, trigger)

            failed_names = [d["name"] for d in verification.test_details if d.get("status") == "FAILED"]
            skipped_count = verification.total_tests - verification.tests_passed - verification.tests_failed
            logger.info(
                "Independent verifier: %d/%d passed, %d failed, %d skipped — failed: %s",
                verification.tests_passed,
                verification.total_tests,
                verification.tests_failed,
                skipped_count,
                ", ".join(failed_names[:5]) + ("..." if len(failed_names) > 5 else ""),
            )

            # Record intervention (includes cheap GT test)
            await self._record_intervention(environment, trigger=trigger, surrogate_result=surrogate_dict)

            # Reset progress checklist (P2-P6 unchecked)
            reset_msg = await self._reset_progress_checklist(environment)

            # In the locked path, run a lightweight diagnosis agent to provide
            # root-cause analysis (the unlocked path gets diagnosis from the full
            # generate_and_run agent, but the locked path skips that).
            if self._surrogate_tests_locked and verification.tests_failed > 0 and not verification.diagnosis:
                try:
                    diagnosis = await self._independent_verifier.diagnose_failures(
                        environment=environment,
                        instruction=self._instruction,
                        logs_dir=self.logs_dir,
                        verification=verification,
                    )
                    if diagnosis:
                        verification.diagnosis = diagnosis
                        logger.info("Diagnosis-only agent provided %d chars of analysis", len(diagnosis))
                except Exception as diag_exc:
                    logger.warning("Diagnosis-only agent failed: %s", diag_exc)

            # Feed surrogate failures + reset notice back to agent
            if verification.tests_failed > 0:
                feedback = self._build_surrogate_feedback(verification)
            else:
                # Tests were skipped/errored (pass_rate < 1.0 but tests_failed == 0)
                feedback = (
                    f"Independent verifier: only {verification.tests_passed}/{verification.total_tests} tests passed "
                    f"({skipped_count} tests were skipped or errored — likely due to missing dependencies or import errors "
                    f"in the verifier script). A pass rate of 100% is required.\n\n"
                    "Please check that your output is complete and correct, then signal task_complete again."
                )
            feedback = reset_msg + "\n\n" + feedback
            return EpisodeExitResult(should_exit=False, override_prompt=feedback)

        # ── 5. Progress checklist — enforce once, then advisory ──
        # Skip checklist and frontmatter validation when surrogate is disabled (clean ablation)
        if self._skip_surrogate_verifier:
            unchecked = []
            checklist_feedback = None
        else:
            try:
                progress_text = await self._read_progress_checklist(environment)
                unchecked = self._parse_unchecked_items(progress_text)
            except Exception:
                unchecked = []

        checklist_feedback: str | None = None
        if unchecked:
            self._checklist_fail_count += 1
            if self._checklist_fail_count <= 1:
                # First checklist fail — enforce: send agent back to complete items
                self._surrogate_retry_count += 1
                logger.info(
                    "Surrogate retry %d/%d (trigger=surrogate_pass_checklist_fail, attempt=%d)",
                    self._surrogate_retry_count,
                    self._max_surrogate_retries,
                    self._checklist_fail_count,
                )
                await self._record_intervention(environment, trigger="surrogate_pass_checklist_fail", surrogate_result=surrogate_dict)
                feedback = (
                    "Independent verifier tests passed, but you have unchecked phases in /root/progress.md:\n"
                    + "\n".join(f"- {item}" for item in unchecked)
                    + "\n\nComplete each unchecked phase, update /root/progress.md, "
                    "then signal task_complete."
                )
                logger.info(
                    "Surrogate passed but %d checklist items unchecked — returning agent (attempt %d)",
                    len(unchecked),
                    self._checklist_fail_count,
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

            # 2nd+ checklist fail — proceed to GT oracle anyway
            logger.info(
                "Surrogate passed, %d checklist items unchecked (attempt %d) — proceeding to GT oracle",
                len(unchecked),
                self._checklist_fail_count,
            )
            checklist_feedback = (
                "Note: You have unchecked phases in /root/progress.md:\n"
                + "\n".join(f"- {item}" for item in unchecked)
                + "\n\nPlease complete each unchecked phase and update /root/progress.md."
            )
        else:
            self._checklist_fail_count = 0  # reset on success

        # ── 5b. Skill frontmatter validation (enforce once) ──
        if not self._skip_surrogate_verifier and not self._frontmatter_fix_requested:
            missing_fm = await self._validate_skill_frontmatter(environment)
            if missing_fm:
                self._frontmatter_fix_requested = True
                self._surrogate_retry_count += 1
                logger.info(
                    "Surrogate retry %d/%d (trigger=missing_frontmatter, %d skills)",
                    self._surrogate_retry_count,
                    self._max_surrogate_retries,
                    len(missing_fm),
                )
                await self._record_intervention(environment, trigger="missing_frontmatter", surrogate_result=surrogate_dict)
                skill_list = "\n".join(f"- {p}" for p in missing_fm)
                feedback = (
                    "Your evolved skills have YAML frontmatter issues. Other agents (Codex, Gemini, etc.) "
                    "require valid YAML frontmatter to discover and load skills.\n\n"
                    f"Issues found:\n{skill_list}\n\n"
                    "Each SKILL.md must start with valid YAML frontmatter:\n"
                    "```\n---\nname: <skill-name>\n"
                    'description: "<what this skill does — MUST be quoted if it contains colons>"\n'
                    "---\n```\n\n"
                    "IMPORTANT: If description contains colons (:), wrap the entire value in double quotes.\n"
                    "Fix all issues listed above, then signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

        # ── 6. Surrogate passed — run GT oracle ──
        self._host_intervention_count += 1
        trigger = "surrogate_pass_checklist_incomplete" if unchecked else "surrogate_pass"
        logger.info(
            "Oracle intervention %d/%d (surrogate 100%% pass, checklist_incomplete=%s)",
            self._host_intervention_count,
            self._max_host_interventions,
            bool(unchecked),
        )
        intervention = await self._record_intervention(environment, trigger=trigger, surrogate_result=surrogate_dict)

        # ── 7. Full GT oracle (always, default to same model) ──
        oracle_model = self._gt_oracle_model or self._model_name
        _evo_print(
            f"[evolution] Running GT oracle (iteration {self._host_intervention_count}/{self._max_host_interventions})..."
        )
        logger.info("Surrogate passed all tests — running GT oracle mid-loop with %s", oracle_model)

        evolved_skills_dir = await self._export_evolved_skills_to_host(environment)
        try:
            gt_oracle_result = await self._run_gt_oracle_check(
                self._instruction,
                environment,
                oracle_model=oracle_model,
                evolved_skills_dir=evolved_skills_dir,
                oracle_label=f"gt-oracle-{self._host_intervention_count}",
            )
        except Exception as oracle_exc:
            logger.warning("GT oracle check failed during intervention: %s", oracle_exc)
            gt_oracle_result = {"passed": None, "error": str(oracle_exc)}
        finally:
            if evolved_skills_dir:
                shutil.rmtree(evolved_skills_dir, ignore_errors=True)

        gt_passed = gt_oracle_result.get("passed") if gt_oracle_result else None
        gt_error = gt_oracle_result.get("error") if gt_oracle_result else None
        if gt_error:
            _evo_print(f"[evolution] GT Oracle: ERROR ({gt_error})")
        elif gt_oracle_result is not None:
            gt_pr = gt_oracle_result.get("pass_rate", 0.0)
            _evo_print(f"[evolution] GT Oracle: {'PASS' if gt_passed else 'FAIL'} ({gt_pr:.0%})")
        else:
            _evo_print("[evolution] GT Oracle: ERROR (no result)")

        # Back-fill GT oracle result into this intervention entry for analysis
        # (test_details/failure_reasons/raw_output are for logging only — never shown to agent)
        if gt_oracle_result is not None:
            if gt_error:
                intervention["gt_result"] = {
                    "source": "gt_oracle",
                    "passed": None,
                    "error": gt_error,
                }
            else:
                raw = gt_oracle_result.get("raw_output") or ""
                intervention["gt_result"] = {
                    "source": "gt_oracle",
                    "passed": gt_passed,
                    "pass_rate": gt_oracle_result.get("pass_rate"),
                    "tests_passed": gt_oracle_result.get("tests_passed"),
                    "total_tests": gt_oracle_result.get("total_tests"),
                    "test_details": gt_oracle_result.get("test_details"),
                    "failure_reasons": gt_oracle_result.get("failure_reasons"),
                    "raw_output": raw[-5000:] if len(raw) > 5000 else raw,
                }
                await self._maybe_save_best_snapshot(environment, gt_oracle_result, self._host_intervention_count)

        if gt_passed is True:
            self._exit_reason = "gt_oracle_pass"
            _evo_print("[evolution] Exit: gt_oracle_pass — stopping early")
            logger.info("GT oracle passed — stopping early")
            task_name = self._extract_task_name(environment)
            self._write_oracle_stop_signal(task_name, gt_result=gt_oracle_result)
            return EpisodeExitResult(should_exit=True, exit_reason="gt_oracle_pass")

        if gt_passed is False:
            self._surrogate_tests_locked = False
            self._checklist_fail_count = 0  # reset so agent gets one enforced checklist pass per GT cycle
            _evo_print("[evolution] GT oracle failed — returning agent for refinement")
            logger.info("GT oracle failed — unlocking surrogate tests for refinement")
            feedback = (
                "The independent verifier tests all passed, but a ground truth evaluation "
                "found issues with your output. Your solution likely has gaps.\n\n"
                "Please:\n"
                "1. Re-read the FULL task instruction carefully\n"
                "2. Identify requirements you may have missed\n"
                "3. Fix your skill scripts and re-run to regenerate output\n"
                "4. Do NOT edit output files directly — fix the skill logic\n"
                "Then signal task_complete."
            )
            if checklist_feedback:
                feedback = feedback + "\n\n" + checklist_feedback
            logger.info("GT oracle failed — returning agent to fix issues")
            return EpisodeExitResult(should_exit=False, override_prompt=feedback)

        # Oracle error (passed=None) — trust surrogate, stop
        gt_err_msg = gt_error or "unknown error"
        _evo_print(f"[evolution] Exit: surrogate_pass (GT oracle error: {gt_err_msg} — trusting surrogate)")
        logger.info("GT oracle error (%s) — trusting surrogate pass", gt_err_msg)
        self._exit_reason = "surrogate_pass"
        return EpisodeExitResult(should_exit=True, exit_reason="surrogate_pass")

    @staticmethod
    def _build_surrogate_feedback(verification: VerificationResult) -> str:
        """Format independent verifier failures into actionable feedback for the agent."""
        lines = [
            "HOST VERIFICATION: An independent verifier detected failures in your output.",
            f"Result: {verification.tests_passed}/{verification.total_tests} tests passed.",
            "",
            "Failed tests:",
        ]

        for detail in verification.test_details:
            if detail.get("status") in ("FAILED", "ERROR"):
                name = detail.get("name", "unknown")
                msg = detail.get("message", "")
                if msg:
                    lines.append(f"  - {name}: {msg}")
                else:
                    lines.append(f"  - {name}")

        if verification.diagnosis:
            lines.extend(
                [
                    "",
                    "DIAGNOSIS (from independent analysis):",
                    verification.diagnosis,
                ]
            )
        elif verification.raw_output:
            # Locked path: no LLM diagnosis available, extract traceback sections
            # from raw pytest output so the agent sees full assertion context
            tb_sections = HarborTerminus2Evolution._extract_failure_tracebacks(verification.raw_output)
            if tb_sections:
                lines.extend(["", "FAILURE DETAILS (from pytest traceback):", tb_sections])

        lines.extend(
            [
                "",
                "Fix these failures in your skill's scripts/ and re-run to regenerate output.",
                "Do NOT edit output files directly — fix the skill logic.",
                "Then signal task_complete when you believe output is correct.",
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def _extract_failure_tracebacks(raw_output: str) -> str:
        """Extract FAILURES section from pytest --tb=short output.

        Returns the content between ``= FAILURES =`` and
        ``short test summary info`` headers, truncated to ~3000 chars
        to avoid blowing up the context window.
        """
        start = raw_output.find("= FAILURES =")
        if start < 0:
            start = raw_output.find("FAILURES")
        if start < 0:
            return ""
        end = raw_output.find("short test summary info", start)
        if end < 0:
            end = raw_output.find("====", start + 20)
        if end < 0:
            end = len(raw_output)
        section = raw_output[start:end].strip()
        if len(section) > 3000:
            # Cut at a line boundary to avoid garbled output
            cut = section.rfind("\n", 0, 3000)
            if cut > 0:
                section = section[:cut]
            else:
                section = section[:3000]
            section += "\n... (truncated)"
        return section

    async def _record_intervention(
        self,
        environment: BaseEnvironment,
        trigger: str,
        surrogate_result: dict | None = None,
    ) -> dict:
        """Record an intervention entry with surrogate result and skills snapshot.

        Returns the intervention entry dict.  The ``gt_result`` field is initially
        ``None`` and may be back-filled later by the full GT oracle.
        """
        # Snapshot current skills in container
        try:
            skills = sorted(await self._list_container_skills(environment))
        except Exception as exc:
            logger.warning("Failed to snapshot container skills during intervention recording: %s", exc)
            skills = []

        entry: dict = {
            "intervention_number": len(self._intervention_history) + 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "trigger": trigger,
            "surrogate_result": surrogate_result,
            "surrogate_tests_locked": self._surrogate_tests_locked,
            "gt_result": None,
            "skills_snapshot": skills,
        }
        self._intervention_history.append(entry)
        logger.info(
            "Intervention #%d recorded (trigger=%s)",
            entry["intervention_number"],
            trigger,
        )
        return entry

    async def _maybe_save_best_snapshot(self, environment: BaseEnvironment, gt_result: dict, intervention_number: int) -> None:
        """Save a skills snapshot if this GT result is the best so far.

        Each time the GT oracle returns a valid result, compare its pass_rate
        to the current best.  If better, export the container's evolved skills
        to a persistent temp directory and record the snapshot metadata.
        The previous best snapshot's temp dir is cleaned up immediately.
        """
        pass_rate = gt_result.get("pass_rate", 0.0)
        current_best = self._best_gt_snapshot.get("pass_rate", -1) if self._best_gt_snapshot else -1
        if pass_rate <= current_best:
            return

        # Clean up old snapshot
        if self._best_gt_snapshot and self._best_gt_snapshot.get("skills_dir"):
            shutil.rmtree(self._best_gt_snapshot["skills_dir"], ignore_errors=True)

        # Export current skills to a new temp dir
        skills_dir = await self._export_evolved_skills_to_host(environment)
        self._best_gt_snapshot = {
            "pass_rate": pass_rate,
            "tests_passed": gt_result.get("tests_passed"),
            "total_tests": gt_result.get("total_tests"),
            "intervention_number": intervention_number,
            "skills_dir": skills_dir,
        }
        _evo_print(f"[evolution] New best GT: {pass_rate:.0%} at iteration #{intervention_number}")
        logger.info(
            "Saved best GT snapshot: %.1f%% at intervention #%d",
            pass_rate * 100,
            intervention_number,
        )

    async def _reset_progress_checklist(self, environment: BaseEnvironment) -> str:
        """Reset /root/progress.md with P1 checked and P2-P6 unchecked.

        Returns a message string explaining the reset to prepend to agent feedback.
        """
        checklist = (
            "# Progress\n"
            "- [x] P1: Discover environment files (ls /app/environment/, /root/)\n"
            "- [x] P1b: Discover installed tools and libraries\n"
            "- [ ] P2: Create/update task skill with utility function scripts\n"
            "- [ ] P3: Self-reflect (re-read FULL instruction, verify skill covers ALL requirements)\n"
            "- [ ] P4: Execute task (run skill scripts, produce ALL output files)\n"
            "- [ ] P5: Fix any failures from host verifier feedback, re-run until stable\n"
            "- [ ] P6: Write /root/evolution_summary.md\n"
        )
        encoded = base64.b64encode(checklist.encode("utf-8")).decode("ascii")
        result = await environment.exec(
            command=f"echo '{encoded}' | base64 -d > /root/progress.md",
            timeout_sec=15,
        )
        if result.return_code != 0:
            logger.warning("Failed to reset progress checklist: %s", result.stderr)

        return (
            "CHECKLIST RESET: /root/progress.md has been reset. P1 and P1b (environment and tool discovery) "
            "are already done. You MUST complete P2-P6 in order before signalling task_complete.\n"
            "Start with P2: review and update your task skill, then proceed through each phase."
        )

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """Run the evolution agent: execute task in-container with host intervention.

        The agent creates skills, executes the task, runs tests, and writes a summary — all in-container.
        Host intervention (independent verifier, progress checklist, GT oracle) gates task_complete
        during execution.  Post-execution, the host exports verifier scripts and writes logs.
        """
        self._instruction = instruction
        run_timestamp = datetime.now(UTC).isoformat()
        task_name = self._extract_task_name(environment)
        run_id = f"{self.name()}-{task_name}-{run_timestamp}"

        # Reset host intervention state for this run
        self._host_intervention_count = 0
        self._surrogate_retry_count = 0
        self._exit_reason = ""
        self._intervention_history = []
        self._independent_verifier.reset()
        self._surrogate_tests_locked = False
        self._consecutive_idle_episodes = 0
        self._episodes_since_last_complete = 0
        # Clean up any leftover best snapshot from a previous run
        if self._best_gt_snapshot and self._best_gt_snapshot.get("skills_dir"):
            shutil.rmtree(self._best_gt_snapshot["skills_dir"], ignore_errors=True)
        self._best_gt_snapshot = None
        logger.info("Evolution state reset for run %s (task=%s)", run_id, task_name)

        # ── Timers ──
        total_start = time.monotonic()

        # Refresh skill index so parent sees meta skills
        await self.refresh_skill_index()

        # Initialize result variables
        execution_start = time.monotonic()
        execution_duration = 0.0
        skills_loaded: list[str] = []
        trajectory_data: list[dict] | None = None
        trajectory_summary = ""
        post_execution_start = time.monotonic()
        evolution_summary_text = ""
        interrupted_by_error: str | None = None
        gt_oracle_result: dict | None = None
        main_exit_reason: str = ""
        main_intervention_count: int = 0

        # Snapshot pre-existing skills so we can diff after execution
        self._pre_existing_skills = await self._list_container_skills(environment)

        agent_error: BaseException | None = None
        try:
            # ── Single agent execution — agent does everything in-container ──
            # Wrap in nested try/except so post-execution work (export verifier,
            # read summary) still runs even if the agent
            # times out (AgentTimeoutError / asyncio.CancelledError).
            try:
                await super().run(instruction, environment, context)
            except BaseException as run_exc:
                agent_error = run_exc
                interrupted_by_error = f"{type(run_exc).__name__}: {run_exc}"
                logger.warning("Agent execution interrupted: %s", interrupted_by_error)

                # Parent's run() writes full_conversation.json at the end of its
                # method body.  When it's interrupted (timeout, cancel, etc.) that
                # write is skipped, so we do it here to preserve the conversation.
                try:
                    if self._chat is not None and hasattr(self._chat, "messages"):
                        (self.logs_dir / "full_conversation.json").write_text(
                            json.dumps(self._chat.messages, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        logger.info("Saved full_conversation.json after interrupted run")
                except Exception as conv_save_exc:
                    logger.warning("Failed to save conversation after interrupt: %s", conv_save_exc)

            execution_duration = time.monotonic() - execution_start

            # Snapshot exit reason from main run before follow-ups overwrite it
            main_exit_reason = self._exit_reason
            main_intervention_count = self._host_intervention_count

            # Extract results (read trajectory once for both summary and execution info)
            skills_loaded = list((context.metadata or {}).get("skills_loaded", []))
            trajectory_data = self._read_trajectory()
            trajectory_summary = self._build_trajectory_summary(trajectory_data)

            # Read evolution_summary.md from container
            evolution_summary_text = await self._read_evolution_summary(environment)

            # Export agent-generated verifier script before container is destroyed
            try:
                exported = await self._export_verifier_script(environment)
                if exported:
                    logger.info("Verifier script exported to %s", exported)
            except Exception as export_exc:
                logger.warning("Failed to export verifier script: %s", export_exc)

            # Import agent-created skills from container to host
            try:
                imported = await self._import_agent_created_skills(environment, self._pre_existing_skills)
                if imported:
                    logger.info("Imported %d agent-created skills to host: %s", len(imported), imported)
            except Exception as import_exc:
                logger.warning("Failed to import agent-created skills: %s", import_exc)

            # Final post-execution oracle test with evolved skills
            # Skip if the last intervention already ran a passing oracle
            if not self._did_last_oracle_pass():
                logger.info("Running final post-execution oracle test with evolved skills")

                # Prefer best snapshot skills (already GT-validated during iteration)
                # over last skills — avoids a wasteful double oracle run.
                best = self._best_gt_snapshot
                if best and best.get("skills_dir"):
                    logger.info(
                        "Using best snapshot skills (%.1f%% from intervention #%d) for final oracle",
                        best["pass_rate"] * 100,
                        best["intervention_number"],
                    )
                    oracle_skills_dir = best["skills_dir"]
                    is_best_snapshot = True
                else:
                    oracle_skills_dir = await self._export_evolved_skills_to_host(environment)
                    is_best_snapshot = False

                if oracle_skills_dir is not None:
                    try:
                        oracle_model = self._gt_oracle_model or self._model_name
                        gt_oracle_result = await self._run_gt_oracle_check(
                            self._instruction,
                            environment,
                            oracle_model=oracle_model,
                            evolved_skills_dir=oracle_skills_dir,
                            oracle_label="gt-oracle-final",
                        )
                        if gt_oracle_result is not None and not gt_oracle_result.get("error"):
                            if is_best_snapshot:
                                gt_oracle_result["source"] = "best_snapshot"
                            logger.info(
                                "Final oracle result: passed=%s, pass_rate=%s",
                                gt_oracle_result.get("passed"),
                                gt_oracle_result.get("pass_rate"),
                            )
                        elif gt_oracle_result is not None and gt_oracle_result.get("error"):
                            logger.warning("Final oracle returned error: %s", gt_oracle_result.get("error"))
                            gt_oracle_result = None
                    except Exception as oracle_exc:
                        logger.warning("Final post-execution oracle test failed: %s", oracle_exc)
                        gt_oracle_result = None
                        # If oracle failed but we have best snapshot values, use them directly
                        if is_best_snapshot:
                            gt_oracle_result = {
                                "passed": best["pass_rate"] == 1.0,
                                "tests_passed": best["tests_passed"],
                                "total_tests": best["total_tests"],
                                "pass_rate": best["pass_rate"],
                                "reward": best["pass_rate"],
                                "source": "best_snapshot",
                            }
                            logger.info("Using recorded best snapshot values: %.1f%%", best["pass_rate"] * 100)
                    finally:
                        # Only clean up if we exported last skills (best snapshot dir is managed elsewhere)
                        if not is_best_snapshot:
                            shutil.rmtree(oracle_skills_dir, ignore_errors=True)

                    # If oracle non-determinism gave a worse result than best snapshot, use snapshot values
                    if is_best_snapshot and gt_oracle_result is not None:
                        if gt_oracle_result.get("pass_rate", 0) < best["pass_rate"]:
                            logger.info(
                                "Oracle result (%.1f%%) worse than snapshot (%.1f%%) due to non-determinism — using snapshot values",
                                gt_oracle_result.get("pass_rate", 0) * 100,
                                best["pass_rate"] * 100,
                            )
                            gt_oracle_result = {
                                "passed": best["pass_rate"] == 1.0,
                                "tests_passed": best["tests_passed"],
                                "total_tests": best["total_tests"],
                                "pass_rate": best["pass_rate"],
                                "reward": best["pass_rate"],
                                "source": "best_snapshot",
                            }

                    # Overwrite host skills with best snapshot version
                    if is_best_snapshot:
                        self._rollback_host_skills(environment, best["skills_dir"])

                if gt_oracle_result is not None:
                    task_name_for_oracle = self._extract_task_name(environment)
                    self._write_oracle_stop_signal(task_name_for_oracle, gt_result=gt_oracle_result)
            else:
                logger.info("Skipping final oracle — last intervention oracle already passed")
                # Extract GT result from last intervention so _write_evolution_log gets it
                last_gt = self._intervention_history[-1].get("gt_result") if self._intervention_history else None
                if last_gt is not None:
                    gt_oracle_result = {
                        "passed": last_gt.get("passed"),
                        "tests_passed": last_gt.get("tests_passed"),
                        "total_tests": last_gt.get("total_tests"),
                        "pass_rate": last_gt.get("pass_rate"),
                        "reward": last_gt.get("pass_rate"),
                    }

            # Re-raise agent error after all post-execution work is done
            if agent_error is not None:
                raise agent_error

        except BaseException as exc:
            if not interrupted_by_error:
                interrupted_by_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Evolution run error: %s", interrupted_by_error)
            if not trajectory_summary:
                trajectory_summary = self._build_trajectory_summary()
            if not skills_loaded and context.metadata is not None:
                skills_loaded = list(context.metadata.get("skills_loaded", []))
            if not execution_duration:
                execution_duration = time.monotonic() - execution_start
            raise
        finally:
            post_execution_duration = time.monotonic() - post_execution_start
            total_duration = time.monotonic() - total_start

            # Clean up best GT snapshot temp dir
            if self._best_gt_snapshot and self._best_gt_snapshot.get("skills_dir"):
                shutil.rmtree(self._best_gt_snapshot["skills_dir"], ignore_errors=True)

            if context.metadata is not None:
                context.metadata["evolution_summary"] = evolution_summary_text

            try:
                self._write_evolution_log(
                    task_name=task_name,
                    run_timestamp=run_timestamp,
                    skills_loaded=skills_loaded,
                    trajectory_summary=trajectory_summary,
                    trajectory_data=trajectory_data,
                    context=context,
                    timing={
                        "total_duration_sec": round(total_duration, 1),
                        "execution_duration_sec": round(execution_duration, 1),
                        "post_execution_duration_sec": round(post_execution_duration, 1),
                        "interrupted_by": interrupted_by_error,
                        "exit_reason": main_exit_reason,
                        "host_intervention_count": main_intervention_count,
                        "surrogate_retry_count": self._surrogate_retry_count,
                    },
                    evolution_summary=evolution_summary_text,
                    gt_oracle_result=gt_oracle_result,
                    intervention_history=self._intervention_history,
                )
            except Exception as log_exc:
                logger.error("Failed to write evolution log in finally: %s", log_exc)

            # Re-generate full_conversation.md
            try:
                self._regenerate_conversation_md()
            except Exception as conv_exc:
                logger.warning("Failed to regenerate conversation md: %s", conv_exc)

    async def _run_ground_truth_evaluation(self, environment: BaseEnvironment) -> dict | None:
        """Run ground truth tests for measuring evolution effectiveness.

        Results are for analysis only — NOT fed back to the agent or written to history.
        Uploads the entire tests/ directory to /tests/ in the container (matching
        Harbor's normal verifier behaviour) so that co-located modules (test_utils.py,
        conftest.py) and data files (catalog.csv, labels.csv, …) are available.
        """
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir:
            return None
        task_dir = Path(env_dir).parent
        tests_dir = task_dir / "tests"
        test_file = tests_dir / "test_outputs.py"
        test_sh = tests_dir / "test.sh"
        if not test_file.exists() and not test_sh.exists():
            return None

        # Upload the whole tests/ directory (only once — skip if already there)
        check = await environment.exec(
            command="test -f /tests/test_outputs.py && echo exists || echo missing",
            timeout_sec=10,
        )
        if "missing" in (check.stdout or ""):
            try:
                await environment.upload_dir(
                    source_dir=str(tests_dir),
                    target_dir="/tests",
                )
            except Exception:
                logger.warning("GT evaluation: failed to upload tests/ directory, falling back to single-file inject")
                raw = test_file.read_bytes()
                encoded = base64.b64encode(raw).decode("ascii")
                inject = await environment.exec(
                    command=f"mkdir -p /tests && echo '{encoded}' | base64 -d > /tests/test_outputs.py",
                    timeout_sec=30,
                )
                if inject.return_code != 0:
                    return None
            # Ensure pytest + dependencies
            await environment.exec(
                command="pip install --break-system-packages -q pytest 2>/dev/null || pip install -q pytest",
                timeout_sec=60,
            )

        # Run GT test — prefer test.sh (handles dependencies + app startup) over bare pytest
        if test_sh.exists():
            # Upload test.sh and run it; it installs deps, starts app, runs pytest, writes reward.txt
            raw_sh = test_sh.read_bytes()
            encoded_sh = base64.b64encode(raw_sh).decode("ascii")
            await environment.exec(
                command=f"echo '{encoded_sh}' | base64 -d > /tests/test.sh && chmod +x /tests/test.sh",
                timeout_sec=30,
            )
            result = await environment.exec(
                command="bash /tests/test.sh 2>&1",
                timeout_sec=1800,
            )
        else:
            result = await environment.exec(
                command="python3 -m pytest /tests/test_outputs.py -v --tb=short 2>&1",
                timeout_sec=120,
            )
        # Reuse SelfVerifier's pytest parser
        vr = SelfVerifier._parse_pytest_output(result.stdout or "", result.return_code)

        # Fallback: some tasks redirect test output to /logs/verifier/output.log
        if vr.total_tests == 0:
            log_result = await environment.exec(
                command="cat /logs/verifier/output.log 2>/dev/null || true",
                timeout_sec=10,
            )
            if log_result.stdout and log_result.stdout.strip():
                vr_fallback = SelfVerifier._parse_pytest_output(log_result.stdout, result.return_code)
                if vr_fallback.total_tests > 0:
                    logger.info("GT evaluation: parsed %d tests from /logs/verifier/output.log (stdout had 0)", vr_fallback.total_tests)
                    vr = vr_fallback

        # Fallback: check reward.txt for reward signal when tests can't be parsed
        reward_override = None
        if vr.total_tests == 0:
            reward_result = await environment.exec(
                command="cat /logs/verifier/reward.txt 2>/dev/null || true",
                timeout_sec=10,
            )
            if reward_result.stdout and reward_result.stdout.strip():
                try:
                    reward_override = float(reward_result.stdout.strip())
                    logger.info("GT evaluation: found reward.txt = %s", reward_override)
                except ValueError:
                    pass

        gt_result = {
            "tests_passed": vr.tests_passed,
            "total_tests": vr.total_tests,
            "tests_failed": vr.tests_failed,
            "pass_rate": vr.tests_passed / vr.total_tests if vr.total_tests > 0 else 0.0,
            "estimated_success": vr.estimated_success,
            "test_details": vr.test_details,
            "failure_reasons": vr.failure_reasons,
            "raw_output": vr.raw_output,
        }
        if reward_override is not None:
            gt_result["reward"] = reward_override
            # Synthesize test counts from reward when pytest parsing found 0 tests
            # (e.g., tasks using custom test scripts that write reward.txt directly)
            if vr.total_tests == 0:
                gt_result["total_tests"] = 1
                gt_result["tests_passed"] = 1 if reward_override >= 1.0 else 0
                gt_result["tests_failed"] = 0 if reward_override >= 1.0 else 1
                gt_result["pass_rate"] = 1.0 if reward_override >= 1.0 else 0.0
        return gt_result

    def _create_oracle_agent(self, agent_type: str, logs_dir: Path, model_name: str):
        """Create an oracle agent instance based on the configured agent type."""
        if agent_type == "terminus-2":
            return HarborTerminus2WithSkills(logs_dir=logs_dir, model_name=model_name)
        elif agent_type == "claude-code":
            from libs.terminus_agent.agents.bedrock_claude_code import BedrockClaudeCode

            return BedrockClaudeCode(logs_dir=logs_dir, model_name=model_name)
        elif agent_type == "codex":
            from harbor.agents.installed.codex import Codex

            return Codex(logs_dir=logs_dir, model_name=model_name)
        elif agent_type == "gemini-cli":
            from harbor.agents.installed.gemini_cli import GeminiCli

            return GeminiCli(logs_dir=logs_dir, model_name=model_name)
        else:
            raise ValueError(f"Unknown oracle agent type: {agent_type!r}. Expected 'terminus-2', 'claude-code', 'codex', or 'gemini-cli'.")

    async def _run_gt_oracle_check(
        self,
        instruction: str,
        environment: BaseEnvironment,
        oracle_model: str | None = None,
        evolved_skills_dir: Path | None = None,
        oracle_label: str | None = None,
    ) -> dict | None:
        """Spawn a clean independent agent to re-execute the task, then run GT tests.

        A fresh Docker container is created from the same Dockerfile and a
        lightweight ``HarborTerminus2WithSkills`` agent (new LLM session)
        executes the task.  Ground truth tests are then run inside that container.

        Design constraints:
        - ISOLATION: Fresh LLM session + clean container. No shared state with the
          evolution agent — prevents context contamination.
        - INFORMATION BARRIER: Only ``passed`` (True/False) is used by the evolution
          loop. Full test details are stored in ``oracle_stop.json`` for the experiment
          runner but never fed back to the agent.
        - COST: Uses ``oracle_model`` if provided, otherwise falls back to the
          evolution agent's own model (``self._model_name``).

        Returns:
            Dict with ``passed``, ``tests_passed``, ``total_tests``, ``pass_rate``,
            ``reward`` keys, or None on errors.
        """
        oracle_model = oracle_model or self._model_name
        if not oracle_model:
            logger.warning("GT oracle check: no model available")
            return None

        # Resolve task directory and load task config
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir:
            logger.warning("GT oracle check: no environment_dir on environment")
            return None
        task_dir = Path(env_dir).parent
        task_toml_path = task_dir / "task.toml"
        if not task_toml_path.exists():
            logger.warning("GT oracle check: task.toml not found at %s", task_toml_path)
            return None

        task_config = TaskConfig.model_validate(tomllib.loads(task_toml_path.read_text(encoding="utf-8")))
        task_name = task_dir.name

        # Create a temporary directory for oracle trial paths
        temp_dir = Path(tempfile.mkdtemp(prefix=f"oracle-{task_name}-"))
        oracle_trial_paths = TrialPaths(trial_dir=temp_dir)
        oracle_trial_paths.mkdir()

        # Create a fresh DockerEnvironment (reuses the cached image from the same Dockerfile)
        oracle_session_id = f"oracle-{task_name}-{uuid4().hex[:8]}"
        oracle_env = DockerEnvironment(
            environment_dir=Path(env_dir),
            environment_name=task_name,
            session_id=oracle_session_id,
            trial_paths=oracle_trial_paths,
            task_env_config=task_config.environment,
        )

        try:
            await oracle_env.start(force_build=False)

            # Inject evolved skills into the oracle container so the oracle agent
            # can discover and use them via SkillDocLoader
            if evolved_skills_dir is not None:
                for skill_subdir in sorted(evolved_skills_dir.iterdir()):
                    if skill_subdir.is_dir():
                        success = await self._inject_skill_dir_to_container(
                            skill_subdir.name,
                            skill_subdir,
                            oracle_env,
                        )
                        if success:
                            logger.info("Injected evolved skill %s into oracle container", skill_subdir.name)
                        else:
                            logger.warning("Failed to inject evolved skill %s into oracle container", skill_subdir.name)

                # Symlink injected skills to all agent-specific discovery paths
                # so that any oracle agent type (Codex, Claude Code, etc.) can find them
                await oracle_env.exec(
                    command=(
                        "for d in /root/.codex/skills /root/.claude/skills /root/.terminus/skills "
                        "/root/.opencode/skills /root/.agents/skills /root/.gemini/skills "
                        "/root/.goose/skills /root/.factory/skills; do "
                        'mkdir -p "$d" && ln -sf /app/environment/skills/evo-* "$d/" 2>/dev/null; '
                        "done"
                    ),
                    timeout_sec=15,
                )

            # Instantiate a fresh oracle agent (new LLM session — complete isolation)
            oracle_agent = self._create_oracle_agent(
                self._gt_oracle_agent,
                logs_dir=oracle_trial_paths.agent_dir,
                model_name=oracle_model,
            )
            await oracle_agent.setup(oracle_env)

            # Installed agents (claude-code, codex) need extra time for CLI setup.
            # Use task.toml agent timeout as the base (respects per-task tuning),
            # and apply the timeout multiplier for consistency.
            task_agent_timeout = int(task_config.agent.timeout_sec) if task_config.agent and task_config.agent.timeout_sec else 3600
            task_agent_timeout = int(task_agent_timeout * self._timeout_multiplier)
            oracle_timeout = task_agent_timeout

            # Augment instruction with skill discovery hint for ALL oracle agents.
            # Even agents with native skill discovery (Claude Code, Terminus-2)
            # benefit from an explicit hint to prioritize loading evolved skills.
            oracle_instruction = instruction
            if evolved_skills_dir is not None:
                skill_names = sorted(d.name for d in evolved_skills_dir.iterdir() if d.is_dir())
                if skill_names:
                    agent_skills_path = {
                        "codex": "/root/.codex/skills",
                        "gemini-cli": "/root/.gemini/skills",
                        "claude-code": "/root/.claude/skills",
                        "terminus-2": "/root/.terminus/skills",
                    }.get(self._gt_oracle_agent, "/root/.agents/skills")

                    # Extract code examples from each skill's SKILL.md to give the
                    # oracle agent a concrete, copy-pasteable invocation pattern
                    code_examples = []
                    for sname in skill_names:
                        skill_md_path = evolved_skills_dir / sname / "SKILL.md"
                        if skill_md_path.exists():
                            md_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
                            # Extract first ```python ... ``` block as the usage example
                            import re as _re

                            m = _re.search(r"```python\n(.+?)```", md_text, _re.DOTALL)
                            if m:
                                example = m.group(1).strip()
                                # Rewrite /app/environment/skills/ paths to the agent-specific path
                                example = example.replace("/app/environment/skills/", f"{agent_skills_path}/")
                                code_examples.append(f"# Skill: {sname}\n{example}")

                    hint = (
                        f"IMPORTANT: Task-specific skills with ready-to-use utility scripts are available at {agent_skills_path}/. "
                        f"Skills: {', '.join(skill_names)}. "
                        "You MUST import and call the skill's helper functions — do NOT reimplement the logic yourself. "
                        "The skill scripts encode domain-specific semantics (e.g., ordering rules, unit conversions) "
                        "that are critical for correctness and very difficult to reproduce from scratch.\n"
                    )
                    if code_examples:
                        hint += "\nReady-to-use code (adapt paths if needed):\n```python\n"
                        hint += "\n\n".join(code_examples)
                        hint += "\n```\n\n"
                    else:
                        hint += "\n"

                    oracle_instruction = hint + instruction

            # Run the oracle agent with a timeout
            await asyncio.wait_for(
                oracle_agent.run(oracle_instruction, oracle_env, AgentContext()),
                timeout=oracle_timeout,
            )

            # Run ground truth tests inside the oracle container
            gt_result = await self._run_ground_truth_evaluation(oracle_env)
            if gt_result is None:
                logger.warning("GT oracle check: ground truth evaluation returned None")
                return {"passed": None, "error": "ground truth evaluation returned None"}

            total = gt_result.get("total_tests", 0)
            passed = gt_result.get("tests_passed", 0)
            return {
                "passed": bool(gt_result.get("estimated_success")),
                "tests_passed": passed,
                "total_tests": total,
                "pass_rate": passed / total if total > 0 else 0.0,
                "reward": passed / total if total > 0 else 0.0,
                "test_details": gt_result.get("test_details"),
                "failure_reasons": gt_result.get("failure_reasons"),
                "raw_output": gt_result.get("raw_output"),
            }

        except TimeoutError:
            logger.warning("GT oracle check timed out after %ds", oracle_timeout)
            return {"passed": None, "error": f"timeout after {oracle_timeout}s"}
        except Exception as exc:
            logger.warning("GT oracle check failed: %s", exc)
            return {"passed": None, "error": str(exc)}
        finally:
            try:
                await oracle_env.stop(delete=True)
            except Exception as stop_exc:
                logger.warning("GT oracle check: failed to stop oracle container: %s", stop_exc)
            # Persist oracle logs for debugging before cleaning up
            label = oracle_label or f"gt-oracle-{self._host_intervention_count}"
            oracle_persist_dir = self.logs_dir / label
            try:
                if temp_dir.exists():
                    shutil.copytree(temp_dir, oracle_persist_dir, dirs_exist_ok=True)
                    logger.info("Persisted GT oracle logs to %s", oracle_persist_dir)
            except Exception as copy_exc:
                logger.warning("Failed to persist oracle logs: %s", copy_exc)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _write_oracle_stop_signal(self, task_name: str, gt_result: dict | None = None) -> None:
        """Write oracle_stop.json so the experiment runner can detect early-stop between sequential rounds.

        When ``gt_result`` is provided, the oracle's GT test results (reward, tests_passed,
        total_tests) are stored alongside the stop signal.  The experiment runner reads
        these to use the oracle reward instead of the (potentially stale) evolution
        container reward.
        """
        evo_dir = self._resolve_evolution_dir()
        evo_dir.mkdir(parents=True, exist_ok=True)
        stop_file = evo_dir / "oracle_stop.json"
        payload: dict = {
            "task_name": task_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "sequential_run": self._sequential_run,
        }
        if gt_result is not None:
            payload["gt_result"] = gt_result
        stop_file.write_text(json.dumps(payload))
        logger.info("Oracle stop signal written to %s", stop_file)

    # ------------------------------------------------------------------
    # Evolution helpers
    # ------------------------------------------------------------------

    async def _read_progress_checklist(self, environment: BaseEnvironment) -> str:
        """Read /root/progress.md from container."""
        result = await environment.exec(
            command="cat /root/progress.md 2>/dev/null || true",
            timeout_sec=15,
        )
        return (result.stdout or "").strip()

    @staticmethod
    def _parse_unchecked_items(progress_text: str) -> list[str]:
        """Extract unchecked items from progress checklist."""
        unchecked = []
        for line in progress_text.splitlines():
            line = line.strip()
            if line.startswith("- [ ]"):
                unchecked.append(line[6:].strip())
        return unchecked

    async def _read_evolution_summary(self, environment: BaseEnvironment) -> str:
        """Read /root/evolution_summary.md from the container."""
        result = await environment.exec(
            command="cat /root/evolution_summary.md 2>/dev/null || true",
            timeout_sec=15,
        )
        raw = (result.stdout or "").strip()
        if not raw:
            logger.info("No evolution_summary.md found in container")
            return ""
        # Filter out bash shell warnings that precede actual content
        lines = [line for line in raw.splitlines() if not is_shell_warning(line)]
        content = "\n".join(lines).strip()
        logger.info("Read evolution_summary.md from container (%d chars)", len(content))
        return content

    async def _list_container_skills(self, environment: BaseEnvironment) -> set[str]:
        """List skill directory names under /app/environment/skills/ in the container."""
        result = await environment.exec(
            command="ls -1 /app/environment/skills/ 2>/dev/null || true",
            timeout_sec=15,
        )
        names = set()
        for line in (result.stdout or "").strip().splitlines():
            name = line.strip()
            if not name or is_shell_warning(line):
                continue
            names.add(name)

        # If exec returned nothing useful (service down), fall back to docker compose cp
        if not names and hasattr(environment, "download_dir"):
            try:
                import tempfile

                with tempfile.TemporaryDirectory() as tmp:
                    await environment.download_dir("/app/environment/skills/", tmp)
                    skills_tmp = Path(tmp) / "skills"
                    if skills_tmp.exists():
                        names = {d.name for d in skills_tmp.iterdir() if d.is_dir()}
                        logger.info("Listed %d skills via download_dir fallback", len(names))
            except Exception as dl_exc:
                logger.warning("download_dir fallback for skill listing failed: %s", dl_exc)

        return names

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Strip markdown code fences (```json ... ```) from LLM responses."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1 :]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[: -len("```")].rstrip()
        return cleaned

    @staticmethod
    def _clean_base64(raw: str) -> str:
        """Filter shell warnings from base64 output.

        Shell environments (especially Docker containers) may emit warnings
        to stdout (e.g., ``bash: cannot set terminal process group``).
        These corrupt the base64 string.  Filter to only valid base64 lines.
        """
        lines = []
        for line in raw.strip().splitlines():
            stripped = line.strip()
            if is_shell_warning(line):
                continue
            # Keep only lines that look like valid base64
            if re.fullmatch(r"[A-Za-z0-9+/=]+", stripped):
                lines.append(stripped)
        return "".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_task_name(environment: BaseEnvironment) -> str:
        """Extract a task name from the environment."""
        env_dir = getattr(environment, "environment_dir", None)
        if env_dir:
            # environment_dir is typically .../tasks/task-name/environment
            task_dir = Path(env_dir).parent
            return task_dir.name
        return "unknown"

    def _read_trajectory(self) -> list[dict] | None:
        """Read and parse trajectory.json once. Returns None on failure."""
        trajectory_path = self.logs_dir / "trajectory.json"
        if not trajectory_path.exists():
            return None
        try:
            return json.loads(trajectory_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _build_trajectory_summary(self, trajectory: list[dict] | None = None) -> str:
        """Build a rich trajectory summary including command outputs and agent analysis."""
        if trajectory is None:
            trajectory = self._read_trajectory()
        if trajectory is None:
            return "No trajectory data available."

        lines: list[str] = []
        for i, entry in enumerate(trajectory):
            ep = entry.get("episode", "?")
            response = entry.get("response", "")
            prompt = entry.get("prompt", "")

            # Include terminal output from this episode's prompt (shows results of previous commands)
            # Skip the first episode's prompt (it's the full system prompt, not command output)
            if i > 0 and prompt:
                output_text = prompt.strip()
                for prefix in ["Current Terminal Screen:\n", "New Terminal Output:\n"]:
                    if output_text.startswith(prefix):
                        output_text = output_text[len(prefix) :]
                        break
                if output_text:
                    lines.append(f"Episode {ep} terminal output:\n{output_text[:1500]}")

            # Detect action type from response
            if "load_skill" in response:
                match = re.search(r'"load_skill"\s*:\s*"([^"]+)"', response)
                if match:
                    lines.append(f"Episode {ep}: Loaded skill {match.group(1)}")
                else:
                    lines.append(f"Episode {ep}: Skill load request")
            elif "task_complete" in response and "true" in response.lower():
                lines.append(f"Episode {ep}: Task completed")
            else:
                try:
                    data = json.loads(self._strip_code_fences(response))
                    analysis = data.get("analysis", "")
                    if analysis:
                        lines.append(f"Episode {ep} analysis: {analysis[:500]}")
                    cmds = data.get("commands", [])
                    if cmds:
                        cmd_strs = [c.get("cmd", c.get("keystrokes", ""))[:200] for c in cmds]
                        lines.append(f"Episode {ep} commands: {'; '.join(cmd_strs)}")
                    else:
                        lines.append(f"Episode {ep}: Response (no commands)")
                except (json.JSONDecodeError, TypeError, AttributeError):
                    lines.append(f"Episode {ep}: Response (unparseable)")

        return "\n".join(lines) if lines else "Empty trajectory."

    def _build_execution_info(
        self,
        skills_loaded: list[str],
        trajectory_summary: str,
        trajectory: list[dict] | None = None,
    ) -> dict:
        """Build the execution section of the log."""
        if trajectory is None:
            trajectory = self._read_trajectory()

        trajectory_entries: list[dict] = []
        total_episodes = 0

        if trajectory:
            total_episodes = len(trajectory)

            for i, entry in enumerate(trajectory):
                ep = entry.get("episode", "?")
                response = entry.get("response", "")

                if "load_skill" in response:
                    match = re.search(r'"load_skill"\s*:\s*"([^"]+)"', response)
                    trajectory_entries.append(
                        {
                            "episode": ep,
                            "action": "skill_load",
                            "skill_name": match.group(1) if match else "unknown",
                            "detail": "Agent requested to load skill",
                        }
                    )
                elif "task_complete" in response and "true" in response.lower():
                    trajectory_entries.append(
                        {
                            "episode": ep,
                            "action": "task_complete",
                            "detail": "Agent signaled task completion",
                        }
                    )
                else:
                    try:
                        data = json.loads(self._strip_code_fences(response))
                        cmds = data.get("commands", [])
                        cmd_strs = [c.get("cmd", c.get("keystrokes", ""))[:100] for c in cmds[:5]]
                        output_preview = ""
                        if i + 1 < len(trajectory):
                            next_prompt = trajectory[i + 1].get("prompt", "")
                            output_preview = next_prompt.strip()[:200]
                        trajectory_entries.append(
                            {
                                "episode": ep,
                                "action": "commands",
                                "commands": cmd_strs,
                                "output_preview": output_preview,
                            }
                        )
                    except (json.JSONDecodeError, TypeError):
                        trajectory_entries.append(
                            {
                                "episode": ep,
                                "action": "unknown",
                                "detail": "Unparseable response",
                            }
                        )

        task_completed = any(e.get("action") == "task_complete" for e in trajectory_entries)

        return {
            "total_episodes": total_episodes,
            "task_completed": task_completed,
            "skills_loaded_by_agent": sorted(skills_loaded),
            "trajectory": trajectory_entries,
            "trajectory_summary": trajectory_summary,
        }

    def _write_evolution_log(
        self,
        task_name: str,
        run_timestamp: str,
        skills_loaded: list[str],
        trajectory_summary: str,
        context: AgentContext,
        timing: dict,
        evolution_summary: str = "",
        gt_oracle_result: dict | None = None,
        intervention_history: list[dict] | None = None,
        trajectory_data: list[dict] | None = None,
    ) -> None:
        """Write the comprehensive evolution_run_log.json."""
        log = {
            # Basic info
            "task_name": task_name,
            "model": self._model_name,
            "timestamp": run_timestamp,
            "sequential_run": self._sequential_run,
            "evolution_summary": evolution_summary,
            # Execution
            "execution": self._build_execution_info(
                skills_loaded,
                trajectory_summary,
                trajectory_data,
            ),
            # GT Oracle check
            "gt_oracle_agent": self._gt_oracle_agent,
            "gt_oracle_result": gt_oracle_result,
            # Best GT snapshot (highest GT score seen during iterations)
            "best_gt_snapshot": {
                "pass_rate": self._best_gt_snapshot["pass_rate"],
                "tests_passed": self._best_gt_snapshot["tests_passed"],
                "total_tests": self._best_gt_snapshot["total_tests"],
                "intervention_number": self._best_gt_snapshot["intervention_number"],
            }
            if self._best_gt_snapshot
            else None,
            # Intervention history (per-intervention GT scores + surrogate results)
            "intervention_history": intervention_history or [],
            # Token usage
            "token_usage": {
                "agent_input_tokens": context.n_input_tokens or 0,
                "agent_output_tokens": context.n_output_tokens or 0,
            },
            # Timing
            "timing": timing,
        }

        log_path = self.logs_dir / "evolution_run_log.json"
        log_path.write_text(
            json.dumps(log, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Evolution run log written to %s", log_path)

        # Generate Markdown report alongside the JSON log
        from libs.terminus_agent.evolution.report_generator import generate_evolution_report

        md_content: str | None = None
        try:
            md_content = generate_evolution_report(log)
            md_path = self.logs_dir / "evolution_report.md"
            md_path.write_text(md_content, encoding="utf-8")
            logger.info("Evolution report written to %s", md_path)
        except Exception as exc:
            logger.warning("Failed to generate evolution report: %s", exc)

        # Phase 9: Sync verifier results to task environment directory
        self._sync_verifier_to_environment(log, md_content)

    def _sync_verifier_to_environment(self, log: dict, md_content: str | None = None) -> None:
        """Save verifier/evolution results to the task's environment directory.

        Writes to ``environment/verifier/`` so the data persists alongside
        skills and is available inside Docker on the next build.
        """
        env_dir = getattr(self._environment, "environment_dir", None)
        if not env_dir:
            logger.debug("No environment_dir available; skipping verifier sync")
            return

        verifier_dir = Path(env_dir) / "verifier"
        try:
            verifier_dir.mkdir(parents=True, exist_ok=True)

            # Full evolution run log
            (verifier_dir / "evolution_run_log.json").write_text(
                json.dumps(log, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            # Extract a compact verification summary for quick inspection
            summary = {
                "task_name": log.get("task_name"),
                "timestamp": log.get("timestamp"),
                "gt_oracle_result": log.get("gt_oracle_result"),
                "intervention_history": log.get("intervention_history", []),
                "evolution_summary": log.get("evolution_summary", ""),
            }
            (verifier_dir / "verification_summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            # Markdown report (reuse pre-generated content)
            if md_content:
                (verifier_dir / "evolution_report.md").write_text(md_content, encoding="utf-8")

            logger.info("Verifier results synced to %s", verifier_dir)
        except Exception as exc:
            logger.warning("Failed to sync verifier results to environment: %s", exc)

    async def _export_verifier_script(self, environment: BaseEnvironment) -> str | None:
        """Export /root/verifier/test_outputs.py from container to host.

        Returns the host path where the script was saved, or None on failure.
        Versions previous scripts (test_outputs_generated_v1.py, v2.py, ...).
        """
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir:
            return None

        result = await environment.exec(
            command="base64 /root/verifier/test_outputs.py 2>/dev/null || true",
            timeout_sec=15,
        )
        encoded = self._clean_base64(result.stdout or "")
        if not encoded:
            return None

        try:
            content = base64.b64decode(encoded).decode("utf-8")
        except Exception:
            logger.warning("Failed to decode verifier script from container")
            return None

        scripts_dir = Path(env_dir) / "verifier" / "generated_scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        versions = [int(m.group(1)) for p in scripts_dir.glob("test_outputs_v*.py") if (m := re.search(r"_v(\d+)\.py$", p.name))]
        next_version = max(versions, default=0) + 1
        target = scripts_dir / f"test_outputs_v{next_version}.py"

        target.write_text(content, encoding="utf-8")
        logger.info("Exported verifier script to %s", target)
        return str(target)

    async def _export_skills_from_container(
        self,
        environment: BaseEnvironment,
        skill_names: set[str],
        target_dir: Path,
        include_references: bool = False,
    ) -> list[str]:
        """Export skill directories from container to a host directory.

        Primary method: base64 via exec (works when terminal service is up).
        Fallback: docker compose cp via environment.download_dir (works even when
        the terminal service is down, e.g. after agent timeout or completion).

        Copies SKILL.md and scripts/ for each skill. Optionally copies references/.

        Returns:
            List of successfully exported skill names.
        """
        exported: list[str] = []

        for skill_name in sorted(skill_names):
            skill_host_dir = target_dir / skill_name
            skill_host_dir.mkdir(parents=True, exist_ok=True)

            # --- Primary path: base64 via exec ---
            result = await environment.exec(
                command=f"base64 '/app/environment/skills/{skill_name}/SKILL.md' 2>/dev/null || true",
                timeout_sec=15,
            )
            encoded = self._clean_base64(result.stdout or "")

            if encoded:
                try:
                    content = base64.b64decode(encoded).decode("utf-8")
                    (skill_host_dir / "SKILL.md").write_text(content, encoding="utf-8")
                    # Export scripts/
                    await self._export_container_subdir(environment, skill_name, "scripts", skill_host_dir)
                    # Export references/ (only for oracle export)
                    if include_references:
                        await self._export_container_subdir(environment, skill_name, "references", skill_host_dir)
                    exported.append(skill_name)
                    logger.info("Exported skill %s to %s", skill_name, skill_host_dir)
                    continue
                except Exception:
                    logger.warning("Failed to decode SKILL.md for %s, trying download_dir fallback", skill_name)
                    # clean up partial dir so fallback can overwrite
                    import shutil

                    shutil.rmtree(skill_host_dir, ignore_errors=True)
            else:
                logger.warning("Skill %s: exec-based export returned no data, trying download_dir fallback", skill_name)

            # --- Fallback: docker compose cp (works even when terminal service is down) ---
            if not hasattr(environment, "download_dir"):
                logger.warning("Skill %s has no SKILL.md and download_dir not available, skipping", skill_name)
                continue
            try:
                import shutil
                import tempfile

                with tempfile.TemporaryDirectory() as tmp:
                    container_skill_path = f"/app/environment/skills/{skill_name}"
                    await environment.download_dir(container_skill_path, tmp)
                    # download_dir puts contents under tmp/<skill_name>/
                    src = Path(tmp) / skill_name
                    if not src.exists():
                        # some implementations put files directly under tmp/
                        src = Path(tmp)
                    skill_md = src / "SKILL.md"
                    if not skill_md.exists():
                        logger.warning("Skill %s has no SKILL.md even after download_dir, skipping", skill_name)
                        continue
                    skill_host_dir.mkdir(parents=True, exist_ok=True)
                    # Copy SKILL.md
                    shutil.copy2(skill_md, skill_host_dir / "SKILL.md")
                    # Copy scripts/
                    scripts_src = src / "scripts"
                    if scripts_src.exists():
                        shutil.copytree(scripts_src, skill_host_dir / "scripts", dirs_exist_ok=True)
                    # Copy references/ if requested
                    if include_references:
                        refs_src = src / "references"
                        if refs_src.exists():
                            shutil.copytree(refs_src, skill_host_dir / "references", dirs_exist_ok=True)
                exported.append(skill_name)
                logger.info("Exported skill %s via download_dir fallback to %s", skill_name, skill_host_dir)
            except Exception as dl_exc:
                logger.warning("download_dir fallback failed for skill %s: %s", skill_name, dl_exc)

        return exported

    async def _export_container_subdir(
        self,
        environment: BaseEnvironment,
        skill_name: str,
        subdir: str,
        skill_host_dir: Path,
    ) -> None:
        """Export a subdirectory (scripts/ or references/) of a skill from container."""
        ls_result = await environment.exec(
            command=f"ls -1 /app/environment/skills/{skill_name}/{subdir}/ 2>/dev/null || true",
            timeout_sec=15,
        )
        file_names = [s.strip() for s in (ls_result.stdout or "").strip().splitlines() if s.strip() and not is_shell_warning(s)]
        if not file_names:
            return

        host_subdir = skill_host_dir / subdir
        host_subdir.mkdir(parents=True, exist_ok=True)
        for fname in file_names:
            file_result = await environment.exec(
                command=f"base64 '/app/environment/skills/{skill_name}/{subdir}/{fname}' 2>/dev/null || true",
                timeout_sec=15,
            )
            file_encoded = self._clean_base64(file_result.stdout or "")
            if file_encoded:
                try:
                    file_content = base64.b64decode(file_encoded).decode("utf-8")
                    (host_subdir / fname).write_text(file_content, encoding="utf-8")
                except Exception as exc:
                    logger.warning("Failed to decode %s/%s/%s: %s", skill_name, subdir, fname, exc)

    async def _import_agent_created_skills(
        self,
        environment: BaseEnvironment,
        pre_existing_skills: set[str],
    ) -> list[str]:
        """Import agent-created skills from container to host environment directory."""
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir:
            return []

        current_skills = await self._list_container_skills(environment)
        new_skill_names = current_skills - pre_existing_skills

        if not new_skill_names:
            logger.info("No new agent-created skills to import")
            return []

        host_skills_dir = Path(env_dir) / "skills"
        host_skills_dir.mkdir(parents=True, exist_ok=True)

        return await self._export_skills_from_container(environment, new_skill_names, host_skills_dir, include_references=False)

    def _rollback_host_skills(self, environment: BaseEnvironment, snapshot_skills_dir: Path) -> None:
        """Overwrite host environment skills with the best snapshot version.

        Replaces each evolved skill directory in ``environment/skills/`` with
        the corresponding directory from the snapshot, so that persisted skills
        match the GT-best version rather than the (potentially degraded) final
        container version.
        """
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir or not snapshot_skills_dir or not snapshot_skills_dir.is_dir():
            return

        host_skills_dir = Path(env_dir) / "skills"
        host_skills_dir.mkdir(parents=True, exist_ok=True)

        rolled_back: list[str] = []
        for skill_subdir in sorted(snapshot_skills_dir.iterdir()):
            if not skill_subdir.is_dir():
                continue
            target = host_skills_dir / skill_subdir.name
            try:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(skill_subdir, target)
                rolled_back.append(skill_subdir.name)
            except Exception as exc:
                logger.warning("Failed to rollback skill %s: %s", skill_subdir.name, exc)

        if rolled_back:
            logger.info("Rolled back %d host skills to best snapshot: %s", len(rolled_back), rolled_back)

    def _did_last_oracle_pass(self) -> bool:
        """Check whether the most recent intervention included a passing GT oracle."""
        if not self._intervention_history:
            return False
        gt_result = self._intervention_history[-1].get("gt_result")
        return gt_result is not None and gt_result.get("passed") is True

    async def _export_evolved_skills_to_host(self, environment: BaseEnvironment) -> Path | None:
        """Export evolved skills from the container to a temporary directory on the host.

        Returns:
            Path to the temp directory containing exported skills, or None if
            no evolved skills exist. Caller is responsible for cleanup.
        """
        current_skills = await self._list_container_skills(environment)
        new_skill_names = current_skills - self._pre_existing_skills

        if not new_skill_names:
            logger.info("No evolved skills to export for oracle")
            return None

        temp_dir = Path(tempfile.mkdtemp(prefix="evolved-skills-"))

        exported = await self._export_skills_from_container(environment, new_skill_names, temp_dir, include_references=True)

        if not exported:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        logger.info("Exported %d evolved skills to %s", len(exported), temp_dir)
        return temp_dir

    def _regenerate_conversation_md(self) -> None:
        """Re-generate full_conversation.md."""
        conv_path = self.logs_dir / "full_conversation.json"
        if not conv_path.exists():
            return
        try:
            messages = json.loads(conv_path.read_text(encoding="utf-8"))
            from .conversation_renderer import render_conversation_markdown

            md_content = render_conversation_markdown(messages)
            (self.logs_dir / "full_conversation.md").write_text(md_content, encoding="utf-8")
            logger.info("Re-generated full_conversation.md")
        except Exception as exc:
            logger.warning("Failed to re-generate conversation md: %s", exc)
