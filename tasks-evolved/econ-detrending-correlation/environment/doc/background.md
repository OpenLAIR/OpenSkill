# Comprehensive Technical Guide: Macroeconomic Time Series Analysis Pipeline in Python

This report details the theoretical foundations, computational best practices, and programmatic implementation of a macroeconomic time series analysis pipeline in Python. Integrating legacy data formats, modern statistical libraries, and economic theory requires a rigorous approach to data ingestion, alignment, and filtering.

**Key Points**
*   **Data Ingestion Constraints:** The `xlrd` library (version 2.0.1) restricts ingestion strictly to `.xls` formats due to deliberate deprecation of `.xlsx` support for security reasons. Pandas must be explicitly configured to use the `xlrd` engine for these legacy files.
*   **Deflation Mechanics:** Nominal macroeconomic indicators must be adjusted for inflation using the Consumer Price Index (CPI), specifically the FRED CPIAUCSL series (base period 1982-1984=100), requiring aggregation of monthly indices to annual averages.
*   **Cycle-Trend Decomposition:** The Hodrick-Prescott (HP) filter (`statsmodels.tsa.filters.hp_filter.hpfilter`) decomposes non-stationary time series into trend and cyclical components. For annual data, a smoothing parameter ($\lambda$) of 100 is standard. The function returns the components in the exact order of `cycle, trend`.
*   **Statistical Correlation:** The Pearson product-moment correlation coefficient assesses the linear dependence between the cyclical components of the series. SciPy 1.14.1 returns a structured `PearsonRResult` object containing both the statistic and the p-value.
*   **Robustness against Anomalies:** Missing values (NaNs) and formatting irregularities in Economic Report of the President (ERP) tables necessitate rigorous preprocessing, as algorithms like the HP filter do not inherently support non-finite values.

### The Necessity of Programmatic Macroeconomic Analysis
Macroeconomic policy and empirical research rely heavily on the analysis of stylized facts—systematic, predictable patterns in economic data. Understanding the co-movement of indicators such as Personal Consumption Expenditures (PCE) and Private Fixed Investment (PFI) over the business cycle is fundamental to dynamic stochastic general equilibrium (DSGE) modeling. Automating the extraction and processing of this data ensures reproducibility and reduces the risk of human error inherent in manual spreadsheet manipulation. 

### Pipeline Architecture Overview
The pipeline detailed in this report involves several distinct phases: data acquisition and parsing, temporal aggregation, real-value deflation, log-transformation, cycle-trend decomposition, and statistical correlation. Each phase utilizes specific Python libraries—`pandas` 2.2.3 for data wrangling, `numpy` 1.26.4 for numerical transformations, `scipy` 1.14.1 for statistical testing, and `statsmodels` 0.14.4 for econometric filtering.

---

## 1. Parsing and Processing the Economic Report of the President (ERP) Data

The Economic Report of the President (ERP) provides historical macroeconomic data. Historically, these data tables have been published in the legacy Excel format (`.xls`). Extracting this data requires careful navigation of the file format constraints and the idiosyncrasies of government data presentation.

### 1.1 Understanding the `xlrd` 2.0.1 Limitation
The `xlrd` library was once the standard engine for reading all Excel files in Python. However, beginning with version 2.0.0, the maintainers explicitly removed support for the modern Office Open XML format (`.xlsx`) [cite: 1, 2]. This decision was driven by unmitigated security vulnerabilities associated with parsing XML bombs within zipped `.xlsx` archives [cite: 3]. Consequently, `xlrd` version 2.0.1 supports *only* the legacy `.xls` format [cite: 2, 4]. 

When using `pandas` (version 2.2.3) to read ERP `.xls` files, the user must explicitly invoke the `xlrd` engine. Relying on default engine detection may lead to errors or warnings if the file extension is misidentified or if conflicting libraries are present [cite: 5, 6].

```python
import pandas as pd

# Correct API usage for reading .xls files with pandas 2.2.3
file_path = "ERP-2024-Table10.xls"
df_erp = pd.read_excel(file_path, engine="xlrd")
```

### 1.2 Navigating ERP Table Structures
ERP tables (such as Table 10 for Personal Consumption Expenditures and Table 12 for Private Fixed Investment) are not formatted as clean, relational databases. They are formatted for human readability, introducing significant programmatic challenges.

