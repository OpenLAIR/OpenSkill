# Domain Reference for evo-macro-cycle-correlation

**Responsibility**: Deflation, log-transformation, HP filtering with lambda=100, temporal alignment (1973-2024), Pearson correlation computation, and formatted output.

**Key functions to implement**: deflate_nominal_to_real, extract_hp_cycle, compute_cycle_pearson_correlation, run_full_pipeline

---

### 2.3 The Deflation Formula

To convert a nominal macroeconomic series (such as PCE or PFI) into a real series, the nominal value is divided by the price index of the corresponding year, and then multiplied by 100.

$$ \text{Real Value}_t = \left( \frac{\text{Nominal Value}_t}{\text{CPI}_t} \right) \times 100 $$

Because the CPI uses the 1982-1984 base, the resulting "Real Value" will be expressed in constant 1982-1984 dollars.

```python

## 3. Cycle-Trend Decomposition Using the Hodrick-Prescott Filter


The Hodrick-Prescott (HP) filter is a cornerstone technique in macroeconomics for separating a non-stationary time series into a long-term trend component ($\tau_t$) and a short-term cyclical component ($c_t$).

### 3.1 Theoretical Formulation

The HP filter isolates the trend by minimizing the variance of the cyclical component, subject to a penalty for variations in the second difference of the trend component. The objective function is:

$$ \min_{\tau_t} \sum_{t=1}^{T} (x_t - \tau_t)^2 + \lambda \sum_{t=2}^{T-1} [(\tau_{t+1} - \tau_t) - (\tau_t - \tau_{t-1})]^2 $$

The parameter $\lambda$ (lambda) dictates the smoothness of the trend. A higher $\lambda$ penalizes changes in the trend's growth rate more severely, resulting in a straighter trend line. For annual data, economic consensus strictly suggests $\lambda = 100$ [cite: 12]. (Conversely, $\lambda = 1600$ is used for quarterly data, and $\lambda = 129600$ for monthly data [cite: 12]).

### 3.2 Implementation in `statsmodels` 0.14.4

The `statsmodels` library provides a highly optimized implementation of the HP filter using sparse matrix ridge regression via `scipy.sparse` [cite: 13].

**Exact Import Path:**
The correct, canonical import path in statsmodels 0.14.4 is:
```python
from statsmodels.tsa.filters.hp_filter import hpfilter
```
While it can sometimes be accessed via the API namespace `import statsmodels.api as sm; sm.tsa.filters.hpfilter`, directly importing from the submodule is explicit, robust, and preferred for utility modules.

**Function Signature and Returns:**
The `hpfilter` function has the following signature:
```python
hpfilter(x, lamb=1600)
```
*   `x`: An `array_like` object containing the 1-dimensional time series to filter (e.g., a NumPy array, a Pandas Series, or a standard list) [cite: 13].
*   `lamb`: A float representing the smoothing parameter. The exact parameter name is `lamb` (not `lambda`, which is a reserved keyword in Python, nor `lam`) [cite: 13].

The function returns a tuple of two NumPy arrays in a very specific order:
1.  `cycle`: The estimated cyclical component [cite: 13].
2.  `trend`: The estimated trend component [cite: 13].

**Log-Transformation:**
Before applying the HP filter, real macroeconomic series should undergo a natural logarithm transformation (`np.log`). This transformation achieves two goals:
1.  It stabilizes the variance of the series over time.
2.  It allows the resulting cyclical component to be interpreted directly as the **percentage deviation from the trend** (log deviation).

```python
import numpy as np
from statsmodels.tsa.filters.hp_filter import hpfilter

### 3.3 Handling NaNs with the HP Filter

A critical limitation of `hpfilter` in `statsmodels` is its inability to process missing data (NaNs). Because the filter utilizes matrix inversion over the entire temporal sequence ($T = (I + \lambda K^T K)^{-1} x$), the presence of a single NaN value will propagate through the matrices, resulting in an output entirely composed of NaNs, or raising a computational error [cite: 14].

Therefore, any NaN values must be imputed or strictly filtered out prior to passing the array to `hpfilter`.

---

## 4. Statistical Alignment and Pearson Correlation Computation


After decomposing the PCE and PFI time series, the subsequent step is to compute the correlation between their cyclical components to determine the degree of co-movement over the business cycle.

### 4.1 Temporal Alignment (1973-2024 Inclusive)

Before running a correlation, both series must represent the exact same timeframe. Discrepancies in index length will misalign vectors and produce spurious statistical results or broadcast errors.

Pandas offers robust index-based filtering. To filter inclusive bounds between 1973 and 2024:

