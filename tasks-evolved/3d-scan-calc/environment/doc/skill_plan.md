# Skill Creation Plan

**Task**: Parse a binary STL file with Material IDs in attribute bytes, find the largest connected component, look up material density, compute volume and mass, and output results as JSON.

**Rationale**: This task involves three distinct concerns: (1) binary STL parsing with Material ID extraction, (2) mesh topology analysis for connected component filtering, and (3) volume computation with unit conversion and mass calculation. Combining topology and volume into one geometric analysis skill keeps the count manageable while maintaining clear boundaries.

**Number of skills**: 3

---

## Skill 1: evo-stl-binary-parser

**Description**: Parses binary STL files using Python's struct module, extracting triangle vertices, normals, and the 2-byte attribute byte count (used as Material ID). Provides filtering by Material ID.

**Responsibility**: Read binary STL file layout (80-byte header, 4-byte count, 50-byte facet records), unpack all triangle data, and expose vertices and material IDs as structured data. Also parse the material density markdown table.

**Key functions**: `parse_binary_stl`, `parse_material_density_table`, `filter_facets_by_material_id`, `detect_material_id`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-stl-binary-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-mesh-geometry-analysis

**Description**: Performs connected component analysis on triangle meshes using Union-Find and computes mesh volume via the signed tetrahedron method (Divergence Theorem). Handles unit conversion and mass calculation.

**Responsibility**: Identify the largest connected component of triangles via vertex adjacency (Union-Find with coordinate snapping), compute closed mesh volume using the scalar triple product formula, convert units from mm³ to cm³, and calculate mass given density.

**Key functions**: `get_largest_connected_component`, `compute_mesh_volume`, `convert_volume_mm3_to_cm3`, `calculate_mass`

**Depends on**: evo-stl-binary-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-mesh-geometry-analysis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-mass-report-output

**Description**: Orchestrates the full pipeline: parses STL, determines material, filters debris, computes mass, and writes the JSON report in the required format.

**Responsibility**: Coordinate the end-to-end workflow: invoke STL parsing, determine the dominant Material ID, filter by material, find largest connected component, compute volume and mass, round results, and serialize to /root/mass_report.json with the exact required schema.

**Key functions**: `run_mass_calculation_pipeline`, `write_mass_report_json`

**Depends on**: evo-stl-binary-parser, evo-mesh-geometry-analysis


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-mass-report-output/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