**Typical ERP Table Characteristics:**
1.  **Multi-row Headers:** The first several rows (often rows 0 to 4) contain the table title, subtitle, unit descriptions (e.g., "Billions of dollars"), and hierarchical column labels.
2.  **Mixed Indices:** The first column acts as the index, containing years (e.g., `1973`, `1974`) followed by quarterly breakdowns (e.g., `2023: I`, `2023: II`). Interspersed within this column are section headers like "Seasonally adjusted at annual rates".
3.  **Footnotes:** The bottom rows of the file contain textual footnotes and source attributions.

**Best Practices for Pandas Parameters:**
*   `skiprows`: Instead of manually counting rows to skip, it is often safer to read the file without a header (`header=None`), locate the row containing a known header keyword (e.g., "Total" or "Year"), and slice the DataFrame. Alternatively, if the structure is perfectly static, `skiprows=4` (or similar) can be hardcoded.
*   `usecols`: To extract the "Total" column (which is typically the first data column after the Year index), `usecols=[cite: 7]` extracts the index and the first column.
*   `skipfooter`: While `skipfooter` can remove footnotes, it requires the engine to read from the end of the file, which is slow and can disable fast-path parsing. Programmatic filtering (e.g., dropping rows where the index cannot be cast to a numeric year) is significantly more robust.

**Programmatic Extraction and Cleaning:**
To extract the annual data and discard the quarterly breakdowns located at the bottom of the table, we can leverage regular expressions and type casting. Annual data is represented by a four-digit integer or string (e.g., "1973"). Quarterly data usually contains colons or the letter "Q" (e.g., "2024:III"). 

```python
def extract_erp_total(file_path):
    # Read the first two columns: Year/Period and the Total
    # Skipping the first 4 rows which usually contain titles
    df = pd.read_excel(file_path, engine="xlrd", skiprows=4, usecols=[cite: 7])
    
    # Rename columns for standardization
    df.columns = ['Period', 'Total']
    
    # Drop rows with NaN in Period or Total to remove empty spacing rows
    df = df.dropna(subset=['Period', 'Total'])
    
    # Convert 'Period' to string and strip whitespace
    df['Period'] = df['Period'].astype(str).str.strip()
    
    # Isolate annual data: Years are purely numeric (4 digits)
    # We use a regex match to filter out "2024:I", "Seasonally adjusted", etc.
    df_annual = df[df['Period'].str.match(r'^\d{4}$')]
    
    # Isolate quarterly data: Look for patterns containing a colon or "Q"
    df_quarterly = df[df['Period'].str.contains(r':|Q', regex=True)]
    
    # Convert Period to integer years for the annual data
    df_annual['Year'] = df_annual['Period'].astype(int)
    
    return df_annual.set_index('Year')['Total'], df_quarterly
```

### 1.3 Handling Partial Year Data (2024)
When analyzing data up to the current year, the final year (e.g., 2024) may only have partial data available (e.g., Q1 through Q3) at the time of the report's publication. ERP tables typically append this quarterly data at the bottom of the sheet.

To accurately represent 2024 as an annualized figure, one must compute the arithmetic mean of the available quarters. Economic data in these tables is usually presented at "seasonally adjusted annual rates" (SAAR). Therefore, the annual average is simply the mean of the available quarterly SAAR values.

```python
def compute_partial_year(df_quarterly, target_year="2024"):
    # Filter quarterly strings that start with the target year
    # e.g., "2024:I", "2024:II"
    q_data = df_quarterly[df_quarterly['Period'].str.startswith(target_year)].copy()
    
    if not q_data.empty:
        # Convert values to float and calculate the mean
        q_data['Total'] = pd.to_numeric(q_data['Total'], errors='coerce')
        annual_average = q_data['Total'].mean()
        return annual_average
    return None
```

---

## 2. Processing and Deflating with FRED Consumer Price Index Data

Nominal economic data reflects the prices current at the time the data was collected. To isolate true changes in economic volume (real growth) and conduct meaningful cycle-trend decomposition, nominal values must be deflated using a price index. The Consumer Price Index for All Urban Consumers: All Items (CPIAUCSL) is the standard metric for this adjustment [cite: 8].