```python

### 4.2 Pearson Correlation Functions

Python offers multiple avenues to compute the Pearson correlation coefficient ($r$), each with different return structures.

1.  **`pandas.Series.corr(other)`:**
    *   This is the simplest method if data is already in Pandas objects.
    *   **Returns:** A single `float` representing the correlation coefficient.
    *   *Note:* It does not calculate a p-value.

2.  **`numpy.corrcoef(x, y)`:**
    *   This function computes the Pearson product-moment correlation coefficients matrix.
    *   **Returns:** A 2x2 NumPy array (matrix) where the main diagonal is 1.0.
    *   To extract the single correlation coefficient between `x` and `y`, one must index the matrix at `[cite: 7]` or `[cite: 7]`.
    *   *Code:* `r = np.corrcoef(x, y)[cite: 7]`

3.  **`scipy.stats.pearsonr(x, y)`:**
    *   This is the most statistically rigorous method for utility modules that require hypothesis testing [cite: 15, 16].
    *   **Returns:** In SciPy 1.14.1, this returns a `PearsonRResult` object [cite: 17, 18]. This object has attributes to extract the specific metrics.
    *   *Code:* 
        ```python
        import scipy.stats
        result = scipy.stats.pearsonr(df_filtered['PCE_Cycle'], df_filtered['PFI_Cycle'])
        r_value = result.statistic
        p_value = result.pvalue
        ```

For an academic or rigorous utility module, `scipy.stats.pearsonr` is superior because providing the p-value allows the user to assess the statistical significance of the cyclical co-movement.

---

### 5.3 `np.log` vs `np.log10`

In Python's NumPy library, `np.log()` calculates the **natural logarithm** ($\ln$, base $e$). This is the mathematically correct function for calculating continuous growth rates and percentage deviations in macroeconomics. 
Using `np.log10()` computes the base-10 logarithm, which will drastically alter the magnitude of the cyclical component and corrupt the economic interpretation of the data.

### 5.4 Exclusive vs. Inclusive Indexing Off-By-One Errors

When filtering years using Python's standard `range(start, stop)` or list slicing `list[start:stop]`, the `stop` bound is *exclusive*. `range(1973, 2024)` stops at 2023. 
**Mitigation:** When using pandas label-based indexing via `.loc[1973:2024]`, the bounds are **inclusive** of both ends. Always use `.loc` for year filtering to avoid omitting the 2024 data.

### 5.5 String Formatting and Float Rounding

For outputting final statistics, precision matters.
*   `round(value, 5)` returns a floating-point number. Because of binary floating-point representation in memory, it may display fewer than 5 decimal places if trailing zeros are present (e.g., `0.15000` becomes `0.15`).
*   `f"{value:.5f}"` is a string formatter that strictly enforces the display of exactly 5 decimal places, guaranteeing uniform table alignment in logs and standard outputs. **This is the preferred approach.**

---

## 6. Complete Working Code Implementation


The following Python script synthesizes all the methodologies discussed into a cohesive, robust utility module compatible with pandas 2.2.3, numpy 1.26.4, openpyxl 3.1.5, xlrd 2.0.1, scipy 1.14.1, and statsmodels 0.14.4.

```python
"""
macro_cycle_analyzer.py

A comprehensive utility module for parsing Economic Report of the President (ERP)
data and FRED CPI data, deflating nominal series, extracting cyclical components
via the Hodrick-Prescott filter, and computing Pearson correlation statistics.
"""

import pandas as pd
import numpy as np
import scipy.stats
from statsmodels.tsa.filters.hp_filter import hpfilter

def parse_erp_annual_total(filepath: str, target_year: int = 2024) -> pd.Series:
    """
    Parses an ERP .xls file to extract the annual "Total" column.
    
    Args:
        filepath: Path to the ERP .xls file.
        target_year: The final year to handle partial quarterly integration.
        
    Returns:
        A Pandas Series of annual totals indexed by integer years.
    """
    # 1. Read .xls file using xlrd. Skip headers and use only the first two columns.
    df = pd.read_excel(filepath, engine="xlrd", skiprows=4, usecols=[cite: 7])
    df.columns = ['Period', 'Total']
    df = df.dropna(subset=['Period', 'Total'])
    
    # 2. Clean 'Period' column
    df['Period'] = df['Period'].astype(str).str.strip()
    
    # 3. Isolate annual data (regex: exactly 4 digits)
    df_annual = df[df['Period'].str.match(r'^\d{4}$')]
    
    # 4. Isolate quarterly data (regex: contains colon or Q)
    df_quarterly = df[df['Period'].str.contains(r':|Q', regex=True)]
    
    # 5. Extract series and set integer index
    annual_series = pd.Series(
        data=pd.to_numeric(df_annual['Total'].values, errors='coerce'),
        index=df_annual['Period'].astype(int).values,
        name='Total'
    )
    
    # 6. Handle partial data for the target_year if it's missing from annual
    if target_year not in annual_series.index:
        # Find quarters belonging to target year
        q_target = df_quarterly[df_quarterly['Period'].str.startswith(str(target_year))]
        if not q_target.empty:
            q_values = pd.to_numeric(q_target['Total'], errors='coerce')
            annual_average = q_values.mean() # Average of available quarters
            annual_series.loc[target_year] = annual_average
            
    # Sort index chronologically and drop any NaNs created by coercion
    annual_series = annual_series.sort_index().dropna()
    return annual_series

