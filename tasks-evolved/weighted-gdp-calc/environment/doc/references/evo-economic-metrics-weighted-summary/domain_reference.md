# Domain Reference for evo-economic-metrics-weighted-summary

**Responsibility**: Economic and statistical calculations only: derive net exports % of GDP in H35:L40, calculate min/max/median/simple mean/25th percentile/75th percentile, and compute the weighted mean for GCC using valid source values and weights.

**Key functions to implement**: compute_net_exports_pct, compute_summary_statistics, compute_excel_percentile_inc, compute_weighted_mean_sumproduct

---

### The Challenge of Formula Evaluation

The fundamental limitation of most native Python Excel libraries, including Openpyxl, is the absence of an integrated calculation engine. When a Python script writes a formula to a cell, the result is not immediately available. Relying on the host operating system to force recalculation via tools like LibreOffice or Gnumeric introduces dependencies and potential points of failure. Consequently, robust automation skills often must mirror Excel's mathematical operations within the Python environment.

## Writing Excel Formulas with Openpyxl


Openpyxl does not compute formulas; it simply stores the formula string into the cell's underlying XML structure. The host application (Excel, LibreOffice) parses and evaluates this string upon opening the file.

## Formula Recalculation and Evaluation Outside Excel


Because Python automation environments frequently execute on headless Linux servers (e.g., Ubuntu 24.04), relying on a user to open Excel and press F9 is unacceptable. External recalculation of the `.xlsx` file must be invoked programmatically. Two primary tools exist for this on Ubuntu: **LibreOffice Calc** and **Gnumeric**.

## Implementing Domain Calculations in Reusable Python Helpers


When migrating logic from Excel formulas to Python, the skill author must replicate spreadsheet semantics accurately, paying special attention to missing data, divide-by-zero errors, and array broadcasting.

## Statistical Functions Parity with Excel


The calculation of quantiles (percentiles and quartiles) is a mathematically fragmented domain. Different software packages utilize different interpolation algorithms when estimating quantiles for continuous distributions from discrete samples [cite: 38, 39, 40].