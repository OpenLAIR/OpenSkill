# Skill Creation Plan

**Task**: Implement a dialogue script parser that converts a structured text file into a validated JSON graph and Graphviz DOT visualization

**Rationale**: The task has three clear functional domains: (1) parsing text into a graph data structure, (2) validating graph constraints and serializing to JSON, and (3) generating DOT visualization. However, these are tightly coupled and the research document provides a near-complete implementation, so two skills suffice: one for parsing/validation/serialization (the core logic) and one for DOT visualization generation.

**Number of skills**: 2

---

## Skill 1: evo-dialogue-parser

**Description**: Parses structured dialogue script text into a graph with nodes and edges, validates graph constraints (reachability, edge target existence), and serializes to JSON. Handles node type detection (line vs choice), implicit terminal node synthesis, tag extraction from choices, and BFS reachability validation.

**Responsibility**: Text parsing via regex, graph data structure construction, node type classification, implicit node generation, graph validation (BFS reachability, edge target existence), and JSON serialization

**Key functions**: `parse_script`, `validate_graph`, `save_json`, `synthesize_implicit_nodes`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dialogue-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-dialogue-dotgen

**Description**: Generates Graphviz DOT visualization files from the parsed dialogue graph structure using the graphviz 0.20.3 Python API. Handles label escaping, node shape styling by type, and edge label formatting including tags.

**Responsibility**: DOT file generation using graphviz Python API, label escaping with graphviz.escape(), visual styling of nodes and edges, and saving DOT source files without rendering

**Key functions**: `generate_dot`, `escape_label`, `style_node`

**Depends on**: evo-dialogue-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dialogue-dotgen/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
