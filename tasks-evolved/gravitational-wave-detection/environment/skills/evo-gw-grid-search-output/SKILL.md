---
name: evo-gw-grid-search-output
description: Orchestrates mass parameter grid search across approximants for GW matched filtering, tracks best SNR per approximant, handles errors gracefully, manages memory, and writes final CSV output.
---

# evo-gw-grid-search-output

Orchestrates the grid search over mass parameters and approximants, using evo-gw-matched-filter-engine for core computations.

## Functions

### run_grid_search(gwf_path, channel, approximants, mass_range, conditioned_data=None, psd=None)
Runs matched filtering for every (m1, m2) combination where m1 >= m2 across all approximants.
Tracks best SNR per approximant. Handles TaylorT4 failures gracefully.
Returns list of dicts: [{approximant, snr, total_mass}, ...]

### extract_best_per_approximant(results)
Extracts the highest SNR entry per approximant from results list.

### write_detection_results_csv(results, output_path)
Writes results to CSV with columns: approximant, snr, total_mass

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-gw-matched-filter-engine/scripts')
from utils import read_and_condition_data, estimate_psd

sys.path.insert(0, '/app/environment/skills/evo-gw-grid-search-output/scripts')
from utils import run_grid_search, write_detection_results_csv

# Condition data once
data = read_and_condition_data('/root/data/PyCBC_T2_2.gwf', 'H1:TEST-STRAIN')
psd = estimate_psd(data)

# Run grid search
approximants = ['SEOBNRv4_opt', 'IMRPhenomD', 'TaylorT4']
mass_range = range(10, 41)  # 10 to 40 inclusive, integer steps
results = run_grid_search(
    '/root/data/PyCBC_T2_2.gwf', 'H1:TEST-STRAIN',
    approximants, mass_range,
    conditioned_data=data, psd=psd
)

# Write CSV
write_detection_results_csv(results, '/root/detection_results.csv')
```

## Key Design Decisions
- Data is conditioned ONCE and reused for all templates
- m1 >= m2 convention avoids duplicate computations
- TaylorT4 may fail for high-mass BBH (inspiral-only approximant)
- Memory cleanup with del + gc.collect() after each template
- SNR rounded to 2 decimal places
- total_mass = mass1 + mass2 (integer for integer inputs)
