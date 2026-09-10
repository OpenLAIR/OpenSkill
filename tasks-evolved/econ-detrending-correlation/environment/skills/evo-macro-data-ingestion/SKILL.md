---
name: evo-macro-data-ingestion
description: Parses ERP .xls tables and CPI .xlsx files, handles multi-row headers, extracts annual totals, computes partial-year averages from quarterly data, and produces clean annual series indexed by integer year.
---

# evo-macro-data-ingestion

Parses Economic Report of the President (ERP) `.xls` tables and CPI `.xlsx` files into clean pandas Series indexed by integer year.

## Key Functions

### `parse_erp_annual_total(filepath, target_year=2024)`
Parses an ERP .xls file to extract the annual "Total" column (first data column).
- Handles multi-row headers, trailing periods on years (e.g., '1973.')
- Handles quarterly data at bottom of table  
- For partial years (e.g., 2024 with Q1-Q3 only), computes average of available quarters
- Uses `engine="xlrd"` for .xls files
- Returns: pd.Series indexed by integer year

### `compute_partial_year_average(df, target_year=2024)`
Computes arithmetic mean of available quarterly SAAR values for a partial year.
- Handles ERP quarterly format: '2024: I.' followed by indented '    II.', '    III p.'
- Returns: float or None

### `process_cpi_annual(filepath)`
Reads CPI data from .xlsx file. Auto-detects format:
- Pre-processed annual data (Year + CPI columns)
- Raw FRED monthly CPIAUCSL data (aggregated to annual mean)
- Uses `engine="openpyxl"` for .xlsx files
- Returns: pd.Series indexed by integer year

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-macro-data-ingestion/scripts')
from utils import parse_erp_annual_total, process_cpi_annual

pce_nominal = parse_erp_annual_total('/root/ERP-2025-table10.xls', target_year=2024)
pfi_nominal = parse_erp_annual_total('/root/ERP-2025-table12.xls', target_year=2024)
cpi_annual = process_cpi_annual('/root/CPI.xlsx')
```

## Data Format Notes

### ERP Tables (.xls)
- Rows 0-4: Multi-row headers (title, units, column labels)
- Row 5+: Data rows with Period in col 0, Total in col 1
- Years have trailing periods: '1973.'
- Quarterly data appended at bottom: '2024: I.', '    II.', '    III p.'
- Use xlrd engine (xlrd 2.0.1 only supports .xls)

### CPI File (.xlsx)
- May be annual (columns: Year, CPI_2024) or monthly FRED data
- Use openpyxl engine for .xlsx files
- CPI_2024 is normalized to 2024=1.0
