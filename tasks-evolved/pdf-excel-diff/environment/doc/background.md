# Comprehensive Guide to PDF Table Extraction, Excel Data Integration, and DataFrame Diffing in Python

**Key Points**
*   **PDF structure is visually, not semantically, driven:** Unlike Excel or CSV files, PDFs generally lack inherent tabular metadata, requiring heuristic-based parsing techniques to reconstruct tables from geometric coordinates.
*   **`pdfplumber` excels in layout-aware extraction:** It utilizes geometric lines and character bounding boxes to identify rows and columns, making it highly effective for digitally generated PDFs but ineffective for scanned documents without prior Optical Character Recognition (OCR).
*   **`tabula-py` offers robust alternatives:** Acting as a wrapper for Java's Tabula engine, it provides `lattice` (line-based) and `stream` (whitespace-based) algorithms, offering a reliable fallback when `pdfplumber` struggles with complex visual alignments.
*   **Data type normalization is a critical intermediary step:** Pandas inherently infers data types, which often leads to integer arrays being downcast to floats when missing values (`NaN`) are present.
*   **Comparing DataFrames requires structural alignment:** Using an outer merge with indicator columns is the most robust methodology for identifying row-level differences (insertions, deletions, and modifications).
*   **NumPy types break native JSON serialization:** When exporting analytical results, data pipelines frequently crash due to `numpy.int64` or `numpy.float64` objects, necessitating custom JSON encoder classes.

**Overview of the Analytical Challenge**
The automated extraction of tabular data from Portable Document Format (PDF) files and subsequent reconciliation with structured datasets (such as Microsoft Excel) represents a prevalent challenge in data science and enterprise automation. PDFs are designed for presentation fidelity, not data retrieval; they position text characters at absolute coordinates on a canvas without preserving the logical relationships of rows and columns [cite: 1, 2]. Consequently, extracting data requires specialized libraries to mathematically reconstruct these relationships. 

**Scope of this Report**
This report provides an exhaustive, academic-level examination of building a resilient Python utility for extracting, normalizing, and comparing tabular data. It evaluates `pdfplumber` (v0.11.4) and `tabula-py` (v2.9.3) for PDF extraction, combined with `pandas` (v2.2.3) and `openpyxl` (v3.1.5) for Excel ingestion. Furthermore, it details rigorous methodologies for row-by-row data comparison, datatype normalization, handling edge cases like float precision and missing values, and safely exporting results to JSON.

---

## 1. Extracting Tables from PDFs with `pdfplumber` (Version 0.11.4)

`pdfplumber` is an advanced Python library built on top of `pdfminer.six` [cite: 1]. Rather than attempting to read a PDF as a continuous text stream, `pdfplumber` treats the document as a coordinate system. It identifies individual characters, lines, and rectangles, utilizing their spatial coordinates to infer the presence of tabular structures [cite: 2, 3]. 

### 1.1 Core API: Opening and Processing Files

The primary entry point to the library is the `pdfplumber.open()` method, which functions as a context manager and yields a `pdfplumber.PDF` object [cite: 1, 4]. 

```python
import pdfplumber

# Correct usage pattern using context manager
pdf_path = "financial_report.pdf"
with pdfplumber.open(pdf_path) as pdf:
    # Access the first page (0-indexed)
    first_page = pdf.pages
    print(f"Processing page {first_page.page_number} with width {first_page.width}")
```

The `.open()` method can accept file paths, file objects, or file-like objects loaded as bytes [cite: 1]. It also accepts layout analysis parameters (`laparams`) that govern the underlying `pdfminer` engine's behavior (e.g., `line_overlap`) and a `password` parameter for encrypted documents [cite: 1, 4].

### 1.2 `extract_table()` vs `extract_tables()`

The `pdfplumber.Page` class provides two distinct methods for retrieving tables, each returning a differently structured Python native data type [cite: 1].

1.  **`page.extract_table(table_settings={})`**: This method searches the page for the *largest* table (measured by the number of cells). It returns a 2-dimensional list of strings (a list of lists). The structural hierarchy is `row -> cell` [cite: 1, 3]. 
    *   *Return Type Example*: `[['Header1', 'Header2'], ['Value1', 'Value2']]`
2.  **`page.extract_tables(table_settings={})`**: This method extracts *all* detected tables on the given page. It returns a 3-dimensional list of strings (a list of lists of lists). The structural hierarchy is `table -> row -> cell` [cite: 1].
    *   *Return Type Example*: `[[['Table1_H1', 'Table1_H2'], ['T1_V1', 'T1_V2']], [['Table2_H1'], ['T2_V1']]]`

Header rows are not semantically identified by `pdfplumber`. Instead, the library returns the visual top row of the table as the first list in the returned structure. When converting this to a `pandas.DataFrame`, it is up to the developer to slice the list and assign the first row as the column headers.

### 1.3 Deep Dive into `table_settings` Parameters

By default, `pdfplumber` attempts to detect tables by looking for explicit geometric lines (ruling lines) drawn on the PDF canvas [cite: 1, 3]. However, many modern PDFs feature borderless tables. To reconstruct these, the `table_settings` dictionary must be meticulously configured [cite: 1].

The default configuration is:
```python
DEFAULT_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "intersection_tolerance": 3,
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 3
}
```

#### Strategic Parameters
*   **`vertical_strategy` / `horizontal_strategy`**: Determines how cell boundaries are deduced [cite: 5].
    *   `"lines"` (Default): Relies strictly on explicitly drawn lines or rectangle edges in the PDF [cite: 1].
    *   `"lines_strict"`: Similar to lines, but ignores rectangle edges [cite: 5].
    *   `"text"`: A heuristic approach for borderless tables. It deduces imaginary boundary lines by finding alignments of text. For `vertical_strategy`, it looks for words sharing the same left, right, or center x-coordinate. For `horizontal_strategy`, it uses the tops of words sharing the same y-coordinate [cite: 5].
    *   `"explicit"`: Requires the user to manually provide a list of coordinates via `explicit_vertical_lines` and `explicit_horizontal_lines` [cite: 6].

