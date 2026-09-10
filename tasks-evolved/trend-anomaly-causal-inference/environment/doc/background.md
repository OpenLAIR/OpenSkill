# Python Utility Module for E-commerce Anomaly Detection and Causal Inference: A Comprehensive Guide

**Key Points:**
*   Building robust e-commerce analytical pipelines requires carefully integrating data cleaning, anomaly detection, and causal inference techniques.
*   Recent library updates, such as `pandas` 2.3.3 and `scikit-learn` 1.8.0, introduce breaking changes that necessitate updated coding paradigms.
*   Facebook Prophet (v1.2.1) serves as an effective tool for counterfactual prediction, though handling its logging backend requires specific configurations.
*   Difference-in-Differences (DiD) models using `statsmodels` (v0.14.6) elegantly estimate causal impacts by separating intensive (spend volume) and extensive (purchase propensity) margins.

**Introduction to the Technical Landscape**
Developing a Python utility module for e-commerce anomaly detection and causal inference is a complex undertaking that bridges data engineering and advanced econometrics. The process generally begins with the ingestion of noisy transaction and survey data, which must be systematically cleaned and structured. Analysts then frequently employ forecasting models to detect anomalies—deviations from expected trends—often utilizing Facebook Prophet to generate baseline expectations, or "counterfactuals." Following anomaly detection, causal inference frameworks like the Difference-in-Differences (DiD) method help isolate the impact of specific demographic or behavioral traits on consumer behavior. 

**Addressing Analytical Complexities**
It seems likely that handling this pipeline requires navigating several nuanced technical challenges, particularly given the rapid evolution of the Python data science ecosystem. Breaking changes in `pandas` 2.x, the deprecation of legacy methods in `scikit-learn`, and the nuances of the `cmdstanpy` backend in Prophet all present potential stumbling blocks. This guide aims to provide a comprehensive, academically rigorous breakdown of each component, ensuring that practitioners can confidently build stable, scalable, and statistically sound analytical pipelines.

---

## 1. Data Cleaning Patterns for Dirty E-commerce & Survey Data (`pandas` 2.3.3)

The foundation of any robust e-commerce pipeline is pristine data. In `pandas` version 2.3.3, data cleaning strategies must account for modern updates, particularly the transition toward the PyArrow backend for strings, which significantly enhances performance but alters traditional `object` type paradigms [cite: 1, 2].

### 1.1 Deduplication Strategies
Duplicate records frequently plague e-commerce logs due to retry mechanisms, browser refreshes, or faulty ETL processes. The `DataFrame.drop_duplicates()` method remains the standard, but it must be applied with precision.

*   **Identifying Duplicates:** Do not drop duplicates blindly across all columns. Specify the `subset` parameter to define what constitutes a true duplicate (e.g., `['TransactionID', 'ProductID']`).
*   **Keeping specific records:** Use the `keep` parameter (`'first'`, `'last'`, or `False`) to determine which instance is retained. For instance, if an updated transaction overwrites an older one, `keep='last'` combined with prior sorting by `Timestamp` is essential.

```python
import pandas as pd

def deduplicate_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicates transaction data keeping the latest update."""
    df_sorted = df.sort_values(by=['TransactionID', 'Timestamp'])
    return df_sorted.drop_duplicates(subset=['TransactionID', 'ProductID'], keep='last')
```

### 1.2 Handling Missing Values
In `pandas` 2.3.3, missing values behave slightly differently depending on the backend. When utilizing PyArrow-backed strings, missing values are standardly represented as `np.nan` [cite: 2], though `pd.NA` may appear in nullable extension types.

*   **Numeric Columns:** Use `fillna(0)` for continuous variables where a null implies zero action (e.g., `Total_Spend`). Use `.dropna(subset=['Price'])` if the price is an essential missing attribute.
*   **Categorical Columns:** Fill missing categories with an explicit placeholder using `fillna('Unknown')` or `fillna('Not_Provided')` to retain these records in demographic stratifications.

### 1.3 Inconsistent Formatting and String Normalization
With the shift in pandas toward a dedicated `str` data type backed by PyArrow (often activated via `pd.options.future.infer_string = True` in early 2.x versions and defaulted in 3.0 [cite: 2, 3]), string operations are faster but strictly require string inputs.

```python
def clean_strings(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    for col in columns:
        # Lowercase, strip whitespace, and title-case for standardization
        df[col] = df[col].astype("string").str.strip().str.lower().str.title()
    return df
```

