# Domain Reference for evo-lake-trend-analysis

**Responsibility**: Trend detection on water temperature series, handling autocorrelation via modified MK tests, NaN removal, and CSV output of slope and p-value.

**Key functions to implement**: run_mann_kendall_trend, save_trend_result

---

## 2. Non-Parametric Trend Detection: `pymannkendall` (Version 1.4.3)


The Mann-Kendall (MK) trend test is a non-parametric statistical technique used to detect monotonic trends in time series data without assuming an underlying normal distribution [cite: 1, 2]. The Python implementation `pymannkendall` brings together various MK test methodologies specifically engineered to address the complexities of environmental data [cite: 1].

## 3. Parametric Linear Regression: `scipy.stats` (Version 1.14.1)


While non-parametric tests assess monotonic trends, parametric methods like Ordinary Least Squares (OLS) regression assume a linear relationship and normally distributed residuals. The `scipy.stats` library provides tools for this through the `linregress` function.