#### Tolerance Parameters
Because PDF rendering engines often introduce microscopic variations in coordinates, `pdfplumber` utilizes tolerance values (measured in PDF points, where 1 point = 1/72 inch).
*   **`snap_tolerance`** (Default: 3): Defines how close together two parallel lines must be to be mathematically "snapped" into a single line [cite: 7]. Increase this if a single thick border is being interpreted as two separate thin lines.
*   **`join_tolerance`** (Default: 3): Defines how close two collinear line segments must be to be joined into a continuous line [cite: 7]. Useful if a continuous border is drawn as dashed segments.
*   **`intersection_tolerance`** (Default: 3): Defines how far a horizontal line and vertical line can be from mathematically intersecting to still be considered a valid cell corner [cite: 7]. 
*   **`edge_min_length`** (Default: 3): Any line shorter than this length is ignored. This prevents random artifacts (like underlines or hyphens) from being interpreted as table boundaries [cite: 5, 8].

### 1.4 Handling Multi-page Tables

A crucial limitation of `pdfplumber` is that it evaluates the document on a strictly page-by-page basis. It does *not* automatically merge tables that span multiple pages [cite: 2]. If a table flows from Page 1 to Page 2, it will be extracted as one table from Page 1 and an entirely separate table from Page 2. 

To handle multi-page tables, the developer must iterate over `pdf.pages`, extract the tables independently, and concatenate them programmatically using list extension or `pandas.concat`. Furthermore, the table on the second page will typically lack header rows (unless the PDF generator explicitly repeated the headers), requiring logic to normalize the schema before concatenation.

### 1.5 Common Pitfalls in `pdfplumber` Extraction

1.  **Empty Cells (`None` vs `""`)**: Depending on the extraction strategy, an empty cell may be returned as `None` or an empty string `""`. When converting to Pandas, `None` becomes `NaN`, while `""` remains a string. This complicates subsequent numeric operations.
2.  **Stringified Numerics**: Because the PDF contains visual text characters rather than typed data, an integer like `5000` is extracted as the string `"5000"`.
3.  **Whitespace and Line Breaks**: Cells with wrapped text often contain newline characters (`\n`). Values may also contain trailing or leading spaces, rendering exact string matching impossible without pre-processing.
4.  **Merged Cells**: `pdfplumber` struggles inherently with merged headers or spanned cells. A horizontally merged cell will typically assign the text to the first bounding box and populate the subsequent merged columns with `None`.
5.  **Scanned Documents**: `pdfplumber` operates on the embedded text layer of a PDF. Scanned images or flat PDFs contain no text layers. Attempting extraction on these will yield empty results unless the document is first pre-processed through an OCR (Optical Character Recognition) engine like Tesseract [cite: 8].

### 1.6 Complete `pdfplumber` Working Example

The following is a robust example demonstrating opening a PDF, defining custom settings for a borderless table, cleaning the output, and generating a validated `pandas.DataFrame`.

```python
import pdfplumber
import pandas as pd

def extract_pdf_table_to_df(pdf_path: str, page_num: int = 0) -> pd.DataFrame:
    """
    Extracts a borderless table from a specified PDF page and converts it to a DataFrame.
    """
    # Custom settings optimized for tables without explicit grid lines
    custom_settings = {
        "vertical_strategy": "text", 
        "horizontal_strategy": "text",
        "intersection_tolerance": 5,
        "snap_tolerance": 5
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        if page_num >= len(pdf.pages):
            raise ValueError(f"Page number {page_num} is out of bounds.")
            
        page = pdf.pages[page_num]
        # Extract the largest table on the page
        table_data = page.extract_table(table_settings=custom_settings)
        
    if not table_data or len(table_data) < 2:
        return pd.DataFrame() # Return empty if no valid table found
        
    # The first row is visually interpreted as headers
    headers = table_data
    
    # Clean headers: remove newlines and leading/trailing spaces
    clean_headers = [
        str(h).replace('\n', ' ').strip() if h is not None else f"Column_{i}" 
        for i, h in enumerate(headers)
    ]
    
    # Extract data rows
    data_rows = table_data[1:]
    
    # Create DataFrame
    df = pd.DataFrame(data_rows, columns=clean_headers)
    
    # Preliminary cleaning: replace newline characters in cells and handle None
    df = df.applymap(lambda x: x.replace('\n', ' ').strip() if isinstance(x, str) else x)
    df.fillna('', inplace=True)
    
    return df
```

---

## 2. Alternative Table Extraction with `tabula-py` (Version 2.9.3)

While `pdfplumber` offers granular geometric control, `tabula-py` remains an industry standard for automated extraction [cite: 9, 10]. `tabula-py` is a Python wrapper around the Java library `tabula-java` [cite: 11].

### 2.1 Dependency Requirements and Errors

Because `tabula-py` relies on `tabula-java`, a Java Runtime Environment (JRE) is a strict system prerequisite (typically Java 8 or higher) [cite: 12]. The wrapper utilizes `jpype` or invokes Java as a subprocess [cite: 11]. 

**Common Error:** `JavaNotFoundError` or a failure stating `java is not recognized`. This occurs when the Java executable is not mapped to the system's `PATH` environment variable [cite: 12]. To rectify this, developers must install Java and explicitly configure the system environment paths. Additionally, users can set the `TABULA_JAR` environment variable to point to a custom JAR file [cite: 11].

### 2.2 Function Signature and Key Parameters

The primary function is `tabula.read_pdf()` [cite: 11]. Unlike `pdfplumber`, which returns lists, `tabula.read_pdf()` outputs a list of `pandas.DataFrame` objects directly [cite: 11].

