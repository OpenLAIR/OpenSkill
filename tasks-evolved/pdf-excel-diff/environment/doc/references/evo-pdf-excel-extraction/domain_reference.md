# Domain Reference for evo-pdf-excel-extraction

**Responsibility**: Handle all data ingestion: PDF table extraction (with multi-page support, header detection, cell cleaning) and Excel file reading. Normalize column names, strip whitespace, preserve string IDs, and coerce numeric columns appropriately.

**Key functions to implement**: extract_table_from_pdf, read_excel_file, normalize_dataframe

---

## 1. Extracting Tables from PDFs with `pdfplumber` (Version 0.11.4)


`pdfplumber` is an advanced Python library built on top of `pdfminer.six` [cite: 1]. Rather than attempting to read a PDF as a continuous text stream, `pdfplumber` treats the document as a coordinate system. It identifies individual characters, lines, and rectangles, utilizing their spatial coordinates to infer the presence of tabular structures [cite: 2, 3].

### 1.1 Core API: Opening and Processing Files


The primary entry point to the library is the `pdfplumber.open()` method, which functions as a context manager and yields a `pdfplumber.PDF` object [cite: 1, 4]. 

```python
import pdfplumber

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

## 3. Reading Excel Files with `pandas` (v2.2.3) and `openpyxl` (v3.1.5)


To establish a baseline for comparison, data must be ingested from Excel (`.xlsx`) files. In pandas versions prior to 1.2, `xlrd` was the default engine for all Excel files. However, `xlrd` dropped support for `.xlsx` to mitigate security vulnerabilities [cite: 15]. In pandas 2.2.3, the explicit, standardized engine for `.xlsx` is `openpyxl` [cite: 16, 17].

*(Note: Pandas 2.2 introduces the `calamine` engine as a highly performant Rust-based alternative [cite: 18], but for industry-standard compatibility and macro-free files, `openpyxl` remains heavily utilized and is required by the current query parameters.)*

### 3.1 Correct Parameters for Reading `.xlsx`


```python
import pandas as pd

excel_path = "employee_database.xlsx"

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