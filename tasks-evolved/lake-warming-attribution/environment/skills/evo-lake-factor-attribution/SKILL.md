---
name: evo-lake-factor-attribution
description: Trains Random Forest to determine feature importances of environmental predictors on water temperature, maps features to categories (Heat/Flow/Wind/Human), and identifies the dominant driving factor category.
---

# evo-lake-factor-attribution

Uses Random Forest feature importances to attribute water temperature changes to physical driver categories.

## Category Mapping

| Category | Variables | Description |
|----------|-----------|-------------|
| Heat | AirTempLake, Shortwave, Longwave | Thermodynamic forcing |
| Flow | Precip, Outflow, Inflow | Hydrological forcing |
| Wind | WindSpeedLake | Mechanical forcing |
| Human | DevelopedArea, AgricultureArea | Anthropogenic forcing |

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-lake-factor-attribution/scripts')
from utils import train_random_forest, compute_feature_importances, map_features_to_categories, get_dominant_category, save_dominant_factor

# Train RF model
model = train_random_forest(X, y)

# Get feature importances
importance_df = compute_feature_importances(model, feature_names)

# Map to categories and aggregate
category_contributions = map_features_to_categories(importance_df, category_map)

# Get dominant category
category_name, contribution = get_dominant_category(category_contributions)

# Save output (columns: variable, contribution)
save_dominant_factor(category_name, contribution, '/root/output/dominant_factor.csv')
```

## Key Functions

- `train_random_forest(X, y)` — fits RF regressor with random_state=42
- `compute_feature_importances(model, feature_names)` — extracts importances as percentages
- `map_features_to_categories(importance_df, category_map)` — aggregates by category
- `get_dominant_category(category_contributions)` — returns (name, contribution_decimal)
- `save_dominant_factor(name, contribution, path)` — writes single-row CSV

## Output Format

dominant_factor.csv:
```
variable,contribution
Heat,0.45
```

Note: contribution is in decimal form (0-1 range), NOT percentage.

## Import Pattern (avoiding naming conflicts)

When using multiple skills that each have `utils.py`, use importlib to avoid conflicts:

```python
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

data_utils = load_module('data_utils', '/app/environment/skills/evo-lake-data-pipeline/scripts/utils.py')
trend_utils = load_module('trend_utils', '/app/environment/skills/evo-lake-trend-analysis/scripts/utils.py')
factor_utils = load_module('factor_utils', '/app/environment/skills/evo-lake-factor-attribution/scripts/utils.py')
```
