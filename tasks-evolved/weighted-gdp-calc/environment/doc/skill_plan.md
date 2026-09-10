# Skill Creation Plan

**Task**: Populate specified Task-sheet ranges from Data using two-key lookups, compute GCC net exports as a share of GDP plus summary stats, and calculate the GCC weighted mean in gdp.xlsx without altering workbook formatting or sheet structure.

**Rationale**: This task is best split into one foundational spreadsheet I/O and lookup skill and one computation/formula-targeting skill. The first isolates safe workbook manipulation and 2D data retrieval, while the second handles the domain math and placement of formulas or computed results in the Task sheet.

**Number of skills**: 2

---

## Skill 1: evo-spreadsheet-lookup-population

**Description**: Safely load and edit the existing workbook, read the Data sheet into a two-dimensional lookup structure keyed by series code and year, and populate the specified Task-sheet yellow ranges while preserving formatting.

**Responsibility**: Workbook-safe I/O, Excel coordinate/range handling, source-table extraction from the Data sheet, and writing retrieved values or lookup formulas into H12:L17, H19:L24, and H26:L31 only.

**Key functions**: `load_workbook_preserve_structure`, `extract_series_year_lookup`, `populate_task_lookup_ranges`, `atomic_save_workbook`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-spreadsheet-lookup-population/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-economic-metrics-weighted-summary

**Description**: Compute net exports as a percentage of GDP for the six GCC countries, generate summary statistics, and calculate the GDP-weighted GCC mean using Excel-compatible logic such as SUMPRODUCT.

**Responsibility**: Economic and statistical calculations only: derive net exports % of GDP in H35:L40, calculate min/max/median/simple mean/25th percentile/75th percentile, and compute the weighted mean for GCC using valid source values and weights.

**Key functions**: `compute_net_exports_pct`, `compute_summary_statistics`, `compute_excel_percentile_inc`, `compute_weighted_mean_sumproduct`

**Depends on**: evo-spreadsheet-lookup-population


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-economic-metrics-weighted-summary/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
