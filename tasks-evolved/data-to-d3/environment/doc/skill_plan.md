# Skill Creation Plan

**Task**: Build a single-page D3.js v6 web app with a force-simulation bubble chart (sector-clustered, market-cap-sized) and an interactive data table, connected via click highlighting, using Python to generate all output files.

**Rationale**: The task has two distinct concerns: (1) Python-side orchestration to set up the output directory, copy data, fetch D3.js, and generate the HTML/CSS/JS files, and (2) the actual D3.js visualization logic (force simulation, bubble chart, table, interactions). Splitting these keeps file-generation logic separate from the complex visualization code, making each skill focused and reusable.

**Number of skills**: 2

---

## Skill 1: evo-web-scaffold-generator

**Description**: Python utility that creates the output directory structure, copies input data, downloads d3.v6.min.js locally, and writes the index.html and style.css files for the stock visualization dashboard.

**Responsibility**: Directory setup, data copying, D3.js library fetching, HTML boilerplate generation, and CSS stylesheet creation. Does NOT contain visualization logic.

**Key functions**: `setup_output_directory`, `copy_input_data`, `download_d3_library`, `generate_index_html`, `generate_style_css`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-web-scaffold-generator/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-d3v6-stock-visualization

**Description**: Generates the complete visualization.js file implementing a D3.js v6 force-simulation bubble chart with sector clustering, an interactive data table, tooltips, legends, and bidirectional click-based highlighting between chart and table.

**Responsibility**: All D3.js v6 client-side visualization logic: CSV loading/parsing, force simulation setup (forceX/forceY/forceCollide), scaleSqrt for bubble sizing, ordinal color scale for sectors, legend rendering, tooltip with v6 event handling, HTML table generation with formatted market cap, and bidirectional click interaction with scroll-into-view.

**Key functions**: `generate_visualization_js`, `build_force_simulation_code`, `build_bubble_chart_code`, `build_data_table_code`, `build_interaction_code`

**Depends on**: evo-web-scaffold-generator


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-d3v6-stock-visualization/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
