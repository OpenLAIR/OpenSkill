"""Agent Planner: LLM-based DR query generation.

Uses an LLM to analyze task context (instruction, environment files, task.toml)
and generate a focused Deep Research query. Unlike the template-based
DocManager.build_planner_query(), this can reason about which domain knowledge
is most critical and produce more targeted queries.

Improvements over template approach:
- PDF text extraction via pdfplumber (not just "binary file" note)
- LLM reasons about what knowledge matters most for the task
- Dynamic query generation instead of fixed template
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import litellm

logger = logging.getLogger(__name__)

# Default planner model
_DEFAULT_PLANNER_MODEL = "anthropic/claude-opus-4-6"


def build_domain_hint(task_toml: dict, instruction: str = "") -> str:
    """Build a concise domain description from task metadata and instruction.

    Returns a string like:
        "Domain: cheminformatics (tags: rdkit, molecular-similarity).
         Task summary: Find the top-K most similar chemicals to a query molecule..."

    Used to inject task-specific context into system prompts so LLMs know
    what domain they are working in from the very first message.
    """
    parts = []

    category = task_toml.get("category", "")
    tags = task_toml.get("tags", [])
    if category:
        domain_str = f"Domain: {category}"
        if tags:
            domain_str += f" (tags: {', '.join(tags)})"
        domain_str += "."
        parts.append(domain_str)
    elif tags:
        parts.append(f"Domain tags: {', '.join(tags)}.")

    # Extract first 1-2 sentences of instruction as a task summary
    if instruction:
        # Take up to 300 chars, cut at last sentence boundary
        snippet = instruction[:300]
        for end_char in (".\n", ". ", ".\t"):
            idx = snippet.rfind(end_char)
            if idx > 30:
                snippet = snippet[: idx + 1]
                break
        parts.append(f"Task summary: {snippet.strip()}")

    return "\n".join(parts) if parts else "Domain: general programming."


def _build_planner_system_prompt(task_toml: dict, instruction: str = "") -> str:
    """Build the Agent Planner system prompt with task-specific domain context."""
    domain_hint = build_domain_hint(task_toml, instruction)

    return textwrap.dedent(f"""\
        You are a Research Planner for an AI coding agent. Your job is to generate a
        precise Deep Research query that will retrieve domain knowledge needed to BUILD
        A REUSABLE SKILL (a Python utility module) for a programming task.

        The query you produce will be sent to Google's Gemini Deep Research API, which
        performs web search and synthesizes a comprehensive background document.

        TASK DOMAIN:
        {domain_hint}

        IMPORTANT CONTEXT — SKILL CREATION:
        The retrieved information will be used to create a SKILL — a standalone Python
        utility module (SKILL.md + scripts/utils.py) containing helper functions that
        a coding agent can import to solve the task. The skill should encapsulate the
        domain-specific logic so the agent only needs to call high-level functions.

        Therefore, your research query must focus on what a SKILL AUTHOR needs to know
        for the domain described above:

        Guidelines:
        - Focus on the EXACT LIBRARY APIs, function signatures, parameter defaults, and
          return types that the skill's utility functions must use. Ask for WORKING CODE
          EXAMPLES with correct imports and calling conventions.
        - Identify the CRITICAL PARAMETERS that affect correctness — the specific flags,
          thresholds, and configuration values that change the output. Request documentation
          on their correct values for the task's domain.
        - Request information about DATA PIPELINE PATTERNS: how to read the input data,
          transform it, and produce the expected output format — as reusable functions.
        - Ask about COMMON PITFALLS and edge cases that would cause utility functions to
          return wrong results (deprecated API attributes, version-specific behavior,
          data type mismatches, etc.).
        - Request CORRECT IMPORT PATHS and package names for the domain's libraries.
          Explicitly ask whether any commonly-used APIs are deprecated and what the
          current recommended replacements are.
        - Do NOT include the answer or solution approach — the agent must figure that out.
        - The output should be a single, well-structured research query.

        Output ONLY the research query text. No preamble, no explanation, no markdown
        formatting around it. Just the query itself.
    """)


def _extract_pdf_text(pdf_path: Path, max_chars: int = 5000) -> str:
    """Extract text from a PDF file using pdfplumber.

    Falls back to file size note if pdfplumber is not available.
    """
    try:
        import pdfplumber
    except ImportError:
        return f"[PDF file: {pdf_path.name}, {pdf_path.stat().st_size} bytes — pdfplumber not installed]"

    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                if sum(len(p) for p in text_parts) > max_chars:
                    break
        full_text = "\n".join(text_parts)
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + f"\n... (truncated, {len(full_text)} chars total)"
        return full_text if full_text.strip() else f"[PDF file: {pdf_path.name}, no extractable text]"
    except Exception as e:
        return f"[PDF file: {pdf_path.name}, extraction failed: {e}]"


def build_planner_context(
    instruction: str,
    task_toml: dict,
    environment_dir: Path | None = None,
) -> str:
    """Build the full context string for the planner LLM.

    Similar to DocManager.build_planner_context() but with PDF text extraction.
    """
    parts = []

    # 1. Task instruction
    parts.append("## Task Instruction\n")
    parts.append(instruction)

    # 2. Task metadata
    if task_toml:
        parts.append("\n## Task Metadata (task.toml)\n")
        category = task_toml.get("category", "")
        tags = task_toml.get("tags", [])
        difficulty = task_toml.get("difficulty", "")
        if category:
            parts.append(f"- Category: {category}")
        if tags:
            parts.append(f"- Tags: {', '.join(tags)}")
        if difficulty:
            parts.append(f"- Difficulty: {difficulty}")
        agent_cfg = task_toml.get("agent", {})
        if agent_cfg:
            timeout = agent_cfg.get("timeout_sec", "")
            if timeout:
                parts.append(f"- Agent timeout: {timeout}s")

    # 3. Environment files with content preview (enhanced with PDF extraction)
    if environment_dir and environment_dir.exists():
        parts.append("\n## Environment Files\n")
        for item in sorted(environment_dir.iterdir()):
            if item.name.startswith(".") or item.name == "skills":
                continue
            if item.name == "doc":
                continue  # Skip existing doc dir

            if item.name == "Dockerfile":
                try:
                    content = item.read_text(encoding="utf-8", errors="replace")
                    parts.append(f"### {item.name}\n```\n{content}\n```")
                except Exception:
                    parts.append(f"- {item.name} (read error)")

            elif item.is_file():
                size = item.stat().st_size

                # PDF: extract text
                if item.suffix == ".pdf":
                    pdf_text = _extract_pdf_text(item)
                    parts.append(f"### {item.name} ({size} bytes, PDF)\n```\n{pdf_text}\n```")

                # Text-based files: preview
                elif size < 50000 and item.suffix in (
                    ".csv", ".json", ".txt", ".md", ".yaml", ".yml",
                    ".toml", ".py", ".sh", ".r", ".R",
                ):
                    try:
                        content = item.read_text(encoding="utf-8", errors="replace")
                        preview = content[:2000]
                        if len(content) > 2000:
                            preview += f"\n... ({len(content)} chars total, truncated)"
                        parts.append(f"### {item.name} ({size} bytes)\n```\n{preview}\n```")
                    except Exception:
                        parts.append(f"- {item.name} ({size} bytes, read error)")

                # Excel: note only
                elif item.suffix in (".xlsx", ".xls", ".png", ".jpg"):
                    parts.append(f"- {item.name} ({size} bytes, binary file)")

                else:
                    parts.append(f"- {item.name} ({size} bytes)")

            elif item.is_dir():
                sub_files = list(item.iterdir())
                parts.append(f"- {item.name}/ ({len(sub_files)} items)")

    return "\n".join(parts)


class AgentPlanner:
    """Generates DR queries using an LLM to analyze task context."""

    def __init__(self, model: str = _DEFAULT_PLANNER_MODEL):
        self._model = model

    def generate_dr_query(
        self,
        instruction: str,
        task_toml: dict,
        environment_dir: Path | None = None,
    ) -> str:
        """Generate a focused DR query by having an LLM analyze the task.

        Args:
            instruction: Full text of instruction.md.
            task_toml: Parsed task.toml dict.
            environment_dir: Path to the environment/ directory.

        Returns:
            The DR query string.
        """
        context = build_planner_context(instruction, task_toml, environment_dir)

        user_prompt = textwrap.dedent(f"""\
            Analyze the following programming task and generate a Deep Research query
            that will retrieve the domain knowledge needed to BUILD A REUSABLE SKILL
            (Python utility module with helper functions) for this task.

            The skill will contain functions like data loaders, domain-specific
            computation routines, and output formatters that an AI coding agent can
            import and call. Focus your query on what a SKILL AUTHOR needs: exact
            API usage, correct parameter values, working code patterns, and pitfalls.

            {context}

            Generate the research query now.
        """)

        logger.info(
            "Generating DR query via %s (%d char context)",
            self._model, len(context),
        )

        system_prompt = _build_planner_system_prompt(task_toml, instruction)

        try:
            response = litellm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=4096,
                drop_params=True,
            )
            query = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM call failed for DR query generation: %s", e)
            # Fallback: use the template-based approach
            query = self._fallback_query(instruction, task_toml, environment_dir)

        logger.info("Generated DR query: %d chars", len(query))
        return query

    @staticmethod
    def _fallback_query(
        instruction: str,
        task_toml: dict,
        environment_dir: Path | None = None,
    ) -> str:
        """Fallback template-based query if LLM call fails."""
        category = task_toml.get("category", "")
        tags = task_toml.get("tags", [])
        domain_hint = ""
        if category:
            domain_hint = f"This task is in the domain of {category}"
            if tags:
                domain_hint += f" (related topics: {', '.join(tags)})"
            domain_hint += "."

        context = build_planner_context(instruction, task_toml, environment_dir)

        return textwrap.dedent(f"""\
            I need a comprehensive technical background document for building a
            REUSABLE PYTHON SKILL (utility module with helper functions) for the
            following programming task. The skill will be a standalone module that
            an AI coding agent can import to solve the task.

            {domain_hint}

            {context}

            ## Requirements for the Background Document

            Write a thorough background document focused on SKILL CREATION:

            1. **Library APIs & Imports**: Exact import paths, function signatures,
               and parameter defaults for domain-specific libraries.
            2. **Reusable Function Patterns**: Code patterns for utility functions
               (data loaders, domain computation, output formatters).
            3. **Critical Parameters**: Parameter values that affect correctness
               — flags, thresholds, and configuration specific to this task's domain.
            4. **Data Pipeline**: How to read inputs and produce outputs as
               composable utility functions.
            5. **Pitfalls & Deprecations**: Deprecated APIs, version-specific
               behavior, and common mistakes.
            6. **Working Code Examples**: Complete, runnable code snippets showing
               correct library usage.

            Format the document as Markdown with clear section headers.
        """)
