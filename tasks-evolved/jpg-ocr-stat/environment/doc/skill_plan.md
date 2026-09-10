# Skill Creation Plan

**Task**: Extract dates and total amounts from scanned receipt images using OCR and write results to an Excel file

**Rationale**: This task has three distinct concerns: (1) image preprocessing and OCR text extraction, (2) structured data parsing (dates and amounts) from noisy OCR text using keyword matching and regex, and (3) Excel output formatting. However, since the parsing logic is tightly coupled to the OCR output and the Excel writing is straightforward, two skills provide the best balance: one for OCR preprocessing/extraction and one for receipt-specific text parsing with output generation.

**Number of skills**: 2

---

## Skill 1: evo-ocr-preprocess-extract

**Description**: Preprocesses receipt images using Pillow (grayscale, upscaling, contrast enhancement, binarization) and extracts raw text using pytesseract with optimal PSM configuration for receipt layouts. Provides utilities for batch processing image directories.

**Responsibility**: Image loading, preprocessing pipeline (grayscale, resize, contrast, threshold), Tesseract OCR configuration and text extraction, batch file discovery and sorting

**Key functions**: `preprocess_image`, `extract_text_from_image`, `get_sorted_image_files`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-ocr-preprocess-extract/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-receipt-parse-export

**Description**: Parses OCR text from receipts to extract dates and total amounts using keyword-priority matching and regex patterns, then writes structured results to an Excel file. Handles OCR noise, keyword exclusions, multi-line value extraction, and comma-separated amounts.

**Responsibility**: Date extraction with multiple format support and ISO formatting, total amount extraction using prioritized keyword matching with exclusion rules and fallback logic, Excel file creation with openpyxl including proper sheet naming and null handling

**Key functions**: `extract_date`, `extract_total_amount`, `parse_receipt_text`, `write_results_to_excel`

**Depends on**: evo-ocr-preprocess-extract


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-receipt-parse-export/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