### 1.4 Date Parsing with Coercion
E-commerce data often contains mixed date formats (e.g., `MM-DD-YYYY` vs. `YYYY/MM/DD`). Utilizing `pd.to_datetime()` with `errors='coerce'` converts unparseable dates to `NaT` (Not a Time) rather than failing the entire pipeline. The `format="mixed"` parameter (introduced in modern pandas) or explicit parsing functions can resolve discrepancies.

```python
df['TransactionDate'] = pd.to_datetime(df['DateString'], errors='coerce', format='mixed')
df = df.dropna(subset=['TransactionDate']) # Drop rows with unparseable dates
```

### 1.5 Cleaning Price and Monetary Columns
Price columns scraped or exported from legacy systems often arrive as strings prepended with currency symbols and containing commas.

```python
def clean_monetary_column(series: pd.Series) -> pd.Series:
    """Removes currency symbols and converts to float."""
    clean_series = series.astype(str).str.replace(r'[\$,]', '', regex=True)
    # Convert to float, coercing remaining errors to NaN
    return pd.to_numeric(clean_series, errors='coerce').fillna(0.0)
```

### 1.6 Extracting Product Categories from Hierarchies
Amazon and other e-commerce datasets frequently provide categories as a hierarchical string (e.g., `Electronics > Computers > Laptops`). Extracting the top-level category is critical for aggregate analysis.

```python
def extract_top_category(df: pd.DataFrame, col: str = 'CategoryTree') -> pd.DataFrame:
    """Extracts the root category from a delimited string."""
    df['TopCategory'] = df[col].astype("string").str.split(' > ').str
    return df
```

### 1.7 Merging Transaction and Survey Data
Merging requires matching keys. Survey platforms (like Qualtrics) might export Respondent IDs as strings, while backend databases export User IDs as integers. 

```python
def merge_survey_transactions(transactions: pd.DataFrame, survey: pd.DataFrame) -> pd.DataFrame:
    # Ensure join keys share the same data type (string is safest for alphanumeric IDs)
    transactions['UserID'] = transactions['UserID'].astype("string")
    survey['RespondentID'] = survey['RespondentID'].astype("string")
    
    # Left join to keep all transactions, even if the user didn't take the survey
    merged = pd.merge(
        transactions, 
        survey, 
        left_on='UserID', 
        right_on='RespondentID', 
        how='left'
    )
    return merged
```

---

## 2. Feature Engineering on Survey/Demographic Data (`scikit-learn` 1.8.0)

Feature engineering transforms raw demographic survey variables into numerically consumable inputs for causal regressions. `scikit-learn` 1.8.0 provides highly optimized tools for this process.

### 2.1 Handling Categorical Variables
There is a fundamental difference between `OneHotEncoder`, `OrdinalEncoder`, and `LabelEncoder` in `scikit-learn`. 

*   **`LabelEncoder`:** Strictly designed for encoding **target labels** (`y`), not input features (`X`) [cite: 4]. Using it for independent variables is an anti-pattern.
*   **`OrdinalEncoder`:** Used for features with an inherent rank or order (e.g., Income Brackets, Education Levels) [cite: 5].
*   **`OneHotEncoder`:** Used for nominal features without an inherent order (e.g., Region, Favorite Color) [cite: 6]. In versions post 1.2 (including 1.8.0), the parameter `sparse` was deprecated in favor of `sparse_output` [cite: 7]. To output standard arrays suitable for pandas DataFrames, use `sparse_output=False` [cite: 6, 7].

#### Ordinal Encoding Example
For ordered variables, it is crucial to pass the explicit order of categories; otherwise, the encoder defaults to lexicographical sorting.

```python
from sklearn.preprocessing import OrdinalEncoder

def encode_income(df: pd.DataFrame) -> pd.DataFrame:
    income_order = ['Low', 'Medium', 'High']
    encoder = OrdinalEncoder(categories=[income_order])
    
    # Reshape is required as sklearn expects 2D arrays
    df['Income_Encoded'] = encoder.fit_transform(df[['IncomeBracket']])
    return df
```

