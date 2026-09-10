---
name: evo-crystallography-fraction-format
description: Converts floating-point fractional coordinates to clean rational fraction strings with bounded denominators (<=12), handling edge cases like near-zero/near-one wrapping and integer values.
---

# evo-crystallography-fraction-format

Converts floating-point crystallographic fractional coordinates to rational fraction strings.

## Key Functions

- `float_to_fraction_string(val, max_den=12)` - Convert single float to fraction string
- `rationalize_coordinate_vector(coords, max_den=12)` - Convert 3-element coordinate vector to list of fraction strings

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-crystallography-fraction-format/scripts')
from fraction_utils import float_to_fraction_string, rationalize_coordinate_vector

# Single value
float_to_fraction_string(0.33333)  # Returns "1/3"
float_to_fraction_string(0.5)      # Returns "1/2"
float_to_fraction_string(0.0)      # Returns "0"
float_to_fraction_string(0.9999)   # Returns "0" (near-1 snapping)
float_to_fraction_string(0.999)    # Returns "0" (near-1 snapping with 1e-3 threshold)

# Vector
rationalize_coordinate_vector([0.0, 0.5, 0.385])  # Returns ["0", "1/2", "3/8"]
```

## Rules

1. Wrap coordinates to [0, 1) using modulo 1.0
2. Snap near-0 (< 1e-3) and near-1 (> 1-1e-3) values to "0"
3. Use `fractions.Fraction.limit_denominator(12)` for conversion
4. If fraction result >= 1 or <= 0, return "0" (safety wrap)
5. Integers display as "0"; fractions as "p/q"
