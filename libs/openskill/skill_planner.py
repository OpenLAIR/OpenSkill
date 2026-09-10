"""Skill Planner: LLM-based decomposition of DR doc into multi-skill plans.

Takes a DR background document and task context, then uses an LLM to decompose
the domain knowledge into N independent skills with clear responsibility
boundaries (e.g., data loading vs algorithm implementation vs output formatting).

Also implements reference injection: for each planned skill, extracts the
relevant sections of the DR doc into per-skill reference files that get
placed in the skill's references/ directory.

Used by the pipeline between Steps 2 (DR doc generation) and 3 (Skill Creator).
The skill plan and per-skill references are placed in the container so the
agent can follow the plan when creating skills.
"""

from __future__ import annotations

import json
import logging
import re
import textwrap
from pathlib import Path

import litellm

from .agent_planner import build_domain_hint, build_planner_context

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "anthropic/claude-opus-4-6"


def _build_skill_plan_system_prompt(
    task_toml: dict,
    instruction: str = "",
) -> str:
    """Build system prompt for the skill plan decomposition LLM."""
    domain_hint = build_domain_hint(task_toml, instruction)

    return textwrap.dedent(f"""\
        You are a Skill Architect for an AI coding agent pipeline. Your job is to
        analyze a programming task and its associated background research document,
        then decompose the domain knowledge into a MULTI-SKILL PLAN.

        TASK DOMAIN:
        {domain_hint}

        CONTEXT — SKILL CREATION PIPELINE:
        An AI coding agent will receive your plan and create each skill as a standalone
        Python utility module (SKILL.md + scripts/). Each skill must have:
        - A clear, non-overlapping responsibility
        - Self-contained utility functions (importable via sys.path)
        - YAML frontmatter with name and description

        YOUR TASK:
        Analyze the background research document and task instruction to produce a
        structured skill plan that decomposes the work into 1-4 independent skills.

        DECOMPOSITION PRINCIPLES:
        1. **Separation by concern**: Each skill handles one functional domain
           (e.g., data I/O, domain-specific computation, output formatting)
        2. **Clear boundaries**: No overlapping responsibilities between skills
        3. **Dependency ordering**: Skills listed in creation order (foundational first)
        4. **Reference mapping**: For each skill, identify which sections of the
           background document are relevant

        RESPONSE FORMAT — STRICT JSON:
        You MUST respond with a single JSON object (no markdown fences, no
        commentary). The JSON must match this schema exactly:

        {{
          "task_summary": "One-line summary of what the task requires",
          "decomposition_rationale": "Why this decomposition (1-2 sentences)",
          "skills": [
            {{
              "name": "evo-<domain>-<function>",
              "description": "What this skill does and when to use it",
              "responsibility": "Specific responsibility boundary",
              "key_functions": ["func_a", "func_b"],
              "dr_sections": ["Section Title 1", "Section Title 2"],
              "depends_on": []
            }}
          ]
        }}

        RULES:
        - Skill names MUST start with "evo-"
        - Use 1 skill for simple tasks, 2-3 for medium complexity, up to 4 for complex
        - Each skill's dr_sections lists the EXACT section headers from the background
          document that are relevant to this skill
        - depends_on lists names of other skills this one depends on (empty if none)
        - key_functions are the main utility functions this skill should provide
        - If the task is simple enough for a single skill, output exactly 1 skill
        - Do NOT over-decompose — fewer skills is better when responsibilities overlap
    """)


