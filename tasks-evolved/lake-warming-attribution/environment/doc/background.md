# Comprehensive Utility Module Design for Lake Water Temperature Trend Analysis and Driving Factor Attribution

### Key Points
*   **Trend Detection:** The `pymannkendall` library offers robust non-parametric statistical methods to detect monotonic trends in environmental time series, with specialized modifications to account for serial correlation (autocorrelation).
*   **Alternative Parametric Approaches:** The `scipy.stats` library provides standard parametric options like Ordinary Least Squares (OLS) regression, though recent updates (version 1.14.1) deprecate older array-handling paradigms.
*   **Factor Attribution:** `scikit-learn` enables powerful factor attribution through Random Forest feature importances and standardized linear regression coefficients, helping quantify the relative impact of environmental drivers.
*   **Multicollinearity Challenges:** Research suggests that high correlation among environmental predictors complicates feature importance mapping, often necessitating advanced methods like permutation importance or hierarchical clustering.
*   **Data Pipelines:** `pandas` provides essential data wrangling capabilities required to merge disparate environmental datasets (climate, hydrology, land cover) and route them efficiently into modeling pipelines.
*   **Factor Analysis Limits:** While the `factor_analyzer` library can uncover latent variables statistically, manual deterministic categorization (e.g., Heat, Flow, Wind, Human) is generally preferred when specific physical mechanisms are being modeled.

### Methodological Complexity
Attributing changes in lake water temperatures to specific driving factors involves untangling interconnected physical, meteorological, and anthropogenic variables. It seems likely that traditional statistical methods alone may fail to capture non-linear relationships. Therefore, combining non-parametric trend analysis with machine learning attribution techniques represents a state-of-the-art approach to environmental data science.

### Technical Uncertainty
When identifying feature importances in complex ecosystems, absolute attribution percentages should be interpreted with caution. Variables like "solar radiation" and "air temperature" inherently co-vary. While algorithmic normalization provides clear mathematical percentages, the true physical contribution is inherently entangled. Analysts must balance statistical outputs with known thermodynamic mechanisms.

---

## 1. Introduction to Environmental Time Series Analysis

Lake water temperature is a critical indicator of ecological health, reflecting both localized anthropogenic impacts and broader climatic shifts. Developing a robust Python-based analytical utility requires two primary analytical phases:
1.  **Trend Detection:** Quantifying the historical direction and magnitude of temperature changes over time (e.g., degrees per decade).
2.  **Driving Factor Attribution:** Determining which external variables (e.g., rising air temperatures, urban development, changing inflows) are primarily responsible for the observed trends.

This report comprehensively details the implementation of a reusable Python utility module utilizing `pymannkendall` (v1.4.3), `scipy.stats` (v1.14.1), `scikit-learn` (v1.5.2), `pandas` (v2.2.3), and `factor_analyzer` (v0.5.1).

---

## 2. Non-Parametric Trend Detection: `pymannkendall` (Version 1.4.3)

The Mann-Kendall (MK) trend test is a non-parametric statistical technique used to detect monotonic trends in time series data without assuming an underlying normal distribution [cite: 1, 2]. The Python implementation `pymannkendall` brings together various MK test methodologies specifically engineered to address the complexities of environmental data [cite: 1]. 

### 2.1 API Reference and Exact Signatures
The `pymannkendall` library features multiple testing functions that share similar input parameters [cite: 1].

**Function Signatures:**
```python
pymannkendall.original_test(x, alpha=0.05)
pymannkendall.hamed_rao_modification_test(x, alpha=0.05, lag=None)
pymannkendall.yue_wang_modification_test(x, alpha=0.05, lag=None)
pymannkendall.seasonal_test(x, period=12, alpha=0.05)
```

**Parameters:**
*   `x`: A 1D array-like structure (e.g., a standard Python list, a `numpy` 1D array, or a `pandas.Series`) containing the time series data [cite: 1].
*   `alpha`: The significance level for the hypothesis test, defaulting to 0.05 [cite: 1].
*   `lag`: For tests handling serial correlation, this specifies the number of first significant lags. If `None`, the function automatically determines all significant lags [cite: 1].
*   `period`: Used strictly in seasonal tests (e.g., `seasonal_test`), defining the number of data points in a single seasonal cycle (e.g., 12 for monthly data) [cite: 1].

