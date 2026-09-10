---
name: evo-civ6-placement-optimizer
description: Searches for optimal city center and district placements to maximize total adjacency bonuses in Civ6 scenarios.
---

# evo-civ6-placement-optimizer

Optimizes district placement for maximum adjacency bonuses.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-civ6-placement-optimizer/scripts')
from utils import load_scenario, find_optimal_placements, write_solution_json

sys.path.insert(0, '/app/environment/skills/evo-civ6-map-parser/scripts')
from utils import parse_civ6map

scenario = load_scenario('/data/scenario_3/scenario.json')
map_data = parse_civ6map('/data/maps/e2e_test_case_0.Civ6Map')
solution = find_optimal_placements(map_data, scenario)
write_solution_json(solution, '/output/scenario_3.json')
```

## Key Functions

- `load_scenario(path)` - Load scenario JSON
- `find_optimal_placements(map_data, scenario)` - Find best placements
- `write_solution_json(solution, output_path)` - Write output JSON
- `evaluate_placement(map_data, cc, assignments, civ)` - Evaluate a placement
