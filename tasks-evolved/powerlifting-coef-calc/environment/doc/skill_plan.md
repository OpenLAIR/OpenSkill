# Skill Creation Plan

**Task**: Calculate DOTS powerlifting scores by copying relevant columns from 'Data' to 'Dots' sheet, then appending TotalKg and Dots columns with Excel formulas in /root/data/openipf.xlsx

**Rationale**: This task has two distinct concerns: (1) understanding the data schema and identifying/copying the right columns, and (2) implementing the DOTS formula logic as Excel formulas. However, since both are tightly coupled in a single openpyxl workflow and the task is straightforward, two skills suffice: one for the domain knowledge (DOTS formula, coefficients, edge cases) and one for the openpyxl Excel manipulation pattern.

**Number of skills**: 2

---

## Skill 1: evo-powerlifting-dots-formula

**Description**: Provides the exact DOTS scoring formula, sex-specific polynomial coefficients, TotalKg computation rules, edge case handling (negative values, Mx category), and the corresponding Excel formula strings for both TotalKg and DOTS columns.

**Responsibility**: Domain knowledge: DOTS formula definition, male/female coefficients, valid input handling (negative best lifts, blank values, Mx sex category mapping to male coefficients), required columns from OpenPowerlifting schema (Name, Sex, BodyweightKg, Best3SquatKg, Best3BenchKg, Best3DeadliftKg), and precision requirements (3 decimal places).

**Key functions**: `get_dots_coefficients`, `build_totalkg_excel_formula`, `build_dots_excel_formula`, `get_required_columns`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-powerlifting-dots-formula/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-openpyxl-sheet-processor

**Description**: Provides utilities for loading an Excel workbook with openpyxl, copying selected columns from a source sheet to a destination sheet preserving order and headers, appending formula columns, and saving the workbook. Handles the specific workflow of reading from 'Data' sheet and writing to 'Dots' sheet.

**Responsibility**: Excel I/O operations: loading workbook, mapping source column headers to indices, copying column data row-by-row to destination sheet, writing Excel formula strings into new columns, and saving the modified workbook. Handles openpyxl 3.1.5 specifics.

**Key functions**: `load_workbook_safe`, `find_column_indices`, `copy_columns_to_sheet`, `append_formula_column`, `save_workbook`

**Depends on**: evo-powerlifting-dots-formula


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-openpyxl-sheet-processor/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