### 2.2 Return Value Structure
Every MK test in `pymannkendall` returns a Python `namedtuple` containing precise attributes. To answer the specific inquiry regarding attribute names:
*   The exact attribute name for the **Sen's slope** is `.slope` [cite: 1, 3].
*   The exact attribute name for the **p-value** is `.p` [cite: 1, 3].

The full structure of the returned `namedtuple` includes [cite: 1, 3]:
*   `trend`: A string indicating the trend direction (`'increasing'`, `'decreasing'`, or `'no trend'`).
*   `h`: A boolean (`True` or `False`) representing the rejection of the null hypothesis at the given alpha level.
*   `p`: The exact p-value of the significance test.
*   `z`: The normalized test statistic.
*   `Tau`: Kendall's Tau statistic.
*   `s`: Mann-Kendall's score (variance difference).
*   `var_s`: Variance of S.
*   `slope`: Theil-Sen estimator (the slope magnitude).
*   `intercept`: The intercept of the Kendall-Theil Robust Line.

### 2.3 Handling Autocorrelation: Selecting the Correct Test
Environmental time series data, particularly lake water temperatures, frequently exhibit serial autocorrelation (where today's temperature is dependent on yesterday's temperature). The original Mann-Kendall test assumes that all data points are independent; applying it to autocorrelated data falsely inflates significance, increasing the risk of Type I errors (false positives) [cite: 1, 4].

*   **`original_test`**: Use this strictly when observations are far apart in time (e.g., annual averages) and autocorrelation is confirmed to be absent [cite: 1, 4].
*   **`hamed_rao_modification_test`**: Recommended for time series demonstrating significant autocorrelation. Proposed in 1998, this test applies a variance correction approach to account for serial dependence, preventing false trend detection [cite: 1, 2].
*   **`yue_wang_modification_test`**: Another robust variance correction approach (proposed in 2004) specifically adjusting the variance of the Mann-Kendall statistic based on effective sample size [cite: 1, 2]. 

When examining monthly or daily water temperatures, `hamed_rao_modification_test` or `yue_wang_modification_test` are strictly necessary [cite: 4]. If strong periodic cycles dominate the data, `seasonal_test` must be utilized.

### 2.4 Handling Missing Data (NaNs) and Data Types
A critical pitfall when using `pymannkendall` is its interaction with missing data. The library expects a contiguous 1D array or a `pandas.Series`. If `NaN` values are present within the array, mathematical operations calculating the $S$ statistic fail or propagate `NaN` to the test results [cite: 5]. You **must** apply `.dropna()` to your `pandas.Series` before passing it to the function [cite: 4]. Alternatively, missing values must be imputed using interpolation methods [cite: 5]. Furthermore, passing an entire `pandas.DataFrame` is unsupported; you must pass a single column (a `Series`).

**Working Code Example:**
```python
import pandas as pd
import numpy as np
import pymannkendall as mk

# Simulated lake water temperature data with a NaN value
data = {'temp': [15.2, 15.5, np.nan, 15.9, 16.1, 16.0, 16.4, 16.8, 17.0, 17.2]}
df = pd.DataFrame(data)

# Pitfall avoidance: Drop NaNs and pass a 1D Series
clean_series = df['temp'].dropna()

# Execute the test
result = mk.original_test(clean_series)

# Extract specific attributes
slope = result.slope
p_value = result.p
trend_dir = result.trend

print(f"Trend: {trend_dir}, Slope: {slope:.4f}, p-value: {p_value:.4e}")
```

---

## 3. Parametric Linear Regression: `scipy.stats` (Version 1.14.1)

While non-parametric tests assess monotonic trends, parametric methods like Ordinary Least Squares (OLS) regression assume a linear relationship and normally distributed residuals. The `scipy.stats` library provides tools for this through the `linregress` function.

### 3.1 `scipy.stats.linregress` Return Types and Extraction
In SciPy 1.14.1, `linregress(x, y)` calculates a linear least-squares regression. The exact return type is a `LinregressResult` object [cite: 6]. 

