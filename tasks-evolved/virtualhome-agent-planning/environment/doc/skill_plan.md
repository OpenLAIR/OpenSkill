# Skill Creation Plan

**Task**: Solve IPC Airport domain PDDL planning problems by parsing domain/problem files, generating valid plans, and writing them in correct output format

**Rationale**: The task has two main concerns: (1) orchestrating the solve pipeline (reading problem.json, invoking planners with appropriate configurations, handling failures/timeouts) and (2) ensuring the output plan format matches what the validator expects. These are tightly coupled enough to fit in 2 skills: a core PDDL solver utility and a plan formatting/output utility.

**Number of skills**: 2

---

## Skill 1: evo-pddl-solver

**Description**: Core PDDL planning solver that parses domain/problem files using unified_planning, invokes pyperplan with optimal search configuration (GBFS + hFF), handles timeouts and fallbacks, and returns a plan object. Also supports direct pyperplan invocation as fallback.

**Responsibility**: Parse PDDL files, configure and invoke planning engines (pyperplan via unified_planning or directly), handle timeout/memout errors, return solution plans

**Key functions**: `solve_pddl_task`, `solve_with_unified_planning`, `solve_with_pyperplan_direct`, `solve_with_fallback_strategies`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pddl-solver/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-pddl-plan-formatter

**Description**: Handles plan output formatting and the end-to-end task orchestration: reads problem.json, calls the solver for each task, formats plans in the correct syntax (parenthesized PDDL or function-call style as required by the validator), and writes output files.

**Responsibility**: Read problem.json, orchestrate solving of all tasks, format plan actions correctly (handling case-sensitivity and syntax requirements), write plan files to specified output paths

**Key functions**: `run_all_tasks`, `write_plan_pddl_format`, `write_plan_custom_format`, `format_action_instance`

**Depends on**: evo-pddl-solver


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pddl-plan-formatter/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
