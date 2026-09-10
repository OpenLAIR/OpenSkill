---
name: evo-acopf-network-parser
description: Parses Matpower-style network.json files into Python data structures suitable for ACOPF formulation.
---
# evo-acopf-network-parser

Parses Matpower-style network.json (array format) into solver-ready structures.

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-acopf-network-parser/scripts')
from utils import parse_network_json, map_generators_to_buses, identify_reference_buses, get_branch_bus_mappings

baseMVA, buses, gens, branches, loads_by_bus, shunts_by_bus = parse_network_json('network.json')
gen_at_bus = map_generators_to_buses(gens, buses)
ref_buses = identify_reference_buses(buses)
branch_from, branch_to = get_branch_bus_mappings(branches, buses)
```

## Key Details
- Bus data includes embedded PD/QD (loads) and GS/BS (shunts)
- All power values converted to per-unit (divided by baseMVA)
- Angles converted from degrees to radians
- Cost coefficients scaled for per-unit solver evaluation
- Out-of-service generators and branches are filtered out
