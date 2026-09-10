# Domain Reference for evo-excel-data-extraction

**Responsibility**: Reading and parsing source Excel files (IMF commodity prices and template workbook), handling merged cells, identifying header rows, extracting gold price time series, country reserve data, and understanding the template structure (row/column layout of Answer sheet, Value sheet, Volume sheet, Total Reserves sheet).

**Key functions to implement**: explore_sheet_structure, extract_gold_price_series, extract_country_reserve_data, get_merged_cell_value, find_header_row

---

## 2. Initial Data Exploration with Pandas


Before manipulating an unfamiliar Excel file with `openpyxl`, it is highly recommended to inspect its structure. Financial reports, such as IMF commodity price datasets, rarely start neatly at cell A1. They often contain metadata, merged headers, or blank rows at the top of the file [cite: 7].

### 2.1 Using `pandas.read_excel()` for Structural Discovery

The `pandas.read_excel()` function provides powerful parameters to bypass irregular formatting and isolate the target data [cite: 3]. The underlying engine used for modern `.xlsx` files is `openpyxl`, whereas the older `xlrd` engine is restricted to legacy `.xls` formats [cite: 4]. 

To locate specific data (e.g., "Gold" prices) within an unfamiliar file, you can utilize parameters like `skiprows`, `usecols`, and `header`:

```python
import pandas as pd
from pathlib import Path

### 2.2 Advanced Parsing Arguments

*   **`skiprows`**: Accepts an integer (number of lines to skip), a list of specific 0-indexed row numbers to skip (e.g., `[cite: 1]`), or a callable lambda function (e.g., `lambda x: x in [cite: 1]`) [cite: 4, 8].
*   **`usecols`**: Accepts a string of Excel column letters (e.g., `"B:F"`), a list of integers, or a list of column names [cite: 7].
*   **`true_values` / `false_values`**: Can be used to map specific strings to boolean values during import [cite: 4, 9].
*   **`thousands`**: Setting `thousands=','` ensures that financial figures containing commas are correctly parsed as floats rather than strings [cite: 9].

## 3. Reading IMF Commodity Data with openpyxl


While `pandas` is excellent for ingestion, it destroys formulas and formatting when writing back to Excel. To perform surgical extractions and insertions, `openpyxl` must be used [cite: 5, 10].

### 3.1 Loading the Workbook

The `load_workbook()` function is the entry point. A critical parameter here is `data_only`. 
*   `data_only=False` (default): Returns the actual formula string (e.g., `=SUM(A1:A2)`) [cite: 11, 12].
*   `data_only=True`: Returns the *cached value* of the formula from the last time Excel or LibreOffice evaluated and saved the sheet [cite: 13, 14]. 

```python
import openpyxl

### 3.2 Iterating Through Rows and Handling Merged Cells

When reading structured data, you can iterate through a designated range using `ws.iter_rows()`. This is significantly more memory-efficient than calling `ws.rows` on a massive sheet, as accessing unpopulated cells dynamically creates them in memory, potentially bloating the application footprint [cite: 15].

Merged cells pose a unique problem: only the top-left cell of a merged range contains the value; all other cells in the range return `None` [cite: 6]. To extract data from merged cells reliably, you must check if a cell's coordinates fall within any merged range boundaries [cite: 16].

```python
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string

def get_real_value(sheet, cell):
    """
    Returns the value of a cell. If the cell is part of a merged range,
    it returns the value of the top-left cell of that range. [cite: 16]
    """
    if cell.value is not None:
        return cell.value
        
    for merged_range in sheet.merged_cells.ranges:
        if cell.coordinate in merged_range:
            # Get the top-left cell of the merged range
            top_left_coord = merged_range.start_cell.coordinate
            return sheet[top_left_coord].value
            
    return None

### 3.3 Handling Date-Formatted Cells

`openpyxl` automatically detects cells formatted as dates in Excel and converts them to Python `datetime` objects [cite: 5]. If you are writing dates back into Excel, you can simply assign a Python `datetime.date` or `datetime.datetime` object to `cell.value`, and `openpyxl` will apply the default date formatting. You can also explicitly set the number format:

```python
import datetime

date_cell = ws['B1']
date_cell.value = datetime.datetime(2025, 1, 1)
date_cell.number_format = 'YYYY-MM-DD' # Enforce specific date formatting [cite: 5]
```

## 9. openpyxl Pitfalls and Edge Cases


When deploying this architecture in production, several edge cases must be navigated carefully.

### 9.1 The `data_only` Dilemma

As discussed, the `data_only` parameter is mutually exclusive per load [cite: 11, 12]. 
*   If you load with `data_only=False`, modify a cell, and save, the formulas are preserved, but newly triggered formula results are not computed.
*   If you load with `data_only=True` and save, **all formulas in the workbook are permanently destroyed** and replaced by their hardcoded cached values [cite: 11]. 

**Best Practice:** Never call `.save()` on a workbook that was loaded with `data_only=True` unless your explicit goal is to "flatten" the workbook and remove all formulas. Always maintain two separate `load_workbook` instances in memory if you need to read values and write formulas simultaneously [cite: 11].

### 9.2 Version-Specific Issues

In `openpyxl` versions around 3.1.x, developers must ensure they manage memory correctly. Accessing `ws.iter_cols()` or `ws.iter_rows()` without bounds (e.g., iterating entirely through `ws.rows`) on sparsely populated sheets can cause openpyxl to instantiate millions of empty `Cell` objects in memory, leading to out-of-memory crashes [cite: 15]. Always use `min_row`, `max_row`, `min_col`, and `max_col` limits.

### 9.3 Preserving Existing Sheets and Formats

When `openpyxl` saves a workbook, it generally preserves existing sheets, background colors, borders, and fonts. However, it does not copy charts or images when using `wb.copy_worksheet()` [cite: 15]. To avoid corrupting external links, ensure `keep_links=True` is maintained during loading [cite: 12].