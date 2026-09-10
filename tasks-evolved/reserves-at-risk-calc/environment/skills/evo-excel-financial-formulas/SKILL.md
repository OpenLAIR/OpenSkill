---
name: evo-excel-financial-formulas
description: Utilities for writing financial Excel formulas (log returns, rolling volatility, annualized volatility, XLOOKUP/INDEX+MATCH, RaR calculations) into openpyxl workbooks and triggering LibreOffice headless recalculation.
---

# evo-excel-financial-formulas

Write financial formulas into Excel workbooks and recalculate with LibreOffice.

## Key Functions

- `write_gold_price_sheet(wb, gold_series)` - Populate gold prices into Gold price sheet col B
- `write_log_return_formulas(wb, start_row, end_row)` - Write =LN(Bn/Bn-1)*100 in col C
- `write_volatility_formulas(wb, start_row, end_row)` - Write STDEV.S formulas in cols D (3-month) and E (12-month)
- `write_answer_sheet_step1(wb)` - Fill z-score, volatilities in Answer sheet
- `write_answer_sheet_step2(wb, value_countries, volume_countries, gold_avg_price)` - Fill country reserves and exposure
- `write_answer_sheet_step3(wb, step2_countries, total_reserves_data)` - Fill RaR calculations
- `recalculate_with_libreoffice(filepath)` - Force formula recalculation
- `create_output_workbook(template_path, output_path, ...)` - Main orchestrator function

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-excel-financial-formulas/scripts')
from utils import create_output_workbook

create_output_workbook(
    template_path='/root/data/test-rar.xlsx',
    output_path='/root/output/rar_result.xlsx',
    gold_series=gold_series,
    value_countries=value_countries,
    volume_countries=volume_countries,
    total_reserves_data=total_reserves_data,
    gold_avg_price=avg_price
)
```

## Formula Details

- Log returns: `=LN(B{r}/B{r-1})*100` (multiply by 100 for percentage)
- 3-month vol: `=STDEV.S(C{r-2}:C{r})` starting at row 5
- 12-month vol: `=STDEV.S(C{r-11}:C{r})` starting at row 14
- Annualized 3-month vol: `=C4*SQRT(12)` where C4 is latest 3-month vol
- Gold exposure: `=reserves * annualized_vol/100 * z_score`
- RaR: `=exposure / total_reserves * 100`