**Attributes of `LinregressResult`:**
*   `slope`: Float representing the gradient of the regression line [cite: 6].
*   `intercept`: Float representing the y-intercept [cite: 6].
*   `rvalue`: The Pearson correlation coefficient [cite: 6].
*   `pvalue`: The p-value for the Wald Test (testing if the slope is zero) [cite: 6].
*   `stderr`: Standard error of the estimated slope [cite: 6].
*   `intercept_stderr`: Standard error of the estimated intercept [cite: 6].

**Code Example:**
```python
from scipy import stats
import numpy as np

years = np.array()
temps = np.array([12.1, 12.3, 12.2, 12.5, 12.7, 12.9])

res = stats.linregress(years, temps)
print(f"Slope: {res.slope:.4f}, p-value: {res.pvalue:.4e}")
```

### 3.2 Important Deprecations in 1.14.1
A critical development in SciPy 1.14.0/1.14.1 is the deprecation of one-argument inference [cite: 7]. Previously, developers could pass a single 2D array of shape $(2, N)$ to `linregress`, and the library would infer the splitting of $X$ and $Y$ [cite: 6]. As of version 1.14, this behavior is deprecated, and you **must specify `x` and `y` as separate arguments** [cite: 6, 7, 8]. Failing to do so will result in errors in upcoming releases.

### 3.3 Alternatives: `kendalltau` and `theilslopes`
If `pymannkendall` is not desired, `scipy.stats` offers alternative non-parametric functions:
*   `scipy.stats.kendalltau(x, y)`: Computes Kendall's Tau correlation measure.
*   `scipy.stats.theilslopes(y, x)`: Computes the Theil-Sen estimator for a set of points. The return object is a tuple where the first element is the median slope. 

*Comparison Note:* `pymannkendall` provides a much more comprehensive framework specifically designed for environmental hydrology (incorporating seasonal and autocorrelation corrections) compared to the basic implementations in `scipy.stats`.

---

## 4. Driving Factor Attribution via `scikit-learn` (Version 1.5.2)

Once a warming or cooling trend is established, the next analytical requirement is understanding *why* the temperature is changing. We utilize machine learning to model water temperature against environmental predictors, allowing us to extract "feature importances."

### 4.1 Random Forest Regressor and `feature_importances_`
The `sklearn.ensemble.RandomForestRegressor` provides built-in feature importance based on Mean Decrease in Impurity (Gini importance) [cite: 9]. At each node split, the algorithm calculates how much a specific feature reduces the variance (impurity) of the target variable [cite: 9]. 

The attribute containing these values is `.feature_importances_`. By default, scikit-learn normalizes these values so that they sum to $1.0$ [cite: 9]. To convert them to relative percentage contributions, simply multiply by 100.

**Code Example:**
```python
from sklearn.ensemble import RandomForestRegressor
import pandas as pd

# Assume X contains predictors (air_temp, wind_speed, etc.), y contains water_temp
rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
rf_model.fit(X, y)

# Extract and format as percentages
importances = rf_model.feature_importances_
percent_contributions = importances * 100

# Create a ranking DataFrame
importance_df = pd.DataFrame({
    'Factor': X.columns,
    'Contribution (%)': percent_contributions
}).sort_values(by='Contribution (%)', ascending=False)
```

### 4.2 Standardized Linear Regression Coefficients
For a highly interpretable, linear alternative, `LinearRegression` can be used. However, because predictors have different physical units (e.g., watts per square meter for solar radiation vs. meters per second for wind), their raw regression coefficients cannot be directly compared. 

Using `sklearn.preprocessing.StandardScaler` transforms all features to have a mean of 0 and a standard deviation of 1. The resulting standardized coefficients ($ \beta $) represent the relative influence of each feature. 

**Code Example:**
```python
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import numpy as np

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

lr_model = LinearRegression()
lr_model.fit(X_scaled, y)

# Get absolute coefficients as raw importance
abs_coef = np.abs(lr_model.coef_)

# Normalize to sum to 100%
relative_importance_pct = (abs_coef / np.sum(abs_coef)) * 100
```

