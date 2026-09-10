---
name: evo-excel-gcc-net-exports-formulas
description: Generate workbook-specific INDEX/MATCH lookup formulas and downstream GCC net-exports formulas for the target workbook layout.
---

This skill handles workbook-specific financial/statistical formula construction.

Knowledge internalized:
- The lookup blocks H12:L17, H19:L24, and H26:L31 must contain formulas, not pasted values.
- For this workbook, stable lookup formulas are built with `INDEX` on the exact Data row for each series and `MATCH` on the year header in `Data!I4:M4` against the Task year cells in row 9.
- Net exports percent of GDP is `(exports - imports) / GDP` with blank/zero guard.
- Summary rows are MIN row 43, MAX row 44, MEDIAN row 45, AVERAGE row 46, 25th percentile row 47, 75th percentile row 48.
- Percentiles must use `PERCENTILE.INC`, not legacy `PERCENTILE`.
- GCC weighted mean is on row 50 and uses `SUMPRODUCT(ratios, GDPs)/SUM(GDPs)`.
- Formula strings must be English and comma-separated.

Functions:
- `map_task_ranges()`
- `build_two_key_lookup_formula(task_row, year_col)`
- `build_lookup_formula_map()`
- `build_net_exports_pct_formula(ratio_row, year_col)`
- `build_summary_stat_formulas(year_col)`
- `build_weighted_mean_formula(year_col)`
- `build_formula_map()`
