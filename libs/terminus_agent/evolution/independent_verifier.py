"""Independent verifier — generates and runs surrogate verification in isolation.

Uses a separate LLM session (no shared context with the evolution agent) to
generate pytest scripts based solely on the task instruction, environment files,
and output files.  Eliminates confirmation bias by preventing the verifier from
seeing the evolution agent's implementation code or reasoning.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from libs.terminus_agent.agents.terminus_2.skill_docs import SkillDocLoader

from .models import VerificationResult
from .self_verifier import SelfVerifier

logger = logging.getLogger(__name__)


class IndependentVerifier:
    """Generate and run a surrogate verifier using an independent LLM session.

    The verifier agent runs inside the *same* Docker container as the evolution
    agent (so it can read output files), but uses a completely separate LLM
    session with its own prompt template — no context pollution from
    implementation details.

    Workflow per invocation:
    1. Spin up a fresh ``HarborTerminus2WithSkills`` agent with the independent
       verifier prompt template.
    2. The agent autonomously discovers files, writes pytest tests, runs them,
       and signals task_complete.
    3. ``SelfVerifier.verify()`` reads the generated test results.
    """

    def __init__(self, model_name: str, temperature: float = 0.3):
        self._model_name = model_name
        self._temperature = temperature
        self._generation_count: int = 0
        self._last_result: VerificationResult | None = None

    async def generate_and_run(
        self,
        environment: BaseEnvironment,
        instruction: str,
        logs_dir: Path,
        dr_context: str = "",
    ) -> VerificationResult:
        """Launch an independent verifier agent, then read pytest results.

        The agent runs in the same container as the evolution agent (shared
        output files) but with a fresh LLM session and verification-only prompt.

        Args:
            dr_context: Optional DR-surrogate research text.  When provided,
                injected into the verifier prompt as authoritative domain
                knowledge for deriving expected pytest assertion values.
        """
        # Lazy import to avoid circular dependency (evolution -> skills -> evolution)
        from libs.terminus_agent.agents.terminus_2.harbor_terminus_2_skills import (
            HarborTerminus2WithSkills,
        )

        self._generation_count += 1

        verifier_logs = logs_dir / f"independent-verifier-{self._generation_count}"
        verifier_logs.mkdir(parents=True, exist_ok=True)

        prompt_template_path = Path(__file__).parent / "prompt_templates" / "independent_verifier.txt"

        # Delete per-session progress files and previous diagnosis; keep the verifier script for inheritance
        await environment.exec(
            command="rm -f /root/verifier_progress.md /root/verifier_requirements.txt /root/verifier/diagnosis.md",
            timeout_sec=10,
        )

        # Read existing verifier script (if any) for inheritance context
        previous_verifier_context = await self._build_previous_verifier_context(environment)

        # Create a minimal agent: fresh LLM session, verifier prompt, no skill loading
        verifier_agent = HarborTerminus2WithSkills(
            logs_dir=verifier_logs,
            model_name=self._model_name,
            temperature=self._temperature,
            prompt_template=str(prompt_template_path),
            max_episodes=20,
        )
        # Minimal setup: ensure python3, initialize skill loader (needed by
        # _check_for_new_skills in run loop) but skip full index build
        await verifier_agent._ensure_python3_installed(environment)
        verifier_agent._skill_loader = SkillDocLoader(environment=environment)
        raw_template = prompt_template_path.read_text(encoding="utf-8")
        # Escape braces in previous_verifier_context so they survive str.format()
        # in run() — the context often contains Python scripts with dict literals
        # and f-strings that would otherwise be interpreted as format placeholders.
        safe_context = previous_verifier_context.replace("{", "{{").replace("}", "}}")
        rendered = raw_template.replace("{previous_verifier_context}", safe_context)

        # Inject DR-surrogate domain research — authoritative domain
        # knowledge for deriving expected values in pytest assertions.
        safe_dr = (
            dr_context.replace("{", "{{").replace("}", "}}")
            if dr_context
            else "No DR-surrogate research available."
        )
        verifier_agent._prompt_template = rendered.replace("{dr_surrogate_context}", safe_dr)

        logger.info(
            "Starting independent verifier agent (generation #%d, model=%s)",
            self._generation_count,
            self._model_name,
        )

        agent_error: str | None = None
        try:
            await asyncio.wait_for(
                verifier_agent.run(instruction, environment, AgentContext()),
                timeout=480,  # 8 minutes
            )
        except TimeoutError:
            agent_error = "Independent verifier agent timed out after 480s"
            logger.warning(agent_error)
        except Exception as exc:
            agent_error = f"Independent verifier agent failed: {exc}"
            logger.warning(agent_error)

        # Read the test results written by the agent (may have partially succeeded)
        self_verifier = SelfVerifier()
        result = await self_verifier.verify(environment=environment)

        # Read diagnosis file (written by V8 step for failed tests)
        result.diagnosis = await self._read_diagnosis(environment)

        self._last_result = result  # Store for next invocation's context

        # Always propagate infrastructure errors so the caller knows the verifier
        # had issues, even if a partial script was produced before the crash/timeout.
        if agent_error:
            result.error = agent_error
            if result.source in ("no_script", "script_error"):
                logger.warning("Verifier infrastructure failure, no usable script produced (source=%s): %s", result.source, agent_error)
            else:
                logger.warning(
                    "Verifier infrastructure failure but partial script found (%d tests). Results may be incomplete: %s",
                    result.total_tests,
                    agent_error,
                )
        else:
            logger.info(
                "Independent verifier completed: source=%s, tests=%d passed / %d total",
                result.source,
                result.tests_passed,
                result.total_tests,
            )

        return result

    async def _build_previous_verifier_context(self, environment: BaseEnvironment) -> str:
        """Read the existing verifier script and build inheritance context for the prompt."""
        try:
            result = await environment.exec(
                command="cat /root/verifier/test_outputs.py 2>/dev/null",
                timeout_sec=10,
            )
            script_content = result.stdout.strip() if result.stdout else ""
        except Exception:
            script_content = ""

        if not script_content:
            return "No previous verifier script exists. Write a new verifier from scratch following the workflow below."

        test_count = len(re.findall(r"def test_", script_content))
        logger.info(
            "Previous verifier script found with %d tests (generation #%d)",
            test_count,
            self._generation_count,
        )

        # Build failure info from last run's results
        failure_info = ""
        if self._last_result and self._last_result.test_details:
            failed = [d for d in self._last_result.test_details if d.get("status") == "FAILED"]
            if failed:
                failure_names = [d["name"] for d in failed[:20]]
                failure_info = (
                    f"\nThe previous run had {len(failed)} FAILING tests (out of {self._last_result.total_tests}):\n"
                    + "\n".join(f"  - {name}" for name in failure_names)
                    + (f"\n  (+ {len(failed) - 20} more...)" if len(failed) > 20 else "")
                    + "\n\nThese failures may be bugs in the TEST SCRIPT itself (not the output). "
                    "Read the script, diagnose each failure, and fix the test logic.\n"
                )

        return (
            f"PREVIOUS VERIFIER EXISTS with {test_count} test(s) at /root/verifier/test_outputs.py.\n"
            "A ground truth evaluation found issues with the output despite surrogate tests.\n"
            "This means the previous verifier missed real problems OR had bugs in its own tests.\n\n"
            "QUALITY OVER QUANTITY — 30 correct tests are better than 200 buggy tests.\n"
            f"{failure_info}\n"
            "=== PREVIOUS SCRIPT CONTENT ===\n"
            f"```python\n{script_content}\n```\n"
            "=== END PREVIOUS SCRIPT ===\n\n"
            "You MUST:\n"
            "1. Review the previous script above (already in context)\n"
            "2. FIX BUGS in existing tests first — tests that raise AttributeError, KeyError,\n"
            "   SyntaxError, or other exceptions are BROKEN TEST CODE and must be fixed\n"
            "3. Remove or merge redundant/duplicate tests\n"
            "4. Only AFTER fixing existing tests, add new deeper tests for CONTENT CORRECTNESS:\n"
            "   - Independently derive expected values from environment data\n"
            "   - Test individual output items/entries separately (not all-at-once)\n"
            "   - Verify domain logic, not just structure/format\n"
            f"5. Keep total test count UNDER 60 — previous had {test_count}. "
            "Do NOT blindly add parameterized tests that multiply test count.\n"
            "6. The previous script already handles file existence and format — "
            "your new tests should focus on whether output VALUES are actually correct."
        )

    async def diagnose_failures(
        self,
        environment: BaseEnvironment,
        instruction: str,
        logs_dir: Path,
        verification: VerificationResult,
    ) -> str:
        """Run a lightweight diagnosis agent to analyze failures without regenerating tests.

        Uses ``diagnosis_only.txt`` — a stripped-down prompt with only JSON
        format, file-writing instructions, and V8 diagnosis format (no V1-V7
        test-generation workflow).  The agent runs the existing locked test
        script, reads output files, and writes ``/root/verifier/diagnosis.md``.
        The test script is backed up before the run and restored afterward to
        preserve locking.

        Returns the diagnosis text (empty string on failure).
        """
        from libs.terminus_agent.agents.terminus_2.harbor_terminus_2_skills import (
            HarborTerminus2WithSkills,
        )

        # Backup the locked test script
        await environment.exec(
            command="cp /root/verifier/test_outputs.py /root/verifier/test_outputs.py.locked 2>/dev/null || true",
            timeout_sec=10,
        )

        # Delete previous diagnosis so we get a fresh one
        await environment.exec(
            command="rm -f /root/verifier/diagnosis.md /root/verifier_progress.md",
            timeout_sec=10,
        )

        # Build diagnosis context with failed test details
        failed_details = []
        for d in verification.test_details:
            if d.get("status") == "FAILED":
                msg = d.get("message", "")
                name = d.get("name", "unknown")
                failed_details.append(f"  - {name}: {msg}" if msg else f"  - {name}")

        diagnosis_context = (
            f"Current test results: {verification.tests_passed}/{verification.total_tests} passed.\nFailed tests:\n" + "\n".join(failed_details)
        )

        diag_logs = logs_dir / f"diagnosis-{self._generation_count}"
        diag_logs.mkdir(parents=True, exist_ok=True)

        prompt_template_path = Path(__file__).parent / "prompt_templates" / "diagnosis_only.txt"
        raw_template = prompt_template_path.read_text(encoding="utf-8")

        verifier_agent = HarborTerminus2WithSkills(
            logs_dir=diag_logs,
            model_name=self._model_name,
            temperature=self._temperature,
            prompt_template=str(prompt_template_path),
            max_episodes=8,
        )
        await verifier_agent._ensure_python3_installed(environment)
        verifier_agent._skill_loader = SkillDocLoader(environment=environment)
        # Escape braces in diagnosis_context so they survive str.format() in run()
        safe_diag_context = diagnosis_context.replace("{", "{{").replace("}", "}}")
        verifier_agent._prompt_template = raw_template.replace("{diagnosis_context}", safe_diag_context)

        logger.info("Starting diagnosis-only verifier agent (model=%s)", self._model_name)

        try:
            await asyncio.wait_for(
                verifier_agent.run(instruction, environment, AgentContext()),
                timeout=500,
            )
        except TimeoutError:
            logger.warning("Diagnosis agent timed out after 500s")
        except Exception as exc:
            logger.warning("Diagnosis agent failed: %s", exc)

        # Read the diagnosis
        diagnosis = await self._read_diagnosis(environment)

        # Restore the locked test script
        await environment.exec(
            command="cp /root/verifier/test_outputs.py.locked /root/verifier/test_outputs.py 2>/dev/null || true",
            timeout_sec=10,
        )

        logger.info("Diagnosis-only agent completed (%d chars)", len(diagnosis))
        return diagnosis

    async def _read_diagnosis(self, environment: BaseEnvironment) -> str:
        """Read /root/verifier/diagnosis.md from the container."""
        try:
            result = await environment.exec(
                command="cat /root/verifier/diagnosis.md 2>/dev/null",
                timeout_sec=10,
            )
            raw = (result.stdout or "").strip()
            if not raw:
                return ""
            # Filter out shell warnings (e.g. "bash: cannot set terminal process group")
            from libs.terminus_agent.agents.terminus_2.skill_docs import is_shell_warning

            lines = [line for line in raw.splitlines() if not is_shell_warning(line)]
            return "\n".join(lines).strip()
        except Exception:
            return ""

    def reset(self) -> None:
        """Reset generation counter (call at the start of each evolution run)."""
        self._generation_count = 0
        self._last_result = None
