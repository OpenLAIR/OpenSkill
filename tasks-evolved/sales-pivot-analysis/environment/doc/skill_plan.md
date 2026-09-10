# Skill Creation Plan

**Task**: Extract population data from PDF and income data from Excel, merge them, compute quartiles and derived columns, then produce a multi-sheet Excel report with four pivot tables and a source data sheet.

**Rationale**: The task has three distinct concerns: (1) data ingestion from heterogeneous sources (PDF + Excel), (2) data transformation including merging, quartile computation, and pivot table generation, and (3) multi-sheet Excel export with proper formatting. Separating ingestion from transformation/export keeps each skill focused and reusable.

**Number of skills**: 2

---

## Skill 1: evo-demographic-data-ingestion

**Description**: Extracts and cleans tabular data from PDF files using pdfplumber and from Excel files using pandas/openpyxl. Handles multi-page PDF table stitching, header deduplication, numeric parsing (comma removal, type casting), and string normalization for merge keys.

**Responsibility**: All data extraction and cleaning from source files (PDF and Excel). Produces clean, merge-ready DataFrames with normalized column names, stripped/uppercased string keys, and properly typed numeric columns.

**Key functions**: `extract_population_from_pdf`, `load_income_from_excel`, `normalize_merge_keys`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-demographic-data-ingestion/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-demographic-analysis-reporting

**Description**: Merges population and income DataFrames, computes quartile assignments via pd.qcut with rank-based tie handling, generates derived columns (Total = EARNERS × MEDIAN_INCOME), creates all four pivot tables (Population by State, Earners by State, Regions by State, State Income Quartile), and exports everything to a multi-sheet Excel workbook with proper formatting.

**Responsibility**: All data merging, transformation (quartile assignment, derived columns), pivot table generation, and multi-sheet Excel output. Handles sheet ordering, index management for pivots, and column width auto-fitting.

**Key functions**: `merge_population_income`, `assign_income_quartiles`, `compute_derived_columns`, `generate_pivot_population_by_state`, `generate_pivot_earners_by_state`, `generate_pivot_regions_by_state`, `generate_pivot_state_income_quartile`, `export_demographic_report`

**Depends on**: evo-demographic-data-ingestion


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-demographic-analysis-reporting/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
