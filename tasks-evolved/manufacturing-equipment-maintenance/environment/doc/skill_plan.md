# Skill Creation Plan

**Task**: Extract reflow soldering parameters from a PDF handbook and CSV data files, compute thermal profile metrics (ramp rate, TAL, peak temp, conveyor speed), and select best runs per board family, outputting structured JSON results.

**Rationale**: The task divides naturally into three concerns: (1) extracting domain parameters from the PDF handbook, (2) processing thermocouple/MES/defect CSV data to compute thermal metrics and compliance checks, and (3) formatting and serializing results to JSON. The handbook extraction is foundational since all thresholds come from it; the thermal analysis is the core computation; and the JSON output formatting handles serialization pitfalls.

**Number of skills**: 3

---

## Skill 1: evo-reflow-handbook-parser

**Description**: Extracts critical reflow soldering process parameters from the PDF handbook, including preheat temperature range, ramp rate limits, liquidus temperature, TAL window, peak temperature requirements, conveyor speed formulas, and board geometry specifications. Uses standard library PDF parsing (zlib/re) or subprocess-based pdftotext as available.

**Responsibility**: Parse the handbook PDF and return structured dictionaries of all process thresholds, formulas, and compliance limits needed by downstream analysis. No CSV processing or computation.

**Key functions**: `extract_pdf_text`, `parse_preheat_params`, `parse_tal_params`, `parse_peak_temp_params`, `parse_conveyor_speed_params`, `get_all_handbook_params`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-reflow-handbook-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-reflow-thermal-analysis

**Description**: Processes thermocouple CSV data, MES logs, and test defect data to compute preheat ramp rates, time above liquidus (TAL), peak temperatures, conveyor speed compliance, and best-run selection per board family. Uses handbook parameters as inputs for threshold-based compliance checks.

**Responsibility**: All CSV data loading, merging, time-series computation (ramp rates, TAL, peak temps), conveyor speed feasibility checks, and multi-criteria best-run selection logic. Produces Python dicts/DataFrames ready for serialization.

**Key functions**: `load_thermocouple_data`, `load_mes_log`, `load_test_defects`, `calculate_ramp_rates`, `get_max_preheat_ramp_by_run`, `calculate_tal_by_run`, `extract_peak_temperatures`, `select_representative_thermocouple`, `check_conveyor_speed_compliance`, `find_best_run_per_board_family`

**Depends on**: evo-reflow-handbook-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-reflow-thermal-analysis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-reflow-json-output

**Description**: Formats and serializes computed analysis results into the exact JSON structures required for each question output (q01.json through q05.json), handling numpy/pandas type coercion, NaN-to-null conversion, rounding, and sorting.

**Responsibility**: All JSON serialization, type-safe encoding of numpy/pandas types, rounding to 2 decimals, sorting by run_id/board_family/board_id, null handling, and file writing to /app/output/.

**Key functions**: `build_q01_output`, `build_q02_output`, `build_q03_output`, `build_q04_output`, `build_q05_output`, `safe_json_dump`, `numpy_pandas_encoder`

**Depends on**: evo-reflow-thermal-analysis


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-reflow-json-output/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