---

## 5. Overcoming Pitfalls: Multicollinearity and Permutation Importance

### 5.1 The Problem of Multicollinearity
In environmental datasets, predictors are intrinsically linked. High air temperatures often co-occur with high solar radiation and low cloud cover. When using `RandomForestRegressor`, this multicollinearity dilutes the `feature_importances_` [cite: 9, 10, 11]. The model will arbitrarily select one feature over another highly correlated feature to perform a node split, spreading the importance score across the correlated group. Consequently, truly important physical drivers might appear artificially weak [cite: 9, 10]. 

### 5.2 `permutation_importance` as a Solution
To mitigate bias toward high-cardinality features and verify true predictive power, `sklearn.inspection.permutation_importance` is utilized [cite: 9, 10]. Permutation importance is model-agnostic. It involves taking a trained model, systematically shuffling the values of one feature column at a time, and observing the drop in model performance (e.g., $R^2$ or Mean Squared Error) [cite: 9, 11]. A significant drop implies the feature is vital.

However, be warned: **permutation importance also struggles with multicollinearity** [cite: 9, 11]. If two features share identical information, permuting one may not impact the model's accuracy because the model simply relies on the un-permuted correlated feature [cite: 9]. Scikit-learn documentation explicitly recommends handling this by running hierarchical clustering on Spearman rank-order correlations and keeping only one feature per cluster prior to training [cite: 10, 12].

**Permutation Importance Code:**
```python
from sklearn.inspection import permutation_importance

# Calculate permutation importance
# n_repeats controls how many times the feature is shuffled to compute a stable mean
result = permutation_importance(rf_model, X, y, n_repeats=10, random_state=42, scoring='r2')

# result.importances_mean contains the average performance drop
perm_importances = result.importances_mean
perm_pct = (perm_importances / np.sum(perm_importances)) * 100
```

### 5.3 Reporting Precision Standards
When reporting analytical results, floating-point precision matters. For slopes representing degrees per year, 3 or 4 decimal places are standard (e.g., `0.0245 °C/yr`). For p-values, scientific notation is preferred for extremely small values (e.g., `4.2e-5`), while values above `0.001` are typically reported to three decimal places (e.g., `p = 0.034`).

---

## 6. Categorization of Driving Factors

To make environmental attribution actionable, it is standard practice to aggregate dozens of individual variables into overarching physical or societal themes. These broadly fall into four categories: Heat, Flow, Wind, and Human.

### 6.1 Definitions and Variable Mapping
*   **Heat (Thermodynamic forcing):** Variables governing the direct transfer of thermal and radiation energy to the water body [cite: 13].
    *   *Mapped Variables:* Air Temperature (Mean/Max/Min), Shortwave Radiation, Longwave Radiation, Solar Radiation, Cloud Cover, Relative Humidity [cite: 13, 14].
*   **Flow (Hydrological forcing):** Variables affecting the advection of heat via water mass movement and volume changes.
    *   *Mapped Variables:* Precipitation, Streamflow, Inflow volume, Outflow/Discharge, Groundwater recharge, Water Level/Depth.
*   **Wind (Mechanical forcing):** Variables driving turbulent mixing, evaporation, and stratification breakdowns [cite: 13].
    *   *Mapped Variables:* Wind Speed, Wind Direction, Wind Gust.
*   **Human (Anthropogenic forcing):** Variables capturing land-use alterations and urban heat island effects [cite: 13].
    *   *Mapped Variables:* Land Cover Change (%) [cite: 13], Urban Area expansion, Impervious Surface Area, Population Density, Industrial thermal discharges [cite: 13].

### 6.2 Using `factor_analyzer` vs. Manual Categorization
The `factor_analyzer` (v0.5.1) module executes Exploratory Factor Analysis (EFA), a statistical method to identify unobserved latent factors mapping to observed variables [cite: 15]. 

**API Usage:**
```python
from factor_analyzer import FactorAnalyzer
fa = FactorAnalyzer(n_factors=4, rotation='varimax')
fa.fit(X)
loadings = fa.loadings_
variances = fa.get_factor_variance() # Returns (SS Loadings, Proportion Var, Cumulative Var)
```

