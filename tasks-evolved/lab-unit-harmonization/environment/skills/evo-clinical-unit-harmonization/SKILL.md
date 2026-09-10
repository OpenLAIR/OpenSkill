---
name: evo-clinical-unit-harmonization
description: Domain-specific clinical lab unit detection and conversion module with conversion factor registry, physiological range boundaries, and boundary-based auto-detection logic to convert SI units to US conventional units.
---

# evo-clinical-unit-harmonization

Converts clinical lab values from SI to US conventional units using boundary-based auto-detection.

## Key Functions

- `build_conversion_registry()` - Returns dict mapping column names to analyte configs
- `detect_and_convert_value(val, config)` - Detect and convert a single value
- `harmonize_column(series, config)` - Harmonize an entire column
- `harmonize_all_features(df, skip_cols)` - Harmonize all features in DataFrame

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-clinical-unit-harmonization/scripts')
from utils import harmonize_all_features

df = harmonize_all_features(df, skip_cols=['patient_id'])
```

## Conversion Registry

Covers all 62 CKD features including:
- Creatinine (SI umol/L -> US mg/dL, factor 0.0113)
- BUN (SI mmol/L -> US mg/dL, factor 2.8)
- Hemoglobin (SI g/L -> US g/dL, factor 0.1)
- Albumin/Total Protein (SI g/L -> US g/dL, factor 0.1)
- Glucose (SI mmol/L -> US mg/dL, factor 18.0)
- HbA1c (SI mmol/mol -> US %, linear: val*0.0915+2.15)
- Calcium (SI mmol/L -> US mg/dL, factor 4.0)
- Phosphorus (SI mmol/L -> US mg/dL, factor 3.1)
- Cholesterol/LDL/HDL (SI mmol/L -> US mg/dL, factor 38.67)
- Triglycerides (SI mmol/L -> US mg/dL, factor 88.57)
- Uric Acid (SI umol/L -> US mg/dL, factor 0.0168)
- Bilirubin (SI umol/L -> US mg/dL, factor 0.0585)
- Iron/TIBC (SI umol/L -> US ug/dL, factor 5.587)
- Hematocrit (SI L/L -> US %, factor 100)
