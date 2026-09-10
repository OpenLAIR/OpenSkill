"""OpenSkill evolution agents — the in-container skill creators (Stage 2).

Both classes extend HarborTerminus2Evolution with Deep Research-generated
background docs injected at setup, and override the exit gate so that the
hidden ground-truth oracle is never invoked (the pipeline runs its own
independent evaluation afterwards).

OpenSkillAgentBase — the surrogate verification loop:
  - Agent creates skills + executes the task
  - An independent verifier session (separate LLM) generates and runs pytest;
    failures are fed back into the same agent session until the virtual pass
    rate reaches 1.0 or the retry budget is exhausted

OpenSkillAgent — the full method, extending the base loop with:
  - Verification research injected into the verifier's prompt
    (surrogate_dr_research.md, produced by the pipeline)
  - Targeted retrieval when a surrogate failure is classified as a
    domain-knowledge gap rather than a code bug (TargetedDRRunner)
"""

from __future__ import annotations

import base64
import logging
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from libs.terminus_agent.agents.terminus_2.harbor_terminus_2_evolution import (
    EpisodeExitResult,
    HarborTerminus2Evolution,
)

from .deep_research_client import DeepResearchClient
from .doc_manager import DocManager

logger = logging.getLogger(__name__)


def _osk_print(msg: str) -> None:
    """Print OpenSkill status to stdout."""
    try:
        print(msg, flush=True)
    except BrokenPipeError:
        pass


# ======================================================================
# Shared mixin: DR doc setup + injection + skill export
# ======================================================================

