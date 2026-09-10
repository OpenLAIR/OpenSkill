# Domain Reference for evo-macro-data-ingestion

**Responsibility**: All data reading, parsing, cleaning, and temporal aggregation from raw Excel files into clean pandas Series indexed by integer year.

**Key functions to implement**: parse_erp_annual_total, compute_partial_year_average, process_cpi_annual

---

## 1. Parsing and Processing the Economic Report of the President (ERP) Data


The Economic Report of the President (ERP) provides historical macroeconomic data. Historically, these data tables have been published in the legacy Excel format (`.xls`). Extracting this data requires careful navigation of the file format constraints and the idiosyncrasies of government data presentation.

### 1.1 Understanding the `xlrd` 2.0.1 Limitation

The `xlrd` library was once the standard engine for reading all Excel files in Python. However, beginning with version 2.0.0, the maintainers explicitly removed support for the modern Office Open XML format (`.xlsx`) [cite: 1, 2]. This decision was driven by unmitigated security vulnerabilities associated with parsing XML bombs within zipped `.xlsx` archives [cite: 3]. Consequently, `xlrd` version 2.0.1 supports *only* the legacy `.xls` format [cite: 2, 4]. 

When using `pandas` (version 2.2.3) to read ERP `.xls` files, the user must explicitly invoke the `xlrd` engine. Relying on default engine detection may lead to errors or warnings if the file extension is misidentified or if conflicting libraries are present [cite: 5, 6].

```python
import pandas as pd

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

### 5.1 The `xlrd` 2.0.1 `.xlsx` Compatibility Trap

Developers frequently upgrade libraries without reviewing changelogs. A user might attempt to read a FRED CPI `.xlsx` file using the `xlrd` engine out of habit from older pandas code. Doing so with `xlrd` >= 2.0.0 throws an `xlrd.biffh.XLRDError: Excel xlsx file; not supported` [cite: 3, 19]. 
**Mitigation:** Strictly enforce `engine="xlrd"` for ERP `.xls` files and `engine="openpyxl"` for FRED `.xlsx` files [cite: 4, 20].

### 5.2 ERP Table Index Artifacts

Because ERP tables are designed for print, the "Year" column often contains footnote references (e.g., "1973 1/"), or intermediate section text (e.g., "Seasonally adjusted").
**Mitigation:** Do not rely on fixed rows. Coerce the target column to strings, strip whitespace, and use regular expressions (`r'^\d{4}$'`) to positively identify rows that are purely annual data. Drop any rows that yield NaNs upon string-to-numeric coercion.