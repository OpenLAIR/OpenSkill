# Domain Reference for evo-excel-io

**Responsibility**: All Excel file I/O operations: loading workbooks with correct parameters, scanning all sheets for '???' markers and returning their locations, safely reading cell values (handling MergedCell objects), writing recovered numeric values with correct data types, and saving the output workbook with the AppVersion monkey-patch applied.

**Key functions to implement**: load_workbook_safe, find_missing_cells, get_cell_value_safe, write_recovered_value, save_workbook_safe

---

## 1. The openpyxl API for Multi-Sheet Excel Reading and Writing


The `openpyxl` library is the de facto standard in the Python ecosystem for interacting with Excel `.xlsx` files without requiring a native Microsoft Excel installation. To build a reliable data recovery tool, one must master the intricacies of file loading, workbook traversal, data typing, and file serialization.

## 2. Detecting and Locating "???" Placeholder Cells


The first functional requirement of the utility module is to scan the entire workbook for cells explicitly containing the string "???". Because real-world spreadsheets often mix strings, numbers, and dates, string operations must be protected with type checking.

## 5. openpyxl Pitfalls and Edge Cases


Building robust utilities in `openpyxl` requires navigating several idiosyncratic behaviors of the library and the OOXML specification.