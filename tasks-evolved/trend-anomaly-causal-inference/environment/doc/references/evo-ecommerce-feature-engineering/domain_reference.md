# Domain Reference for evo-ecommerce-feature-engineering

**Responsibility**: All feature engineering on survey data, creation of panel datasets (intensive and extensive margin), and output of survey_feature_engineered.csv, user_category_period_aggregated_intensive.csv, and user_category_period_aggregated_extensive.csv.

**Key functions to implement**: engineer_survey_features, encode_ordinal_features, encode_nominal_features, bin_continuous_variables, create_intensive_margin_panel, create_extensive_margin_panel, assign_period_labels

---

## 2. Feature Engineering on Survey/Demographic Data (`scikit-learn` 1.8.0)


Feature engineering transforms raw demographic survey variables into numerically consumable inputs for causal regressions. `scikit-learn` 1.8.0 provides highly optimized tools for this process.

### 2.1 Handling Categorical Variables

There is a fundamental difference between `OneHotEncoder`, `OrdinalEncoder`, and `LabelEncoder` in `scikit-learn`. 

*   **`LabelEncoder`:** Strictly designed for encoding **target labels** (`y`), not input features (`X`) [cite: 4]. Using it for independent variables is an anti-pattern.
*   **`OrdinalEncoder`:** Used for features with an inherent rank or order (e.g., Income Brackets, Education Levels) [cite: 5].
*   **`OneHotEncoder`:** Used for nominal features without an inherent order (e.g., Region, Favorite Color) [cite: 6]. In versions post 1.2 (including 1.8.0), the parameter `sparse` was deprecated in favor of `sparse_output` [cite: 7]. To output standard arrays suitable for pandas DataFrames, use `sparse_output=False` [cite: 6, 7].

### 2.2 Binning Continuous Variables

Continuous demographic variables, like `Age`, often exhibit non-linear effects and are better transformed into categorical bins using pandas.

```python
def bin_age(df: pd.DataFrame) -> pd.DataFrame:
    bins = [cite: 1, 8, 9]
    labels = ['<18', '18-34', '35-54', '55+']
    df['Age_Group'] = pd.cut(df['Age'], bins=bins, labels=labels, right=False)
    return df
```

### 2.3 Preserving Identification Columns

When pushing data matrices through `scikit-learn` transformers, the output strips away indices and metadata (returning a NumPy array). Always ensure that operations are conducted by aligning indices or preserving the `Survey_ResponseID` outside of the transformation matrix, as shown in the `pd.concat` step in the One-Hot encoding snippet utilizing `index=df.index`.

---

## 3. Aggregation Patterns for User-Category-Period Data


To prepare the dataset for causal inference (Difference-in-Differences), the transaction log must be transformed into a panel dataset. This requires aggregating data to the User-Category-Period level.

### 3.1 Defining the Temporal Periods

DiD requires a clearly demarcated baseline (pre-treatment) and post-treatment period. For anomaly tracking and causal inference concerning a specific shock (e.g., the March 2020 COVID-19 pandemic onset), periods must be mapped correctly.

```python
def assign_periods(df: pd.DataFrame, treatment_date: str) -> pd.DataFrame:
    """Assigns binary Post indicator: 0 for Baseline, 1 for Treatment Period."""
    cutoff = pd.to_datetime(treatment_date)
    df['Post'] = (df['TransactionDate'] >= cutoff).astype(int)
    return df
```

### 3.2 Intensive vs. Extensive Margin Aggregations

In labor and trade economics, responses to shocks are decomposed into intensive and extensive margins [cite: 10, 11]. In e-commerce:
*   **Extensive Margin:** Does the user purchase within the category at all? This is a binary outcome (1 = purchased, 0 = did not purchase) calculated across the **entire at-risk population** [cite: 9, 10].
*   **Intensive Margin:** Among the users who *did* purchase, how much did they spend? This is a continuous outcome calculated only over the subset of users with spend > 0 [cite: 8, 12].