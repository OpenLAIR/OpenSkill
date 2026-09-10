---
name: evo-reflow-json-output
description: Formats and serializes computed analysis results into exact JSON structures for q01-q05 output files with numpy/pandas type coercion, rounding, and sorting.
---

# evo-reflow-json-output

## Purpose
JSON serialization with proper type handling for manufacturing data.

## Key Functions
- `safe_json_dump(data, filepath)` - Write JSON with numpy type handling
- `build_q01_output(max_ramp_by_run, ramp_rate_limit)` - Format Q1
- `build_q02_output(tal_results)` - Format Q2
- `build_q03_output(failing_runs, min_peak_by_run)` - Format Q3
- `build_q04_output(speed_results)` - Format Q4
- `build_q05_output(best_runs)` - Format Q5

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-reflow-json-output/scripts')
from utils import build_q01_output, safe_json_dump

output = build_q01_output(ramp_data, 2.0)
safe_json_dump(output, '/app/output/q01.json')
```
