# Skill Creation Plan

**Task**: Detect BGP route oscillation and valley-free route leaks in an Azure Virtual WAN topology, then evaluate which proposed solutions resolve each issue.

**Rationale**: The task has three distinct functional concerns: (1) loading/parsing BGP topology data with proper type handling, (2) detecting oscillation cycles and route leak violations using graph/policy algorithms, and (3) evaluating natural-language solution descriptions against resolution criteria. These map cleanly to 3 skills with clear boundaries.

**Number of skills**: 3

---

## Skill 1: evo-bgp-data-loader

**Description**: Loads and normalizes BGP topology JSON files from /app/data/, handling the critical Python JSON integer-key coercion pitfall. Provides robust file I/O with encoding and error handling.

**Responsibility**: Load all input JSON files (route.json, preferences.json, local_pref.json, relationships.json, topology.json, route_events.json, possible_solutions.json) and normalize data types, especially converting string dictionary keys back to integers for ASN lookups.

**Key functions**: `load_json_with_int_keys`, `load_json_list`, `load_all_bgp_data`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-bgp-data-loader/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-bgp-anomaly-detection

**Description**: Detects BGP route oscillation via preference cycle detection in directed graphs and identifies route leaks by evaluating valley-free routing constraints against route events.

**Responsibility**: Implement DFS-based cycle detection on the routing preference graph to find oscillation cycles, and apply Gao-Rexford valley-free rules to route events to classify route leaks. Produces deterministically ordered cycle lists and standardized leak report objects.

**Key functions**: `detect_preference_cycle`, `check_route_leak`, `detect_route_leaks`

**Depends on**: evo-bgp-data-loader


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-bgp-anomaly-detection/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-bgp-solution-evaluator

**Description**: Evaluates natural-language solution descriptions to determine if each resolves BGP oscillation and/or route leaks, then assembles and writes the final structured JSON report.

**Responsibility**: Use regex pattern matching to classify each proposed solution as resolving oscillation (breaks preference cycle or disables peering link), resolving route leaks (enforces export/ingress filtering, community tagging, routing intent, or disables peering), or neither. Assemble the complete oscillation_report.json output with all required fields.

**Key functions**: `evaluate_solution`, `evaluate_all_solutions`, `generate_oscillation_report`, `save_report`

**Depends on**: evo-bgp-data-loader, evo-bgp-anomaly-detection


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-bgp-solution-evaluator/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