class _OpenSkillDRMixin:
    """Mixin providing Deep Research doc generation and container injection.

    Must be mixed into a class that inherits from HarborTerminus2Evolution.
    """

    def _init_dr(
        self,
        dr_api_key: str | None = None,
        dr_agent: str = "deep-research-pro-preview-12-2025",
        enable_dr_initial: bool = True,
    ) -> None:
        self._dr_api_key = dr_api_key
        self._dr_agent = dr_agent
        self._enable_dr_initial = enable_dr_initial

        self._doc_manager: DocManager | None = None
        self._dr_executor: ThreadPoolExecutor | None = None
        self._task_dir: Path | None = None
        self._task_toml: dict = {}

    async def _osk_setup(self, environment: BaseEnvironment) -> None:
        """Read task context and optionally generate+inject DR doc."""
        env_dir = getattr(environment, "environment_dir", None)
        if not env_dir:
            logger.warning("No environment_dir — skipping OpenSkill DR setup")
            return

        env_dir = Path(env_dir)
        self._task_dir = env_dir.parent

        # Read task.toml
        task_toml_path = self._task_dir / "task.toml"
        if task_toml_path.exists():
            try:
                self._task_toml = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to read task.toml: %s", e)

        # Read task instruction
        task_instruction = ""
        instruction_path = self._task_dir / "instruction.md"
        if instruction_path.exists():
            try:
                task_instruction = instruction_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to read instruction.md: %s", e)

        # Collect environment file listing
        env_files = []
        try:
            for item in env_dir.iterdir():
                if item.name.startswith("."):
                    continue
                env_files.append(item.name)
        except Exception:
            pass

        # Initialize Deep Research client
        try:
            dr_client = DeepResearchClient(
                api_key=self._dr_api_key,
                agent=self._dr_agent,
            )
        except ValueError as e:
            logger.warning("Deep Research client init failed: %s", e)
            _osk_print(f"[openskill] WARNING: DR client init failed: {e}")
            return

        doc_dir = env_dir / "doc"

        self._doc_manager = DocManager(
            dr_client=dr_client,
            doc_dir=doc_dir,
            task_instruction=task_instruction,
            environment_files=env_files,
            task_toml=self._task_toml,
            environment_dir=env_dir,
        )

        self._dr_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dr")

        # Generate initial doc via Deep Research
        if self._enable_dr_initial and task_instruction:
            await self._generate_initial_doc(environment)
        elif doc_dir.exists() and any(doc_dir.iterdir()):
            # Pipeline already generated docs (background.md, skill_plan.md,
            # references/) on the HOST side. Inject them into the container
            # even when DR generation is skipped (enable_dr_initial=False).
            _osk_print("[openskill] Injecting pre-existing docs into container...")
            await self._inject_doc_to_container(environment)

        # Read verification research (surrogate_dr_research.md) from the
        # container for explicit injection into the IndependentVerifier prompt.
        # When the file does not exist, _dr_surrogate_context stays empty.
        self._dr_surrogate_context = ""
        try:
            dr_result = await environment.exec(
                command="cat /app/environment/doc/surrogate_dr_research.md 2>/dev/null",
                timeout_sec=10,
            )
            self._dr_surrogate_context = (dr_result.stdout or "").strip()
            if self._dr_surrogate_context:
                _osk_print(
                    f"[openskill] DR-surrogate context loaded: "
                    f"{len(self._dr_surrogate_context)} chars"
                )
        except Exception:
            pass

    async def _generate_initial_doc(self, environment: BaseEnvironment) -> None:
        """Generate initial doc via DR and inject into container."""
        _osk_print("[openskill] Generating initial background doc via Deep Research...")
        start = time.time()
        try:
            result = self._doc_manager.generate_initial_doc()
        except Exception as e:
            logger.error("Initial DR doc generation failed: %s", e)
            _osk_print(f"[openskill] Initial doc generation failed: {e}")
            return

        elapsed = time.time() - start
        if result.status == "completed" and result.text:
            _osk_print(
                f"[openskill] Initial doc generated: {len(result.text)} chars, "
                f"{len(result.sources)} sources in {elapsed:.0f}s"
            )
            doc_dir = self._doc_manager._doc_dir
            host_docs = list(doc_dir.glob("*.md")) if doc_dir.exists() else []
            _osk_print(f"[openskill] Host doc_dir={doc_dir}, files={[f.name for f in host_docs]}")
            await self._inject_doc_to_container(environment)
        else:
            _osk_print(f"[openskill] Initial doc generation failed: status={result.status}")

    async def _inject_doc_to_container(
        self, environment: BaseEnvironment, clear_existing: bool = True
    ) -> None:
        """Inject all doc files from host doc_dir into the container.

        Handles:
        - Top-level .md and .json files (background.md, skill_plan.md, etc.)
        - references/ subdirectory tree (per-skill reference files)
        """
        if self._doc_manager is None:
            _osk_print("[openskill] INJECT SKIP: doc_manager is None")
            return

        doc_dir = self._doc_manager._doc_dir
        if not doc_dir.exists():
            _osk_print(f"[openskill] INJECT SKIP: doc_dir does not exist: {doc_dir}")
            return

        container_doc_dir = await self._find_container_doc_dir(environment)
        if not container_doc_dir:
            _osk_print("[openskill] INJECT FAIL: could not find/create doc dir in container")
            logger.warning("Could not find doc directory in container")
            return

        _osk_print(f"[openskill] INJECT: container doc dir = {container_doc_dir}")

        if clear_existing:
            await environment.exec(
                command=f"rm -rf '{container_doc_dir}'/*",
                timeout_sec=10,
            )

        # Inject all files recursively from host doc_dir
        injected_count = 0
        for item in sorted(doc_dir.rglob("*")):
            if not item.is_file():
                continue
            # Get relative path from doc_dir
            rel_path = item.relative_to(doc_dir)
            container_path = f"{container_doc_dir}/{rel_path}"
            container_parent = str(Path(container_path).parent)

            # Create parent directory in container
            await environment.exec(
                command=f"mkdir -p '{container_parent}'",
                timeout_sec=5,
            )

            # Inject file via base64
            content = item.read_bytes()
            encoded = base64.b64encode(content).decode("ascii")
            result = await environment.exec(
                command=(
                    f"echo '{encoded}' | base64 -d > '{container_path}'"
                ),
                timeout_sec=30,
            )
            if result.return_code != 0:
                _osk_print(
                    f"[openskill] INJECT FAIL: {rel_path} "
                    f"rc={result.return_code} stderr={result.stderr}"
                )
                logger.warning("Failed to inject doc %s: %s", rel_path, result.stderr)
            else:
                injected_count += 1
                logger.info("Injected doc: %s (%d bytes)", rel_path, len(content))

        _osk_print(f"[openskill] INJECT OK: {injected_count} files injected")

        # Verify injection
        verify = await environment.exec(
            command=f"find '{container_doc_dir}' -type f | head -20",
            timeout_sec=10,
        )
        _osk_print(f"[openskill] INJECT VERIFY: {verify.stdout}")

    async def _find_container_doc_dir(self, environment: BaseEnvironment) -> str:
        """Find the doc directory inside the container."""
        candidates = [
            "/app/environment/doc",
            "/root/environment/doc",
            "/home/github/build/environment/doc",
        ]
        for path in candidates:
            result = await environment.exec(
                command=f"test -d '{path}' && echo 'found'",
                timeout_sec=5,
            )
            _osk_print(f"[openskill] FIND_DOC_DIR: {path} -> rc={result.return_code} stdout='{(result.stdout or '').strip()}'")
            if result.return_code == 0 and "found" in (result.stdout or ""):
                return path

        _osk_print("[openskill] FIND_DOC_DIR: no candidate found, creating /app/environment/doc")
        r1 = await environment.exec(command="mkdir -p /app/environment/doc", timeout_sec=5)
        _osk_print(f"[openskill] FIND_DOC_DIR: mkdir /app/environment/doc rc={r1.return_code}")
        r2 = await environment.exec(
            command="mkdir -p /root/environment && ln -sfn /app/environment/doc /root/environment/doc",
            timeout_sec=5,
        )
        _osk_print(f"[openskill] FIND_DOC_DIR: symlink /root/environment/doc rc={r2.return_code}")
        return "/app/environment/doc"

    async def _export_skills_to_logs(self, environment: BaseEnvironment) -> None:
        """Export evo-* skills from container to logs_dir/evolved_skills/."""
        export_dir = self.logs_dir / "evolved_skills"
        export_dir.mkdir(parents=True, exist_ok=True)

        ls_result = await environment.exec(
            command="ls -1d /app/environment/skills/evo-* 2>/dev/null || true",
            timeout_sec=120,
        )
        skill_paths = [
            s.strip() for s in (ls_result.stdout or "").strip().splitlines()
            if s.strip() and s.strip().startswith("/app/environment/skills/evo-")
        ]

        if not skill_paths:
            _osk_print("[openskill] No evo-* skills found in container to export")
            return

        skill_names = {Path(p).name for p in skill_paths}
        _osk_print(f"[openskill] Exporting skills: {sorted(skill_names)}")

        exported = await self._export_skills_from_container(
            environment, skill_names, export_dir, include_references=False,
        )
        _osk_print(f"[openskill] Exported {len(exported)} skills to {export_dir}")

    def _osk_cleanup(self) -> None:
        """Cleanup DR resources."""
        if self._dr_executor is not None:
            self._dr_executor.shutdown(wait=False)
            self._dr_executor = None


