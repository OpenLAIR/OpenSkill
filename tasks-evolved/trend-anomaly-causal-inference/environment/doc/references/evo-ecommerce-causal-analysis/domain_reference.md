# Domain Reference for evo-ecommerce-causal-analysis

**Responsibility**: All DiD regression modeling, extraction of top 3 intensive and extensive margin drivers per category, result sorting by contribution strength, JSON report generation with proper NumPy serialization.

**Key functions to implement**: run_intensive_margin_did, run_extensive_margin_did, extract_top_drivers, build_causal_report, save_report_json, NpEncoder

---

## 5. Difference-in-Differences (DiD) Causal Analysis (`statsmodels` 0.14.6)


Once anomalies are detected, the next step is determining *who* drove these anomalies. Difference-in-Differences (DiD) allows us to estimate the causal effect of a specific demographic feature (the `Treatment`) on purchasing behavior during the shock (the `Post` period).

### 5.1 DiD Theory and Formula Definition

The canonical DiD regression model takes the form:
\[ Y_{it} = \beta_0 + \beta_1 \text{Treatment}_i + \beta_2 \text{Post}_t + \beta_3 (\text{Treatment}_i \times \text{Post}_t) + \epsilon_{it} \]

*   \( \text{Treatment}_i \): Indicator for the demographic group (e.g., `Age_18_34`).
*   \( \text{Post}_t \): Indicator for the post-shock period (e.g., March 2020 onward) [cite: 19].
*   \( \text{Treatment}_i \times \text{Post}_t \): The interaction term. Its coefficient (\( \beta_3 \)) is the **DiD Estimator**, representing the isolated effect of the trait during the shock [cite: 19].

In `statsmodels` 0.14.6, the `formula.api` handles the interaction automatically using the `*` operator in Patsy formulas [cite: 19]. Writing `Treatment * Post` automatically expands to `Treatment + Post + Treatment:Post` [cite: 20].

### 5.2 Statsmodels OLS API

The `statsmodels.formula.api.ols` function requires a formula string and a pandas DataFrame.
```python
import statsmodels.api as sm
import statsmodels.formula.api as smf

### 5.3 Intensive Margin DiD (Univariate)

The intensive margin measures the change in the *amount spent* by users who were already going to purchase [cite: 10]. Consequently, this model is estimated **only on the subset of data where `Total_Spend > 0`**. 

In univariate DiD, we test one demographic feature at a time to profile specific user segments independently.

```python
def run_intensive_margin_did(panel_df: pd.DataFrame, feature_col: str) -> dict:
    """
    Runs DiD on Intensive Margin (Purchasers Only) for a single feature.
    """
    # Filter to purchasers
    purchasers = panel_df[panel_df['Total_Spend'] > 0].copy()
    
    # Construct formula
    formula = f"Total_Spend ~ {feature_col} * Post"
    
    # Fit OLS model
    model = smf.ols(formula=formula, data=purchasers)
    results = model.fit(cov_type='HC1') # Heteroskedasticity-robust standard errors
    
    # Extract DiD estimator (Interaction term)
    interaction_term = f"{feature_col}:Post"
    
    return {
        'Feature': feature_col,
        'DiD_Estimate': results.params.get(interaction_term, np.nan),
        'P_Value': results.pvalues.get(interaction_term, np.nan),
        'CI_Lower': results.conf_int().loc[interaction_term, 0] if interaction_term in results.conf_int().index else np.nan,
        'CI_Upper': results.conf_int().loc[interaction_term, 1] if interaction_term in results.conf_int().index else np.nan
    }
```

### 5.4 Extensive Margin DiD (Multivariate Heterogeneous)

The extensive margin models the *propensity to buy*—whether users entered or exited the market [cite: 10, 11]. This model uses the binary outcome `Has_Purchase` and is run on the **entire at-risk population** (including zeroes). 

Because outcomes are binary, estimating via OLS constitutes a Linear Probability Model (LPM) [cite: 21, 22]. While Logistic regression is theoretically preferable for binary outcomes, LPMs are standard in causal inference DiD contexts because interaction terms in non-linear models (Logit/Probit) are notoriously difficult to interpret as marginal effects.

A multivariate DiD includes multiple features simultaneously to account for confounding demographic factors.

```python
def run_extensive_margin_multivariate(panel_df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    """
    Runs Multivariate DiD on Extensive Margin (All Users) using a Linear Probability Model.
    """
    # Construct formula: Has_Purchase ~ Post + F1 + F1:Post + F2 + F2:Post ...
    formula_parts = []
    for f in feature_cols:
        formula_parts.append(f"{f} * Post")
        
    formula = "Has_Purchase ~ " + " + ".join(formula_parts)
    
    model = smf.ols(formula=formula, data=panel_df)
    results = model.fit(cov_type='HC1')
    
    # Extract results for all interaction terms
    metrics = []
    for f in feature_cols:
        interaction_term = f"{f}:Post"
        if interaction_term in results.params:
            metrics.append({
                'Feature': f,
                'DiD_Estimate': results.params[interaction_term],
                'P_Value': results.pvalues[interaction_term]
            })
            
    return pd.DataFrame(metrics)
```

### 5.5 Sorting Results by Contribution Strength

To derive business insights, we sort the DiD results:
*   **Surge Categories:** Sort by descending `DiD_Estimate`. The highest positive coefficients indicate demographic groups that disproportionately drove the spike.
*   **Slump Categories:** Sort by ascending `DiD_Estimate`. The most negative coefficients highlight the groups driving the decline.

---

### 6.1 JSON Serialization of NumPy Types

When exporting analytical results (such as DiD dictionaries or Prophet deviations) to an API or disk, `json.dump()` will immediately raise a `TypeError: Object of type int64 is not JSON serializable` if it encounters NumPy numbers [cite: 23, 24]. Standard Python JSON encoders do not recognize `numpy.int64` or `numpy.float64` classes [cite: 25].

**Solution:** Subclass `json.JSONEncoder` to map NumPy types to native Python types [cite: 13, 23].

```python
import json
import numpy as np

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

### 6.3 Sparse Binary Outcomes in `statsmodels`

When estimating Extensive Margin LPMs on highly granular product categories, you may encounter demographic segments where *no user made a purchase*. This leads to "perfect separation" or singular design matrices (`np.linalg.LinAlgError: Singular matrix`), causing `statsmodels` to fail.

**Prevention strategy:** Implement a threshold check before running OLS.
```python
def check_variance(df: pd.DataFrame, col: str) -> bool:
    return df[col].nunique() > 1

if not check_variance(panel_df, 'Has_Purchase'):
    print("Skipping category: No variance in target variable.")
```
Furthermore, `OneHotEncoder` parameters like `min_frequency` [cite: 7] can lump extremely rare categorical survey responses into an "Infrequent" bin, preventing sparse feature columns that cause collinearity failures.