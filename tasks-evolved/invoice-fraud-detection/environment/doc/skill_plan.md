# Skill Creation Plan

**Task**: Extract invoice data from PDF, cross-reference against vendor and PO databases, detect fraud based on 5 priority-ordered criteria, and output flagged invoices as JSON.

**Rationale**: The task has three distinct functional domains: (1) PDF text extraction and field parsing, (2) reference data ingestion from Excel/CSV, and (3) cross-reference fraud detection logic with fuzzy matching. Combining extraction and parsing into one skill, data loading into another, and the fraud detection pipeline into a third keeps responsibilities cleanly separated while maintaining manageable complexity.

**Number of skills**: 3

---

## Skill 1: evo-pdf-invoice-parser

**Description**: Extracts text from each page of a PDF invoice file using pdfplumber and parses structured fields (vendor name, IBAN, PO number, invoice amount) using regular expressions. Handles whitespace normalization, locale-specific amount formats, and spaced IBANs.

**Responsibility**: PDF text extraction and regex-based field parsing for invoice data. Returns a list of parsed invoice records with page numbers.

**Key functions**: `extract_all_invoices`, `extract_invoice_fields_from_text`, `extract_iban`, `extract_invoice_amount`, `extract_po_number`, `extract_vendor_name`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-invoice-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-reference-data-loader

**Description**: Loads and normalizes vendor master data from Excel (.xlsx) and purchase order data from CSV. Handles dtype management, whitespace stripping, and creates lookup dictionaries for downstream cross-referencing.

**Responsibility**: Ingesting, cleaning, and structuring reference data from vendors.xlsx and purchase_orders.csv into Python dictionaries suitable for lookup operations.

**Key functions**: `load_vendor_database`, `load_po_database`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-reference-data-loader/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-invoice-fraud-detector

**Description**: Implements the full fraud detection pipeline: fuzzy-matches vendor names against the vendor database using rapidfuzz, then applies the 5 priority-ordered fraud checks (Unknown Vendor, IBAN Mismatch, Invalid PO, Amount Mismatch, Vendor Mismatch). Outputs flagged invoices as a JSON report.

**Responsibility**: Fuzzy vendor matching, priority-ordered fraud rule evaluation, and JSON report generation. Orchestrates parsed invoice data against reference data to produce the final fraud_report.json.

**Key functions**: `find_vendor_match`, `check_invoice_fraud`, `run_fraud_detection_pipeline`, `save_fraud_report`

**Depends on**: evo-pdf-invoice-parser, evo-reference-data-loader


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-invoice-fraud-detector/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
