---
name: evo-reflow-handbook-parser
description: Extracts reflow soldering process parameters from the PDF handbook including preheat range, ramp rate limits, TAL window, peak temp requirements, and conveyor speed formulas.
---

# evo-reflow-handbook-parser

## Purpose
Parse the reflow machine handbook PDF and return structured dictionaries of all process thresholds, formulas, and compliance limits.

## Key Parameters (from handbook)

### Preheat Zone
- Temperature range: 100°C to 150°C
- Max ramp rate: 2°C/second
- Ramp rate equation: ΔT/Δt (temperature change over time change)

### TAL (Wetting Time)
- Window: 30 to 60 seconds
- Measured as time solder is above its melting (liquidus) point
- Liquidus is paste-specific (from MES solder_liquidus_c column)

### Peak Temperature
- Must exceed liquidus by approximately 20°C
- Required min peak = solder_liquidus_c + 20

### Conveyor Speed
- LINE SPEED (MIN) = boards_per_min × board_length_cm / loading_factor
- Actual speed must be >= minimum line speed

### Representative Thermocouple
- Handbook says to thermocouple the largest and smallest device
- TC at "largest_mass" location represents the coldest spot (hardest to heat)
- Use largest_mass TC for compliance checks (minimum peak, TAL)

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-reflow-handbook-parser/scripts')
from utils import get_all_handbook_params, parse_preheat_params, parse_tal_params

params = get_all_handbook_params()
print(params['preheat']['max_ramp_rate_c_per_s'])  # 2.0
```
