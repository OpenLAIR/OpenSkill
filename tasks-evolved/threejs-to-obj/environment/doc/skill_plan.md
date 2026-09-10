# Skill Creation Plan

**Task**: Write a Node.js script to load a Three.js object definition, apply Y-up to Z-up coordinate transformation, and export it as a Wavefront OBJ file for Blender

**Rationale**: This is a focused pipeline task with a single clear workflow: load Three.js scene → apply coordinate transform → export OBJ. All steps are tightly coupled and share the same Three.js/Node.js context, so a single skill covering the entire export pipeline is most appropriate to avoid artificial boundaries.

**Number of skills**: 1

---

## Skill 1: evo-threejs-obj-export

**Description**: Generates a Node.js ES module script that dynamically imports a Three.js object definition file, constructs a scene graph, applies a -90° X-rotation for Y-up to Z-up coordinate conversion (Blender compatibility), forces world matrix updates in the headless environment, serializes the scene to Wavefront OBJ format using OBJExporter, and writes the result to disk.

**Responsibility**: Handle the complete pipeline: dynamic import of the Three.js object.js file, scene graph construction, coordinate system transformation (Y-up → Z-up via -π/2 X-rotation), explicit matrixWorld update, OBJ serialization via OBJExporter, and file I/O to write the .obj output

**Key functions**: `generate_export_script`, `create_obj_export_node_script`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-threejs-obj-export/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
