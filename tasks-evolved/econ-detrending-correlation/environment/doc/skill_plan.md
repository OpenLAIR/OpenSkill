# Skill Creation Plan

**Task**: Calculate Pearson correlation between HP-filtered cyclical components of real PCE and real PFI (1973-2024) using ERP tables and CPI data.

**Rationale**: The task is a single end-to-end pipeline with tightly coupled steps (parse, deflate, filter, correlate). Splitting into more than 2 skills would create artificial boundaries. Two skills cleanly separate data ingestion/cleaning from the econometric analysis pipeline.

**Number of skills**: 2

---

## Skill 1: evo-macro-data-ingestion

**Description**: Parses ERP .xls tables and FRED CPI .xlsx files, handles multi-row headers, extracts annual totals, computes partial-year averages from quarterly data, and produces clean annual CPI series.

**Responsibility**: All data reading, parsing, cleaning, and temporal aggregation from raw Excel files into clean pandas Series indexed by integer year.

**Key functions**: `parse_erp_annual_total`, `compute_partial_year_average`, `process_cpi_annual`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-data-ingestion/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-macro-cycle-correlation

**Description**: Deflates nominal series to real values using CPI, applies log transformation and Hodrick-Prescott filter to extract cyclical components, and computes Pearson correlation between two cyclical series.

**Responsibility**: Deflation, log-transformation, HP filtering with lambda=100, temporal alignment (1973-2024), Pearson correlation computation, and formatted output.

**Key functions**: `deflate_nominal_to_real`, `extract_hp_cycle`, `compute_cycle_pearson_correlation`, `run_full_pipeline`

**Depends on**: evo-macro-data-ingestion


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-cycle-correlation/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
