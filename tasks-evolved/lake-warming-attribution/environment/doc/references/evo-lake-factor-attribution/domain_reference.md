# Domain Reference for evo-lake-factor-attribution

**Responsibility**: ML-based feature importance extraction, manual category mapping of all predictor variables, aggregation of importance by category, identification of the single most important category, and CSV output.

**Key functions to implement**: train_random_forest, compute_feature_importances, map_features_to_categories, get_dominant_category, save_dominant_factor

---

## 4. Driving Factor Attribution via `scikit-learn` (Version 1.5.2)


Once a warming or cooling trend is established, the next analytical requirement is understanding *why* the temperature is changing. We utilize machine learning to model water temperature against environmental predictors, allowing us to extract "feature importances."

## 5. Overcoming Pitfalls: Multicollinearity and Permutation Importance



## 6. Categorization of Driving Factors


To make environmental attribution actionable, it is standard practice to aggregate dozens of individual variables into overarching physical or societal themes. These broadly fall into four categories: Heat, Flow, Wind, and Human.