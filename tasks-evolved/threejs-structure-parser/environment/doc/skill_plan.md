# Skill Creation Plan

**Task**: Parse a Three.js createScene() file to extract part-level structure, exporting individual meshes per part and merged part assemblies as OBJ files.

**Rationale**: The task is cohesive—parse a Three.js scene in headless Node.js and export OBJs in two structured forms. A single skill covering headless execution, scene traversal, and OBJ export keeps related logic together without artificial separation.

**Number of skills**: 1

---

## Skill 1: evo-threejs-scene-parser

**Description**: Parse a Three.js createScene() file in headless Node.js, identify part-level structure (Groups and standalone Meshes), and export OBJ files for both individual sub-meshes per part and merged part assemblies (links). Use when extracting decomposed 3D object structure from Three.js scene definitions.

**Responsibility**: Headless Three.js execution, scene graph traversal/classification, world-matrix resolution, per-mesh and merged-part OBJ export with the required output directory layout.

**Key functions**: `run_threejs_parser`, `generate_node_harness`, `export_part_meshes_and_links`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-threejs-scene-parser/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