```python
import tabula

dfs = tabula.read_pdf(
    "report.pdf",
    pages="all",             # '1', '1-3', or 'all'
    multiple_tables=True,    # If True, returns multiple DFs per page
    lattice=False,           # Forces line-based extraction
    stream=True,             # Forces whitespace-based extraction
    pandas_options={'header': 0, 'dtype': str} # Passed to pd.read_csv/pd.DataFrame
)
```

#### Lattice vs. Stream Mode
`tabula-py` fundamentally approaches tables through two distinct algorithmic modes [cite: 9, 12]:
*   **`lattice=True`**: This mode dictates that Tabula should map the table entirely based on ruling lines (explicit borders) [cite: 9, 12]. It performs exceptionally well on fully enclosed grids (like a spreadsheet printed to PDF).
*   **`stream=True`**: Used when the table lacks ruling lines. This mode employs a clustering algorithm that looks for contiguous streams of whitespace to infer the separation between columns [cite: 12, 13]. 

By default, tabula attempts to guess the bounding box of the table (using `guess=True` [cite: 11]), and historically used a heuristic to alternate between lattice and stream, though recent versions allow specifying both or overriding defaults [cite: 14].

#### `pandas_options` Parameter
Because Tabula parses the PDF into CSV formats under the hood before funneling to Pandas, you can pass standard `pandas.read_csv` kwargs via the `pandas_options` parameter [cite: 11]. This is highly useful for preventing pandas from treating the first data row as a multi-index or incorrectly inferring numeric types: `pandas_options={'header': None, 'dtype': str}` [cite: 11, 13].

### 2.3 When to Choose `tabula-py` vs. `pdfplumber`

Use `tabula-py` when:
*   You require rapid prototyping and the table features a highly standard, grid-based layout.
*   You want direct-to-DataFrame outputs without writing custom list-parsing logic.

Use `pdfplumber` when:
*   The tables are misaligned, borderless, or highly complex.
*   You need to extract specific text coordinates, or debug *why* a cell is failing to parse via visual debugging (`.to_image()`).
*   You are operating in an environment where installing an external Java runtime is prohibited or restrictive (e.g., lightweight Docker containers, AWS Lambda).

---

## 3. Reading Excel Files with `pandas` (v2.2.3) and `openpyxl` (v3.1.5)

To establish a baseline for comparison, data must be ingested from Excel (`.xlsx`) files. In pandas versions prior to 1.2, `xlrd` was the default engine for all Excel files. However, `xlrd` dropped support for `.xlsx` to mitigate security vulnerabilities [cite: 15]. In pandas 2.2.3, the explicit, standardized engine for `.xlsx` is `openpyxl` [cite: 16, 17].

*(Note: Pandas 2.2 introduces the `calamine` engine as a highly performant Rust-based alternative [cite: 18], but for industry-standard compatibility and macro-free files, `openpyxl` remains heavily utilized and is required by the current query parameters.)*

### 3.1 Correct Parameters for Reading `.xlsx`

```python
import pandas as pd

excel_path = "employee_database.xlsx"

# Standard robust reading pattern
df_excel = pd.read_excel(
    io=excel_path,
    engine='openpyxl',      # Explicitly declare engine
    sheet_name='Sheet1',    # Can be string or 0-indexed integer
    header=0,               # Specifies the 0th row is the header
    dtype={'Employee_ID': str} # Explicit typing to preserve leading zeros
)
```

### 3.2 Data Type Handling and Inference Limitations

Pandas employs a type inference engine that analyzes the data upon ingestion. This inference frequently introduces logical bugs when dealing with enterprise data.

**The Integer / Float / NaN Issue:** 
By default, Pandas maps integers to the NumPy `int64` datatype. However, standard NumPy `int64` arrays do not support `NaN` (Not a Number) values [cite: 19]. If a column contains salaries (e.g., `50020`), but one employee's salary is missing (blank in Excel), Pandas will detect the missing value, insert a `NaN`, and subsequently **upcast the entire column to `float64`** [cite: 18]. Thus, `50020` becomes `50020.0`. 

**Preserving IDs (The Zero-Padding Issue):**
If an employee ID is `004521`, Pandas will interpret this as an integer and automatically strip the leading zeros, resulting in `4521`. 

**The Solution:**
1.  **Explicit String Coercion:** Pass a `dtype` dictionary to `read_excel`. `dtype={'Employee_ID': str, 'Salary': str}` ensures the literal text from Excel is preserved.
2.  **Using Nullable Integer Types:** Pandas recently introduced an extension array `Int64` (note the capital "I"), which *can* hold `NaN` values without upcasting to float [cite: 18]. `dtype={'Salary': 'Int64'}`. However, for diffing against PDF data (which is entirely strings), reading all reference data as `str` or `object` is often the safest preparatory step.

---

## 4. DataFrame Comparison Patterns for Record Diffing

Once PDF and Excel data are loaded into DataFrames, the task is to compare them row-by-row based on a unique identifier (e.g., Employee ID). We must identify:
1.  **Insertions**: Present in PDF (new) but not Excel (old).
2.  **Deletions**: Present in Excel (old) but not PDF (new).
3.  **Modifications**: Present in both, but fields (like salary) have mutated.

### 4.1 The Outer Merge with `indicator=True`

The most statistically sound methodology for identifying structural overlap in Pandas is the outer merge utilizing the `indicator=True` parameter [cite: 19, 20, 21].

```python
# Assuming df_excel (old) and df_pdf (new) share a common key 'Emp_ID'
merged_df = pd.merge(
    df_excel, 
    df_pdf, 
    on='Emp_ID', 
    how='outer', 
    suffixes=('_old', '_new'), 
    indicator=True
)
```

