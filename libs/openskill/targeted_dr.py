"""Targeted DR on surrogate failure — failure-driven domain knowledge acquisition.

When surrogate verification fails and the failure stems from missing domain
knowledge (not a simple code bug), this module searches for the specific
external facts needed to fix the skill.

Flow:
  1. LLM classifies failure as SELF-FIXABLE or NEEDS-DR.
  2. If NEEDS-DR, build a targeted query from failure details.
  3. Execute Gemini Search grounding (fast, cheap).
  4. Return research text to inject into creator feedback.

Redundancy avoidance:
  - Hard cap on searches per task (default 3).
  - Topic tracking: prior search summaries included in subsequent queries.
  - Prior knowledge filtering: classifier checks if answer is already in
    background.md / surrogate_dr_research.md.
"""

from __future__ import annotations

import logging
import os
import textwrap
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from libs.terminus_agent.evolution.models import VerificationResult

logger = logging.getLogger(__name__)


def _print(msg: str) -> None:
    print(msg, flush=True)


@dataclass
class TargetedDRResult:
    """Result of a targeted DR search on surrogate failure."""

    query: str
    research_text: str
    failure_names: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0
    was_skipped: bool = False  # True → classified as self-fixable
    skip_reason: str = ""


class TargetedDRRunner:
    """Failure-driven domain search.

    Stateful: tracks previous searches within a single task to avoid
    redundant queries.  Call ``reset()`` between tasks.
    """

    # Default models
    # Search model: used via google.genai (no prefix needed)
    _DEFAULT_SEARCH_MODEL = "gemini-3.1-flash-lite-preview"
    # Classifier model: used via litellm (needs gemini/ prefix for AI Studio)
    _DEFAULT_CLASSIFIER_MODEL = "gemini/gemini-3.1-flash-lite-preview"

    def __init__(
        self,
        search_model: str = _DEFAULT_SEARCH_MODEL,
        classifier_model: str = _DEFAULT_CLASSIFIER_MODEL,
        max_searches_per_task: int = 3,
        search_temperature: float = 0.2,
        search_max_output_tokens: int = 2048,
    ):
        self._search_model = search_model
        self._classifier_model = classifier_model
        self._max_searches = max_searches_per_task
        self._search_temperature = search_temperature
        self._search_max_tokens = search_max_output_tokens

        # Per-task state
        self._searches_done: int = 0
        self._searched_topics: list[str] = []
        self._background_excerpt: str = ""
        self._surrogate_dr_excerpt: str = ""

    # ------------------------------------------------------------------
    # Prior knowledge setup
    # ------------------------------------------------------------------

    def set_prior_knowledge(
        self,
        background_md: str = "",
        surrogate_dr_md: str = "",
    ) -> None:
        """Cache excerpts of prior DR output for redundancy checking."""
        self._background_excerpt = background_md[:3000]
        self._surrogate_dr_excerpt = surrogate_dr_md[:3000]

    def reset(self) -> None:
        """Reset per-task state.  Call between tasks."""
        self._searches_done = 0
        self._searched_topics = []

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def classify_and_search(
        self,
        verification: VerificationResult,
        instruction: str,
        task_toml: dict,
    ) -> TargetedDRResult | None:
        """Classify failure and optionally run targeted DR search.

        Returns:
            ``TargetedDRResult`` with research text if a search was performed,
            ``TargetedDRResult`` with ``was_skipped=True`` if self-fixable,
            or ``None`` on infrastructure failure.
        """
        # Budget check
        if self._searches_done >= self._max_searches:
            _print(
                f"[targeted-dr] Budget exhausted "
                f"({self._searches_done}/{self._max_searches}), skipping"
            )
            return TargetedDRResult(
                query="",
                research_text="",
                was_skipped=True,
                skip_reason="search_budget_exhausted",
            )

        # No failures to analyze
        failed = [
            d for d in verification.test_details
            if d.get("status") == "FAILED"
        ]
        if not failed:
            return TargetedDRResult(
                query="",
                research_text="",
                was_skipped=True,
                skip_reason="no_failed_tests",
            )

        # Step 1: classify
        needs_dr, reasoning = self._classify_failure(verification, instruction)
        failure_names = [d.get("name", "unknown") for d in failed[:10]]

        if not needs_dr:
            _print(f"[targeted-dr] Classified as self-fixable: {reasoning}")
            return TargetedDRResult(
                query="",
                research_text="",
                failure_names=failure_names,
                was_skipped=True,
                skip_reason=f"self_fixable: {reasoning}",
            )

        _print(f"[targeted-dr] Classified as NEEDS-DR: {reasoning}")

        # Step 2: build query
        query = self._build_targeted_query(
            verification, instruction, task_toml, reasoning,
        )

        # Step 3: execute search
        t0 = time.time()
        research_text = self._execute_search(query)
        elapsed = time.time() - t0

        if research_text:
            self._searches_done += 1
            # Track topic for deduplication
            topic = reasoning[:120]
            self._searched_topics.append(topic)
            _print(
                f"[targeted-dr] Search #{self._searches_done} completed: "
                f"{len(research_text)} chars in {elapsed:.1f}s"
            )
        else:
            _print("[targeted-dr] Search returned no results")

        return TargetedDRResult(
            query=query,
            research_text=research_text,
            failure_names=failure_names,
            elapsed_sec=elapsed,
        )

    # ------------------------------------------------------------------
    # Step 1: Classification
    # ------------------------------------------------------------------

    def _classify_failure(
        self,
        verification: VerificationResult,
        instruction: str,
    ) -> tuple[bool, str]:
        """LLM judge: does this failure need external domain knowledge?

        Returns:
            (needs_dr, reasoning) where needs_dr is True if a search should
            be performed, and reasoning explains why.
        """
        # Format failure details
        failure_lines = []
        for d in verification.test_details:
            if d.get("status") == "FAILED":
                name = d.get("name", "unknown")
                msg = d.get("message", "")[:200]
                failure_lines.append(f"- {name}: {msg}" if msg else f"- {name}")

        failures_text = "\n".join(failure_lines[:15])
        diagnosis_text = (verification.diagnosis or "")[:1500]

        # Excerpt of prior knowledge
        prior_knowledge = ""
        if self._background_excerpt or self._surrogate_dr_excerpt:
            prior_knowledge = (
                "## Prior Domain Knowledge Available to the Creator\n\n"
                "The creator already has access to the following domain "
                "information. If the knowledge needed to fix the failure is "
                "ALREADY present here but the creator just failed to use it "
                "correctly, classify as SELF-FIXABLE.\n\n"
            )
            if self._background_excerpt:
                prior_knowledge += (
                    f"### Background Research\n{self._background_excerpt[:1500]}\n\n"
                )
            if self._surrogate_dr_excerpt:
                prior_knowledge += (
                    f"### Surrogate Verification Research\n"
                    f"{self._surrogate_dr_excerpt[:1500]}\n\n"
                )

        prompt = textwrap.dedent(f"""\
            Classify the following surrogate test failures to decide if the
            skill creator agent can fix them without additional domain knowledge.

            ## Test Failures
            {failures_text}

            ## Diagnosis (root cause analysis)
            {diagnosis_text if diagnosis_text else "(no diagnosis available)"}

            {prior_knowledge}

            ## Classification Rules

            SELF-FIXABLE — the creator can fix with existing knowledge:
            - Coding bug (wrong variable, off-by-one, missing import, typo)
            - Format mismatch (wrong column name, wrong file path, wrong key)
            - Type error or data structure issue
            - The diagnosis clearly identifies a simple code fix
            - The needed knowledge is already in "Prior Domain Knowledge" above

            NEEDS-DR — external domain knowledge is required:
            - Wrong numerical result and the correct value is unknown
            - Incorrect algorithm variant or parameter choice requiring
              domain expertise not in prior knowledge
            - Library API used incorrectly and correct usage is NOT in prior
              knowledge or diagnosis
            - Multiple tests fail with related domain-specific errors suggesting
              a fundamental misunderstanding

            Output EXACTLY one line in this format:
            SELF-FIXABLE: <brief reason>
            or
            NEEDS-DR: <what specific domain knowledge is missing>
        """)

        try:
            import litellm

            response = litellm.completion(
                model=self._classifier_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
                drop_params=True,
            )
            answer = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Classification LLM call failed: %s", exc)
            # On failure, default to self-fixable (conservative)
            return False, f"classification_error: {exc}"

        # Parse response
        first_line = answer.split("\n")[0].strip()
        if first_line.upper().startswith("NEEDS-DR"):
            reason = first_line.split(":", 1)[-1].strip() if ":" in first_line else first_line
            return True, reason
        else:
            reason = first_line.split(":", 1)[-1].strip() if ":" in first_line else first_line
            return False, reason

    # ------------------------------------------------------------------
    # Step 2: Query construction
    # ------------------------------------------------------------------

    def _build_targeted_query(
        self,
        verification: VerificationResult,
        instruction: str,
        task_toml: dict,
        dr_reasoning: str,
    ) -> str:
        """Build a focused search query from failure details."""
        from .agent_planner import build_domain_hint

        domain_hint = build_domain_hint(task_toml, instruction)

        # Specific failure messages
        failure_lines = []
        for d in verification.test_details:
            if d.get("status") == "FAILED":
                name = d.get("name", "unknown")
                msg = d.get("message", "")[:200]
                failure_lines.append(f"- {name}: {msg}" if msg else f"- {name}")

        failures_text = "\n".join(failure_lines[:10])
        diagnosis_text = (verification.diagnosis or "")[:1000]

        # Already searched topics
        searched_text = (
            "\n".join(f"- {t}" for t in self._searched_topics)
            if self._searched_topics
            else "None"
        )

        return textwrap.dedent(f"""\
            ## Domain
            {domain_hint}

            ## Context
            A Python skill was built for the following task but produced wrong
            results.  I need specific domain facts to fix the failures.

            Task (summary): {instruction[:500]}

            ## Specific Test Failures
            {failures_text}

            ## Root Cause Analysis
            {diagnosis_text if diagnosis_text else "(not available)"}

            ## What Domain Knowledge Is Missing
            {dr_reasoning}

            ## Already Searched (do NOT repeat these topics)
            {searched_text}

            ## What I Need
            Search for the SPECIFIC DOMAIN FACTS that would resolve the
            failures above.  Focus narrowly on:
            - Correct parameter values, algorithm variants, or formulas
            - Reference implementations or authoritative documentation
            - Exact expected results for the inputs described in the failures

            Be extremely specific and concise.  Only provide information that
            DIRECTLY addresses the failures listed above.
        """)

    # ------------------------------------------------------------------
    # Step 3: Search execution
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_query(query: str) -> str:
        """Remove banned keywords from query to prevent answer leakage."""
        import re
        for kw in ["SkillsBench", "skillsbench", "skills-bench", "skills_bench"]:
            query = re.sub(re.escape(kw), "", query, flags=re.IGNORECASE)
        return query

    def _execute_search(self, query: str) -> str:
        """Run Gemini Search grounding (same API as surrogate DR)."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.warning("google-genai not installed, skipping targeted DR")
            return ""

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            _print("[targeted-dr] No Gemini API key, skipping search")
            return ""

        try:
            client = genai.Client(api_key=api_key)

            response = client.models.generate_content(
                model=self._search_model,
                contents=self._sanitize_query(query),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=self._search_temperature,
                    max_output_tokens=self._search_max_tokens,
                ),
            )

            return (response.text or "").strip()

        except Exception as exc:
            logger.warning("Targeted DR search failed: %s", exc)
            _print(f"[targeted-dr] Search failed: {exc}")
            return ""
