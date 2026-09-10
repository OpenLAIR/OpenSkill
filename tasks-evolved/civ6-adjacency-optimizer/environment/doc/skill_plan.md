# Skill Creation Plan

**Task**: Parse a .Civ6Map SQLite file, compute hex adjacencies, and optimally place city centers and districts to maximize total adjacency bonuses for Civilization VI scenario 3.

**Rationale**: The task naturally decomposes into three concerns: (1) parsing the binary map format from SQLite, (2) encoding all Civ6 district adjacency rules and computing bonuses, and (3) orchestrating the search/optimization for optimal placements. Separating map I/O from game rules from optimization logic keeps each skill focused and testable.

**Number of skills**: 3

---

## Skill 1: evo-civ6-map-parser

**Description**: Parses .Civ6Map SQLite database files to extract map dimensions, terrain, features, resources, and river edge data into Python data structures. Provides hex coordinate utilities (offset-to-cube conversion, neighbor enumeration) for the odd-r pointy-top hex grid used by Civ6.

**Responsibility**: All SQLite I/O, map data extraction (Plots, PlotRivers, PlotFeatures, PlotResources, MapAttributes), coordinate system math (odd-r offset to cube and back), and neighbor computation. Does NOT compute game rules or adjacency bonuses.

**Key functions**: `parse_civ6map`, `get_map_dimensions`, `offset_to_cube`, `cube_to_offset`, `get_hex_neighbors`, `is_tile_river_adjacent`, `get_tile_terrain`, `get_tile_feature`, `get_tile_resource`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-civ6-map-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-civ6-adjacency-rules

**Description**: Encodes all Civilization VI Gathering Storm district adjacency bonus rules, placement validity checks, population-based district limits, and civilization-specific modifiers. Computes the adjacency bonus for any district placed at any tile given current map state and placed districts.

**Responsibility**: District placement validation (terrain restrictions, distance limits, resource blocking), population-to-district-slot calculation, complete adjacency bonus computation for all district types (Campus, Commercial Hub, Industrial Zone, Holy Site, Theater Square, Harbor, Aqueduct, etc.), civilization-specific overrides (Japan, Germany, Korea, Australia, Brazil, Netherlands, Mali), and minor bonus floor rounding.

**Key functions**: `is_valid_district_placement`, `max_specialty_districts`, `calculate_adjacency_bonus`, `get_available_district_types`, `is_specialty_district`, `apply_civ_modifiers`

**Depends on**: evo-civ6-map-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-civ6-adjacency-rules/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-civ6-placement-optimizer

**Description**: Searches for optimal city center and district placements to maximize total adjacency bonuses given scenario constraints (num_cities, population, civilization). Reads scenario JSON, uses map parser and adjacency rules to evaluate candidates, and writes the solution JSON output.

**Responsibility**: Loading scenario configuration, enumerating candidate city center locations, enumerating valid district placement combinations within city working range (3 tiles), running optimization/search (brute force, greedy, or heuristic) to maximize total adjacency, handling multi-city scenarios, and writing the final output JSON in the required format.

**Key functions**: `load_scenario`, `find_optimal_placements`, `enumerate_city_center_candidates`, `enumerate_district_combinations`, `evaluate_placement`, `write_solution_json`

**Depends on**: evo-civ6-map-parser, evo-civ6-adjacency-rules


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-civ6-placement-optimizer/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