#### One-Hot Encoding Example
```python
from sklearn.preprocessing import OneHotEncoder

def encode_nominal_features(df: pd.DataFrame, categorical_cols: list) -> pd.DataFrame:
    # Set sparse_output=False to yield a dense numpy array
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore', drop='first')
    encoded_array = encoder.fit_transform(df[categorical_cols])
    
    # Retrieve new feature names
    feature_names = encoder.get_feature_names_out(categorical_cols)
    
    # Create a DataFrame and concatenate
    encoded_df = pd.DataFrame(encoded_array, columns=feature_names, index=df.index)
    return pd.concat([df, encoded_df], axis=1).drop(columns=categorical_cols)
```
*Note: We use `drop='first'` to avoid perfect multicollinearity (the dummy variable trap) which causes singular matrix issues in OLS regressions.*

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

#### Creating the Cross-Product Panel (Extensive Margin Base)
To evaluate the extensive margin, we need records for users even when they spent $0. This requires a Cartesian product (cross join) of all unique users and categories for both pre and post periods, followed by a left join to the actual aggregated data.

```python
import numpy as np

def create_panel_data(df: pd.DataFrame, all_users: pd.Series) -> pd.DataFrame:
    categories = df['TopCategory'].unique()
    periods = [cite: 13] # 0: Pre, 1: Post
    
    # Create MultiIndex of all combinations
    idx = pd.MultiIndex.from_product(
        [all_users, categories, periods], 
        names=['UserID', 'TopCategory', 'Post']
    )
    base_panel = pd.DataFrame(index=idx).reset_index()
    
    # Aggregate actual spend
    spend_agg = df.groupby(['UserID', 'TopCategory', 'Post'])['Total_Spend'].sum().reset_index()
    
    # Merge and fill NaNs with 0
    panel = pd.merge(base_panel, spend_agg, on=['UserID', 'TopCategory', 'Post'], how='left')
    panel['Total_Spend'] = panel['Total_Spend'].fillna(0.0)
    
    # Extensive margin indicator
    panel['Has_Purchase'] = (panel['Total_Spend'] > 0).astype(int)
    
    return panel
```

---

## 4. Facebook Prophet for Counterfactual Prediction & Anomaly Detection

To identify which categories experienced surges or slumps, we build a counterfactual model. The counterfactual answers the question: *What would the daily sales have been in March 2020 if the prior trends had simply continued?* We use Facebook Prophet version 1.2.1 for this time series forecasting.

### 4.1 Prophet API in v1.2.1
The correct import path in modern versions is `from prophet import Prophet` (the legacy `fbprophet` is obsolete) [cite: 14]. 
Prophet is strict about data formatting:
1.  The date column must be named precisely `ds` and be of type datetime or string parseable as a date.
2.  The target metric column must be named precisely `y` and be numeric [cite: 15, 16].

### 4.2 Handling Prophet's Logging Output
A common edge case in Prophet v1.2.1 is excessive and unsuppressible logging generated by the underlying `cmdstanpy` backend during optimization. Standard arguments like `verbose=False` often fail to suppress these logs [cite: 17]. The most effective solution is to disable the `cmdstanpy` logger at the Python logging level [cite: 14, 18].

```python
import logging
from prophet import Prophet

# Suppress verbose optimization logs from cmdstanpy
logging.getLogger("cmdstanpy").disabled = True
```

### 4.3 Building the Counterfactual Model
To build a counterfactual for an anomaly occurring in March 2020, we filter the training data to everything *before* March 1, 2020.

```python
def fit_predict_prophet(df_daily: pd.DataFrame, cutoff_date: str, forecast_periods: int) -> pd.DataFrame:
    """
    df_daily must have 'ds' (Date) and 'y' (Sales).
    """
    # 1. Split data into training (historical)
    train_df = df_daily[df_daily['ds'] < cutoff_date]
    
    # 2. Instantiate and fit model
    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False
    )
    m.fit(train_df)
    
    # 3. Create future dataframe for the duration of the anomaly period
    future = m.make_future_dataframe(periods=forecast_periods, freq='D')
    
    # 4. Generate prediction
    forecast = m.predict(future)
    
    return forecast
```

### 4.4 Extracting Intervals and Computing the Deviation Index
Prophet's `.predict()` outputs a DataFrame containing `yhat` (the point forecast), `yhat_lower` (lower bound of uncertainty), and `yhat_upper` (upper bound of uncertainty) [cite: 16].

We define an anomaly by comparing the *actual* sales during the treatment period to these predicted counterfactuals. To normalize across categories with different sales volumes, we can compute a **Deviation Index**.

A statistically sound formulation scales the residual (actual minus predicted) by the width of Prophet's confidence interval. If the actual value falls within the interval, the index is close to 0. If it exceeds the upper bound, it scales rapidly toward 100.

