---
name: evo-protein-expression-analysis
description: Use when populating Excel workbooks for quantitative proteomics tasks - computing expression lookups, group statistics, and log2 fold-change values using Python and writing numeric results via openpyxl while preserving cell formatting. Handles two-sheet workbooks (Task + Data) with 2D protein×sample expression matrices.
---

# evo-protein-expression-analysis

Utilities for populating Excel workbooks with proteomics expression values,
group statistics, and fold-change calculations while preserving all cell formatting.

## CRITICAL: Write computed numeric values, NOT formulas

openpyxl does NOT have a calculation engine. If you write Excel formulas (strings
starting with `=`), they will only be evaluated when the file is opened in Excel.
Tools that read the file with `data_only=True` will see `None` for all formula cells.

**You MUST compute values in Python and write float/int results directly.**

## Key facts about the protein_expression.xlsx task

- File has two sheets: `Task` (where work happens) and `Data` (raw expression values).
- **Data sheet layout**:
  - Column A = Protein_ID, Column B = Gene_Symbol, Column C = Description
  - Row 1 (D1:BA1) = 50 sample header names (e.g., "MDAMB468_BREAST_TenPx01")
  - Rows 2–201 = 200 proteins with log2-transformed expression values in D2:BA201
- **Task sheet layout**:
  - Row 9 (C9:L9): "Control" or "Treated" group labels
  - Row 10 (C10:L10): 10 sample names (must match Data sheet headers exactly)
  - Column A, rows 11–20: 10 target Protein_IDs; Column B = Gene_Symbol
  - **C11:L20** (yellow): expression values looked up from Data sheet
  - **B24:K27** (yellow): per-protein group statistics
    - Row 24 = Control Mean, Row 25 = Control StdDev, Row 26 = Treated Mean, Row 27 = Treated StdDev
    - Column B → protein in row 11; Column K → protein in row 20
  - **C32:D41** (yellow): fold change results
    - Column C = Log2 Fold Change (Treated Mean − Control Mean)
    - Column D = Fold Change (2^Log2FC)
    - Row 32 → protein in row 11; Row 41 → protein in row 20

## Critical rules

1. **Write computed numeric values, not formulas** — openpyxl doesn't evaluate formulas.
2. Load with `data_only=False` to preserve existing formatting; only set `.value` on target cells.
3. Data is already log2-transformed: use regular mean/stdev; Log2FC = Treated_Mean − Control_Mean; Fold Change = 2^Log2FC.
4. Use Python's `statistics.mean()` and `statistics.stdev()` (sample stdev) for calculations.
5. Group classification comes from text values in row 9 ("Control" / "Treated").
6. Sample names in the Data sheet may have prefixes like "MDAMB468_BREAST_TenPx01" — match exactly against Task row 10.
7. Do not alter file format, colors, fonts, or add macros/VBA.
8. Setting cell.value preserves existing cell formatting (fill, font, border).

## Usage

```python
import sys
sys.path.insert(0, '/root/.claude/skills/evo-protein-expression-analysis/scripts')
from utils import populate_protein_expression_task

# One-shot populate the standard task:
populate_protein_expression_task('/root/protein_expression.xlsx')
```

## Alternate usage (step-by-step)

```python
import sys
sys.path.insert(0, '/root/.claude/skills/evo-protein-expression-analysis/scripts')
from utils import (
    load_workbook_preserving,
    save_workbook_safely,
    build_data_index,
    classify_group_columns,
    fill_expression_values,
    compute_group_stats,
    compute_fold_changes,
)

wb = load_workbook_preserving('/root/protein_expression.xlsx')
ws_task = wb['Task']
ws_data = wb['Data']

# Build lookup index from Data sheet
data_index = build_data_index(ws_data)

# Detect Control/Treated grouping from row 9
groups = classify_group_columns(ws_task, group_row=9, start_col=3, end_col=12)

# Step 1: Fill expression values (numeric)
fill_expression_values(ws_task, data_index)

# Step 2: Compute and write statistics (numeric)
compute_group_stats(ws_task, groups=groups)

# Step 3: Compute and write fold changes (numeric)
compute_fold_changes(ws_task)

save_workbook_safely(wb, '/root/protein_expression.xlsx')
```

## Output validation

After running, the following cells must contain **numeric values** (int or float):
- C11:L20 — expression values looked up from Data sheet
- B24:K27 — mean and stdev values computed in Python
- C32:D41 — log2 fold change and linear fold change values computed in Python

No cell formatting (fills, fonts) should change.