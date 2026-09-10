# Skill Creation Plan

**Task**: Analyze lake water temperature for long-term warming trends and identify the most important driving factor category (Heat/Flow/Wind/Human) from climate, hydrology, and land cover data.

**Rationale**: The task has two distinct analytical phases: (1) trend detection using Mann-Kendall statistics, and (2) driving factor attribution using ML-based feature importance with category aggregation. A data loading/merging skill is foundational to both. Three skills cleanly separate data pipeline, trend analysis, and factor attribution concerns.

**Number of skills**: 3

---

## Skill 1: evo-lake-data-pipeline

**Description**: Loads, merges, and preprocesses the four CSV datasets (water_temperature, climate, land_cover, hydrology) into analysis-ready DataFrames. Handles date parsing, temporal alignment, annual aggregation, and NaN management.

**Responsibility**: All data I/O, merging, resampling, and cleaning. Produces unified DataFrames ready for trend analysis and factor attribution.

**Key functions**: `load_all_datasets`, `merge_datasets`, `compute_annual_means`, `get_feature_columns_by_category`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-lake-data-pipeline/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-lake-trend-analysis

**Description**: Performs non-parametric Mann-Kendall trend detection on lake water temperature time series using pymannkendall, outputting slope and p-value to trend_result.csv.

**Responsibility**: Trend detection on water temperature series, handling autocorrelation via modified MK tests, NaN removal, and CSV output of slope and p-value.

**Key functions**: `run_mann_kendall_trend`, `save_trend_result`

**Depends on**: evo-lake-data-pipeline


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-lake-trend-analysis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-lake-factor-attribution

**Description**: Trains a Random Forest model to determine feature importances of environmental predictors, maps features to categories (Heat/Flow/Wind/Human), sums contributions per category, and outputs the dominant factor to dominant_factor.csv.

**Responsibility**: ML-based feature importance extraction, manual category mapping of all predictor variables, aggregation of importance by category, identification of the single most important category, and CSV output.

**Key functions**: `train_random_forest`, `compute_feature_importances`, `map_features_to_categories`, `get_dominant_category`, `save_dominant_factor`

**Depends on**: evo-lake-data-pipeline


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-lake-factor-attribution/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
