"""Document manager: builds Deep Research queries from task context and
manages the environment/doc/ background documents (with source tracking)."""

from __future__ import annotations

import json
import logging
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path

from .deep_research_client import DeepResearchClient, DeepResearchResult

logger = logging.getLogger(__name__)


@dataclass
class DocUpdateRecord:
    """Record of a single doc update for logging/analysis."""

    trigger: str  # e.g. "initial"
    iteration: int
    query: str
    result_status: str
    chars_added: int
    elapsed_sec: float
    sources_count: int = 0
    timestamp: float = field(default_factory=time.time)


class DocManager:
    """Manages environment/doc/ content generated via Deep Research."""

    def __init__(
        self,
        dr_client: DeepResearchClient,
        doc_dir: Path,
        task_instruction: str,
        environment_files: list[str] | None = None,
        task_toml: dict | None = None,
        environment_dir: Path | None = None,
    ):
        self._dr_client = dr_client
        self._doc_dir = Path(doc_dir)
        self._task_instruction = task_instruction
        self._environment_files = environment_files or []
        self._task_toml = task_toml or {}
        self._environment_dir = Path(environment_dir) if environment_dir else None
        self._update_history: list[DocUpdateRecord] = []
        self._iteration = 0
        self._sources: list[dict] = []  # accumulated sources across all DR calls

    @property
    def update_history(self) -> list[DocUpdateRecord]:
        return list(self._update_history)

    @property
    def all_sources(self) -> list[dict]:
        return list(self._sources)

    def get_current_doc(self) -> str:
        """Read and concatenate all .md files in doc_dir."""
        if not self._doc_dir.exists():
            return ""
        parts = []
        for f in sorted(self._doc_dir.glob("*.md")):
            parts.append(f.read_text(encoding="utf-8", errors="replace"))
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Planner: build retrieval plan from task context
    # ------------------------------------------------------------------

    def build_planner_context(self) -> str:
        """Build the full context that the Planner LLM will see.

        Includes: instruction.md, task.toml metadata, environment file
        contents (first N lines of data files), Dockerfile.
        """
        parts = []

        # 1. Task instruction
        parts.append("## Task Instruction\n")
        parts.append(self._task_instruction)

        # 2. Task metadata from task.toml
        if self._task_toml:
            parts.append("\n## Task Metadata (task.toml)\n")
            category = self._task_toml.get("category", "")
            tags = self._task_toml.get("tags", [])
            difficulty = self._task_toml.get("difficulty", "")
            if category:
                parts.append(f"- Category: {category}")
            if tags:
                parts.append(f"- Tags: {', '.join(tags)}")
            if difficulty:
                parts.append(f"- Difficulty: {difficulty}")
            agent_cfg = self._task_toml.get("agent", {})
            if agent_cfg:
                timeout = agent_cfg.get("timeout_sec", "")
                if timeout:
                    parts.append(f"- Agent timeout: {timeout}s")

        # 3. Environment files with content preview
        if self._environment_dir and self._environment_dir.exists():
            parts.append("\n## Environment Files\n")
            for item in sorted(self._environment_dir.iterdir()):
                if item.name.startswith(".") or item.name == "skills":
                    continue
                if item.name == "Dockerfile":
                    try:
                        content = item.read_text(encoding="utf-8", errors="replace")
                        parts.append(f"### {item.name}\n```\n{content}\n```")
                    except Exception:
                        parts.append(f"- {item.name} (read error)")
                elif item.is_file():
                    size = item.stat().st_size
                    if size < 50000 and item.suffix in (
                        ".csv", ".json", ".txt", ".md", ".yaml", ".yml",
                        ".toml", ".py", ".sh", ".r", ".R",
                    ):
                        try:
                            content = item.read_text(encoding="utf-8", errors="replace")
                            # Show first 2000 chars for data files
                            preview = content[:2000]
                            if len(content) > 2000:
                                preview += f"\n... ({len(content)} chars total, truncated)"
                            parts.append(f"### {item.name} ({size} bytes)\n```\n{preview}\n```")
                        except Exception:
                            parts.append(f"- {item.name} ({size} bytes, read error)")
                    elif item.suffix in (".pdf", ".xlsx", ".xls", ".png", ".jpg"):
                        parts.append(f"- {item.name} ({size} bytes, binary file)")
                    else:
                        parts.append(f"- {item.name} ({size} bytes)")
                elif item.is_dir() and item.name != "doc":
                    sub_files = list(item.iterdir())
                    parts.append(f"- {item.name}/ ({len(sub_files)} items)")
        elif self._environment_files:
            parts.append("\n## Environment Files\n")
            for f in self._environment_files[:20]:
                parts.append(f"- {f}")

        return "\n".join(parts)

    def build_planner_query(self) -> str:
        """Build the DR query that includes the Planner's context.

        Since we use DR as both planner and researcher (DR does web search
        internally), we combine the task analysis request with the retrieval
        request into a single DR call.
        """
        context = self.build_planner_context()

        # Extract task.toml info for targeted query
        category = self._task_toml.get("category", "")
        tags = self._task_toml.get("tags", [])
        domain_hint = ""
        if category:
            domain_hint = f"This task is in the domain of {category}"
            if tags:
                domain_hint += f" (related topics: {', '.join(tags)})"
            domain_hint += "."

        return textwrap.dedent(f"""\
            I need a comprehensive technical background document for an AI agent
            that will solve the following programming task. The document should
            provide domain knowledge, algorithms, best practices, common pitfalls,
            and critical implementation details.

            {domain_hint}

            {context}

            ## Requirements for the Background Document

            Write a thorough background document that covers:

            1. **Domain Knowledge**: Core concepts, terminology, and theory needed
               to solve this task. {f"Focus on {category}-specific knowledge." if category else ""}
               Include relevant mathematical formulations if applicable.

            2. **Key Algorithms & Methods**: Specific algorithms, libraries, APIs,
               or techniques that are most appropriate. Include which Python packages
               to use and their key function signatures.

            3. **Data Formats & Parsing**: How to correctly parse, interpret, and
               validate any input data files mentioned in the environment. Be specific
               about column indices, delimiters, encoding, and schema.

            4. **Critical Implementation Details**: Common mistakes, edge cases,
               and gotchas that an implementer must avoid. Be very specific — e.g.,
               "use sparse representation, NOT fixed-length hash" rather than vague
               guidance like "choose the right data structure".

            5. **Correctness Criteria**: What makes a solution correct vs incorrect.
               Include numerical tolerances, sort orders, output formats, and
               validation rules.

            6. **Code Patterns**: Short code snippets showing the correct API usage
               for critical operations (not full solutions, just patterns).

            Format the document as Markdown with clear section headers. Be precise
            and specific — this document will be the AI agent's primary reference
            for solving the task correctly.
        """)

    # ------------------------------------------------------------------
    # Initial doc generation
    # ------------------------------------------------------------------

    def generate_initial_doc(self) -> DeepResearchResult:
        """Generate the initial background document via Deep Research.

        Uses Planner context (task.toml + file contents) to build a
        targeted DR query.
        """
        self._iteration = 0
        query = self.build_planner_query()

        logger.info("Generating initial doc via Deep Research (%d char query)", len(query))
        result = self._dr_client.research(query)

        if result.status == "completed" and result.text:
            self._write_doc("background.md", result.text)
            self._accumulate_sources(result)
            self._save_sources_file()
            self._record_update("initial", query, result)
            logger.info("Initial doc written: %d chars, %d sources", len(result.text), len(result.sources))
        else:
            logger.warning("Initial doc generation failed: status=%s", result.status)

        return result

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

    def _write_doc(self, filename: str, content: str) -> None:
        """Write (overwrite) a doc file, removing existing docs first."""
        self._doc_dir.mkdir(parents=True, exist_ok=True)
        for f in self._doc_dir.glob("*.md"):
            f.unlink()
        filepath = self._doc_dir / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info("Wrote doc: %s (%d chars)", filepath.name, len(content))

    def _accumulate_sources(self, result: DeepResearchResult) -> None:
        """Add new sources from a DR result to the accumulated list."""
        seen = {s.get("url") for s in self._sources}
        for src in result.sources:
            if src.get("url") and src["url"] not in seen:
                self._sources.append(src)
                seen.add(src["url"])

    def _save_sources_file(self) -> None:
        """Save accumulated sources to a JSON file alongside docs."""
        if not self._sources:
            return
        self._doc_dir.mkdir(parents=True, exist_ok=True)
        sources_path = self._doc_dir / "sources.json"
        sources_path.write_text(
            json.dumps(self._sources, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _record_update(self, trigger: str, query: str, result: DeepResearchResult) -> None:
        self._update_history.append(
            DocUpdateRecord(
                trigger=trigger,
                iteration=self._iteration,
                query=query[:500],
                result_status=result.status,
                chars_added=len(result.text),
                elapsed_sec=result.elapsed_sec,
                sources_count=len(result.sources),
            )
        )

    def save_history(self, path: Path) -> None:
        """Save update history to a JSON file for analysis."""
        records = []
        for r in self._update_history:
            records.append({
                "trigger": r.trigger,
                "iteration": r.iteration,
                "result_status": r.result_status,
                "chars_added": r.chars_added,
                "elapsed_sec": round(r.elapsed_sec, 1),
                "sources_count": r.sources_count,
                "timestamp": r.timestamp,
            })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        logger.info("Saved doc update history: %s (%d records)", path, len(records))
