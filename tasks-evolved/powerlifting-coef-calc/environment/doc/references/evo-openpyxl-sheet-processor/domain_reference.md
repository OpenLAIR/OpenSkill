# Domain Reference for evo-openpyxl-sheet-processor

**Responsibility**: Excel I/O operations: loading workbook, mapping source column headers to indices, copying column data row-by-row to destination sheet, writing Excel formula strings into new columns, and saving the modified workbook. Handles openpyxl 3.1.5 specifics.

**Key functions to implement**: load_workbook_safe, find_column_indices, copy_columns_to_sheet, append_formula_column, save_workbook

---

## 4. Programmatic Data Processing Using Python's `openpyxl`


When dealing with datasets featuring tens of thousands of powerlifting meets, manual Excel input becomes impossible. The Python library `openpyxl` is the industry standard for programmatically interacting with `.xlsx` workbooks [cite: 16]. 

Below is a complete, executable Python script establishing several vital workflows:
1. Loading an Excel workbook with multiple sheets.
2. Copying specific columns from one sheet to a new layout while preserving order.
3. Programmatically writing the Excel `TotalKg` and `DOTS` formulas as strings.
4. Saving the workbook while retaining all sheets intact.

### 4.1 Working Python Implementation


```python
import os
from openpyxl import load_workbook, Workbook

def process_powerlifting_data(input_file, output_file):
    # Workflow 1: Load the workbook
    # Note: We do not use data_only=True here because we want to preserve 
    # any existing formulas on the sheet if we modify them.
    wb = load_workbook(input_file)
    
    # Assume the raw data is on a sheet named 'RawData'
    if 'RawData' not in wb.sheetnames:
        raise ValueError("The workbook must contain a sheet named 'RawData'")
    
    source_sheet = wb['RawData']
    
    # Create a new sheet to hold the copied columns and new computed formulas
    # Existing empty sheets are preserved by default in openpyxl.
    if 'DOTS_Calculations' in wb.sheetnames:
        del wb['DOTS_Calculations'] # Clean up if running multiple times
    
    dest_sheet = wb.create_sheet(title='DOTS_Calculations')
    
    # Define the columns we want to copy from the source
    headers_to_copy = ['Name', 'Sex', 'BodyweightKg', 'Best3SquatKg', 'Best3BenchKg', 'Best3DeadliftKg']
    
    # Find the column indices in the source sheet
    source_headers = {cell.value: idx for idx, cell in enumerate(source_sheet[cite: 17], 1)}
    
    # Write headers to the destination sheet
    for col_idx, header in enumerate(headers_to_copy, 1):
        dest_sheet.cell(row=1, column=col_idx, value=header)
        
    # Append the headers for our calculated columns
    dest_sheet.cell(row=1, column=7, value="TotalKg")
    dest_sheet.cell(row=1, column=8, value="DotsScore")
    
    # Workflow 2: Copy specific columns row by row
    max_row = source_sheet.max_row
    for row in range(2, max_row + 1):
        for col_idx, header in enumerate(headers_to_copy, 1):
            source_col = source_headers.get(header)
            if source_col:
                source_value = source_sheet.cell(row=row, column=source_col).value
                dest_sheet.cell(row=row, column=col_idx, value=source_value)
                
        # Workflow 3: Writing Excel formulas using openpyxl
        # openpyxl requires formulas to be written exactly as they would appear in Excel (starting with '=')
        # We construct dynamic string references (e.g., D2, E2, F2)
        
        # TotalKg formula (Columns: D=Squat, E=Bench, F=Deadlift)
        total_formula = f'=IF(OR(ISBLANK(D{row}), ISBLANK(E{row}), ISBLANK(F{row}), D{row}<=0, E{row}<=0, F{row}<=0), "", D{row}+E{row}+F{row})'
        dest_sheet.cell(row=row, column=7, value=total_formula)
        
        # DOTS formula (Columns: B=Sex, C=Bodyweight, G=TotalKg)
        dots_formula = (
            f'=IF(OR(G{row}="", C{row}=""), "", ROUND(G{row} * 500 / '
            f'IF(OR(B{row}="M", B{row}="Mx"), '
            f'(-0.000001093*C{row}^4 + 0.0007391293*C{row}^3 - 0.1918759221*C{row}^2 + 24.0900756*C{row} - 307.75076), '
            f'(-0.0000010706*C{row}^4 + 0.0005158568*C{row}^3 - 0.1126655495*C{row}^2 + 13.6175032*C{row} - 57.96288)), 3))'
        )
        dest_sheet.cell(row=row, column=8, value=dots_formula)

    # Workflow 4: Saving the workbook
    # The source 'RawData' sheet remains untouched, and our new sheet is successfully appended.
    wb.save(output_file)
    print(f"File successfully saved to {output_file}")

## 5. Advanced Mechanics and Pitfalls in `openpyxl` (Focusing on Version 3.1.5)


While `openpyxl` is robust, programmatic manipulation of Excel files introduces several edge cases, execution quirks, and specific bugs associated with version 3.1.5, which developers must navigate carefully.

### 5.1 Formula Evaluation and the `data_only=True` Paradigm

One of the most misunderstood aspects of `openpyxl` is its relationship with formula evaluation. `openpyxl` **does not possess an internal calculation engine** [cite: 17, 18]. When you write a formula (e.g., `=A1+B1`) into a cell, `openpyxl` simply writes the literal text string into the underlying XML architecture of the file [cite: 18]. 

If you subsequently load that workbook using `load_workbook('file.xlsx')`, querying that cell will return the formula string, not the calculated number.
*   To retrieve the actual computed result, you must use `load_workbook('file.xlsx', data_only=True)` [cite: 17].
*   **Crucial caveat:** `data_only=True` relies on a cached value that Microsoft Excel calculates and saves the *last time the file was manually opened and saved by a human in the Excel GUI*. If you generate a file with formulas via Python, save it, and immediately reopen it with `data_only=True` via Python, the cells will return `None` because Excel has not yet had an opportunity to launch its calculation engine to generate the cached values [cite: 18].

### 5.2 Handling of Worksheets

By default, `openpyxl` preserves all data, macros (if using `keep_vba=True`), and empty sheets present in a loaded workbook. If a workbook is instantiated fresh (`wb = Workbook()`), it generates a single default sheet named `Sheet`. Empty sheets will remain upon saving unless explicitly deleted utilizing `del wb['SheetName']`.