# ======================================================================
# Surrogate verification loop (no GT oracle)
# ======================================================================

class OpenSkillAgentBase(_OpenSkillDRMixin, HarborTerminus2Evolution):
    """DR doc + EvoSkills surrogate verification loop, no GT oracle.

    Reuses the parent's full _check_episode_exit cascade:
      - Token budget check
      - Idle/stale detection
      - Independent surrogate verifier (separate LLM generates pytest)
      - Progress checklist + frontmatter validation
      - Surrogate failure → feed back to agent → agent fixes → iterate

    The only change from the parent: when surrogate passes and the
    parent would run the GT oracle (step 7), we SKIP it and exit.
    This means surrogate verification is the sole feedback mechanism.

    Max surrogate iterations controlled by max_host_interventions
    (default 1) and max_surrogate_retries (3).
    """

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        dr_api_key: str | None = None,
        dr_agent: str = "deep-research-pro-preview-12-2025",
        enable_dr_initial: bool = True,
        **kwargs,
    ):
        # Limit the surrogate loop — 1 successful pass exits, 3 retries max
        kwargs.setdefault("max_host_interventions", 1)
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._max_surrogate_retries = 3  # override parent's 15
        self._context_budget_warned = False  # 70% warning sent
        self._context_budget_last_chance = False  # 90% last-chance given
        _osk_print(
            f"[openskill] Config: max_host_interventions={self._max_host_interventions}, "
            f"max_surrogate_retries={self._max_surrogate_retries}"
        )
        self._init_dr(dr_api_key, dr_agent, enable_dr_initial)

    @staticmethod
    def name() -> str:
        return "openskill-base"

    def version(self) -> str | None:
        return "3.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)
        await self._osk_setup(environment)

    def _did_last_oracle_pass(self) -> bool:
        """Always True — OpenSkill skips the post-execution GT oracle.

        The pipeline runs its own independent evaluation after the creator
        agent finishes, so the in-agent GT oracle is redundant and wastes
        a large portion of the timeout budget on docker builds.
        """
        return True

    async def _check_for_new_skills(self, environment) -> str | None:
        """Override parent with longer Docker exec timeout (120s).

        The parent hardcodes timeout_sec=15 for the `ls` call that
        checks for new skills.  When the container is CPU-bound
        (e.g. running a TLS/BLS transit search), 15s is not enough
        and the resulting RuntimeError kills the entire agent run.

        We re-implement the logic here with timeout_sec=120 and wrap
        the whole thing in try/except so a timeout never crashes the
        agent.
        """
        try:
            known_names = {s["name"] for s in self._skills_metadata}
            result = await environment.exec(
                command="ls -1 /app/environment/skills/ 2>/dev/null || true",
                timeout_sec=120,
            )
            current_names = {
                line.strip()
                for line in (result.stdout or "").strip().splitlines()
                if line.strip()
            }
            new_names = current_names - known_names
            if not new_names:
                return None

            await self.refresh_skill_index()

            new_entries = [s for s in self._skills_metadata if s["name"] in new_names]
            if not new_entries:
                return None
            lines = ["NEW SKILLS DETECTED — you can now load these:"]
            for entry in new_entries:
                lines.append(
                    f'  {{"load_skill": "{entry["name"]}"}}  — '
                    f'{entry.get("description", "")}'
                )
            return "\n".join(lines)
        except Exception as exc:
            _osk_print(
                f"[openskill] WARNING: Failed to check for new skills "
                f"(container may be unresponsive): {exc}"
            )
            return None

    async def _read_evolution_summary(self, environment) -> str:
        """Override parent with longer timeout (120s) and error handling.

        The parent hardcodes timeout_sec=15 for reading
        evolution_summary.md from the container.  When the container
        is CPU-bound, 15s is not enough.
        """
        try:
            from libs.terminus_agent.agents.terminus_2.harbor_terminus_2_evolution import (
                is_shell_warning,
            )

            result = await environment.exec(
                command="cat /root/evolution_summary.md 2>/dev/null || true",
                timeout_sec=120,
            )
            raw = (result.stdout or "").strip()
            if not raw:
                return ""
            lines = [line for line in raw.splitlines() if not is_shell_warning(line)]
            return "\n".join(lines).strip()
        except Exception as exc:
            _osk_print(
                f"[openskill] WARNING: Failed to read evolution summary "
                f"(container may be unresponsive): {exc}"
            )
            return ""

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            _osk_print(
                f"[openskill] Agent finished (exit_reason={self._exit_reason}). "
                f"Exporting best-effort skills..."
            )
            try:
                await self._export_skills_to_logs(environment)
            except Exception as export_exc:
                _osk_print(
                    f"[openskill] WARNING: Failed to export skills "
                    f"(container may be unresponsive): {export_exc}"
                )
            if self._doc_manager is not None:
                self._doc_manager.save_history(self.logs_dir / "dr_update_history.json")
            self._osk_cleanup()

    async def _check_episode_exit(
        self,
        episode: int,
        result: Any,
        environment: BaseEnvironment,
        terminal_output: str,
    ) -> EpisodeExitResult:
        """Full surrogate loop from parent, but skip GT oracle.

        Delegates to the parent's _check_episode_exit for stages 1-6
        (token budget, idle detection, intervention cap, surrogate
        verifier, checklist, frontmatter). When the parent reaches
        stage 7 (GT oracle), we intercept and exit instead.

        The parent's _check_episode_exit returns EpisodeExitResult.
        We detect GT oracle triggers by checking if the parent
        incremented _host_intervention_count (meaning surrogate passed
        and it's about to run GT oracle). We pre-empt this.
        """
        # ── 1. Token budget check (with early warning + last-chance skill export) ──
        if self._chat is not None:
            max_tokens = self._get_max_context_tokens()
            usage_ratio = self._chat.last_input_tokens / max_tokens if max_tokens > 0 else 0

            # 1a. Early warning at 70% — tell agent to prioritize skill creation
            if usage_ratio >= 0.7 and not self._context_budget_warned:
                self._context_budget_warned = True
                # Check if P2 (skill creation) is done
                progress_text = await self._read_progress_checklist(environment)
                unchecked = self._parse_unchecked_items(progress_text)
                p2_pending = any("P2" in item for item in unchecked)
                if p2_pending:
                    _osk_print(
                        f"[openskill] Context budget 70% "
                        f"({self._chat.last_input_tokens}/{max_tokens}) — "
                        f"P2 not done, sending warning"
                    )
                    warning = (
                        "CONTEXT BUDGET WARNING: You have used 70% of your context budget. "
                        "P2 (skill creation) is NOT yet complete. You MUST create your evo-* "
                        "skill NOW before doing anything else. Load skill-creator, write the "
                        "skill to /app/environment/skills/, then mark P2 as done. "
                        "If you run out of context before creating a skill, this run is a FAILURE."
                    )
                    return EpisodeExitResult(should_exit=False, override_prompt=warning)
                else:
                    _osk_print(
                        "[openskill] Context budget 70% — P2 already done, continuing"
                    )

            # 1b. Hard limit at 90% — last chance to export skills
            if usage_ratio >= 0.9:
                # Check if skills exist in container
                ls_result = await environment.exec(
                    command="ls -1d /app/environment/skills/evo-* 2>/dev/null | head -1",
                    timeout_sec=30,
                )
                has_skills = bool((ls_result.stdout or "").strip())

                if not has_skills and not self._context_budget_last_chance:
                    # No skills yet — give agent ONE last episode to create them
                    self._context_budget_last_chance = True
                    _osk_print(
                        f"[openskill] Context budget 90% "
                        f"({self._chat.last_input_tokens}/{max_tokens}) — "
                        f"NO skills found, giving last-chance episode"
                    )
                    warning = (
                        "CONTEXT BUDGET REACHED: You are at 90% context capacity and "
                        "NO evo-* skills exist in /app/environment/skills/. This is your "
                        "LAST CHANCE to create a skill. You MUST do the following RIGHT NOW:\n"
                        "1. Load skill-creator: {\"load_skill\": \"skill-creator\"}\n"
                        "2. Create a minimal evo-* skill with SKILL.md + scripts/ based on "
                        "what you have learned so far about this task\n"
                        "3. Write /root/evolution_summary.md\n"
                        "4. Signal task_complete\n\n"
                        "Even a partial skill is better than no skill. Focus on capturing "
                        "the key domain knowledge and utility functions."
                    )
                    return EpisodeExitResult(should_exit=False, override_prompt=warning)

                # Skills exist or last chance already given — exit
                self._exit_reason = "token_budget"
                _osk_print(
                    f"[openskill] Exit: token_budget ({self._chat.last_input_tokens}/{max_tokens}) "
                    f"— skills_exist={has_skills}, exporting in finally block"
                )
                await self._record_intervention(environment, trigger="token_budget")
                return EpisodeExitResult(should_exit=True, exit_reason="token_budget")

        # ── 2. Idle / stale detection ──
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
                result.is_task_complete = True
            else:
                return EpisodeExitResult(should_exit=False)

        self._consecutive_idle_episodes = 0
        self._episodes_since_last_complete = 0

        # ── 3. Intervention cap ──
        cap_hit = self._host_intervention_count >= self._max_host_interventions
        retry_cap_hit = self._surrogate_retry_count >= self._max_surrogate_retries
        if cap_hit or retry_cap_hit:
            self._exit_reason = "max_interventions" if cap_hit else "max_surrogate_retries"
            _osk_print(
                f"[openskill] Intervention cap reached ({self._exit_reason}): "
                f"oracle={self._host_intervention_count}/{self._max_host_interventions}, "
                f"retries={self._surrogate_retry_count}/{self._max_surrogate_retries} "
                f"— will export best-effort skills in finally block"
            )
            await self._record_intervention(environment, trigger="max_interventions")
            # No GT oracle — just exit (skills exported via finally in run())
            return EpisodeExitResult(should_exit=True, exit_reason=self._exit_reason)

        _osk_print(
            f"[openskill] Running surrogate verifier "
            f"(interventions={self._host_intervention_count}/{self._max_host_interventions}, "
            f"retries={self._surrogate_retry_count}/{self._max_surrogate_retries}, "
            f"locked={self._surrogate_tests_locked})"
        )

        # ── 4. Independent surrogate verifier (reused from parent) ──
        if self._surrogate_tests_locked:
            try:
                verification = await self._verifier.verify(environment=environment)
            except Exception as exc:
                logger.warning("Locked surrogate re-run failed: %s", exc)
                self._surrogate_retry_count += 1
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
                await self._record_intervention(environment, trigger="locked_" + verification.source)
                feedback = (
                    f"Verification could not be completed ({error_detail}). "
                    "Please verify your output manually — re-read the task instruction, "
                    "check all output files, and signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)
        else:
            try:
                verification = await self._independent_verifier.generate_and_run(
                    environment=environment,
                    instruction=self._instruction,
                    logs_dir=self.logs_dir,
                    dr_context=getattr(self, "_dr_surrogate_context", ""),
                )
            except Exception as exc:
                logger.warning("Independent verification failed: %s", exc)
                self._surrogate_retry_count += 1
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
                await self._record_intervention(environment, trigger="verifier_" + verification.source)
                feedback = (
                    f"Verification could not be completed ({error_detail}). "
                    "Please verify your output manually — re-read the task instruction, "
                    "check all output files, and signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

            # Lock surrogate tests after first valid generation
            self._surrogate_tests_locked = True

        surrogate_dict = {
            "tests_passed": verification.tests_passed,
            "tests_failed": verification.tests_failed,
            "total_tests": verification.total_tests,
            "pass_rate": verification.tests_passed / verification.total_tests if verification.total_tests > 0 else 0.0,
        }
        surrogate_pass_rate = surrogate_dict["pass_rate"]

        _osk_print(
            f"[openskill] Surrogate: {verification.tests_passed}/{verification.total_tests} "
            f"passed ({surrogate_pass_rate:.0%})"
        )

        # Print per-test details for debugging
        for detail in verification.test_details:
            status = detail.get("status", "?")
            name = detail.get("name", "unknown")
            msg = detail.get("message", "")
            if status == "PASSED":
                _osk_print(f"  ✓ {name}")
            else:
                _osk_print(f"  ✗ {name}: {msg}" if msg else f"  ✗ {name} [{status}]")

        if verification.raw_output:
            _osk_print(f"[openskill] Surrogate raw output:\n{verification.raw_output}")

        # ── Surrogate failed → feed back to agent ──
        if verification.tests_failed > 0 or surrogate_pass_rate < 1.0:
            self._surrogate_retry_count += 1
            trigger = "surrogate_fail" if verification.tests_failed > 0 else "surrogate_incomplete"
            await self._record_intervention(environment, trigger=trigger, surrogate_result=surrogate_dict)

            reset_msg = await self._reset_progress_checklist(environment)

            # Run diagnosis if locked path without diagnosis
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
                except Exception:
                    pass

            if verification.tests_failed > 0:
                feedback = self._build_surrogate_feedback(verification)
            else:
                skipped_count = verification.total_tests - verification.tests_passed - verification.tests_failed
                feedback = (
                    f"Independent verifier: only {verification.tests_passed}/{verification.total_tests} tests passed "
                    f"({skipped_count} tests were skipped or errored). A pass rate of 100% is required.\n\n"
                    "Please check that your output is complete and correct, then signal task_complete again."
                )
            feedback = reset_msg + "\n\n" + feedback
            return EpisodeExitResult(should_exit=False, override_prompt=feedback)

        # ── 5. Progress checklist ──
        try:
            progress_text = await self._read_progress_checklist(environment)
            unchecked = self._parse_unchecked_items(progress_text)
        except Exception:
            unchecked = []

        if unchecked:
            self._checklist_fail_count += 1
            if self._checklist_fail_count <= 1:
                self._surrogate_retry_count += 1
                await self._record_intervention(
                    environment, trigger="surrogate_pass_checklist_fail", surrogate_result=surrogate_dict
                )
                feedback = (
                    "Independent verifier tests passed, but you have unchecked phases in /root/progress.md:\n"
                    + "\n".join(f"- {item}" for item in unchecked)
                    + "\n\nComplete each unchecked phase, update /root/progress.md, "
                    "then signal task_complete."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)
        else:
            self._checklist_fail_count = 0

        # ── 5b. Skill frontmatter validation ──
        if not self._frontmatter_fix_requested:
            missing_fm = await self._validate_skill_frontmatter(environment)
            if missing_fm:
                self._frontmatter_fix_requested = True
                self._surrogate_retry_count += 1
                await self._record_intervention(
                    environment, trigger="missing_frontmatter", surrogate_result=surrogate_dict
                )
                skill_list = "\n".join(f"- {p}" for p in missing_fm)
                feedback = (
                    "Your evolved skills have YAML frontmatter issues.\n\n"
                    f"Issues found:\n{skill_list}\n\n"
                    "Each SKILL.md must start with valid YAML frontmatter:\n"
                    "```\n---\nname: <skill-name>\n"
                    'description: "<what this skill does>"\n'
                    "---\n```\n\n"
                    "Fix all issues, then signal task_complete again."
                )
                return EpisodeExitResult(should_exit=False, override_prompt=feedback)

        # ── 6. Surrogate passed all checks → EXIT (no GT oracle) ──
        self._host_intervention_count += 1
        trigger = "surrogate_pass_checklist_incomplete" if unchecked else "surrogate_pass"
        await self._record_intervention(environment, trigger=trigger, surrogate_result=surrogate_dict)

        self._exit_reason = "surrogate_pass"
        _osk_print(
            f"[openskill] Surrogate passed (100%) — exiting "
            f"(intervention {self._host_intervention_count}, no GT oracle)"
        )
        return EpisodeExitResult(should_exit=True, exit_reason="surrogate_pass")


# ======================================================================
# Full method: base loop + verification research + targeted retrieval
# ======================================================================

class OpenSkillAgent(OpenSkillAgentBase):
    """Base surrogate loop + targeted DR on surrogate failure.

    In addition to the base surrogate verification loop, this agent adds:
    - DR-enhanced surrogate tests (pipeline injects surrogate_dr_research.md)
    - Targeted DR search when surrogate failures stem from missing domain
      knowledge (not simple code bugs).  Uses TargetedDRRunner to classify
      failure → optionally search → inject results into creator feedback.
    """

    def __init__(self, *args, enable_targeted_dr: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._enable_targeted_dr = enable_targeted_dr

        from .targeted_dr import TargetedDRRunner

        self._targeted_dr_runner = TargetedDRRunner()

    @staticmethod
    def name() -> str:
        return "openskill"

    async def setup(self, environment: BaseEnvironment) -> None:
        """Parent setup + cache prior knowledge for targeted DR."""
        await super().setup(environment)

        # Cache prior DR knowledge so the targeted DR classifier can
        # check if missing knowledge is already available.
        background_md = ""
        surrogate_dr_md = ""
        if self._doc_manager is not None:
            doc_dir = self._doc_manager._doc_dir
            bg_path = doc_dir / "background.md"
            sdr_path = doc_dir / "surrogate_dr_research.md"
            if bg_path.exists():
                try:
                    background_md = bg_path.read_text(encoding="utf-8")
                except Exception:
                    pass
            if sdr_path.exists():
                try:
                    surrogate_dr_md = sdr_path.read_text(encoding="utf-8")
                except Exception:
                    pass

        self._targeted_dr_runner.set_prior_knowledge(
            background_md=background_md,
            surrogate_dr_md=surrogate_dr_md,
        )
        if background_md or surrogate_dr_md:
            _osk_print(
                f"[openskill] Targeted DR prior knowledge cached: "
                f"background={len(background_md)} chars, "
                f"surrogate_dr={len(surrogate_dr_md)} chars"
            )

    async def _check_episode_exit(
        self,
        episode: int,
        result: Any,
        environment: BaseEnvironment,
        terminal_output: str,
    ) -> EpisodeExitResult:
        """Base surrogate loop + targeted DR on failure.

        Delegates to the base _check_episode_exit. If it returns a surrogate
        failure feedback (should_exit=False with override_prompt), we
        intercept and optionally run targeted DR to enrich the feedback
        with external domain knowledge.
        """
        exit_result = await super()._check_episode_exit(
            episode, result, environment, terminal_output,
        )

        # Only intercept surrogate failure feedbacks (not exits, not
        # non-surrogate continue signals).
        if exit_result.should_exit:
            return exit_result
        if not exit_result.override_prompt:
            return exit_result

        # Check if this is a surrogate failure (contains verification text)
        prompt = exit_result.override_prompt
        is_surrogate_failure = (
            "HOST VERIFICATION" in prompt
            or "independent verifier" in prompt.lower()
        )
        if not is_surrogate_failure:
            return exit_result

        # Attempt targeted DR search (can be disabled for ablation)
        if not self._enable_targeted_dr:
            return exit_result
        targeted_text = await self._run_targeted_dr_on_failure(environment)
        if targeted_text:
            enriched_prompt = (
                prompt
                + "\n\n## Additional Domain Knowledge (from targeted search)\n\n"
                "The following domain knowledge was retrieved by searching for "
                "information specifically related to the failures above. Use this "
                "to fix the domain-knowledge gaps in your skills:\n\n"
                + targeted_text
            )
            return EpisodeExitResult(
                should_exit=False,
                override_prompt=enriched_prompt,
            )

        return exit_result

    async def _run_targeted_dr_on_failure(
        self, environment: BaseEnvironment,
    ) -> str:
        """Run targeted DR search on surrogate failures (async wrapper).

        Wraps the synchronous TargetedDRRunner.classify_and_search() in
        a thread executor to avoid blocking the event loop (Gemini API
        calls are synchronous).

        Returns the research text if a search was performed, or empty
        string if skipped / failed.
        """
        import asyncio
        import functools

        # We need the latest verification result — read it from the
        # verifier stored by the base _check_episode_exit.
        verification = None
        if hasattr(self, "_independent_verifier") and self._independent_verifier._last_result:
            verification = self._independent_verifier._last_result
        elif hasattr(self, "_verifier"):
            # Locked path — try SelfVerifier
            try:
                from libs.terminus_agent.evolution.self_verifier import SelfVerifier
                sv = SelfVerifier()
                verification = await sv.verify(environment=environment)
            except Exception:
                pass

        if verification is None:
            return ""

        # Read instruction
        instruction = getattr(self, "_instruction", "")
        if not instruction:
            return ""

        task_toml = getattr(self, "_task_toml", {})

        loop = asyncio.get_running_loop()
        try:
            dr_result = await loop.run_in_executor(
                None,
                functools.partial(
                    self._targeted_dr_runner.classify_and_search,
                    verification=verification,
                    instruction=instruction,
                    task_toml=task_toml,
                ),
            )
        except Exception as exc:
            logger.warning("Targeted DR failed: %s", exc)
            _osk_print(f"[openskill] Targeted DR failed: {exc}")
            return ""

        if dr_result is None or dr_result.was_skipped or not dr_result.research_text:
            return ""

        return dr_result.research_text
