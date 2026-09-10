---
name: evo-trend-anomaly-causal-inference
description: Complete pipeline for identifying anomalous product category spending patterns in e-commerce data using Prophet counterfactual forecasting, and explaining anomalies through demographic factors via Difference-in-Differences causal inference.
---

# Evo Trend Anomaly Causal Inference

Complete pipeline for identifying anomalous product category spending patterns and using DiD causal inference to explain anomalies through demographic factors.

## Pipeline Steps

1. **Data Cleaning** (`scripts/clean_data.py`): Clean survey and purchase data, handling duplicates, missing values, inconsistent formatting, date parsing, monetary columns, and category extraction.
2. **Anomaly Detection** (`scripts/anomaly_detection.py`): Prophet-based counterfactual forecasting to compute deviation index (-100 to 100) per category for March 2020.
3. **Feature Engineering** (`scripts/feature_engineering.py`): One-hot/ordinal encode demographics, bin continuous variables, produce feature-engineered survey CSV.
4. **DiD Analysis** (`scripts/did_analysis.py`): Difference-in-Differences causal analysis for intensive margin (univariate DiD on spend among purchasers) and extensive margin (multivariate heterogeneous DiD on purchase propensity).

## Usage

```python
import subprocess
subprocess.run(['python3', '/app/environment/skills/evo-trend-anomaly-causal-inference/scripts/clean_data.py'], check=True)
subprocess.run(['python3', '/app/environment/skills/evo-trend-anomaly-causal-inference/scripts/anomaly_detection.py'], check=True)
subprocess.run(['python3', '/app/environment/skills/evo-trend-anomaly-causal-inference/scripts/feature_engineering.py'], check=True)
subprocess.run(['python3', '/app/environment/skills/evo-trend-anomaly-causal-inference/scripts/did_analysis.py'], check=True)
```

## Key Design Decisions

- Survey IDs are case-sensitive (R_ prefix preserved)
- hh-size outliers (53, 33, etc.) capped using IQR method
- Prophet trained on all pre-March 2020 data only; cmdstanpy logging suppressed
- Anomaly index: 100 * tanh(raw_deviation) for [-100, 100] range
- Binary variable one-hot: remove negative indicator (e.g., _No, _Female) to avoid dummy variable trap
- Intensive margin: purchasers only (Total_Spend > 0), sum spending per user-category-period
- Extensive margin: full cross-join of all survey users × selected categories × periods
- Univariate DiD for intensive margin (robust to small samples), multivariate heterogeneous DiD for extensive margin
- Surge drivers sorted descending, slump drivers sorted ascending by DiD estimate
- JSON serialization uses custom NpEncoder to handle numpy types
- Robust error handling: skips categories with insufficient data, handles singular matrices, validates variance before regression

## Output Files (saved to /app/output/)

1. `survey_cleaned.csv` - Cleaned survey data
2. `amazon-purchases-2019-2020-filtered.csv` - Cleaned purchase data
3. `category_anomaly_index.csv` - Anomaly scores (Category, Anomaly_Index)
4. `survey_feature_engineered.csv` - Engineered features
5. `user_category_period_aggregated_intensive.csv` - Intensive margin panel
6. `user_category_period_aggregated_extensive.csv` - Extensive margin panel
7. `causal_analysis_report.json` - Final DiD analysis results