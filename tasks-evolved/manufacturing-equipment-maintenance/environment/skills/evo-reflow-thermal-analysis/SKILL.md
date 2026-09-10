---
name: evo-reflow-thermal-analysis
description: Processes thermocouple CSV data, MES logs, and test defect data to compute preheat ramp rates, TAL, peak temperatures, conveyor speed compliance, and best-run selection per board family.
---

# evo-reflow-thermal-analysis

## Purpose
All CSV data loading, merging, time-series computation, and compliance checks.

## Key Functions
- `load_thermocouple_data()` - Load TC CSV
- `load_mes_log()` - Load MES CSV  
- `load_test_defects()` - Load defects CSV
- `calculate_ramp_rates(tc_df)` - Compute dT/dt per interval
- `get_max_preheat_ramp_by_run(tc_df, preheat_max_c=150.0)` - Max ramp in preheat zone using largest_mass TC
- `calculate_tal_by_run(tc_df, mes_df)` - TAL using largest_mass TC and per-run liquidus
- `check_peak_temp_compliance(tc_df, mes_df, peak_margin_c=20.0)` - Peak temp check
- `check_conveyor_speed_compliance(mes_df)` - Min speed feasibility
- `find_best_run_per_board_family(mes_df, defects_df, tc_df)` - Best run selection

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-reflow-thermal-analysis/scripts')
from utils import load_thermocouple_data, get_max_preheat_ramp_by_run

tc_df = load_thermocouple_data()
ramps = get_max_preheat_ramp_by_run(tc_df)
```
