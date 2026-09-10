# Skill Creation Plan

**Task**: Read an Excel data file and a PDF background file, then compute (Player 1 wins) minus (Player 2 wins) from paired odd/even game rows, and write the numeric answer to a file.

**Rationale**: This task involves three distinct concerns: (1) reading the PDF to understand the data context/column meanings, (2) loading and analyzing the Excel data with correct index-parity logic for paired game comparisons, and (3) writing the result. Since the PDF reading is a simple prerequisite and the core logic is a single analytical pipeline, two skills suffice: one for PDF context extraction and one for the Excel-based match analysis and output.

**Number of skills**: 2

---

## Skill 1: evo-pdf-context-extractor

**Description**: Extracts text content from a PDF file using pypdf 5.x to understand the background context, column definitions, and scoring rules for the data analysis task.

**Responsibility**: Read and parse PDF files, returning extracted text for interpretation of data semantics and question context.

**Key functions**: `extract_pdf_text`, `get_all_pages_text`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-context-extractor/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-excel-match-analyzer

**Description**: Loads an Excel file, splits rows by parity into Player 1 (odd-numbered games) and Player 2 (even-numbered games), pairs them for head-to-head comparison, computes win counts, and writes the final numeric result to a text file.

**Responsibility**: Excel data ingestion, index-parity slicing with correct 0-indexed vs 1-indexed mapping, reset_index alignment for vectorized comparison, win/loss tallying, and strict output formatting.

**Key functions**: `load_excel_data`, `split_by_parity`, `compare_paired_matches`, `compute_win_difference`, `write_answer`

**Depends on**: evo-pdf-context-extractor


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-excel-match-analyzer/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
