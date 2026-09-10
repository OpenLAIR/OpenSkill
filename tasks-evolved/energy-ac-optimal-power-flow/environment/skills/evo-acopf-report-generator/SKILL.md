---
name: evo-acopf-report-generator
description: Extracts ACOPF solution values, computes derived quantities, and produces structured report.json.
---
# evo-acopf-report-generator

Extracts solution from solved Pyomo ACOPF model and generates report.json.

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-acopf-report-generator/scripts')
from utils import generate_report_json

report = generate_report_json(model, baseMVA, results, output_path='report.json', top_n_branches=5)
```

## Key Details
- Converts per-unit values to MW/MVAr/degrees
- Computes branch loading percentages (max of from/to flow vs limit)
- Feasibility check: power mismatches, voltage violations, branch overloads
- Top N most loaded branches sorted by loading percentage
