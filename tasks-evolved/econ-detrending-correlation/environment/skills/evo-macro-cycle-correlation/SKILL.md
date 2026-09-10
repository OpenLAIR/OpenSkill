---
name: evo-macro-cycle-correlation
description: Deflates nominal series to real values using CPI, applies log transformation and Hodrick-Prescott filter to extract cyclical components, and computes Pearson correlation between two cyclical series.
---

# evo-macro-cycle-correlation

Deflates nominal macroeconomic series, applies HP filter for cycle extraction, and computes Pearson correlation between cyclical components.

## Key Functions

### `deflate_nominal_to_real(nominal, cpi)`
Converts nominal to real values: Real_t = (Nominal_t / CPI_t) * 100

### `extract_hp_cycle(real_series, lamb=100)`
Applies np.log() then HP filter (statsmodels hpfilter) to extract cyclical component.
- Uses natural log (np.log, NOT np.log10)
- hpfilter returns (cycle, trend) - parameter name is `lamb`
- lamb=100 for annual data (standard)

### `compute_cycle_pearson_correlation(cycle1, cycle2)`
Computes Pearson r using scipy.stats.pearsonr (returns PearsonRResult.statistic)

### `run_full_pipeline(pce_file, pfi_file, cpi_file, ...)`
Complete end-to-end pipeline: parse -> deflate -> HP filter -> correlate -> output.
Depends on evo-macro-data-ingestion for data parsing.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-macro-cycle-correlation/scripts')
from utils import run_full_pipeline

correlation = run_full_pipeline(
    pce_file='/root/ERP-2025-table10.xls',
    pfi_file='/root/ERP-2025-table12.xls',
    cpi_file='/root/CPI.xlsx',
    start_year=1973,
    end_year=2024,
    hp_lambda=100,
    output_file='/root/answer.txt'
)
```

## Technical Details

### Deflation
- Formula: Real = (Nominal / CPI) * 100
- CPI base period doesn't matter for HP cycle analysis (log differences cancel it)

### HP Filter
- Import: `from statsmodels.tsa.filters.hp_filter import hpfilter`
- Signature: `hpfilter(x, lamb=1600)` - use lamb=100 for annual data
- Returns: `(cycle, trend)` tuple
- Input must have NO NaN values

### Pearson Correlation
- scipy.stats.pearsonr returns PearsonRResult object (scipy 1.14.1)
- Access correlation via `.statistic` attribute
- Output formatted with f"{value:.5f}" for exactly 5 decimal places

### Year Range
- Use pandas .loc[1973:2024] for inclusive filtering
- .loc is inclusive of both start and stop labels
