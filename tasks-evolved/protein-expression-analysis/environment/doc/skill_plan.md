# Skill Creation Plan

**Task**: Populate an Excel workbook with two-way lookups, group statistics, and fold-change calculations on log2-transformed proteomics data while preserving formatting.

**Rationale**: The task is a focused openpyxl workflow on a single file with tightly coupled concerns (formula injection, formatting preservation, and proteomics-specific math). A single cohesive skill avoids artificial boundaries between these interdependent steps.

**Number of skills**: 1

---

## Skill 1: evo-proteomics-excel-formulas

**Description**: Use when populating Excel workbooks for quantitative proteomics tasks: writing INDEX/MATCH lookups, AVERAGE/STDEV.S group statistics, and log2 fold-change formulas while preserving cell formatting via openpyxl 3.1.5.

**Responsibility**: Provide utilities to load/save .xlsx files preserving formulas and formatting, detect group/category cells by fill color, build sample/protein coordinate indices, and emit correctly-formatted Excel formulas (INDEX-MATCH, AVERAGE, _xlfn.STDEV.S, log2FC, 2^FC) for proteomics analysis.

**Key functions**: `load_workbook_preserving`, `save_workbook_safely`, `get_cell_fill_hex`, `build_sample_column_index`, `classify_group_columns`, `build_index_match_formula`, `build_average_formula`, `build_stdev_s_formula`, `build_log2_fold_change_formula`, `build_linear_fold_change_formula`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-proteomics-excel-formulas/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