### 2.1 Structure of FRED CPI Downloads
When downloading the CPIAUCSL series from the Federal Reserve Economic Data (FRED) system as an `.xlsx` file, the structure is highly standardized.
*   **Frequency:** The data is provided at a monthly frequency.
*   **Columns:** The file typically contains a single date column (named `observation_date`) and a data column (named `CPIAUCSL`) [cite: 9].
*   **Date Format:** Dates are formatted as `YYYY-MM-DD`, always falling on the first of the month (e.g., `1973-01-01`) [cite: 9].
*   **Base Year:** The FRED CPIAUCSL index uses the base period of 1982-1984 = 100 [cite: 10, 11]. This means that the index is normalized such that the average price level between 1982 and 1984 is exactly 100.

Because FRED files are provided in `.xlsx` format, `xlrd` cannot be used. The `openpyxl` engine (version 3.1.5) must be utilized.

### 2.2 Converting Monthly CPI to Annual Frequency
Because the ERP data is annual, the monthly CPI data must be aggregated to an annual frequency. The standard method for this is to calculate the arithmetic mean of the 12 monthly observations within a given calendar year.

```python
# Reading FRED .xlsx file requires openpyxl, NOT xlrd
cpi_df = pd.read_excel("CPIAUCSL.xlsx", engine="openpyxl")

# Ensure the date column is datetime and extract the year
cpi_df['observation_date'] = pd.to_datetime(cpi_df['observation_date'])
cpi_df['Year'] = cpi_df['observation_date'].dt.year

# Group by year and compute the annual average
cpi_annual = cpi_df.groupby('Year')['CPIAUCSL'].mean()
```

### 2.3 The Deflation Formula
To convert a nominal macroeconomic series (such as PCE or PFI) into a real series, the nominal value is divided by the price index of the corresponding year, and then multiplied by 100.

$$ \text{Real Value}_t = \left( \frac{\text{Nominal Value}_t}{\text{CPI}_t} \right) \times 100 $$

Because the CPI uses the 1982-1984 base, the resulting "Real Value" will be expressed in constant 1982-1984 dollars.

```python
# Assuming 'nominal_pce' and 'cpi_annual' are pandas Series aligned by Year index
real_pce = (nominal_pce / cpi_annual) * 100
```

---

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

# Convert real values to natural log
log_real_pce = np.log(real_pce)

# Apply HP Filter with lamb=100 for annual data
pce_cycle, pce_trend = hpfilter(log_real_pce, lamb=100)
```

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
# Assuming cycle arrays have been re-attached to a DataFrame with a 'Year' index
df_cycles = pd.DataFrame({
    'PCE_Cycle': pce_cycle,
    'PFI_Cycle': pfi_cycle
}, index=aligned_years) # where aligned_years is the index of the original data

# Inclusive filtering using .loc
df_filtered = df_cycles.loc[1973:2024]
```

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

## 5. Common Pitfalls and Robust Error Handling

Building a production-ready macroeconomic utility module requires anticipating and mitigating several common pitfalls specific to these libraries and data sources.

### 5.1 The `xlrd` 2.0.1 `.xlsx` Compatibility Trap
Developers frequently upgrade libraries without reviewing changelogs. A user might attempt to read a FRED CPI `.xlsx` file using the `xlrd` engine out of habit from older pandas code. Doing so with `xlrd` >= 2.0.0 throws an `xlrd.biffh.XLRDError: Excel xlsx file; not supported` [cite: 3, 19]. 
**Mitigation:** Strictly enforce `engine="xlrd"` for ERP `.xls` files and `engine="openpyxl"` for FRED `.xlsx` files [cite: 4, 20].

### 5.2 ERP Table Index Artifacts
Because ERP tables are designed for print, the "Year" column often contains footnote references (e.g., "1973 1/"), or intermediate section text (e.g., "Seasonally adjusted").
**Mitigation:** Do not rely on fixed rows. Coerce the target column to strings, strip whitespace, and use regular expressions (`r'^\d{4}$'`) to positively identify rows that are purely annual data. Drop any rows that yield NaNs upon string-to-numeric coercion.

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

### Conclusion
By strictly adhering to engine specifications for legacy `.xls` files, intelligently parsing text-heavy government spreadsheets, correctly aligning temporal bounds, and understanding the mathematical prerequisites for the Hodrick-Prescott filter, developers can construct a highly reliable pipeline for macroeconomic time series analysis. Explicit handling of missing data and exact API implementations in `statsmodels` and `scipy` guarantee that the subsequent statistical outputs are analytically sound and numerically verifiable.

