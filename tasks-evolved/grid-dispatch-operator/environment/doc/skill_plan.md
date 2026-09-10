# Skill Creation Plan

**Task**: Solve a DC-OPF with spinning reserve co-optimization from MATPOWER JSON data and produce a structured dispatch report

**Rationale**: The task naturally separates into three concerns: (1) parsing MATPOWER JSON and building network matrices, (2) formulating and solving the DC-OPF with reserves, and (3) post-processing results into the required report format. Separating parsing from optimization allows reuse and clear debugging boundaries.

**Number of skills**: 3

---

## Skill 1: evo-grid-matpower-parser

**Description**: Parses MATPOWER JSON network data into structured Python objects, builds bus/gen/branch/gencost arrays with proper indexing, filters inactive components, constructs the bus susceptance matrix (Bbus), PTDF matrix, and generator-to-bus mapping matrix.

**Responsibility**: All data ingestion from MATPOWER JSON: external-to-internal bus ID mapping, status filtering for generators and branches, susceptance matrix construction, PTDF computation, incidence matrices, and cost coefficient extraction with correct polynomial ordering.

**Key functions**: `load_matpower_json`, `build_bus_index_map`, `filter_active_components`, `build_susceptance_matrix`, `compute_ptdf`, `build_gen_bus_matrix`, `extract_gencost_coefficients`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-grid-matpower-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-grid-dcopf-solver

**Description**: Formulates and solves the DC-OPF with spinning reserve co-optimization as a linear or quadratic program. Supports both scipy.optimize.linprog for linear costs and piecewise-linear approximation of quadratic costs. Handles generator limits, capacity coupling (Pg + Rg <= Pmax), nodal power balance, transmission constraints via PTDF, and system reserve requirements.

**Responsibility**: Mathematical formulation of the optimization problem (objective, constraints), solver invocation, and extraction of optimal decision variables (Pg, Rg, flows). Determines reserve requirement using standard capacity coupling (largest online generator).

**Key functions**: `formulate_dcopf_with_reserves`, `solve_dcopf_linprog`, `solve_dcopf_cvxpy`, `compute_reserve_requirement`, `linearize_quadratic_cost`

**Depends on**: evo-grid-matpower-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-grid-dcopf-solver/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-grid-report-generator

**Description**: Post-processes DC-OPF solution results to compute line loading percentages, identify top-3 most loaded lines, calculate operating margin, aggregate totals, and produce the final report.json in the required schema.

**Responsibility**: All post-optimization computations: line flow calculation from PTDF and optimal injections, loading percentage computation (handling rateA=0), operating margin calculation, total cost/load/generation/reserve aggregation, and JSON report serialization.

**Key functions**: `compute_line_flows`, `compute_line_loading_pct`, `find_top_loaded_lines`, `compute_operating_margin`, `compute_total_cost`, `generate_report_json`

**Depends on**: evo-grid-matpower-parser, evo-grid-dcopf-solver


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-grid-report-generator/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
