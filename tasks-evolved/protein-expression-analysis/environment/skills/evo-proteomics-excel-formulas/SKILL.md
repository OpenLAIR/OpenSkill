---
name: evo-proteomics-excel-formulas
description: Use when populating Excel workbooks for quantitative proteomics tasks - writing INDEX/MATCH lookups, AVERAGE/STDEV.S group statistics, and log2 fold-change formulas while preserving cell formatting via openpyxl 3.1.5.
---

# evo-proteomics-excel-formulas

Utilities for populating Excel workbooks with proteomics Excel formulas
(INDEX-MATCH lookups, AVERAGE, STDEV.S, fold-change) while preserving formatting.

## Key Principles

1. **Write Excel FORMULAS, not computed values** - The task requires formulas.
2. **Load with data_only=False** to preserve existing formulas and formatting.
3. **_xlfn. prefix** for STDEV.S: openpyxl requires `_xlfn.STDEV.S(...)` to avoid #NAME? errors.
4. **AVERAGE** is a core OOXML function - no prefix needed.
5. **Data is log2-transformed**: Log2FC = Treated_Mean - Control_Mean; FC = 2^Log2FC.
6. **Preserve formatting**: Setting cell.value preserves existing fill, font, border.
7. **Use wb["SheetName"]** not deprecated get_sheet_by_name().

## Task Sheet Layout (protein_expression.xlsx)

- **Row 9**: Group labels ("Control" / "Treated") in cols C-L
- **Row 10**: Sample names in cols C-L (match Data sheet headers)
- **A11:A20**: 10 target Protein_IDs; B11:B20: Gene_Symbols
- **C11:L20** (yellow): INDEX-MATCH formulas looking up from Data sheet
- **B24:K27** (yellow): Group statistics
  - Row 24 = Control Mean (AVERAGE), Row 25 = Control StdDev (STDEV.S)
  - Row 26 = Treated Mean (AVERAGE), Row 27 = Treated StdDev (STDEV.S)
  - Columns B-K map to proteins in rows 11-20
- **A32:B41**: Protein IDs and Gene Symbols
- **C32:C41** (yellow): Fold Change = 2^(Log2FC)
- **D32:D41** (yellow): Log2 FC = Treated Mean - Control Mean

## Data Sheet Layout

- Row 1: Headers (Protein_ID, Gene_Symbol, Description, then 50 sample names in D1:BA1)
- Rows 2-201: 200 proteins with log2 expression values in D2:BA201
- Column A: Protein_IDs

## Usage (one-shot)

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-proteomics-excel-formulas/scripts')
from utils import populate_proteomics_task

populate_proteomics_task('/root/protein_expression.xlsx')
```

## Usage (step-by-step)

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-proteomics-excel-formulas/scripts')
from utils import (
    load_workbook_preserving,
    save_workbook_safely,
    classify_group_columns,
    fill_expression_lookup_formulas,
    fill_group_stats_formulas,
    fill_fold_change_formulas,
)

wb = load_workbook_preserving('/root/protein_expression.xlsx')
ws_task = wb['Task']

# Step 1: INDEX-MATCH lookups in C11:L20
fill_expression_lookup_formulas(ws_task, data_sheet_name='Data',
                                 data_max_row=201, data_max_col_letter='BA',
                                 data_start_col_letter='D')

# Step 2: Group stats in B24:K27
groups = classify_group_columns(ws_task)
fill_group_stats_formulas(ws_task, groups)

# Step 3: Fold change in A32:D41
fill_fold_change_formulas(ws_task)

save_workbook_safely(wb, '/root/protein_expression.xlsx')
```

## Formula Patterns

### INDEX-MATCH (two-way lookup)
```
=INDEX(Data!$D$2:$BA$201,MATCH($A11,Data!$A$2:$A$201,0),MATCH(C$10,Data!$D$1:$BA$1,0))
```

### AVERAGE (group mean)
```
=AVERAGE(C11,D11,E11,F11,G11)
```

### STDEV.S (group standard deviation)
```
=_xlfn.STDEV.S(C11,D11,E11,F11,G11)
```

### Log2 Fold Change
```
=B26-B24
```

### Linear Fold Change
```
=2^D32
```
