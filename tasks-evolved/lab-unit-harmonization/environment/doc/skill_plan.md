# Skill Creation Plan

**Task**: Harmonize clinical lab data from multiple healthcare systems by cleaning data formats, detecting mixed units via physiological range boundaries, converting to US conventional units, and outputting clean CSV

**Rationale**: This task has three distinct concerns: (1) data cleaning/parsing of structural issues like commas, scientific notation, and missing values, (2) domain-specific unit detection and conversion requiring clinical knowledge of analyte ranges and conversion factors, and (3) the orchestration of applying these to the actual dataset. Skills 1 and 2 separate the generic data cleaning from the clinical domain logic.

**Number of skills**: 2

---

## Skill 1: evo-clinical-data-cleaning

**Description**: Utility functions for cleaning raw clinical lab CSV data: handling decimal comma formats, scientific notation normalization, missing value detection, and numeric coercion of mixed-type columns.

**Responsibility**: Parse and clean structural data quality issues (decimal commas, scientific notation, mixed dtypes, missing values) without any domain-specific clinical knowledge. Provides reusable functions for loading, coercing, and preparing numeric data.

**Key functions**: `load_clinical_csv`, `replace_decimal_commas`, `coerce_to_numeric`, `drop_incomplete_rows`, `format_output_csv`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-clinical-data-cleaning/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-clinical-unit-harmonization

**Description**: Domain-specific clinical lab unit detection and conversion module. Contains conversion factor registry, physiological range boundaries for each analyte, and boundary-based auto-detection logic to identify and convert SI units to US conventional units.

**Responsibility**: Define analyte-specific conversion factors, physiological range thresholds for US and SI units, implement boundary-based auto-detection algorithm, and provide per-analyte harmonization functions that convert values outside expected US ranges using appropriate conversion factors.

**Key functions**: `get_analyte_config`, `detect_and_convert_value`, `harmonize_column`, `build_conversion_registry`, `harmonize_all_features`

**Depends on**: evo-clinical-data-cleaning


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-clinical-unit-harmonization/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