\[ \text{Deviation}_{t} = \frac{y_t - \hat{y}_t}{\hat{y}_{upper, t} - \hat{y}_{lower, t}} \]

```python
def calculate_deviation_index(actual_df: pd.DataFrame, forecast_df: pd.DataFrame) -> pd.DataFrame:
    # Merge actuals with forecasts on date
    merged = pd.merge(actual_df, forecast_df[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], on='ds', how='inner')
    
    # Calculate difference
    merged['Residual'] = merged['y'] - merged['yhat']
    
    # Calculate uncertainty width
    merged['Interval_Width'] = merged['yhat_upper'] - merged['yhat_lower']
    
    # Avoid division by zero
    merged['Interval_Width'] = merged['Interval_Width'].replace(0, 0.01)
    
    # Compute z-score-like deviation index
    merged['Deviation_Score'] = (merged['Residual'] / merged['Interval_Width']) * 100
    
    # Clip to -100 to 100 range for standardized reporting
    merged['Deviation_Index'] = merged['Deviation_Score'].clip(lower=-100, upper=100)
    
    return merged
```
Categories with high positive aggregate deviations are classified as "Surge" categories, while those with high negative deviations are "Slump" categories.

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

# Example formulation
# model = smf.ols(formula="Total_Spend ~ Age_18_34 * Post", data=df)
# results = model.fit()
```

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

## 6. Common Pitfalls and Edge Cases

Constructing this pipeline exposes developers to several intricate bugs tied directly to library versions.

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

# Usage
# json_string = json.dumps(did_results_dict, cls=NpEncoder)
```

### 6.2 `pandas` 2.3 Breaking Changes
If migrating code from older environments, several deprecated functions will fatally crash the pipeline in `pandas` 2.x:
1.  **`append()` removal:** `DataFrame.append()` was permanently removed. Pipelines must aggregate DataFrames in lists and use `pd.concat(list_of_dfs, ignore_index=True)` [cite: 26, 27].
2.  **`iteritems()` removal:** Generating `FutureWarning` in earlier versions, this has been removed. Use `DataFrame.items()` instead to iterate over columns [cite: 28].
3.  **Copy-on-Write (CoW):** `pandas` version 2.x began standardizing Copy-on-Write, shifting how `df.loc[:, :]` indexing operates. Chained assignments (e.g., `df[df['A'] > 0]['B'] = 1`) will fail. Always use `.loc` directly: `df.loc[df['A'] > 0, 'B'] = 1` [cite: 29, 30, 31].

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

### 6.4 Categories with Zero Sales in Time Series
If an e-commerce platform lists an inactive category, Prophet will attempt to fit a trend line to an array of zeroes. This causes the Box-Cox transformation (if used) to return mathematical domain errors or the multiplicative seasonality optimization to fail. Always assert that the `y` array contains a minimum total volume or non-zero variance before passing it to `Prophet.fit()`.

## 7. Conclusion
Building a causal anomaly detection pipeline requires bridging the gap between rigorous statistical definitions and optimal software engineering practices. By correctly structuring the Intensive and Extensive margins, manipulating modern `pandas` PyArrow text arrays, utilizing `statsmodels` Linear Probability Models for DiD frameworks, and correctly navigating the strict data requirements of Prophet, data teams can successfully isolate, measure, and explain complex e-commerce anomalies. Attention to version-specific edge cases—such as `cmdstanpy` logging, `pandas` deprecations, and NumPy JSON serialization—ensures that the utility module remains stable, reproducible, and ready for deployment in production environments.

