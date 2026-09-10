# Domain Reference for evo-demographic-data-ingestion

**Responsibility**: All data extraction and cleaning from source files (PDF and Excel). Produces clean, merge-ready DataFrames with normalized column names, stripped/uppercased string keys, and properly typed numeric columns.

**Key functions to implement**: extract_population_from_pdf, load_income_from_excel, normalize_merge_keys

---

## Section 1: pdfplumber PDF Table Extraction API (Version 0.11.4)


The `pdfplumber` library, built upon `pdfminer.six`, provides pixel-level control for extracting text, tables, and metadata from digitally generated PDF documents [cite: 1, 2]. Unlike optical character recognition (OCR) tools or heuristic-based parsers, `pdfplumber` utilizes the explicit coordinate geometry of lines and characters embedded within the PDF, making it highly effective for complex, structured layouts [cite: 3, 4].

## Section 2: Excel Data Ingestion using pandas and openpyxl


While `pandas` supports reading legacy `.xls` files via `xlrd`, the `.xlsx` ecosystem relies on the `openpyxl` engine. As of pandas 1.2+, and strictly enforced in modern releases, `xlrd` dropped support for `.xlsx` due to security vulnerabilities, making `engine='openpyxl'` the standard [cite: 10].

## Section 3: Advanced Data Merging and Entity Resolution


Joining regional population data extracted from a PDF with financial data from an Excel workbook is highly susceptible to formatting discrepancies. The relational operation `pd.merge()` requires exact key matches.