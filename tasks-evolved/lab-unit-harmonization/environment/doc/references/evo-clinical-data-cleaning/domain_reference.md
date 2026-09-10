# Domain Reference for evo-clinical-data-cleaning

**Responsibility**: Parse and clean structural data quality issues (decimal commas, scientific notation, mixed dtypes, missing values) without any domain-specific clinical knowledge. Provides reusable functions for loading, coercing, and preparing numeric data.

**Key functions to implement**: load_clinical_csv, replace_decimal_commas, coerce_to_numeric, drop_incomplete_rows, format_output_csv

---

## 3. Python Pandas Code Patterns for Data Cleaning


Building the utility module in Python requires utilizing the `pandas` library to process large CSV files efficiently, manage mixed numeric types, handle scientific notation, and apply our heuristic detection algorithms.

### 3.1 Reading Mixed Formats and Handling Decimal Commas


Clinical data from European systems often use commas as decimal separators (e.g., "12,34" instead of "12.34"). Pandas `read_csv` handles this natively with the `decimal` parameter [cite: 35].

```python
import pandas as pd
import numpy as np

def load_clinical_data(filepath):
    """
    Reads a CSV file, properly parsing comma decimals to standard dots.
    """
    # The decimal=',' parameter forces pandas to interpret '12,34' as 12.34
    try:
        df = pd.read_csv(filepath, decimal=',', low_memory=False)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None
```

### 3.2 Cleaning Scientific Notation and Mixed Dtypes


Sometimes EHR databases export large floats in scientific notation (e.g., `1.23e2`), and columns containing a mix of text (e.g., "<0.01", "NULL") and numbers are cast to the `object` dtype by Pandas [cite: 32, 36]. We must coerce these to `float64`.

```python
def clean_numeric_column(series):
    """
    Converts a mixed pandas Series into float64, stripping erroneous strings 
    and interpreting scientific notation correctly.
    """
    # Replace common textual null indicators with actual NaNs
    series = series.replace(to_replace=[r'(?i)null', r'(?i)nan', r'\?+', r'n/a'], 
                            value=np.nan, regex=True)
    
    # Remove operators like '<' or '>' which prevent float conversion
    if series.dtype == 'object':
        series = series.str.replace(r'[<>]', '', regex=True)
    
    # Coerce to numeric; pandas handles standard scientific notation (1.23e2) natively during coercion
    return pd.to_numeric(series, errors='coerce')
```

### 3.4 Formatting, Dropping NaNs, and Writing Clean CSV


After harmonization, values should be rounded cleanly. Pandas `round()` is utilized, and `dropna()` handles rows with missing values [cite: 37, 38, 39]. To prevent scientific notation upon export, we use the `float_format` parameter in `to_csv` [cite: 36, 40, 41, 42].

```python
def export_harmonized_data(df, output_filepath):
    """
    Drops missing values, rounds to 2 decimal places, and exports without scientific notation.
    """
    # Drop rows where any of the critical CKD features are NaN
    critical_cols = ['creatinine_mg_dl', 'bun_mg_dl', 'hgb_g_dl']
    df_clean = df.dropna(subset=critical_cols, how='any')
    
    # Rounding to exactly 2 decimal places
    df_clean = df_clean.round(2)
    
    # Writing to CSV, enforcing strict float formatting to prevent scientific notation (e.g., 1.00e+01)
    df_clean.to_csv(output_filepath, index=False, float_format='%.2f')
```

---

### 4.4 Pandas Dtype Issues with Mixed Strings

As demonstrated in Section 3, reading a CSV without specifying `dtype` or handling null representations results in columns casting to `object`. If you attempt `df['col'] * 0.0113` on an `object` column containing the string `"1.23"`, Python will duplicate the string 0.0113 times (which fails) rather than multiplying the float. Coercion via `pd.to_numeric` is mandatory prior to applying mathematical logic [cite: 36, 44].

---