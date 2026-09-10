# Domain Reference for evo-spreadsheet-lookup-population

**Responsibility**: Workbook-safe I/O, Excel coordinate/range handling, source-table extraction from the Data sheet, and writing retrieved values or lookup formulas into H12:L17, H19:L24, and H26:L31 only.

**Key functions to implement**: load_workbook_preserve_structure, extract_series_year_lookup, populate_task_lookup_ranges, atomic_save_workbook

---

## Openpyxl 3.1.5 Workbook Input/Output and Sheet Access


The manipulation of Office Open XML (OOXML) files in Python is predominantly achieved using **Openpyxl**, a mature library designed to read and write Excel 2010 `xlsx/xlsm/xltx/xltm` files [cite: 1, 2]. As of version 3.1.5, released on June 28, 2024, the library provides extensive support for interacting with workbook structures, though it demands a precise understanding of its I/O parameters to prevent data corruption or loss of document fidelity [cite: 1, 3].

## Reading Excel Headers and Source Tables Robustly


In automated workflows, source data rarely conforms to strict, immutable coordinates. Task instructions often loosely specify that data resides in a sheet named "Data," but the exact bounding box may shift as rows and columns are added. Robust extraction requires heuristic location of headers and key columns.

## Writing Excel Formulas with Openpyxl


Openpyxl does not compute formulas; it simply stores the formula string into the cell's underlying XML structure. The host application (Excel, LibreOffice) parses and evaluates this string upon opening the file.

## Mapping Between Excel Ranges and Python Structures


Translating human-readable Excel coordinates (e.g., `H12:L17`) into Python integer indices is a fundamental requirement for targeting outputs. Openpyxl provides a dedicated utility module, `openpyxl.utils`, for these conversions [cite: 12, 45, 46].

## Common Pitfalls and Deprecations


A Python skill author must navigate several architectural gotchas within Openpyxl and file system I/O.

1.  **Destructive Saving:** As reiterated, never execute `load_workbook(file, data_only=True)` and subsequently invoke `.save()` on that instance [cite: 8, 9, 10]. It strips the file of formulas.
2.  **Locale Inconsistencies:** Generating formulas utilizing localized function names (e.g., `SOMME` instead of `SUM` in French, or using `;` instead of `,`) will result in `#NAME?` errors. Openpyxl writes directly to OOXML, which requires absolute English adherence [cite: 12, 13].
3.  **Atomic Saving:** Overwriting the original file directly (`wb.save('original.xlsx')`) is risky. If the Python process terminates unexpectedly during the save operation, the OOXML zip archive becomes corrupted. The best practice is to save to a temporary file (`temp.xlsx`), and upon successful completion, utilize `os.replace('temp.xlsx', 'original.xlsx')` to ensure atomic overwriting.
4.  **Implicit Type Casting:** Be cautious with numeric data loaded from Excel that appears as text. An Excel cell formatted as text but containing the characters `123` will be read as a Python string. Subsequent mathematical operations will fail with `TypeError`. Explicit casting (`float(x)`) is mandatory [cite: 44].