---
name: evo-powerlifting-dots-formula
description: Provides the exact DOTS scoring formula, sex-specific polynomial coefficients, TotalKg computation rules, edge case handling (negative best lifts, blank values, Mx category), and corresponding Excel formula strings for both TotalKg and DOTS columns.
---

# DOTS Powerlifting Formula Skill

## Overview
The DOTS (Dynamic Objective Team Scoring) formula is a 4th-degree polynomial-based scoring system for normalizing powerlifting performance across body weights.

## Formula
```
DOTS Score = TotalKg × (500 / (A×BW⁴ + B×BW³ + C×BW² + D×BW + E))
```

### Male Coefficients (also used for Mx)
- A = -0.000001093
- B = 0.0007391293
- C = -0.1918759221
- D = 24.0900756
- E = -307.75076

### Female Coefficients
- A = -0.0000010706
- B = 0.0005158568
- C = -0.1126655495
- D = 13.6175032
- E = -57.96288

## Required Columns
From OpenPowerlifting data: Name, Sex, BodyweightKg, Best3SquatKg, Best3BenchKg, Best3DeadliftKg

## Edge Cases
- **Negative values**: Indicate failed attempts (bombing out). If any Best3 lift is negative or zero, TotalKg must be blank.
- **Blank values**: If any lift is blank, TotalKg must be blank.
- **Mx category**: Uses male coefficients.
- **Precision**: 3 decimal places (ROUND(..., 3))

## TotalKg Excel Formula
```excel
=IF(OR(ISBLANK(D2), ISBLANK(E2), ISBLANK(F2), D2<=0, E2<=0, F2<=0), "", D2+E2+F2)
```
Where D=Best3SquatKg, E=Best3BenchKg, F=Best3DeadliftKg

## DOTS Excel Formula
```excel
=IF(OR(G2="",C2=""),"",ROUND(G2*500/IF(OR(B2="M",B2="Mx"),-0.000001093*C2^4+0.0007391293*C2^3-0.1918759221*C2^2+24.0900756*C2-307.75076,-0.0000010706*C2^4+0.0005158568*C2^3-0.1126655495*C2^2+13.6175032*C2-57.96288),3))
```
Where B=Sex, C=BodyweightKg, G=TotalKg

**IMPORTANT**: Coefficients must be in exact decimal notation (not scientific notation like -1.093e-06).

## Usage
```python
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

dots_utils = load_module('dots_utils', '/app/environment/skills/evo-powerlifting-dots-formula/scripts/utils.py')

# Get required columns
cols = dots_utils.get_required_columns()

# Build Excel formulas for row 2
total_formula = dots_utils.build_totalkg_excel_formula(2)  # Uses default cols D, E, F
dots_formula = dots_utils.build_dots_excel_formula(2)       # Uses default cols B, C, G

# Numeric computation for validation
score = dots_utils.compute_dots_score(607.5, 82.25, 'M')  # Returns float rounded to 3dp
```

**NOTE**: Use importlib.util to avoid module name conflicts when multiple skills have utils.py.
