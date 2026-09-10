# Skill Creation Plan

**Task**: Solve TPP (Travelling Purchase Problem) PDDL planning tasks by reading domain/problem files, generating valid plans using pyperplan via unified_planning, and writing formatted plan output files.

**Rationale**: The task is straightforward: parse JSON config, solve PDDL problems with an existing solver stack, format and write plans. The provided solve.py already demonstrates the core workflow. A single skill covers the end-to-end pipeline since parsing, solving, formatting, and output are tightly coupled and the validation approach requires pickle serialization matching the solver output exactly.

**Number of skills**: 1

---

## Skill 1: evo-tpp-solver

**Description**: End-to-end utility for solving TPP PDDL planning tasks: reads problem.json, parses PDDL domain/problem files using unified_planning's PDDLReader, solves each task using pyperplan (with configurable heuristic/search fallbacks), formats actions in the required function-call syntax, writes plan text files, and serializes plans as pickle for validation compatibility.

**Responsibility**: Complete pipeline: JSON config parsing, PDDL parsing, plan generation with pyperplan (with fallback configurations like gbf/hff if default times out), action formatting as 'action_name(arg1, arg2, ...)' strings, writing plan output files, and pickle serialization for validator compatibility.

**Key functions**: `load_task_config`, `solve_task`, `format_action`, `write_plan`, `solve_all_tasks`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-tpp-solver/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