class SkillPlanner:
    """Decomposes DR background docs into multi-skill plans with references."""

    def __init__(self, model: str = _DEFAULT_MODEL):
        self._model = model

    def generate_skill_plan(
        self,
        instruction: str,
        task_toml: dict,
        dr_background: str,
        environment_dir: Path | None = None,
        max_retries: int = 2,
    ) -> dict:
        """Generate a multi-skill plan from DR background doc and task context.

        Args:
            instruction: Full text of instruction.md.
            task_toml: Parsed task.toml dict.
            dr_background: Full text of DR-generated background.md.
            environment_dir: Path to environment/ directory.
            max_retries: Retries on parse failure.

        Returns:
            Parsed skill plan dict with keys: task_summary, decomposition_rationale,
            skills (list of skill specs).
        """
        context = build_planner_context(instruction, task_toml, environment_dir)

        user_prompt = textwrap.dedent(f"""\
            Analyze the following programming task and its background research document.
            Decompose the domain knowledge into a multi-skill plan.

            ## Task Context
            {context}

            ## Background Research Document
            The following document was generated by Deep Research and contains
            domain knowledge needed to solve the task:

            {dr_background}

            Generate the skill plan now. Output ONLY valid JSON.
        """)

        system_prompt = _build_skill_plan_system_prompt(task_toml, instruction)

        logger.info(
            "Generating skill plan via %s (%d char context, %d char DR doc)",
            self._model, len(context), len(dr_background),
        )

        for attempt in range(1 + max_retries):
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
                raw = response.choices[0].message.content.strip()

                # Strip markdown code fences if present
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    lines = lines[1:]  # Remove opening fence
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    raw = "\n".join(lines)

                plan = json.loads(raw)

                # Validate required fields
                if not isinstance(plan.get("skills"), list) or len(plan["skills"]) == 0:
                    logger.warning(
                        "Skill plan has no skills (attempt %d), retrying...",
                        attempt + 1,
                    )
                    continue

                # Validate each skill has required fields
                valid = True
                for skill in plan["skills"]:
                    if not all(k in skill for k in ("name", "description", "responsibility")):
                        valid = False
                        break
                    # Ensure name starts with evo-
                    if not skill["name"].startswith("evo-"):
                        skill["name"] = f"evo-{skill['name']}"

                if not valid:
                    logger.warning(
                        "Skill plan has invalid skill entries (attempt %d), retrying...",
                        attempt + 1,
                    )
                    continue

                logger.info(
                    "Generated skill plan: %d skills (attempt %d)",
                    len(plan["skills"]), attempt + 1,
                )
                return plan

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    "Skill plan parse error (attempt %d): %s",
                    attempt + 1, e,
                )
            except Exception as e:
                logger.error("LLM call failed for skill plan: %s", e)

        # Fallback: single skill plan
        logger.warning("All skill plan attempts failed, using single-skill fallback")
        return self._fallback_plan(instruction, task_toml)

    def extract_skill_references(
        self,
        skill_plan: dict,
        dr_background: str,
        doc_dir: Path,
    ) -> dict[str, Path]:
        """Extract per-skill reference files from the DR background doc.

        For each skill in the plan, extracts the relevant sections of the
        DR doc (identified by dr_sections) into a separate reference file.
        These files are placed in doc/references/<skill-name>/ and will be
        injected into the container's environment so the agent can use them.

        Args:
            skill_plan: The skill plan dict from generate_skill_plan().
            dr_background: Full DR background document text.
            doc_dir: Path to the doc/ directory (host side).

        Returns:
            Dict mapping skill name -> Path to its reference directory.
        """
        references_dir = doc_dir / "references"
        references_dir.mkdir(parents=True, exist_ok=True)

        # Parse DR doc into sections by header
        sections = _split_by_headers(dr_background)

        result = {}
        for skill in skill_plan.get("skills", []):
            skill_name = skill["name"]
            skill_ref_dir = references_dir / skill_name
            skill_ref_dir.mkdir(parents=True, exist_ok=True)

            # Find matching sections
            dr_section_names = skill.get("dr_sections", [])
            matched_content = _match_sections(sections, dr_section_names)

            if matched_content:
                # Write the reference file
                ref_path = skill_ref_dir / "domain_reference.md"
                header = (
                    f"# Domain Reference for {skill_name}\n\n"
                    f"**Responsibility**: {skill.get('responsibility', 'N/A')}\n\n"
                    f"**Key functions to implement**: "
                    f"{', '.join(skill.get('key_functions', []))}\n\n"
                    "---\n\n"
                )
                ref_path.write_text(
                    header + matched_content,
                    encoding="utf-8",
                )
                logger.info(
                    "Created reference for %s: %d chars (%d sections matched)",
                    skill_name, len(matched_content), len(dr_section_names),
                )
            else:
                # Fallback: give the full DR doc
                ref_path = skill_ref_dir / "domain_reference.md"
                ref_path.write_text(
                    f"# Domain Reference for {skill_name}\n\n"
                    f"**Responsibility**: {skill.get('responsibility', 'N/A')}\n\n"
                    "---\n\n"
                    f"{dr_background}",
                    encoding="utf-8",
                )
                logger.info(
                    "No section matches for %s, using full DR doc as reference",
                    skill_name,
                )

            result[skill_name] = skill_ref_dir

        return result

    @staticmethod
    def _fallback_plan(instruction: str, task_toml: dict) -> dict:
        """Single-skill fallback plan when LLM fails."""
        category = task_toml.get("category", "general")
        tags = task_toml.get("tags", [])
        domain = tags[0] if tags else category

        return {
            "task_summary": "Single skill covering all task requirements",
            "decomposition_rationale": "Fallback: LLM decomposition failed, using single skill",
            "skills": [
                {
                    "name": f"evo-{domain}-solver",
                    "description": f"Complete utility module for {category} task",
                    "responsibility": "All task functionality",
                    "key_functions": ["solve", "load_data", "format_output"],
                    "dr_sections": [],
                    "depends_on": [],
                }
            ],
        }


