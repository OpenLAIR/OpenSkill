# Skill Creation Plan

**Task**: Parse FJSP instance data with downtime/policy constraints, generate an optimized feasible schedule with minimal makespan respecting machine downtimes and policy budgets, and output as JSON and CSV.

**Rationale**: The task naturally separates into three concerns: (1) parsing heterogeneous input formats into unified data structures, (2) core scheduling algorithms with downtime-aware feasibility logic and policy budget enforcement, and (3) validation and output formatting. This decomposition keeps I/O, computation, and verification cleanly separated.

**Number of skills**: 3

---

## Skill 1: evo-fjsp-data-io

**Description**: Parses all input data files (FJSP instance.txt, downtime.csv, policy.json, baseline schedule CSV) into standardized Python data structures, and exports final schedules to JSON and CSV formats.

**Responsibility**: All file I/O: reading instance definitions, downtime windows, policy budgets, baseline schedules; writing solution.json and schedule.csv with proper type handling (numpy int64 serialization).

**Key functions**: `parse_fjsp_instance`, `parse_downtimes_csv`, `parse_policy_budgets`, `parse_baseline_schedule`, `export_solution_json`, `export_solution_csv`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-fjsp-data-io/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-fjsp-scheduler

**Description**: Core scheduling engine implementing downtime-aware earliest-start computation, greedy dispatching, baseline repair with policy budget enforcement, and simulated annealing optimization for FJSP.

**Responsibility**: All scheduling computation: finding earliest feasible start times considering downtimes, greedy constructive heuristics (ECT), constraint-based schedule repair respecting policy budgets, simulated annealing local search optimization, and schedule decoding from OS/MS representations.

**Key functions**: `find_earliest_start`, `greedy_dispatching`, `repair_schedule`, `decode_schedule`, `simulated_annealing_fjsp`, `validate_policy_budgets`

**Depends on**: evo-fjsp-data-io


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-fjsp-scheduler/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-fjsp-validator

**Description**: Validates generated schedules for full FJSP feasibility: operation completeness, precedence constraints, machine eligibility, duration correctness, machine non-overlap, and downtime non-overlap.

**Responsibility**: Post-hoc schedule validation ensuring all hard constraints are satisfied before output. Checks completeness, precedence, machine capacity, duration correctness, downtime compliance, and makespan calculation.

**Key functions**: `validate_schedule`, `check_precedence`, `check_machine_overlaps`, `check_downtime_overlaps`, `check_eligibility_and_duration`, `calculate_makespan`

**Depends on**: evo-fjsp-data-io


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-fjsp-validator/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
