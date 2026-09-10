# Skill Creation Plan

**Task**: Parse a PowerModels JSON network file, solve AC Optimal Power Flow using Pyomo+IPOPT, and produce a structured JSON report with generation dispatch, voltage profile, branch loading, and feasibility checks.

**Rationale**: The task naturally decomposes into three concerns: (1) parsing and preparing network data from the JSON format into solver-ready structures, (2) building and solving the ACOPF mathematical model with Pyomo/IPOPT, and (3) extracting results and producing the structured report. Separating parsing from solving allows reuse and easier debugging, while report generation has distinct formatting logic.

**Number of skills**: 3

---

## Skill 1: evo-acopf-network-parser

**Description**: Parses PowerModels.jl/Matpower-style network.json files into Python data structures suitable for ACOPF formulation. Handles per-unit conventions, Pi-section branch model computation, transformer tap/shift parameters, generator cost coefficients, load/shunt aggregation by bus, and bus-type identification (reference buses).

**Responsibility**: All data ingestion, validation, and transformation from network.json into clean dictionaries/structures for the optimization model. No optimization logic.

**Key functions**: `parse_network_json`, `compute_branch_pi_params`, `aggregate_loads_by_bus`, `aggregate_shunts_by_bus`, `map_generators_to_buses`, `identify_reference_buses`, `get_branch_bus_mappings`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-acopf-network-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-acopf-solver

**Description**: Builds and solves the full AC Optimal Power Flow problem using Pyomo and IPOPT. Implements polar-coordinate formulation with branch power flow expressions, nodal power balance, thermal limits, angle difference constraints, reference bus constraints, and quadratic generation cost objective. Handles solver installation via idaes-pse.

**Responsibility**: Constructing the Pyomo ConcreteModel with all ACOPF variables, constraints, expressions, and objective; configuring and invoking IPOPT; returning the solved model and solver results. No data parsing or report formatting.

**Key functions**: `install_solver`, `build_acopf_model`, `solve_acopf`, `build_and_solve_acopf`

**Depends on**: evo-acopf-network-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-acopf-solver/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-acopf-report-generator

**Description**: Extracts solution values from a solved Pyomo ACOPF model, computes derived quantities (losses, branch loading percentages, power mismatches, voltage violations), and writes the structured report.json file matching the required ISO operator format with proper unit conversions from per-unit to MW/MVAr/degrees.

**Responsibility**: All post-solve extraction, unit conversion (per-unit to physical), feasibility checking, most-loaded-branch identification, summary statistics computation, and JSON report file generation.

**Key functions**: `extract_generator_results`, `extract_bus_results`, `compute_branch_flows_and_loading`, `compute_feasibility_check`, `compute_summary_statistics`, `generate_report_json`

**Depends on**: evo-acopf-solver


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-acopf-report-generator/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
