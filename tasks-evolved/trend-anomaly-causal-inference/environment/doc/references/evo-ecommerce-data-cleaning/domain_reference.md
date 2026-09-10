# Domain Reference for evo-ecommerce-data-cleaning

**Responsibility**: All data ingestion, cleaning, normalization, and output of survey_cleaned.csv and amazon-purchases-2019-2020-filtered.csv. No analytical computations.

**Key functions to implement**: clean_survey_data, clean_transaction_data, deduplicate_dataframe, clean_monetary_column, normalize_strings, parse_dates, extract_top_category

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

### 6.2 `pandas` 2.3 Breaking Changes

If migrating code from older environments, several deprecated functions will fatally crash the pipeline in `pandas` 2.x:
1.  **`append()` removal:** `DataFrame.append()` was permanently removed. Pipelines must aggregate DataFrames in lists and use `pd.concat(list_of_dfs, ignore_index=True)` [cite: 26, 27].
2.  **`iteritems()` removal:** Generating `FutureWarning` in earlier versions, this has been removed. Use `DataFrame.items()` instead to iterate over columns [cite: 28].
3.  **Copy-on-Write (CoW):** `pandas` version 2.x began standardizing Copy-on-Write, shifting how `df.loc[:, :]` indexing operates. Chained assignments (e.g., `df[df['A'] > 0]['B'] = 1`) will fail. Always use `.loc` directly: `df.loc[df['A'] > 0, 'B'] = 1` [cite: 29, 30, 31].