The `indicator=True` parameter appends a categorical column named `_merge` to the resulting DataFrame [cite: 20, 22]. This column will contain one of three values:
*   `"left_only"`: The key exists only in `df_excel`. (This implies a **Deleted** record).
*   `"right_only"`: The key exists only in `df_pdf`. (This implies an **Inserted** or New record).
*   `"both"`: The key exists in both DataFrames [cite: 20].

```python
# Isolating record-level differences
deleted_records = merged_df[merged_df['_merge'] == 'left_only']
new_records = merged_df[merged_df['_merge'] == 'right_only']
intersecting_records = merged_df[merged_df['_merge'] == 'both']
```

### 4.2 Iterating Over Matched Rows for Field-by-Field Diffing

For the intersecting records (`_merge == 'both'`), we must compare the columns to identify modifications. Because column names were appended with suffixes (`_old` and `_new`) during the merge [cite: 23], we can iterate through the shared columns.

```python
columns_to_compare = ['Salary', 'Department', 'Role']
modifications = []

for index, row in intersecting_records.iterrows():
    emp_id = row['Emp_ID']
    row_diffs = {'Emp_ID': emp_id, 'changes': {}}
    
    for col in columns_to_compare:
        val_old = row[f"{col}_old"]
        val_new = row[f"{col}_new"]
        
        # NaN handling is critical here. np.nan != np.nan evaluates to True!
        # We must normalize the comparison.
        if pd.isna(val_old) and pd.isna(val_new):
            continue # Both are NaN, therefore equal
            
        if val_old != val_new:
            row_diffs['changes'][col] = {'old': val_old, 'new': val_new}
            
    if row_diffs['changes']:
        modifications.append(row_diffs)
```

### 4.3 Handling NaN Comparisons and Type Mismatches

A fundamental rule of IEEE 754 floating-point mathematics (inherited by Pandas/NumPy) is that `NaN == NaN` is strictly `False` [cite: 24]. Standard equality operators will falsely flag identical missing records as "modified". As shown above, `pd.isna()` must be used to neutralize this behavior.

Furthermore, type mismatches (e.g., PDF extracts salary as `"50020"`, Excel has `50020.0`) will trigger false positives in a strict `!=` evaluation [cite: 25]. This mandates aggressive data normalization *before* the merge is attempted.

---

## 5. Data Type Normalization Between PDF and Excel

To successfully diff unstructured PDF tables against strict Excel schemas, both datasets must be projected into a normalized state space.

### 5.1 Normalizing Strings and Whitespace

Data from PDFs is inherently "dirty". A string might be `" Operations "` while the Excel counterpart is `"Operations"`.

```python
def normalize_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strips whitespace and converts to standard string types."""
    # Apply to object/string columns only
    str_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in str_cols:
        # Strip leading/trailing spaces and handle None/NaN mapping
        df[col] = df[col].astype(str).str.strip()
        # Convert string representations of NaN/None back to actual NaNs
        df[col] = df[col].replace({'nan': np.nan, 'None': np.nan, '': np.nan})
    return df
```

### 5.2 Preserving Zero-Padded Keys

Employee IDs or account numbers (e.g., `"EMP00002"`) must never be subjected to numeric conversion. If they are mixed alphanumeric, they are safe. If they are purely numeric (e.g., `"000543"`), forcing them to numeric types will truncate them to `543`. They must explicitly be cast as strings and optionally zero-padded using `.str.zfill(length)`.

### 5.3 Coercing Numerics Intelligently

To handle numeric columns extracted as strings from the PDF, use `pd.to_numeric` with `errors='coerce'`. The `coerce` parameter is vital: if it encounters an unparseable string (like `"N/A"` or `"TBD"`), it safely replaces it with `NaN` rather than throwing a runtime exception.

```python
def normalize_numerics(df: pd.DataFrame, numeric_columns: list) -> pd.DataFrame:
    for col in numeric_columns:
        if col in df.columns:
            # Strip out commas representing thousands (e.g., "50,000" -> "50000")
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            
            # Coerce to numeric (float64 by default if NaNs are present)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df
```

### 5.4 Float Precision Tolerance

When comparing financial data or metrics, small precision errors can occur (e.g., `500.0000001` vs `500.0`). For comparing these efficiently, use `numpy.isclose()` instead of strict equality [cite: 24, 25]. `np.isclose()` provides an `rtol` (relative tolerance) and `atol` (absolute tolerance) parameter [cite: 24, 26].

```python
import numpy as np

# Evaluating if old and new salaries are functionally equivalent
is_equivalent = np.isclose(val_old, val_new, atol=1e-5)
```

---

## 6. JSON Output Formatting and Serialization

After the diffing engine computes the insertions, deletions, and modifications, the final enterprise step is frequently pushing this payload to an API or logging system via JSON.

### 6.1 The NumPy Serialization Bug (TypeError)

The standard Python `json` library is remarkably rigid. It only natively understands base Python data types (`int`, `float`, `str`, `dict`, `list`, `bool`, `None`) [cite: 27]. Because Pandas relies on NumPy arrays for fast computation, the values iterated out of DataFrames are often typed as `numpy.int64` or `numpy.float64`. 

If you attempt to execute `json.dumps({"id": np.int64(42)})`, Python will throw a fatal error: `TypeError: Object of type int64 is not JSON serializable` [cite: 28, 29]. Although one might assume NumPy ints would inherit from Python ints, `numpy.int64` deliberately does not, due to memory structuring [cite: 30, 31].

### 6.2 Designing a Custom JSON Encoder

To circumvent this, we must extend `json.JSONEncoder` and override the `default()` method to trap NumPy data types and cast them back to native Python types [cite: 27, 28, 32, 33].