**Sources:**
1. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYejxtJ5JXYpQswAz7Wbl7iRcVL3VjI9IjVFrYXuXkWDxynZ9B1M944n-UGEBFxU1pnxZ-A26YqmDthBvfjlSLoljk0c2uC4FkmWH3_nvWme0wo9YoWbHGRyKpTz0vDh67dk5iVsHmZg==)
2. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHl3nXqjS4zXE4jU2SGnne5_LAOSqn3UzpLeeNI4xxykSXAHWflA3HOKLHUnzKcz8sDDBcpAKIkyxGjBUPxAcEOC5-7ojFH8_35iHKAPvubLffD4QZLap5F_C7Gt-kcZRTpKza3R6Al4L8mziHGQ8Y9xmqDPGfHeyAc5FU=)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0NFBz6IsMM1ISg6IDFEQwtZrwXy9MSFTfqTXB9a7WK2CT6wQ7snfa-veHau-nsf73VNoV6h6CQ6csLcjiuDEcNETTKO00qWbD0Z-i21PwXBDjBGlEkqLFGddmF93Wlgg=)
4. [alteryx.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVuQD4hTrKQx4YBkO0yuI7UmlClVunm496I47tOy7UhXz-C3XWaAYVFk6UjRdQ_aqopNJXhtIdo51UdD3CD8UuZvG6fHk9HYpd27sK6yvA1cLueZRcfhmGpBaKdOnsRNurHh4-nesRzvvdhamBDk6NjTPJAFx9K3-iTGM9atlh6Fr_QUSgMwKxkk1keW4zoSjzUFSnvAYYfQ==)
5. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLNl6t4D6KqBwle2kv79oLbLuDyHQA07llfuynsga_jXG5wkGKEb7q5kGbfvSJ7bpBaqsByryQsQmyw7N_BGQ7LurDftp8Kug5e3asf430EeP40cjU1NfOIGIxe7b_GXuHCoQhxsw-XgvG4Izbn3uqlgnOETGnEZk=)
6. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFs5qSo7QegQ5Q6pEBy2zEYsGsgKA1LnJinBF_81NvumIqit78OWRTrtBPNcZVf03uyNq0Z0TrCWLVWFaGIaoRGzbdXpEIgk8neIJDZUxM1G1Spp8rpFWtWWOqHlSpMVwN5XYYyLTgMT29TNsaD_0Pmyt723Gn652y)
7. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGCia0vldeqLgaWfHeEjplvOf7MEORRVoeHlxr0F1Rc6to_nFXwHvSjwysFGYesVehx48TY0tUHwniYiZdyi11fZwjtPmaETGbkBVHpupiIDxbXnsu-864PTsuqdgDXjGI4Gs_faNdB3UV2d6BpEOo9x7pHgE8rRtg4XnYxTfU=)
8. [stlouisfed.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH-HqtXhCkcUAgfYHqU4JvlIXPXdXbfQElfSBcuzP2aOv5Er40-kas2uQiynoqlZfuWQE3mK9yKrRGuHO1vqlpMnjhwRhyYFaxIzccRz32ox8aA0V0uND9VzzlLyH_ysL2P)
9. [utah.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE08j5hOgAjaXlArclENZBkxiOGDoGqyPhegNsqfldI4jJDzpac4JARqgcBJDOgZhE6MhTevIn6JH272fESpfqBbVJQoYGdKWKH5f08xKrhK0XODLDO2X_cATaxaSxDHA==)
10. [stlouisfed.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2IiGAHnUxFZu5pfG-7HDfWMylFpUVHhOlLhHY6ocH89GRK5VkLhLcSEsGn364wWAUKdYscs-wLdnwConWcCOqmtkbjVtPBiXMiadJ-GjD62pna3_yEkad5ghfCSdtjD4=)
11. [stlouisfed.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFssdAZcHsy063e0nUPMprwAAfdaZU6p-LEDIhJ2SjbPc9xxWht17hvliiw0_y9xfzdAPDrxLqs4LINyKdovUOMB_ggMCgW_ejmCkPVBb-XPT3YCCaHqZvG1SIv1QXw_NY=)
12. [statsmodels.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPzLxbBCTqh5hj4Vyq01xmBUbsqLkdJSZVPcwiBFny9YBZ59lCL-s4587DI21DFgmvr0aAKzlyWTUDfIl-F_n-fwRFn9wAM9zl55pKM5VbnCPyqYAlkDj5HMDuaHtIqPOByZzPn4vZJ0RiKHYlI9xcqJK-lkpBwssdCEOCNNRqBWIMnYg896D1FjA8BK3cmmzLQQ==)
13. [statsmodels.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHF_SzY3WAzAYrHM4F9XRrdAkZCKDDFEo79xdn-lMDhCG3-r4DpIQJEDcgia2c-XmsrA7j-XlKHMdkY9v4G3rM65WgjwxSJBDOFOCyVBXbmrbAIQUaCBO9TYsH4nkSpR58qgUQ4jq_6-2CUplE_5xQUu5nDPGGacBVtENSZDmOhQq_DYkppqUtg8TvFFZHUIahiIXQ=)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGunqMQl6ciEDGeXT2aDOtaXQST8rU9YPPGKDx1AyhsPKRoZ36ia6rZcQPd-4l81vNHpvPbJY12gHb7nWiQeQCwpqp32t48YOhOvKOGWMfGBrU-ZLRp1EG6cHGZojQHkPl_qiZ1XlY1a7WBUQ3Io2YBVhZbsU6w6si-gZ-elVqZ4Xjs6O8f2qhE4xBHMifI40b9fGEUFMx66BHF-w==)
15. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGnqbxmJ0SDFO4xAJxg482FWL2G7j7Q4mGOykEhTaD8lwRqsTa0nbqNgtttI-TNjBwMQeiQc3VR0Q_Fsclp6DlpF5XtD_LWN1cV1DGTi619ru4Pe1SI4ytCOkJCk7YzFG8GQ5QQMW9N-KODFuSfQcIyRedSuNkQq4lBDjdTK5I3MgpQ6Vgm5PuC4qkE)
16. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF1n3OL61FUFgSmoIdfciIXqZ12_JJaPwhnxUd6Vido_XaUJCleuLSm97Qp4vbwiF9st4XNweAFmLRd6m_MXTzFnaXm4KE87cnDhEJ3gedcuQGEJHQML_84AtBYuXMsIQPKuHlEr1gl2O-4j8MBcz_4B13z3zd6Ic0fR4PZm5lzYYpM7M8=)
17. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG5jW4kRJ_PKhTdQ8uaX-Hrrl4ZeyO_AHE4rTHoQsoeKi9AnWE2B57QnhoWTJ3i66cKLRCiIj0fdYQ1m8iNj7UfQm8UcQea_38NzIYS20LUMPDTQ2EVb19DlDkZ52lq0lGk_La1UuAX8zWH3GU1dzEHMnYWayr4SsnDvJ0oW9nNLZpxlZPcwqtN7mfLZO9aRpU27xLgINpfSvZR6ruH67t6xw==)
18. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEJCzHfQHdrMhB4aCMV3IGR9cu0bXUU0x3J_i_ZOHCf2YXDYYbq7UsAGcK_1sOwkc-Xs_FkYhd8jjqTlzSGGbBzogayPAYvL-l1OD6EO5mDsmmq-5NhKcIVD-L8AFGY4iWBxGdZqyYA1AQP_x6rl93PjsRxrh-OoRkM7RQLY-mRkvgKy1lUmjg1p6NKfKiLZZF92QZLehyMcOZRGcCMOI9a8A==)
19. [stackabuse.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESu0qP3eM4wmwA3e8gaKZ3tXQ-4b6vXWMVciB-jdtxccfptgOdQRjHiGGZA3c0xHAg1no30jSdxOQbfGEqxblWwRj1CvnlBqQLlnPUD2a7ZWqQPXKd5X-Gwsie6ysxyc1f0E-00UPhrx19x5y8wHF3VTyBTq5t9eNozCbIcdYLHqf4HGU6LjCX6pXdOXNt1VE=)
20. [databricks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwex3v_rdGUlzsiQVe1HjqK0h1uQ9X78RzBweGiRPZrtYMMAqiATJ7jcwkKoVHRixWsGRwILCM8E-32V1qdNis9i1742vVUN4Cge_rewrej9UGyY3LbV2BKayhJXtgpf8WxxA1qdttPlxcCdgoZHlWw2mrp-jh)
