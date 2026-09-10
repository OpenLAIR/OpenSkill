# Domain Reference for evo-lake-data-pipeline

**Responsibility**: All data I/O, merging, resampling, and cleaning. Produces unified DataFrames ready for trend analysis and factor attribution.

**Key functions to implement**: load_all_datasets, merge_datasets, compute_annual_means, get_feature_columns_by_category

---

## 6. Categorization of Driving Factors


To make environmental attribution actionable, it is standard practice to aggregate dozens of individual variables into overarching physical or societal themes. These broadly fall into four categories: Heat, Flow, Wind, and Human.

## 7. Data Pipeline Patterns using `pandas` (v2.2.3)


Robust data engineering is paramount. The following pipeline pattern demonstrates loading disparate files, unifying their time indices, grouping data annually, and mapping importance scores to predefined categories.