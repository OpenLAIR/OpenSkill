# Skill Creation Plan

**Task**: Extract employee table from PDF backup, compare with current Excel file, identify deleted and modified employees, and write a JSON diff report.

**Rationale**: This task involves three distinct concerns: (1) extracting tabular data from a PDF, (2) comparing two DataFrames to find deletions and modifications, and (3) serializing results to JSON with proper type handling. However, since the task is relatively straightforward and the steps are tightly coupled, two skills provide clean separation without over-decomposition: one for data extraction/normalization and one for diffing/reporting.

**Number of skills**: 2

---

## Skill 1: evo-pdf-excel-extraction

**Description**: Extracts tabular data from PDF files using pdfplumber and reads Excel files using pandas/openpyxl, returning normalized pandas DataFrames with proper data types.

**Responsibility**: Handle all data ingestion: PDF table extraction (with multi-page support, header detection, cell cleaning) and Excel file reading. Normalize column names, strip whitespace, preserve string IDs, and coerce numeric columns appropriately.

**Key functions**: `extract_table_from_pdf`, `read_excel_file`, `normalize_dataframe`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-excel-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-dataframe-diff-report

**Description**: Compares two pandas DataFrames (old vs new) by a key column to identify deleted rows and modified fields, then exports results as a properly formatted JSON report with NumPy-safe serialization.

**Responsibility**: Perform outer merge with indicator to detect deletions, iterate matched rows for field-by-field comparison with NaN and float tolerance handling, format output per the required JSON schema, and serialize with custom NumPy encoder.

**Key functions**: `find_deleted_employees`, `find_modified_employees`, `build_diff_report`, `export_diff_to_json`

**Depends on**: evo-pdf-excel-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dataframe-diff-report/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
