# Skill Creation Plan

**Task**: Run DC-OPF with reserve co-optimization for base and counterfactual (20% increased line 64→1501 capacity) scenarios, extract LMPs, reserve MCP, binding lines, and produce a comparison report.json

**Rationale**: The task naturally splits into three concerns: (1) parsing MATPOWER JSON data and building network matrices, (2) formulating and solving the DC-OPF with reserve co-optimization and extracting economic signals, and (3) comparing scenarios and formatting the final JSON report. This separation keeps data I/O, optimization logic, and output formatting independent.

**Number of skills**: 3

---

## Skill 1: evo-matpower-parser

**Description**: Parses MATPOWER JSON files into structured Python data: bus, gen, branch, gencost arrays with proper indexing. Builds bus mapping dictionaries (ext2int, int2ext), computes network matrices (incidence matrix A, branch susceptance Bbranch, nodal susceptance Bbus, PTDF), and provides utilities for modifying branch parameters (e.g., increasing thermal limits).

**Responsibility**: All data ingestion from MATPOWER JSON, bus index mapping, network matrix construction (A, Bbranch, Bbus, PTDF), branch modification utilities, and generator cost parsing (polynomial and piecewise linear).

**Key functions**: `load_matpower_json`, `create_bus_mappings`, `parse_generators`, `parse_branches`, `parse_gencost`, `compute_network_matrices`, `modify_branch_rate`, `find_slack_bus`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-matpower-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-dcopf-solver

**Description**: Formulates and solves DC-OPF with spinning reserve co-optimization using Python optimization libraries (PuLP, CVXPY, or Pyomo). Extracts LMPs from nodal power balance dual variables, reserve MCP from system reserve constraint dual, generator dispatch, and identifies binding transmission lines (>=99% loading).

**Responsibility**: Optimization model construction (objective, constraints: power balance, thermal limits, capacity coupling, reserve requirement), solving, dual variable extraction for LMPs and reserve MCP, and identifying binding lines.

**Key functions**: `solve_dcopf_with_reserves`, `extract_lmps`, `extract_reserve_mcp`, `identify_binding_lines`, `compute_total_cost`

**Depends on**: evo-matpower-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dcopf-solver/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-market-report

**Description**: Compares base case and counterfactual DC-OPF results, computes impact analysis metrics (cost reduction, top 3 buses with largest LMP drop, congestion relief flag), and formats everything into the required report.json structure with proper rounding and JSON serialization.

**Responsibility**: Scenario comparison logic, impact analysis computation, JSON report assembly and serialization with correct field names, types, and structure.

**Key functions**: `compute_impact_analysis`, `find_top_lmp_drops`, `check_congestion_relieved`, `build_report_json`, `export_report`

**Depends on**: evo-dcopf-solver


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-market-report/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