```python
import json
import numpy as np

class NumpyTypeEncoder(json.JSONEncoder):
    """Custom encoder to convert NumPy types to Python primitives."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj) # Casts np.int64 to native int
        elif isinstance(obj, np.floating):
            if np.isnan(obj):
                return None # JSON represents NaN as null
            return float(obj) # Casts np.float64 to native float
        elif isinstance(obj, np.ndarray):
            return obj.tolist() # Casts arrays to nested lists
        elif isinstance(obj, np.bool_):
            return bool(obj) # Casts np.bool_ to native bool
        
        # Let the base class handle anything else (will raise TypeError if unsupported)
        return super(NumpyTypeEncoder, self).default(obj)
```

### 6.3 Formatting, Sorting, and Indentation

To produce human-readable JSON reports, utilize the `indent` and `sort_keys` parameters. For our specific payload, we want to ensure the list of differences is sorted by the Employee ID.

```python
# Assuming payload is a list of dictionaries
payload = sorted(modifications, key=lambda x: x['Emp_ID'])

json_output = json.dumps(
    {"modifications": payload},
    cls=NumpyTypeEncoder, # Inject our custom encoder
    indent=4,             # Pretty-print with 4 spaces
    sort_keys=True        # Alphabetize dictionary keys
)
```

---

## 7. Reusable Python Utility Module: Architecture and Code

Synthesizing all researched topics, we formulate a comprehensive, enterprise-grade Python module. This script leverages Object-Oriented Programming (OOP) to encapsulate state and logic, offering robust error handling and adherence to clean architecture principles.

```python
"""
Data Reconciliation Utility
---------------------------
Extracts tables from PDF files using pdfplumber, imports structured Excel data via pandas/openpyxl,
normalizes data types, computes record-level differences, and exports safely to JSON.
"""

import pdfplumber
import pandas as pd
import numpy as np
import json
import os
from typing import List, Dict, Any, Tuple

class NumpyTypeEncoder(json.JSONEncoder):
    """Resolves 'Object of type int64 is not JSON serializable'."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj): return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return super(NumpyTypeEncoder, self).default(obj)


class DataExtractor:
    """Handles parsing and extraction of disparate data sources."""
    
    @staticmethod
    def extract_pdf_tables(pdf_path: str, table_settings: dict = None) -> pd.DataFrame:
        """
        Iterates over a PDF using pdfplumber, extracting tables and concatenating them.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
            
        if table_settings is None:
            # Default to text-based inference for modern borderless grids
            table_settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 4,
                "join_tolerance": 4
            }
            
        all_data = []
        headers = None
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables(table_settings)
                
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                        
                    # Assume first table's first row contains the headers
                    if headers is None:
                        headers = [str(h).replace('\n', ' ').strip() if h else f"Col_{i}" 
                                   for i, h in enumerate(table)]
                        all_data.extend(table[1:]) # Append rows skipping header
                    else:
                        # For subsequent pages/tables, check if the first row is a repeated header
                        current_header = [str(h).replace('\n', ' ').strip() if h else "" for h in table]
                        if current_header == headers:
                            all_data.extend(table[1:])
                        else:
                            # It's actual data, no repeated header was used
                            all_data.extend(table)
                            
        if not all_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(all_data, columns=headers)
        return df

    @staticmethod
    def read_excel_file(excel_path: str, sheet_name: str = 0, dtype_map: dict = None) -> pd.DataFrame:
        """Reads .xlsx using openpyxl, preserving dtypes where specified."""
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
            
        df = pd.read_excel(
            excel_path,
            engine='openpyxl',
            sheet_name=sheet_name,
            dtype=dtype_map
        )
        return df


class DataReconciler:
    """Normalizes and diffs DataFrames."""
    
    def __init__(self, key_col: str, numeric_cols: List[str]):
        self.key_col = key_col
        self.numeric_cols = numeric_cols

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies sanitization rules to the DataFrame."""
        df_clean = df.copy()
        
        # 1. Normalize String columns (strip whitespace, clean NaNs)
        str_cols = df_clean.select_dtypes(include=['object', 'string']).columns
        for col in str_cols:
            df_clean[col] = df_clean[col].astype(str).str.strip()
            df_clean[col] = df_clean[col].replace({'nan': np.nan, 'None': np.nan, '': np.nan})
            
        # 2. Key Column must explicitly be a zero-padded string, assuming 8 character standard
        if self.key_col in df_clean.columns:
            # First remove any '.0' if it accidentally got cast to float
            df_clean[self.key_col] = df_clean[self.key_col].astype(str).str.replace(r'\.0$', '', regex=True)
            df_clean[self.key_col] = df_clean[self.key_col].str.zfill(8)
            
        # 3. Numeric conversions
        for col in self.numeric_cols:
            if col in df_clean.columns:
                if df_clean[col].dtype == 'object':
                    df_clean[col] = df_clean[col].astype(str).str.replace(',', '', regex=False)
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                
        return df_clean

    def diff_dataframes(self, df_old: pd.DataFrame, df_new: pd.DataFrame) -> Dict[str, Any]:
        """Performs a row-by-row outer merge and identifies mutations."""
        df_old_norm = self.normalize(df_old)
        df_new_norm = self.normalize(df_new)
        
        # Merge utilizing indicator to flag structural differences
        merged = pd.merge(
            df_old_norm, 
            df_new_norm, 
            on=self.key_col, 
            how='outer', 
            suffixes=('_old', '_new'), 
            indicator=True
        )
        
        results = {
            "deleted_records": merged[merged['_merge'] == 'left_only'][self.key_col].dropna().tolist(),
            "inserted_records": merged[merged['_merge'] == 'right_only'][self.key_col].dropna().tolist(),
            "modifications": []
        }
        
        # Process modifications
        both = merged[merged['_merge'] == 'both']
        shared_cols = [c for c in df_old_norm.columns if c in df_new_norm.columns and c != self.key_col]
        
        for _, row in both.iterrows():
            record_id = row[self.key_col]
            changes = {}
            
            for col in shared_cols:
                v_old = row[f"{col}_old"]
                v_new = row[f"{col}_new"]
                
                # Check NaNs first
                if pd.isna(v_old) and pd.isna(v_new):
                    continue
                elif pd.isna(v_old) or pd.isna(v_new):
                    changes[col] = {"old": v_old, "new": v_new}
                    continue
                    
                # Float comparisons with tolerance
                if col in self.numeric_cols:
                    if not np.isclose(v_old, v_new, atol=1e-4):
                        changes[col] = {"old": v_old, "new": v_new}
                else:
                    # String / Categorical exact match
                    if v_old != v_new:
                        changes[col] = {"old": v_old, "new": v_new}
                        
            if changes:
                results["modifications"].append({"record_id": record_id, "changes": changes})
                
        # Sort modifications
        results["modifications"] = sorted(results["modifications"], key=lambda x: x["record_id"])
        return results

    @staticmethod
    def export_to_json(payload: Dict[str, Any], output_path: str):
        """Serializes the payload utilizing the custom NumpyEncoder."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, cls=NumpyTypeEncoder, indent=4, sort_keys=True)


# ==========================================
# Execution Example
# ==========================================
if __name__ == "__main__":
    extractor = DataExtractor()
    
    # 1. Extract PDF (New Data)
    print("Extracting PDF...")
    pdf_df = extractor.extract_pdf_tables("new_roster.pdf")
    
    # 2. Extract Excel (Old Data)
    print("Reading Excel...")
    excel_df = extractor.read_excel_file("old_database.xlsx", dtype_map={'EMP_ID': str})
    
    # 3. Diff and Normalize
    if not pdf_df.empty and not excel_df.empty:
        print("Reconciling Data...")
        reconciler = DataReconciler(key_col="EMP_ID", numeric_cols=["Salary", "Bonus_Score"])
        diff_payload = reconciler.diff_dataframes(df_old=excel_df, df_new=pdf_df)
        
        # 4. Export safely to JSON
        print("Exporting Report...")
        reconciler.export_to_json(diff_payload, "reconciliation_report.json")
        print("Completed successfully.")
```

