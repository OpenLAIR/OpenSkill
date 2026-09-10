# Skill Creation Plan

**Task**: Clean e-commerce transaction and survey data, detect anomalous product category sales in March 2020 using Prophet counterfactuals, engineer demographic features, and run Difference-in-Differences causal analysis to identify demographic drivers of surges and slumps.

**Rationale**: The task has four distinct functional domains: (1) data cleaning/preparation, (2) time-series anomaly detection via Prophet, (3) feature engineering on survey data, and (4) causal inference via DiD. These map cleanly to four skills with clear dependency ordering—cleaning feeds all downstream steps, anomaly detection identifies target categories, feature engineering prepares demographic variables, and causal analysis combines everything.

**Number of skills**: 4

---

## Skill 1: evo-ecommerce-data-cleaning

**Description**: Utilities for cleaning and preparing dirty e-commerce transaction data and survey demographic data. Handles deduplication, missing values, inconsistent formatting, date parsing, monetary column cleaning, category extraction, and produces cleaned CSV outputs.

**Responsibility**: All data ingestion, cleaning, normalization, and output of survey_cleaned.csv and amazon-purchases-2019-2020-filtered.csv. No analytical computations.

**Key functions**: `clean_survey_data`, `clean_transaction_data`, `deduplicate_dataframe`, `clean_monetary_column`, `normalize_strings`, `parse_dates`, `extract_top_category`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-ecommerce-data-cleaning/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-ecommerce-anomaly-detection

**Description**: Utilities for detecting anomalous daily sales patterns per product category using Facebook Prophet counterfactual predictions. Computes a deviation index (-100 to 100) comparing actual March 2020 sales against Prophet forecasts trained on all prior history.

**Responsibility**: Time-series aggregation to daily category sales, Prophet model fitting per category, counterfactual prediction, deviation index calculation, and output of category_anomaly_index.csv.

**Key functions**: `aggregate_daily_category_sales`, `fit_prophet_counterfactual`, `calculate_deviation_index`, `compute_category_anomaly_scores`, `get_top_surge_slump_categories`

**Depends on**: evo-ecommerce-data-cleaning


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-ecommerce-anomaly-detection/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-ecommerce-feature-engineering

**Description**: Utilities for engineering features from cleaned survey/demographic data using scikit-learn encoders. Handles ordinal encoding, one-hot encoding, binning continuous variables, and producing the feature-engineered survey CSV and user-category-period aggregated panel datasets for DiD analysis.

**Responsibility**: All feature engineering on survey data, creation of panel datasets (intensive and extensive margin), and output of survey_feature_engineered.csv, user_category_period_aggregated_intensive.csv, and user_category_period_aggregated_extensive.csv.

**Key functions**: `engineer_survey_features`, `encode_ordinal_features`, `encode_nominal_features`, `bin_continuous_variables`, `create_intensive_margin_panel`, `create_extensive_margin_panel`, `assign_period_labels`

**Depends on**: evo-ecommerce-data-cleaning, evo-ecommerce-anomaly-detection


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-ecommerce-feature-engineering/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 4: evo-ecommerce-causal-analysis

**Description**: Utilities for running Difference-in-Differences causal analysis using statsmodels. Estimates intensive margin (univariate DiD on spend among purchasers) and extensive margin (multivariate heterogeneous DiD on purchase propensity) drivers for surge and slump categories, and outputs the final causal_analysis_report.json.

**Responsibility**: All DiD regression modeling, extraction of top 3 intensive and extensive margin drivers per category, result sorting by contribution strength, JSON report generation with proper NumPy serialization.

**Key functions**: `run_intensive_margin_did`, `run_extensive_margin_did`, `extract_top_drivers`, `build_causal_report`, `save_report_json`, `NpEncoder`

**Depends on**: evo-ecommerce-feature-engineering, evo-ecommerce-anomaly-detection


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-ecommerce-causal-analysis/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