EFA groups variables purely based on mathematical correlation [cite: 16]. Consequently, if precipitation (Flow) mathematically correlates heavily with cloud cover (Heat), the algorithm might mistakenly fuse them into a single latent factor. Therefore, for environmental physical attribution, **manual categorization (grouping features based on first-principles physics) is heavily favored over unsupervised statistical grouping.** EFA is best reserved for psychological or survey data where underlying latent variables are entirely unknown [cite: 17].

---

## 7. Data Pipeline Patterns using `pandas` (v2.2.3)

Robust data engineering is paramount. The following pipeline pattern demonstrates loading disparate files, unifying their time indices, grouping data annually, and mapping importance scores to predefined categories.

### 7.1 Reading and Merging Time Series
Ensure that date columns are parsed immediately and set as the DataFrame index.

```python
import pandas as pd

# Read datasets
df_climate = pd.read_csv('climate.csv', parse_dates=['date'], index_col='date')
df_hydro = pd.read_csv('hydrology.csv', parse_dates=['date'], index_col='date')
df_land = pd.read_csv('land_cover.csv', parse_dates=['year'], index_col='year')

# Join daily data (climate and hydro) based on the exact date index
df_daily = df_climate.join(df_hydro, how='inner')

# Compute annual means for trend analysis using 'YE' (Year End) offset
df_annual = df_daily.resample('YE').mean()

# To join with land_cover data, extract the year from the DatetimeIndex
df_annual.index = df_annual.index.year
df_final = df_annual.join(df_land, how='inner')
```

### 7.2 Summing Feature Importances by Category
Once feature importances are calculated, mapping them to the predefined categories allows analysts to conclude, for example, "Heat accounted for 45% of the temperature variation."

```python
# Assuming importance_df has columns ['Factor', 'Contribution (%)']
category_map = {
    'air_temp': 'Heat', 'solar_rad': 'Heat',
    'inflow': 'Flow', 'precip': 'Flow',
    'wind_speed': 'Wind',
    'urban_area': 'Human', 'impervious_pct': 'Human'
}

importance_df['Category'] = importance_df['Factor'].map(category_map)
category_importance = importance_df.groupby('Category')['Contribution (%)'].sum()
```

### 7.3 Outputting a Single-Row CSV
To log analytical results to a CSV without outputting the index (a common pipeline pitfall), ensure `index=False`. If constructing a single row of results:

```python
results = pd.DataFrame([{
    'lake_id': 101,
    'trend_slope': 0.025,
    'p_value': 0.0012,
    'heat_contrib': 45.2,
    'flow_contrib': 20.1
}])

results.to_csv('trend_results.csv', index=False)
```

---

## 8. Integrated Python Utility Module: Working Implementation

This exhaustive script synthesizes all discussed libraries, avoiding common pitfalls and handling full end-to-end functionality.

