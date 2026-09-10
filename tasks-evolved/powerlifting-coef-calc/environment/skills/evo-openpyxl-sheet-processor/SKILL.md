---
name: evo-openpyxl-sheet-processor
description: Provides utilities for loading an Excel workbook with openpyxl, copying selected columns from a source sheet to a destination sheet preserving order and headers, appending formula columns, and saving the workbook.
---

# openpyxl Sheet Processor Skill

## Overview
Utilities for Excel workbook manipulation using openpyxl 3.1.5. Handles loading, column copying, formula insertion, and saving.

## Key Concepts
- openpyxl does NOT evaluate formulas - it stores formula strings
- Do NOT use data_only=True when writing formulas
- Preserve all existing sheets when saving
- Column indices are 1-based in openpyxl

## Functions

### load_workbook_safe(filepath)
Loads an xlsx workbook. Returns openpyxl Workbook object.

### find_column_indices(sheet, column_names)
Finds 1-based column indices for named columns in header row.
Returns dict: {column_name: index}.

### copy_columns_to_sheet(source_sheet, dest_sheet, column_names)
Copies specified columns from source to dest sheet. Preserves column order.
Returns number of data rows copied.

### append_formula_column(dest_sheet, col_index, header_name, formula_builder, num_data_rows)
Appends a formula column. formula_builder is callable(row) -> formula string.

### save_workbook(wb, filepath)
Saves workbook to disk.

### get_column_letter(col_index)
Converts 1-based index to Excel letter (1->A, 2->B, etc.)

## Usage
```python
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

xl_utils = load_module('xl_utils', '/app/environment/skills/evo-openpyxl-sheet-processor/scripts/utils.py')

# Load workbook
wb = xl_utils.load_workbook_safe('/root/data/openipf.xlsx')
source = wb['Data']
dest = wb['Dots']

# Copy columns
column_names = ['Name', 'Sex', 'BodyweightKg', 'Best3SquatKg', 'Best3BenchKg', 'Best3DeadliftKg']
num_rows = xl_utils.copy_columns_to_sheet(source, dest, column_names)

# Append formula column
def total_builder(row):
    return f'=D{row}+E{row}+F{row}'
xl_utils.append_formula_column(dest, 7, 'TotalKg', total_builder, num_rows)

# Save
xl_utils.save_workbook(wb, '/root/data/openipf.xlsx')
```

**NOTE**: Use importlib.util to avoid module name conflicts when multiple skills have utils.py.

## Depends On
- evo-powerlifting-dots-formula (for formula builders and required column list)