def process_cpi_annual(filepath: str) -> pd.Series:
    """
    Reads FRED CPI .xlsx data and computes annual averages.
    
    Args:
        filepath: Path to CPIAUCSL.xlsx
    """
    # Use openpyxl for .xlsx files
    cpi_df = pd.read_excel(filepath, engine="openpyxl")
    
    # Standardize column names based on typical FRED output
    cpi_df.rename(columns={'observation_date': 'Date', 'CPIAUCSL': 'CPI'}, inplace=True)
    cpi_df['Date'] = pd.to_datetime(cpi_df['Date'])
    
    # Group by year and calculate mean
    cpi_df['Year'] = cpi_df['Date'].dt.year
    cpi_annual = cpi_df.groupby('Year')['CPI'].mean()
    return cpi_annual

def compute_cycle_correlation(pce_file: str, pfi_file: str, cpi_file: str):
    """
    Main pipeline function to compute correlation between real PCE and PFI cycles.
    """
    # 1. Parse Data
    pce_nominal = parse_erp_annual_total(pce_file)
    pfi_nominal = parse_erp_annual_total(pfi_file)
    cpi_annual = process_cpi_annual(cpi_file)
    
    # Align dataframes prior to mathematical operations to avoid NaN propagation
    df = pd.DataFrame({
        'PCE_Nominal': pce_nominal,
        'PFI_Nominal': pfi_nominal,
        'CPI': cpi_annual
    })
    
    # Filter by required year range: 1973 to 2024 (inclusive)
    # .loc is inclusive of both the start and stop labels in Pandas
    df = df.loc[1973:2024].copy()
    
    # Ensure no NaNs exist before filtering
    df = df.dropna()
    
    # 2. Deflate to Real Values
    # Real Value = (Nominal / CPI) * 100
    df['PCE_Real'] = (df['PCE_Nominal'] / df['CPI']) * 100
    df['PFI_Real'] = (df['PFI_Nominal'] / df['CPI']) * 100
    
    # 3. Log Transformation
    # np.log is the natural logarithm (ln)
    df['PCE_Log'] = np.log(df['PCE_Real'])
    df['PFI_Log'] = np.log(df['PFI_Real'])
    
    # 4. Hodrick-Prescott Filter
    # Return order is cycle, trend. lambda=100 for annual data.
    pce_cycle, pce_trend = hpfilter(df['PCE_Log'], lamb=100)
    pfi_cycle, pfi_trend = hpfilter(df['PFI_Log'], lamb=100)
    
    df['PCE_Cycle'] = pce_cycle
    df['PFI_Cycle'] = pfi_cycle
    
    # 5. Statistical Correlation using Scipy 1.14.1
    # pearsonr returns a PearsonRResult object with .statistic and .pvalue
    result = scipy.stats.pearsonr(df['PCE_Cycle'], df['PFI_Cycle'])
    
    # 6. Formatting Outputs
    # Use f-strings for exact 5-decimal precision
    print("=== Macroeconomic Cycle Correlation Analysis ===")
    print(f"Data Range: {df.index.min()} to {df.index.max()}")
    print(f"Pearson Correlation (r): {result.statistic:.5f}")
    print(f"P-value:                 {result.pvalue:.5f}")
    
    # Verify via Numpy for sanity check
    r_numpy = np.corrcoef(df['PCE_Cycle'], df['PFI_Cycle'])[cite: 7]
    print(f"[Verification] Numpy r:  {r_numpy:.5f}")

if __name__ == "__main__":
    # Example execution (assuming files exist in the working directory)
    # compute_cycle_correlation("Table_10.xls", "Table_12.xls", "CPIAUCSL.xlsx")
    pass
```