```python
import pandas as pd
import numpy as np
import pymannkendall as mk
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

class LakeTemperatureAnalyzer:
    """
    Utility module for analyzing lake water temperature trends 
    and attributing environmental driving factors.
    """
    
    def __init__(self, target_col='water_temp'):
        self.target_col = target_col
        self.category_mapping = {
            'air_temp': 'Heat', 'solar_radiation': 'Heat', 'shortwave_rad': 'Heat',
            'streamflow': 'Flow', 'precipitation': 'Flow', 'discharge': 'Flow',
            'wind_speed': 'Wind', 'wind_direction': 'Wind',
            'urban_area': 'Human', 'impervious_surface': 'Human'
        }
        
    def detect_trend(self, df, method='hamed_rao'):
        """
        Calculates monotonic trend using pymannkendall.
        Drops NaNs automatically to prevent computation failure.
        """
        # Ensure data is a 1D Pandas Series and drop NaNs
        ts_data = df[self.target_col].dropna()
        
        if len(ts_data) < 4:
            return {'slope': np.nan, 'p_value': np.nan, 'trend': 'insufficient data'}
            
        # Select method based on autocorrelation expectation
        if method == 'hamed_rao':
            result = mk.hamed_rao_modification_test(ts_data)
        elif method == 'yue_wang':
            result = mk.yue_wang_modification_test(ts_data)
        else:
            result = mk.original_test(ts_data)
            
        return {
            'slope': round(result.slope, 4),
            'p_value': result.p, # Exact attribute extraction
            'trend_direction': result.trend
        }
        
    def parametric_trend(self, df):
        """
        Calculates linear regression trend using scipy.stats.linregress.
        Demonstrates updated version 1.14.1 argument syntax.
        """
        clean_df = df[[self.target_col]].dropna()
        # Create an independent variable (time steps)
        x = np.arange(len(clean_df))
        y = clean_df[self.target_col].values
        
        # Two explicit arguments required in scipy 1.14+
        result = stats.linregress(x, y)
        
        return {
            'slope': round(result.slope, 4),
            'p_value': result.pvalue,
            'r_squared': round(result.rvalue**2, 4)
        }

    def attribute_drivers(self, df, predictors, use_permutation=True):
        """
        Trains a Random Forest to extract relative feature importance 
        and groups them by physical categories.
        """
        # Drop rows with any NaNs in predictors or target
        model_df = df[predictors + [self.target_col]].dropna()
        
        X = model_df[predictors]
        y = model_df[self.target_col]
        
        # Fit Model
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X, y)
        
        if use_permutation:
            # Better for multicollinear datasets
            perm_result = permutation_importance(
                rf, X, y, n_repeats=10, random_state=42, scoring='r2'
            )
            raw_importances = perm_result.importances_mean
            # Set negative importances (worse than random) to 0
            raw_importances = np.maximum(raw_importances, 0) 
        else:
            raw_importances = rf.feature_importances_
            
        # Normalize to 100%
        pct_importances = (raw_importances / np.sum(raw_importances)) * 100
        
        # Map to physical categories
        attribution = {'Heat': 0.0, 'Flow': 0.0, 'Wind': 0.0, 'Human': 0.0, 'Uncategorized': 0.0}
        
        for feat, imp in zip(predictors, pct_importances):
            cat = self.category_mapping.get(feat, 'Uncategorized')
            attribution[cat] += imp
            
        # Round final percentages
        attribution = {k: round(v, 2) for k, v in attribution.items()}
        return attribution

# =======================================================
# Example Execution Pipeline
# =======================================================
if __name__ == "__main__":
    # 1. Simulate environmental dataset
    dates = pd.date_range('2000-01-01', '2020-12-31', freq='YE')
    sim_data = pd.DataFrame({
        'date': dates,
        'water_temp': np.linspace(14.0, 15.5, len(dates)) + np.random.normal(0, 0.2, len(dates)),
        'air_temp': np.linspace(15.0, 16.5, len(dates)) + np.random.normal(0, 0.3, len(dates)),
        'precipitation': np.random.uniform(500, 800, len(dates)),
        'wind_speed': np.random.uniform(2.0, 4.0, len(dates)),
        'urban_area': np.linspace(10, 25, len(dates))
    }).set_index('date')

    # Add a NaN to demonstrate robustness
    sim_data.iloc[cite: 18] = np.nan 

    analyzer = LakeTemperatureAnalyzer(target_col='water_temp')
    
    # 2. MK Trend Test
    mk_trend = analyzer.detect_trend(sim_data, method='hamed_rao')
    print("Non-Parametric Trend (Hamed-Rao):", mk_trend)
    
    # 3. Parametric OLS Test
    ols_trend = analyzer.parametric_trend(sim_data)
    print("Parametric Trend (OLS):", ols_trend)
    
    # 4. Factor Attribution
    predictors = ['air_temp', 'precipitation', 'wind_speed', 'urban_area']
    attribution = analyzer.attribute_drivers(sim_data, predictors, use_permutation=True)
    print("Category Contributions (%):", attribution)
    
    # 5. Output Single Row CSV
    final_output = pd.DataFrame([{
        **mk_trend,
        **attribution
    }])
    final_output.to_csv('lake_analysis_results.csv', index=False)
```