def _split_by_headers(text: str) -> list[dict]:
    """Split markdown text into sections by headers (##, ###, etc.).

    Returns list of dicts: [{"header": "...", "level": 2, "content": "..."}]
    """
    sections = []
    current: dict | None = None
    lines = text.split("\n")

    for line in lines:
        header_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if header_match:
            if current is not None:
                current["content"] = current["content"].rstrip()
                sections.append(current)
            current = {
                "header": header_match.group(2).strip(),
                "level": len(header_match.group(1)),
                "content": "",
            }
        elif current is not None:
            current["content"] += line + "\n"
        else:
            # Text before first header — treat as intro
            if sections or (line.strip() and not current):
                current = {
                    "header": "Introduction",
                    "level": 1,
                    "content": line + "\n",
                }

    if current is not None:
        current["content"] = current["content"].rstrip()
        sections.append(current)

    return sections


def _match_sections(
    sections: list[dict],
    target_headers: list[str],
) -> str:
    """Match section headers against target names (fuzzy).

    Returns concatenated content of matching sections.
    """
    if not target_headers:
        return ""

    # Normalize targets for fuzzy matching
    targets_lower = [t.lower().strip() for t in target_headers]

    matched_parts = []
    for section in sections:
        header_lower = section["header"].lower().strip()

        # Exact or substring match
        for target in targets_lower:
            if target in header_lower or header_lower in target:
                level_prefix = "#" * section["level"]
                matched_parts.append(
                    f"{level_prefix} {section['header']}\n\n{section['content']}"
                )
                break

    return "\n\n".join(matched_parts)


def format_skill_plan_md(skill_plan: dict) -> str:
    """Generate a markdown representation of a skill plan dict.

    Returns the markdown string (does NOT write to disk).
    """
    md_parts = [
        "# Skill Creation Plan\n",
        f"**Task**: {skill_plan.get('task_summary', 'N/A')}\n",
        f"**Rationale**: {skill_plan.get('decomposition_rationale', 'N/A')}\n",
        f"**Number of skills**: {len(skill_plan.get('skills', []))}\n",
        "---\n",
    ]

    for i, skill in enumerate(skill_plan.get("skills", []), 1):
        md_parts.append(f"## Skill {i}: {skill['name']}\n")
        md_parts.append(f"**Description**: {skill.get('description', 'N/A')}\n")
        md_parts.append(f"**Responsibility**: {skill.get('responsibility', 'N/A')}\n")

        key_funcs = skill.get("key_functions", [])
        if key_funcs:
            md_parts.append(f"**Key functions**: `{'`, `'.join(key_funcs)}`\n")

        deps = skill.get("depends_on", [])
        if deps:
            md_parts.append(f"**Depends on**: {', '.join(deps)}\n")

        # Reference injection hint
        md_parts.append(
            f"\n> **Reference**: Domain-specific knowledge for this skill is in "
            f"`references/{skill['name']}/domain_reference.md`. "
            f"Read it before implementing this skill's scripts.\n"
        )
        md_parts.append("")

    md_parts.extend([
        "---\n",
        "## Instructions for Agent\n",
        "1. Create skills in the order listed above (dependencies first).\n",
        "2. For each skill, read its reference file in `references/<skill-name>/` FIRST.\n",
        "3. Follow the responsibility boundaries strictly — do NOT overlap functionality.\n",
        "4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.\n",
        "5. Write utility functions in each skill's `scripts/` directory.\n",
        "6. After creating all skills, write a main script that imports from all skills.\n",
    ])

    return "\n".join(md_parts)


def save_skill_plan(
    skill_plan: dict,
    doc_dir: Path,
) -> Path:
    """Save skill plan as JSON and markdown to the doc directory.

    Creates two files:
    - skill_plan.json — machine-readable plan
    - skill_plan.md — human/agent-readable plan that the agent sees in
      /app/environment/doc/

    Returns path to the markdown file.
    """
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = doc_dir / "skill_plan.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(skill_plan, f, indent=2, ensure_ascii=False)

    # Generate and save markdown
    md_text = format_skill_plan_md(skill_plan)
    md_path = doc_dir / "skill_plan.md"
    md_path.write_text(md_text, encoding="utf-8")

    logger.info("Saved skill plan: %s + %s", json_path, md_path)
    return md_path
