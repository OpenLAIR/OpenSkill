# Skill Creation Plan

**Task**: Recover missing '???' values in a multi-sheet NASA budget Excel file by analyzing inter-sheet and intra-sheet mathematical relationships, then save the recovered workbook.

**Rationale**: This task involves two distinct concerns: (1) reading/writing Excel files with openpyxl while handling edge cases like merged cells and data types, and (2) analyzing the specific mathematical relationships in the NASA budget spreadsheet to compute missing values via constraint propagation. Splitting these into two skills keeps I/O concerns separate from domain-specific recovery logic.

**Number of skills**: 2

---

## Skill 1: evo-excel-io

**Description**: Provides utility functions for loading, scanning, and saving Excel workbooks with openpyxl 3.1.5, including handling merged cells, detecting placeholder markers, and preserving formatting when writing numeric values back.

**Responsibility**: All Excel file I/O operations: loading workbooks with correct parameters, scanning all sheets for '???' markers and returning their locations, safely reading cell values (handling MergedCell objects), writing recovered numeric values with correct data types, and saving the output workbook with the AppVersion monkey-patch applied.

**Key functions**: `load_workbook_safe`, `find_missing_cells`, `get_cell_value_safe`, `write_recovered_value`, `save_workbook_safe`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-excel-io/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-nasa-budget-recovery

**Description**: Analyzes the mathematical structure of a NASA budget workbook to recover missing values marked as '???' by detecting row sums, column sums, and cross-sheet aggregation relationships, then iteratively solving via constraint propagation.

**Responsibility**: All domain-specific logic for recovering missing values: detecting sum relationships (row totals, column totals, cross-sheet totals), implementing constraint propagation to iteratively resolve unknowns, handling floating-point precision, inferring correct data types (int vs float), and orchestrating the full recovery pipeline from load to save.

**Key functions**: `detect_sum_relationships`, `detect_cross_sheet_relationships`, `recover_missing_values`, `run_recovery_pipeline`

**Depends on**: evo-excel-io


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-nasa-budget-recovery/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