## 9. Conclusion
Developing an operational environmental time series module requires navigating intricate libraries and overcoming significant statistical pitfalls. For accurate non-parametric assessments under conditions of serial correlation, `pymannkendall`’s modified methods (like Hamed-Rao) are essential [cite: 1, 2]. Parametric comparisons via `scipy.stats` remain robust but require adherence to recent 1.14.x array signature protocols [cite: 6, 7]. Finally, isolating the true thermal, hydrological, and anthropogenic drivers of lake temperatures necessitates leveraging Scikit-Learn’s permutations techniques to combat multicollinearity [cite: 9, 10, 11], followed by careful manual categorization reflecting known thermodynamic realities.

**Sources:**
1. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEF0LDA63UGykKOs0cxhlMiQEuev-LRMRKnx8a7kTi-2pLXcaJsJ--sOP8b9qqIxwjGkC3YZcWldBobnRfeKK0EsFwclVcsBRG4LHH16sWbg5QpInSVfSGI--X7Ksko)
2. [theoj.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHRxBXjlkKz2viP7M2X6ascC6kNO0I_AcPQxEy4asHAdqtJucTBO-6XOtaKNefoc5gh1yblImphO_cfI9cI8wOBWFymvvJpONbd5yZb-lqWpJsRrbfrMpe-G8bVMFZ5wvHe1JyglDSvC6zNZBnwEMCH5zdadoGXgo-Blg==)
3. [kaggle.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEl-SXHXNaMBa8FwkxqexRCpk3W7nw0FhRDoFCXSCb4HQTSfWSKgV10K3sWkjXgGtR2_dftWZZTBVs6A4TK4F-8NvqLG3FnSmXBRPerACw0Mb2RXG9xKvG1khNYrs-uh_5gWppa4BYVWgeKQ23tZSPLZReom2w5gKrokA==)
4. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGU9sans4iR8kcTC3U5c8uzn31G2On9kCs0duImoFHt97mHfVyee4wC079qSuGzJbJJk8Y9lp9nxaGTBjI9fGWehOP386Tdh9CzWcYg8Wv2kTqL1gX17sw9981u8fG_TFUqL4d31YZiteYRS7szPajey52UdcM9Ab-szJlgLWD06caJhRRvoKi77OD1wQBeAw5Bu3hgm4OyFCA7zceDq2p3pzUBT8GpPRO7rA==)
5. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYrUFhtzvakI2uhUFVKsTBQYf0apCekFazftpiWER7OjhPXcUfG9YllI3HIhmYWUp_6aJTtwpBvlHqZ0OTpqDrVlqCiHUiqB1gaDa-Vj8JRNF48frWtQ6SQgn9p3KQGfZP)
6. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgh0LB8Yj_qj9jngvjJJiB4uIQ-8Nw2vDYX_5cUYUYBb-QI38h68cwt_Oqvt6dnRmy2l2hrsyKoUarxCZNfZ4G1IMXGTIhjJ7rCtYFKZV2YYJ8rL6a8BEzX8B1Pl40rJZUYW9Ni8bg5wdi2gv0EzneGOsn6MfusFWFhY0WcGL8zZwGOWAZXLS6xbsdCS8=)
7. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYVby9xNYGTZWgkE_3H66jipjEE7SL0824oPlKkd4kBROXLqgT5L8YExlwd13LuNaB9PDi_E0sskw_2HtE9FsKRAX-yG4w0UUZbk2g7sO6DPgFmK7SigOJFHDwxNt6Uzsc-6LWRDr1eFYVcL3KttO-)
8. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGCdc5xrnJ2U-f-zVzHHCNpofBFuB1blIxcwxUaC-FlGrXmXd1T6UbqNRAPLbUcCMNkFIOSrgBOWRXbPQZuAnZVWLd3KYJSCsTqHTGGRuhuUExUs08SBWbm2J4caraOix04N-l2HzErECblYIZfTljO7wPFAbcQ5w==)
9. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElVr_OhuGnedLu2m97A28dxqGxB1Xt_c0bsMq2aLsDzsgxAL2-ngb8m1x_I9asgNX6ITJCykfVPyLQs2mcb4zWAKcTchMTcsKogoPqkdBLGDppA6cW2qYqixpNsqGYydMFn8bb9RdOcZ5gQl36rsv7wAdoH_BI0eZzjsWAf_7WxobLi6buYWQC0-QyT3hmaQNlEa-SKw==)
10. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTmabFKWDTOCM438rWlRMVUn9YdX9mJ6Y2tInR1-8mYQyWN4P6FwOT62cytuMnoNBqe_eZGu2kmG6pfqyL6glT5lZqAVQ9YipngaUYM-nAS_Vr_5cCj8gjUKYX4HKSzvjLB-q5mbaa7Tm5ABmpSeIatKzGMUWYum6_xWpUuNjardHmG8HfaAwqe4e7coblQdgDvupHJVpJUTk4WiSl3A==)
11. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGWjjL4uxJkWQQDcULqo33logETdigeGg3_B8J8xH3trrzX5Fyko7fPCLT18KOTCCxbygyHF3irlUf1fqXjWRYQpQ4xYHSyIgNKqiau349evqSZgR9RoRl6bVybAevDPyl1VQ73cxcvp7KECvlrFwL0dUA_5Kzb583cgWvW-2wtJIvFnhr9jVkaV-Stk-JGLs7eFXulVFNeVVDT3I7aW3fa-bBqr0jH)
12. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQI7Rk82fT8ih9crfbXMpNGbODrXZPnWzKcxLbk0OrwWspNoPKGBmPKeFFE4AmZGBZ_9TQxjYWvmhnhKx-pg8eC40gQQSOuJYSa6_o_7pt4DwL9CO6XuF6qrEI-qEUxmP1AXq209D7LyxAM9G7xqiEAhozj1i6SvFpLsqVsh056Tjhq-qXioMeGtQiaYcOoggpWcV7NsUmEjuS2Q==)
13. [epa.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNFi1FWbKesFJtMQoDJzsbhzr5sys-WsxEw04vRp9UwQDbFTy0OccNizr1XKQ8gKugDCzq0WEMIGj_C82fXpo9sokIlw0saUYcZ30I58LGGLyHZF9eo16ZSsNDW7fRTPZyBQ-6sw8SceOQ9w==)
14. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFTitK2YhFbHGTwdcDr-zPs2rD2NgqwCcKA5cEdz-Dk00O1I4D2WsOZSVtMO7wshEgyq08jDP6oIzdsnRBuX4k6HB6NbHHW_uL35KTwe-OzIHofzpwZz0IM5ZxMaTf46Zt_NKeRxoxosg==)
15. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHvpiS65IGkanlgNv4Pvm1YtSWatRMrTgEh2zkI92yRFP-Urn9OLosYwvlh1btb3FOLBhWoH4aHk_lt-BJq5WmiLMCyGU8FmO-TX99DVEmxDZNqwjJSJ7s0-EKLuBpwQA==)
16. [fabriziomusacchio.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGdLDEPCPq5R7GfLzvTgk6lVgN6u-k2oAXf01xJangGQd9uMyndVBmJd0t7un4XS0IeLUX6ZDCutaJ5uKFRAwILH4s4Nq4E_fhKAMDBDEbTSRGKrPF_0CPCrlTfnN73tvncgdic6qa0VvW1WHeN-Rrt7xyJdj9dUN07qarlvj4rWhfgMw==)
17. [datacamp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE1LTl4U6fpCj7ZkYQ3cJCeFEgc7a0B0q8ZOMbPaAUz33bm_K475b7zavRrqZBiQuFq_asuVZT0ieqYS0y0_WYZ54bxgxDhV1IRiw67PYv2PYsWX7d5zFIx7taB5cENmFv0ezHscCJ4RhvSUlIZrZaZzlYdVfKZLA==)
18. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGanRa6P8noHBHZmSXqPSBW5VPtr0OsJdkMQAnzW0FiQDR35Jp4KEgj7IxIT2iBFY67zuTIzI2cFUrrQWI3ENqtenZRO16sHK9q380rjt1-FfZzRJ9RnvuaYP5JLeUbTV1RGHhctA==)