## 8. Conclusion

Constructing a reliable pipeline spanning `pdfplumber`, `pandas`, and `json` demands profound attention to the idiosyncratic behaviors of each framework. `pdfplumber` necessitates geometric tuning to overcome visually unstructured PDFs, while `tabula-py` remains a viable stream-based alternative. `pandas` requires strict guardrails around type inference, explicitly utilizing nullable integers or strategic string coercion to prevent the `NaN`-induced upcasting of datasets. Finally, comparing these disparate sources necessitates outer-join pattern mapping, mathematical float tolerance (`np.isclose`), and rigorous subclassing of the `JSONEncoder` to insulate the output layer from NumPy's inherently non-serializable memory structures. By adhering to the patterns engineered in this report, developers can drastically mitigate ETL failures when traversing the unstructured-to-structured data divide.

**Sources:**
1. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEihVNrfT6i0WDUw7O7-L72hPeyBCu6wiu9BmbUqDK5jL3M6Mwb6IBegxQOABUXj4w8EWiGELkmgG9sTIgH9IDdtfIF6zoCUOfz3pgdIKE4ImIw-ZKFHQnmbQ==)
2. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFW4X_-D4BdsLWcXxXC5VDFlgqN7kQ0Id_aAMGRfcGpGZK_w8KAk8P0p31rMkZcSnDbV-VhNQRwQmoj0bfXorujZIsUHxAE7VfgCJIiiiFUQikQMYspnIm5q2QTno-M1NZ75lGpALU882EnZb0fjk7tF559z3PWbliGtlKNJGTnL17S_EaY-pKkwDqlMh9p-cYkKaHnWO_0aZvezsgqgZek27fsVsLJ_2k=)
3. [gitee.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-TPx0GSLXdI5UzOQXVdoVNCCxet1olqAaXpxTevtUmT1cGyXxqkujOILmHLR0PvcjWwkHx6nl1KAKLNgsrh-XQIICLa1apTZn5xdyfEzWBkihseOgKjJDChjsVw==)
4. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZTM9tJrry2fw5rhcfvr5naVY5UF5az4gJR7ZfWyBd9gtxIRYXYVExmv8dNpOW0p8mA7wuB8ju4LXHC4E8R4CpVi1_gUZ270TJV4geInzz9k-V600fkybvieRt2mFN5KccmaI1)
5. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFpaehRgjt9kzLzyaHL7G4yofRC9aBDZsI8WrLM50q11nWSOf0X7Xod89gkhPhO4fBa0-niC-fHYRj8sWvanSWSRRG2E0Bc2x-X8RLaD8HAil_zuXv1GGVlr0wkI8AVlf0TBOAivS0Nhv1D34NwVkk2xnMgDafm35QdyTdHX_bfNQF43ALaGFxFn527eqgmHhwVCsa63rOoK2zSwwnjw_Uogzm86QFoPkwTgQmVaRhZFA==)
6. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHBCRZ2bKiQqT1Pkk1SOfsFPyalgu1DfLeAH53766gUr8WqYJkBoyilRT6BsiaH5bjB8dEIGFIeBbN5aHAdEVIHHJE9mvpEEQ9dpbhsfiUe3u-zGPCRlTLm3e8mariUWnI0kriD0UKwOj0qoEB9nPJeWZHaKLFILmncfc-_ffkFoRxySrIXG4BBs288rwGSbkcF0s4Bv0UCUdQpQG8nhg==)
7. [pdfplumber.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-hgjOVeL7gFRhsGqLahRfF3hEF_ODRVLGOXLD_OTqgVadHB1YFCSZqbRSAkzSD_OVxH3rwcy4_Z6QrJBlzbjVHlTYRpbdmdIILp0YeGbgEnRvsJbrWpYFZNiT8GkOVK9YVt08_ICMlqXByWyzFnXoxYwlWjppyi8=)
8. [pdfplumber.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHsH_taE4lFlYEQ1W5SRD2tO1Uj-_IUVUPQs-yhc_TWnULWI8nuRlkfzdyCLfoBxq9i2OHwtV59aifNOBJmDA9Mim2Qt2msj42aJ7pr5J1gBAzIxkEtBwDTwYHpVzpfTk4TUcZReowIFSYkQgIgZwuh7cUrLEqUa9g=)
9. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEBU3jCkB70TNXx8n0RMLdfbUV1v2GrUNpG1TzG7kvNjssXx8TmptvwEwtliRoitoumUxe0QZUA8c1-SpEyRlwAwLhZwiwsWu15FwHIvorPZXsx-LawNmTWJsmkdshZahApyiJ4jVzTKxmtZQH-0tkiKf70K6C1zVc7Gng-qGvu6rb39n9baQsdeA7_Fb05da3c)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTeOLbMdIIbHanr7WS17HG7aSBYUB2QGRJhLC22Qjy0eng0_ONJ9VwFGhg4T3V50Lo277R54gQefpgrmrYvjIR156essHEcgDvdhNlv1FkGRcIGwRG1dhiSigMxXkDsLJML-NDGSSi_l21ILIDvV8DQ4ddtKApvcC8IixbifaaGAoG)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGnFIVa0mGsp_6I93_f9QbofHtEeLqq6TRwkvt4i0my9N8fnlPSkfZW5sHGD5YAX0NwiSFrvvmViW8jxG7LGtwU4-iQG3RRFgrxjcJOMRF1aMxOZMpxjEoiNHlgqnlDjQWi6mKtaZ2xMN-zQw==)
12. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWplgq2WSJqC4uj8apOZw60KZ0kGvkBXH3RQKxUFm1ztAP8RGzm4O-pXzwhsp8aczBybcbMQDsHoswOR9mUA6ag823S-CguSVSUMQAoBzveFZLuc_YdoGnHmPUbP6HVei6ekrIsntZHVyQkW7JI9bKFDf0LOn7a4lm_a04MAuu4R2XZkJ8MvUIXw==)
13. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEK_ugVyS4PznAe70YRksqAQnvf9oFrdABTH8Hdu81jKqpmUegjQouteRguVuJrOTjnVHLxznwGBm4-HdYhylknMXYBurhvdYi4i4EE_EZa7a0iMXlHYVzyYeEHU5EZ5qlvk9P_FMfqnsqYhwHr-Jlu5Fu0j9H3RI_QT8UV0k5USTB5i_9Nd7CVRQ==)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFGGubfMo7vQmgSNaY0I5-FoLqWljX45cXBB9wxbQGqcMtSyr4lven7Km8KzodGIzVbWB7cDIYvubSUbKdMny0SLIag8Atv61CTKD8mm9nVFRHD_tw7u9huRddcts3y1m9cxzsJXsFUDoR3xK6WPZevptLhjaaRmSu3FYUFUja629U4-zMqUqlXAvpvKxGPbygGQYa-Ghqmukz6YibTsz3eefSEhrtb9yqegl2FpnoYuI=)
15. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-hKyS01WkSFwtAkWtuV6CC_ieIAU3T81MKUdVxIjIu4DQgEDiWfT3LiRL_l7pqELiUud9R1oCv7Ff-khPjiJISVvPAAY8rCjOSZ4ZodPOB_XB8NTV1bmWWm8fS1hdXxEO0f8zGFwjJfN5RzVmxodnBf8XxwZjMSWAbMyERasi15STtHUOgqvPPs_Q)
16. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVnCmDU_ND1y7Mif9vDxsYHGCcQB1yDGRxq7IIwMxlKE2FQ3t6Iz1H5AfObq5BSUidumwjTknP38YG35cROLFv5cDAtBuyH6U9d6eLvIGzLjJR6IvkU24GH5Pd7HyEOv-7kplNtsu4-baYoSgmW_PF6hmi2rrUB4g=)
17. [naukri.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFWsvU6N4eLlitHN2DUT07Bhwk7XdgpwtjqbSZYcn-ngRu65HZ4uOHjC69s2_-tHFT-RM0oMEbwp8qFBgDc9xv00v-I4shqPTv-bYT8EUhZIJSw8R6nFsVHHkxYhGmnWyO2OXxCfemenhmdxZH4)
18. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFb4-84dTOIuDcU7abvINWtGJNJeuKnEJXQljfKXL9klmz7uN5uIjoVY9r5NRMY8OF-N91ZdRKR7scsIpDn_FAjedAvtcchkJ4sHr4bcBzTwfJ8v7NawUUYR6VD9FwUYkZDHr9qdYaVDw==)
19. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF8FQVPi3FrqK7M-Vt0EsjSw6_PTJ_4Tm-b5vO-g1juSDuBMeJvnbrXKeA50l34Z8c3IOFeeRd8Fi1EVgbyuOc0aJphlepzyRvrfWZZhLB2ly35fpBNaHQ0n4_6XiL3mPqENLALi9d3KFZSnczvK2a84puNVe4be9lBBUYEjhjJz4_zRskVFQphpCVX6DFLAgAFkFcGdw==)
20. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwiJZ0Vv0VnAFYUKvX-uc3bZsMzntdPfLijspEHiPFnVaQC69ttiE6avorNRd--9566SemHprWdo08Vp7u7oJxFbyiy7eVKHSYQQs-togQgEObS_BNl0eb9JaSHOUzWeWv2QYMy4R9oqcHYaCW_Foy_IdkXOvwYx0ZJaTz4G6K7Q==)
21. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGiI6cLRPD8lhl0j-1YdU_O6rFz2dXpMni_fOnnjv0jLV3WPvqGQsxvSAsHt08uEilC71UQ1y_QzdjSbUHJ3GT0uVoFAt4eXH3S509ja3LUHwG9Cqk9LkyRtwYkaIf2WdMxqHMi52aj_D3EH1GtweocTu69yVLb)
22. [nkmk.me](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqwXUu77EGYsLSUonSUR58d_DI2k5gZC2EVJJUmA90OwQrkUB9a7CZkovzpImoHKIaZ41usE2Ro69wH1MYxw2sawVWIV0ws3fsGq-y0V-xLep6WWCFxhHqfaqSiFbk_RoxljrUoN4=)
23. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGkA7mnaCbS-pyPmiqUlO1FvnpL9qE01K8GpRLYhIbJ34M18kx52R9ZWcdmowWZs0Cr5iLWNX6QUWpn1mYuCOKcD0g_HUNZoepaebBDTp1tUCCOrIRon9d4ZkTbZAXcmedyllLirZN10EhI7fzBmzq0enL1s4aQ6FsvXRQqsRKW87jdM_KlCFxgJaTf)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHR5LB_BiuXEwuPcGgQhyfneP1r9wfV7ndc8aFsbW77ia8yZCuOD9I4KgvfJX6tGuxApe_cPf7i4P3LWMEBUpDIDKA7pyLzY5_EnnkKmPhrZf56ZpTEG2_8k2oonwV2IWINSytjfL62ZPoS1d9xPwUn1U2PFxYUw9GkUJ6ANLkzjdlN9Gz6MBFtcA==)
25. [plainenglish.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFvpbYIBS5xoKxoRLzvLf8t5Igtek-EJNvRRkK4go_Tigl-lVyNbPGL53MfKLYqxj9O1SbX83oSFkAr8FjxjPAR-R5oApJ_ar0vrPQ2PkUwd505-xoqCxin0XDfMwEKUeeYE1xXDS6x3ZmBq1ZyLERser6ZgmedKT_RKlEOCmVu33Y_B6Vc6ghM0IM5WDyJJNATEqgik1n2QlvjYqZpqtqFuiTxm5A=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsrHD5AwRVP3qsudfJlM8C8RJnk4KS4pt8Z61NeZOA2md7rdflaXvHX_rgupARJjrdmNJKPTKEWc0pq0DezpNnATpm7rDvBYqeW0XczMjtw3bz4ffC4S3OeUnZe2T6M_YyhcA_NKUpCtC8VSexPlcyVv0_9Pz-dW9NiVPDgqS8lUsyj2rm1ST_yLMu7LCxT66kTQ==)
27. [saturncloud.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEaD0FK2JP8uWjzWAuD1yoNw7VjRSjEgnQ313O4T_veS9O8odV5CgRtn3oUtKcMAnODH244U6XBDRaT4kMKuXlq9aGMqJVX_qNLhwJN0OdMFLkcHym4Dg1j34b3Jo16ESz2WqD4zouW7xAe-8ZOVX3ro8XQNcniwKY1oaxynd5LPtqY0vBwLQ==)
28. [janbasktraining.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFkFFVcYjKyrMbdJ_kYe9ntO8OzWbqb-iuan2vz9NswIFIjm3YoLo385nSVqKPqcKTT3F-XWcl04aCTv0bAg8hM1n7sp6BLieogpllb9ppGuvNp5s7Zyr6SNBjprrqkUr5FqEpFM4JBfnUIR0-OhmFy5EmMi0CEf3ouNutDtysWH8dTdhaLNOzNazKL9j0j1gc8fHc6GTTSzNzVZdqBS71PKYrNDeeTUxkZ9rY=)
29. [codemia.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZ703Oxusw2v1WgIFAqIfEUiHnPIbOWv_KkjIeEcFsLLVCVBIGgqZHTRDdzfn61SiFaKdpJ0VrvqgIwdVxr32xVO6k3fZaYHw30MqkJ5dolTei7A7sN93oQ4pLN-V_3vw5P92ZAKF7qwEkafe2-peUVptDN_r2wzgK2mi7PGfaZpx6gr0VBeAUYK8o9WRAPBvLTsvxS8EmrrQcwQ==)
30. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJBdsYr8AcnNivdoETVj-wE3id9viO6oCHnvwyfxvEVf5Y5at9GkQpACA7rNM-AKWuGQX5gXW2i4vkyVtcqwPZF_aWYC9aytJpOa_wa6j2n9RecS-TW1b5vLxdIh8yWz2tCXDdVCx1w5m24ckigiVMnW5-ZkqBqVGUn0Hc3AlWSO8TEWIY8TMLBdNLvmI=)
31. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXTlynevUm-BxSS_gsd1rplNz1s0gwLbXfKtBmZgRogbt9X32jUp8YykpaQWhJNbnoSKXvMfqZlqsNsP2QjwhKSBBFb3l8KVGqtD-5t_SlOWonZVwJ3uAMmfPNZ08iKAc=)
32. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEubM8hEQW4WZq6FBtcJvh2aj6RDVM_oXAejdPlO2B2K1m8eLACSPFiqTNSYbcYTv2XY7ASRs9ToHIlqlrpZkhpXKry6LwULcm0ZQ3ATth_g1phhZ69gJnK9ZrCQdvQHyRMZVZya_OzXI-6XNBu2uT2O4ucQD19yyBRBvMTZSqyQf42Wn0uy5q9HwT7IFFo)
33. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGS6MVw5FU7Q7mQhPDalHPVsdaAeCnDgEe73OQIKqwV2jnRSxTUksKxLcR-n1YVdyvX42h_Uq5v9WcT6IhShggkUF8PFkX56sRHSLeJGpfTZcvPpNSobB4xxcE6QGaYwhZzu8qnQWP9Y37nOpVZQh9eQDD_vfG5JYQc6MW_pwnY3km6DSlIK9nkPtT3DybSpmYPtOh32d8etCrDPFbxWZwO)