**Sources:**
1. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbOM0q-z6mMuokG-Sr4RVehgB1IOgNQrIDD4RDXtsCnciqSH4RBsFsT9vbiYCfg_0lV2EPUnZ7OsL9EI3rTDN1H10D8womOdW0C3zFVcHWPUZXYeJN5q6uiSkeKu1YsLiv74ja8sc7Q5GdnRfkd48N4QXaqOL1ZTWWtjgv60-SJaJBpO6de9ibeakFzpEY_Nr8y6Arbowd)
2. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFjj3F__8om9ogZcoxtbN0AT7lu7Lg5vyaBIiEnfY3s2JpNoahK64x7hHc97h8jmG_AHKm7ZoAk8S_QhNQQotYY9kVTjsYvCdbx6t4g4HOc7HOxXlzRqBSVKt0nDXyGJtwRcCArlSMRGA==)
3. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOTy7xqksyaLpixIr03Cymf_4uGMBNoX7LX2Rxvf6FHEnlq4UPv2_5olFMzHFVIiIQ0A9ST8kirXVH-dsqFex3HDL3b1x0aAaXQQBCpd9VhpRQx-P474a-PA-sZE3CSYOCOv2_5hWAy4xxmmk=)
4. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJZuctYc994zPMWwZej-yELaGMpR0Hm5nGeQX971RdAp06WqlL3yHheD6JwA0-8WAJCNacko3AP996yAqjG-QkafspcWnBmE0nPRwqkzYOh8S-D_h5P0o5hVmL91o1nOClXDXCUqhBgFmBAdsmD7IpB6LkXniMP0PeJMiWnSKe_SUSPDbnec6z9EZrZKCb)
5. [plainenglish.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFXG9skIMi87nrjg0-NV5SNbeLwe6Wt9sj24jOPfCQVeYdT3dLm6yo24m3weXytqJz9vRlsbJs76RTRCcEQEe7q65LD-ceWH3lt8Pb-HiE0gjYYPQtODTSTe92P-kqCm78GWrT09BIx6cgQVu0COYzDv7v1KOVSma6Z7GuL0EQWlotPykbJyxB1OVUSVQMeq2xaLjYwAOYVW7_yzLgW8K556qKdFQ==)
6. [apxml.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYFoMsL3dS3Vqu8E57o7cR6cxL8iquA9ZczdcV7ceZGqUItgVQ8TMSZWsGIikpGxc4oL60O8U6vLuF0RVZotceN_Oj5kB8y4wpaW-VpJqxLs9lKVpZ3PnAb8HHKmK-LwmeQO2KBcCysHtNeEUcKm3o7L3zgBm_W4GBBN9Q8gTjspqzriI93_mKmXYKuvxOVaDhVTq6-k23w0RNbT95QNxXNNA-wpxeYVioX37VnOlTh56cOiN2gWikVxIGRTnN5o0=)
7. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuMesuUoEsaO-dWKbG4VAHGQ4M5pHND_8xlZaJO_FYscpVFYLS7_dtvpAMnrNXOy2bdEyx3hdauc0CGA3F6tU_Wn6elK3DwdYL2megi76vMJ0Bxzab89u0wrt225d3IS26T-CuQwULiNzYZPfQAEa_CB_xOZU3KmZ0QpKlt1T9qccWmXe_ph-dmMYgDDDp7Q==)
8. [iza.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2U5tW_S5mXOUOQ5i3MVeIeyctVJxDigdjHq08bjTPumVnpJ87iL1hd-9moSPGpaIT6LAbk1WpnRLpNWp8pMsU2_voIkS7u377iHYIrZc1J4rp1xs=)
9. [stanford.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFBnSOPZReoyeAwsUDpv4MwrMJqy7XR-B4YjcyU8KKWhSlIZV44vSWocHYvoTGa079ifLl0tjzH4Nl9-XscjLrAB5_YzdDt-93uxmOlPf5QsJf5xu8M0StZNRigJ5g-xbtSFDQI0cWdk2jysw==)
10. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEM1zmyCxshtLu5GpczPjnhocrih7h0Rsmx3qZnqpPTxbaiHF0eXzd5sE1cJI0zFHJkvLfalvKnmgLun7VomqxCak8kuw1Vlg5DM1bdwbxzkybxPkL7SnsMfQgCvnLgc5P5gaZlKCaASJdqyOxqU7cvdRD1A5gFEsaTBfVk1iLM42P7gFBBK6rntpZhNJ7vWck8812Hf3QbnK1k4nC9U54aNu7Z45CwyfAo24Y8v7qOHHI-vPhUqJMsqg==)
11. [frbsf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZKicmxPNyi4pEGf_f4hOsDCAM5hXyGPxxxy5ZUBPcoSGikoQxVznRZUdnChLtAZqTOI1-mf3lQyaxL8Nl3jFkwzBwdvbq6PGt4rayfjmhLCPbzl1VLQMoTjBobrAMbw3-V4iMOnH1KjpJIQ==)
12. [klenow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGIY0T0Oo18l0-nm2pxBAsD63UrDi13FHMRzyCUQ-qICf-iI4QMzmi-dAc8F72fpYDQO4Sjduqp1IYdzhjiI5LMXMzM0NfKvWZhIFXwehKNOlh5cexow4nferwuS-jXzKE=)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0WfXM6iQeqGO9GQ6Y1T2VZ6W16XHN2OgOsIKJwoMgLFk6hWnCNscvS84bLOdBY59kt5UVrTftvYcYfGfDiH3g2nCougKgtiZ1qIxIz00_PEMua9DYQbAR-McS_JFppop6ksXsCRw4tcJ5eDLVslkasZljfACtg6PJkj1hwA3T4iJR7T_mwPq8fA5RLjHnOPTR-T7xgiHS6G1oFp_IPMlg)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_b2FFAUveaKb6dp_vUnkh65aTJdHCY6H4514kwBpizYm9A6X79lIlzEM5NU9lAE2SkMcfBO9a54Pr6mhX76T-a_nnMGS4Z61TO7X26jsoP1uADYKsEwq0fyreMTla63obvbHzuqMLWWzw0tKOv5aI-zTDQrGiQEbSFpkvw8zjSQRt9bsLHA==)
15. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE1ndrTduiG6U7bMvVeFaDUmK9xi1VLz8Iv2CvtkDNuAGkhYjWLdg1x7KLBjeM5voQTZsVk3gOg35guVE6SYSzBRnHirCcE_766xeURbkjqN89TejYSraOxTSANEQLz3j-7-tuz-PsLZeu1v6Pl)
16. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEyIxPov53fuZHfutTrDPxOYkhP-S_A9IOg9USMTk8NlmLON4yo8mKxQrwu5qMJ8neYexVVpQpbTk6F4UmhcJqJuNDTFVXNt1JcmDGLMImyImAePUGqtmIKJar-6R_AiW9Gs5To_9gHJKwbtePDB70fW43d9Z2880sFL-kDr3rGbDo2_NRcP7kp9K7iJw-DK_hQvy3vq9bWsTJbBhJprPER8plD)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1uF7ZgINHbwo0tSC99to49-aEVCBCg7daCxbWBTiIFvhuYqFv2XrsplU5Uu29SMK3pn2HwJPLww3b7eX2s3cU5xlKPZOz0Vq2uIgbLEMhYjzpewYrH8zA1DnZ9pSaBcIEyirhGQyYQcBxhls1zhVSH4-IVOTzRRA4iRrRYo1WeL2gWmvj-Q==)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPlztqEqiLuo9wxaLCTDDkqhhDPeqawxdRVloJWl5nxpPN0e7xsL1ouYBqHbbjT4R-7QyQZHNce00mDhegXlzM3Ox3rpa3ou8NeNTIs2Y_Hk9PwRuvhyWbnUr7QChcRNT_xr7coODuAdgcAKhQ6l2AvKCDFDsH2DP63RP6PnZcUXmrOoicpmxxvM-j)
19. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEoY7OStoNkl-C-7iorPLThg_6BxmORuXoHY2ltXphyaqUp5SYh_eKrd44Z4V4OUdnEQz6lyFssLXfnk0U7PgwfJoICenL7QgTyRQ5AMPb8XL6KdTQtsj4YSsy8rCUTj0LEWFcVjjDWWZWPZZRivxpP2603BNcUhMBy_4WYf-JH1EC6_GnUk_wN7nZ8N3isa7CyEYZlA0YG9XkIwmViDEVOwY0D)
20. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHsYe1_kmf-iN23U03MqnPLr7AJP48WYPndPyeRIhIYNrhtSD3kTdLMZSoc68-YrZ4joq5VPb1WE9DwQKXMJTs4cZSvVvOMiZjsP2UTWo7AaDQEVwppFdPF9uSoFKt0qUhAGYVO93LVBnV9NU41loEbdNyDvJmVAxqGtIcNghjEftuL5xHhUSKrOrYTJV0BDtssdwChDSc3yM-vd6CNOFTuaABibdk7oTMbYYxRTEIEErXPzwl7H09r6BM41IttkbKZur-sk_NiE2zF)
21. [damianclarke.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQELZ6CzKqq3MmyjogF4koB1ADkHUWjwch4c_33tlj474znGeorw9JB5c3HliXxPi9dfQJBkaS8jNHR3n0c9jzMZn3RZzenLKmHPcauqFxgPzBfJZsCXYjk0O83e8C0C4lGhuCMa3zHzXsyTYQbORUCEuD4=)
22. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF8hCJ1V0GyKALCQWgnCW76RdzYVAjPOLBRrsb7haXbFS5vuKHkXj8B7jNq0saVxrMDTreZeN758jjnfuZTEEOoP9SlsvBLMxE7dvTtpfdU56FoRdkZ0-SoPIDkm1TXPuLSllHK62nrU7zffx7d-EXCLB1ywroQi7c2ZfPTRQ==)
23. [hanarosg.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHnUTr-JADCARF4_nXJx44u_0_EZirrSTa7egwUExtQODkQazt2i54SlQ7MWS7GIcM_ZaOtB0jTve-Ybgn04XQB3bJ8o4yJ4CpsGXiJW-u8knXgAZ75-fSBEPnUEi6ltAy5uTwoOFmFrE7TAEu6A==)
24. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEouf4KxYWYPBr-aQq7454UG_BOvWG_NvxdBkKjzw5ZTNWGbTZV2nWj9hwIBQISnImiYLvj2OEOHSLRfXmveFIRi-QRfigMa338hVAu0DM2RKgbLcCvMyisn9lhYja9vq8=)
25. [codemia.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGbAsAho1-pw6G_HDMAVUgKrjwBD22U3zbZw9Bxm-A-yerI1w_QXz4A5Hu6XDo_FE11ETOZGEdLKFs_I4KbJjHS9NrHpY8PyuluB_HAKWEZhUO-0HZn0l4RUB3gwlr8MT7M_3GVJJ2lWxf6cUugUEc62GwSFu9KpzffD-6v8zd-iZ2Vk0EbrrzJc1Fl7UAVGsrxJhtUZE_mVewIOA==)
26. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFuZ2UUPo03jDNuZ8llMZBX_PYsNQJafRP0C2X-BA2V-9T9jludAwLmDFOFBN_GjvUbjId8dccaHKt-P4Z7lezxba1wgF6UyLbc7NDXPamlxLObQCdObQacIrW7GMv1o4cr7DqTi4=)
27. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGARRzWQ-9bOn8Y0hUXxDCm04IQbdrRDkJStFiO-1xAPug6Z0w_zeupFx2Gi85R_rf-IYbugL42PmcST6U4IbEIjjPmkcK-C-yedtJPjKDcnd_5vtvGbpopIIa5eRDqXACrYRR98ezT_JN95lMr8IJs769VFf6hy_DWMoVxRmeneVjlcfeJhusbfFPnonAPxuF5pNAOuB__fWhaL_kuHi6MDyL_VwUDJe0eyghBU9Gut0BlUDhpUA==)
28. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHci5vIu6Zn3rUMv61TbANxAScQx0TDw4afp2kxu1zRXikaFTMqJPMmVuEDxbn7dpvphynOMMClcV2Ey3YaOKg3TV27W5CnMU2hTo16N6ccSUorY0LRlDWc2ZGkEEiETtmKJk6rBJ0L9Hdnt2YFzRujAO4yj6-661I_wmXGWZbUg9nfEIw5kqxKq88JhiDE_6RLxqvWoGvKmughFL2qb_OZKhAtWeozJqZ8YII6XQ==)
29. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGWsDTLstxfE1VNT7rEyeVYzQmkeRQIW0-d4eoVdPSig3nkflyZS6iyVesw2MBRnDR-QOx4dgzAyoQFSwO38sAAnzKxJTi_qj20YAmgg2aq6Ff6h7ST-b0S-UtsxQ3SYuYDcPWnQvbP1jFCg4mo)
30. [algorithmus-schmiede.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGr0gNM9N6iNyH8gbHFVEE4ZOz7rvwV1J6RPE_fOm68ME_aLK38yNSGV_UDcE1gBI7Nfs_aJ1raUFevFCLF1PjcrlfaBBBpKVK1NJyshrEWhQhOc5jpoDNSkRsUq6eolCIEEM5YKYP27QhFW_p6r9LQX0XMvMOQcYNUU2bKNjH7Lg==)
31. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEygi1AzUYL64JJ7UCwUGeblHoF3l53waH9u5GWJyN6gWM83lxkL1fZBLG5fn4UmQAH3OI9RkycbgerWKKCAidJT4EhOnf_c5lJGAInaTmSoacLgKg0dOh9h3iqxAOTLWWf05yDGBsHRClPmyeTzKMdA9nKLe_VuDuEWCivSHaEKOtq-uOiILxcHDKz21jg9w==)
