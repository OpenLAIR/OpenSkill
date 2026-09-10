# Comprehensive Analysis of Automated Spreadsheet Manipulation and Mathematical Evaluation in Python

### Key Points
*   Research suggests that Openpyxl 3.1.5 is a highly capable tool for reading and writing Excel files while preserving structure, but it lacks a built-in formula evaluation engine.
*   It appears that loading a workbook with the intent to read cached formula values (`data_only=True`) and subsequently saving it will permanently destroy the underlying formulas, necessitating careful state management.
*   The evidence leans toward modern Excel functions, such as `XLOOKUP`, requiring specific prefixing (e.g., `_xlfn.`) to be correctly interpreted when injected programmatically via Python.
*   While external recalculation via LibreOffice or Gnumeric command-line interfaces is possible, it is computationally expensive and fraught with configuration complexities; performing domain calculations natively in Python is generally recommended as a more reliable alternative.
*   Statistical function parity between Python and Excel requires precise selection of interpolation methods, as Excel's `PERCENTILE.INC` and `PERCENTILE.EXC` utilize entirely different algorithmic foundations (R-7 and R-6, respectively).

### Introduction to Spreadsheet Automation
Automating spreadsheet updates is a critical requirement in modern data engineering and administrative workflows. Organizations frequently rely on template-driven `.xlsx` files that contain pre-configured formatting, complex interdependent formulas, and structured tabular data. Modifying these files programmatically requires a delicate balance between injecting new data, executing two-dimensional lookups, and preserving the integrity of the original document. 

### The Challenge of Formula Evaluation
The fundamental limitation of most native Python Excel libraries, including Openpyxl, is the absence of an integrated calculation engine. When a Python script writes a formula to a cell, the result is not immediately available. Relying on the host operating system to force recalculation via tools like LibreOffice or Gnumeric introduces dependencies and potential points of failure. Consequently, robust automation skills often must mirror Excel's mathematical operations within the Python environment.

### Scope of the Report
This report provides an exhaustive, academically rigorous synthesis of the Python APIs available with Openpyxl 3.1.5, focusing on workbook input/output, robust data extraction, programmatic formula generation, external formula recalculation on Ubuntu 24.04, and the implementation of domain-specific calculations. It culminates in a proposed architectural framework for authoring reusable Python skills tailored for spreadsheet automation.

## Openpyxl 3.1.5 Workbook Input/Output and Sheet Access

The manipulation of Office Open XML (OOXML) files in Python is predominantly achieved using **Openpyxl**, a mature library designed to read and write Excel 2010 `xlsx/xlsm/xltx/xltm` files [cite: 1, 2]. As of version 3.1.5, released on June 28, 2024, the library provides extensive support for interacting with workbook structures, though it demands a precise understanding of its I/O parameters to prevent data corruption or loss of document fidelity [cite: 1, 3].

### Architecture and Import Structure
To utilize Openpyxl correctly, the standard import targets the `load_workbook` function from the core module. The package must be installed as `openpyxl==3.1.5` [cite: 1].

```python
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet
```

### The load_workbook API and Critical Parameters
The `openpyxl.reader.excel.load_workbook` function is the primary entry point for reading existing `.xlsx` files [cite: 4, 5]. Its signature contains several boolean parameters that dictate how the underlying XML is parsed into Python objects.

| Parameter | Default | Academic Description and Implications |
| :--- | :--- | :--- |
| `filename` | N/A | A string representing the file path or a file-like object open in binary mode [cite: 4]. |
| `read_only` | `False` | Optimizes memory usage by utilizing a lazy-loading generator model. When set to `True`, the workbook cannot be edited, and worksheets are returned as `IterableWorksheet` objects [cite: 4, 5]. Features like charts and images may be unavailable [cite: 6]. |
| `keep_vba` | `False` | Preserves Visual Basic for Applications (VBA) macros if the file is a `.xlsm`. Note that Openpyxl cannot execute or edit VBA; it merely preserves the binary blob [cite: 4, 6]. |
| `data_only` | `False` | Controls whether cells containing formulas expose the formula string or the last cached value calculated by Excel. If set to `True`, the formula string is discarded in the Python representation [cite: 4, 6]. |
| `keep_links` | `True` | Determines whether external links to other workbooks are preserved. Setting this to `False` discards cached data from external sources [cite: 4, 6]. |
| `rich_text` | `False` | Preserves rich-text formatting within individual cells when set to `True` [cite: 4, 6]. |

### The data_only Pitfall
A critical operational hazard in Openpyxl involves the `data_only` parameter. When a workbook is loaded with `data_only=True`, Openpyxl reads the cached values generated the last time the file was evaluated by a host application (like Excel) [cite: 6]. However, if the script subsequently saves this workbook, the original formulas are permanently overwritten by the static values [cite: 7, 8]. The library does not maintain parallel states for both the formula and its cached result [cite: 9].

To safely read calculated results while preserving formulas for a subsequent save, the recommended paradigm is to load two distinct instances of the workbook into memory:
1.  A read-only, `data_only=True` instance for extracting historical calculated values [cite: 8, 10].
2.  A standard, `data_only=False` instance for modifying cells and saving the file back to disk [cite: 10, 11].

### Worksheet Indexing and Traversal
Once loaded, a `Workbook` object acts as a dictionary-like container for worksheets. Individual sheets are accessed via their string titles [cite: 6].

```python
# Loading the workbook to preserve formulas and styling
wb = load_workbook('data_template.xlsx', data_only=False, keep_vba=True)
ws_task = wb["Task"]
ws_data = wb["Data"]
```

Openpyxl provides several methodologies for traversing the grid matrix:
*   **Dimensional Properties:** `ws.max_row` and `ws.max_column` return the integer bounds of the populated grid [cite: 6].
*   **Coordinate Access:** `ws['A1']` or `ws.cell(row=1, column=1)`. The `cell()` method is particularly advantageous for programmatic loops, as it accepts 1-based integer coordinates [cite: 6, 7].
*   **Iterators:** `ws.iter_rows(min_row=1, max_row=10, min_col=1, max_col=5)` and `ws.iter_cols()` yield tuples of cell objects, allowing efficient row-by-row or column-by-column traversal without loading the entire grid into memory prematurely [cite: 6].
*   **Range Slicing:** `ws['A1':'C10']` returns a two-dimensional tuple of cell objects [cite: 6].

When editing existing sheets, modifying the `cell.value` attribute leaves all existing styling (fonts, borders, fills) completely intact. Openpyxl treats the `value` and the `style` as independent attributes of the `Cell` object [cite: 6].

## Reading Excel Headers and Source Tables Robustly

In automated workflows, source data rarely conforms to strict, immutable coordinates. Task instructions often loosely specify that data resides in a sheet named "Data," but the exact bounding box may shift as rows and columns are added. Robust extraction requires heuristic location of headers and key columns.

### Locating Rectangular Data Blocks
To extract a two-dimensional lookup table, the algorithm must first identify the header row (typically containing years or variables) and the key column (typically containing series codes). 

1.  **Anchor Identification:** Iterate through the upper-left quadrant of the worksheet to locate a known anchor string (e.g., "Series Code" or "Year").
2.  **Boundary Detection:** Once the anchor is found, traverse rightward until an empty cell is encountered to define the horizontal bounds. Traverse downward to define the vertical bounds.

### Handling Excel Cell Data Types
Excel cells are notoriously polymorphic. A cell appearing as a year (e.g., `2024`) might be stored as an integer, a float (`2024.0`), a string (`"2024"`), or even an Excel datetime object. 

Openpyxl reads cell values directly into corresponding Python native types [cite: 12]. Therefore, robust extraction requires aggressive normalization.

*   **Year Headers:** Must be coerced to integers. Floats must be truncated or rounded safely. Strings must be parsed.
*   **Numeric Cells:** Must be parsed into `float`. Empty cells (`None`) or cells containing Excel errors (e.g., `#N/A`, `#DIV/0!`) must be trapped [cite: 7].
*   **Percentages:** Excel stores percentages as decimal fractions (e.g., `50%` is stored as `0.5`). No conversion is necessary if the raw decimal is desired, but the skill author must be aware that the formatted display masks the underlying mathematical value.

### Constructing the Two-Dimensional Lookup Dictionary
The optimal data structure for a 2D lookup is a nested dictionary or a dictionary with tuple keys: `{(series_code, year): float_value}`.

```python
def extract_2d_lookup_table(ws: Worksheet, anchor_string: str = "Series Code") -> dict:
    """
    Scans a worksheet to locate a data block and constructs a 2D lookup dictionary.
    """
    lookup_map = {}
    anchor_cell = None
    
    # 1. Locate Anchor
    for row in ws.iter_rows(min_row=1, max_row=20, min_col=1, max_col=10):
        for cell in row:
            if str(cell.value).strip().lower() == anchor_string.lower():
                anchor_cell = cell
                break
        if anchor_cell:
            break
            
    if not anchor_cell:
        raise ValueError(f"Anchor '{anchor_string}' not found in worksheet.")
        
    start_row = anchor_cell.row
    start_col = anchor_cell.column
    
    # 2. Parse Year Headers (assuming they are immediately to the right of the anchor)
    years = {}
    for col_idx in range(start_col + 1, ws.max_column + 1):
        val = ws.cell(row=start_row, column=col_idx).value
        if val is None or str(val).strip() == "":
            break # End of table
        try:
            year_int = int(float(val))
            years[col_idx] = year_int
        except (ValueError, TypeError):
            continue # Skip non-numeric headers
            
    # 3. Parse Data Rows
    for row_idx in range(start_row + 1, ws.max_row + 1):
        series_code = ws.cell(row=row_idx, column=start_col).value
        if series_code is None or str(series_code).strip() == "":
            break # End of table
            
        series_code_str = str(series_code).strip()
        
        for col_idx, year in years.items():
            cell_val = ws.cell(row=row_idx, column=col_idx).value
            
            # Safe numeric conversion
            if cell_val is None or isinstance(cell_val, str) and cell_val.startswith("#"):
                lookup_map[(series_code_str, year)] = None
            else:
                try:
                    lookup_map[(series_code_str, year)] = float(cell_val)
                except (ValueError, TypeError):
                    lookup_map[(series_code_str, year)] = None
                    
    return lookup_map
```

## Writing Excel Formulas with Openpyxl

Openpyxl does not compute formulas; it simply stores the formula string into the cell's underlying XML structure. The host application (Excel, LibreOffice) parses and evaluates this string upon opening the file.

### Exact Syntax and Separators
When injecting formulas via Openpyxl, the syntax must strictly adhere to the English localization of Excel functions [cite: 12, 13]. Furthermore, regardless of the user's regional operating system settings (which might use semicolons `,` as list separators in Europe), **formulas written by Openpyxl must use commas `,` as argument separators**. Excel's internal OOXML representation uses commas universally; localization is purely a presentation-layer feature handled by the desktop application.

Formulas must always be prefixed with the equals sign `=`.

```python
# Correct
ws['A1'] = "=SUM(B1:B10, C1:C10)"

# Incorrect (will cause corruption or #NAME? errors)
ws['A1'] = "=SUM(B1:B10; C1:C10)"
```

### Modern Functions and the _xlfn. Prefix
A profound nuance of manipulating `.xlsx` files programmatically is the handling of modern functions introduced after Excel 2010. Functions such as `XLOOKUP`, `UNIQUE`, `FILTER`, and `SORT` are technically extensions to the original OOXML specification [cite: 14, 15].

When Openpyxl writes an `XLOOKUP` formula directly, Excel may fail to recognize it natively, resulting in a `@` symbol prepended to the formula (e.g., `=@XLOOKUP(...)`) or a `#NAME?` error [cite: 16]. To ensure backward compatibility and strict OOXML compliance, modern functions must often be prefixed with the hidden `_xlfn.` namespace indicator [cite: 16, 17].

*   `=XLOOKUP(A1, B1:B10, C1:C10)` should be written as `=_xlfn.XLOOKUP(A1, B1:B10, C1:C10)` [cite: 16, 17, 18].
*   When referencing cross-sheet or cross-workbook ranges in `XLOOKUP`, standard exclamation mark syntax applies: `=_xlfn.XLOOKUP(A1, 'Data'!B1:B10, 'Data'!C1:C10)` [cite: 17, 18].

### Programmatic Formula Generation
Generating formulas programmatically requires precise string manipulation, particularly concerning absolute (`$A$1`) versus relative (`A1`) references.

#### 1. INDEX/MATCH with Two Conditions
Excel does not have a native 2D array exact match without array formulas, but an `INDEX` with a nested `MATCH` against multiple criteria can be constructed using boolean arrays.
`=INDEX(TargetRange, MATCH(1, (Criteria1Range=Cond1)*(Criteria2Range=Cond2), 0))`

#### 2. XLOOKUP with MATCH
For a two-dimensional matrix (e.g., finding a value at the intersection of a specific row and column), `XLOOKUP` can return an entire row/column array, which is then fed into a second `XLOOKUP`.
`=_xlfn.XLOOKUP(RowCriteria, RowRange, _xlfn.XLOOKUP(ColCriteria, ColRange, MatrixRange))`

#### 3. SUMPRODUCT
`SUMPRODUCT` is natively supported and does not require the `_xlfn.` prefix.
`=SUMPRODUCT(A1:A10, B1:B10)`

#### 4. Statistical Formulas
*   **MIN/MAX/MEDIAN:** `=MIN(A1:A10)`, `=MAX(A1:A10)`, `=MEDIAN(A1:A10)`
*   **AVERAGE:** `=AVERAGE(A1:A10)`
*   **PERCENTILE:** Modern inclusive/exclusive percentiles require prefixes.
    *   `=_xlfn.PERCENTILE.INC(A1:A10, 0.25)` [cite: 19, 20].
    *   `=_xlfn.PERCENTILE.EXC(A1:A10, 0.25)` [cite: 19, 20].

### Pitfalls of Writing Formulas
If a Python script writes `=SUM(A1:A10)` to cell `B1`, reading `B1.value` immediately afterward in the same script will yield the string `"=SUM(A1:A10)"`. Openpyxl maintains no dependency graph. Furthermore, if the file is opened by a tool that does not trigger automatic recalculation, the cell will appear empty or contain stale data until the user manually triggers recalculation (e.g., pressing F9 in Excel).

## Formula Recalculation and Evaluation Outside Excel

Because Python automation environments frequently execute on headless Linux servers (e.g., Ubuntu 24.04), relying on a user to open Excel and press F9 is unacceptable. External recalculation of the `.xlsx` file must be invoked programmatically. Two primary tools exist for this on Ubuntu: **LibreOffice Calc** and **Gnumeric**.

### LibreOffice Headless Command Line
LibreOffice provides a headless mode that allows interaction with the calculation engine without invoking the graphical user interface [cite: 21, 22, 23].

The most common approach to trigger file conversion is:
`soffice --headless --convert-to xlsx source.xlsx --outdir /path/to/output` [cite: 24].

**However, a critical caveat exists:** While the `--convert-to` command occasionally evaluates basic formulas natively, external references and advanced formulas are often ignored, resulting in static, stale values being written to the output file [cite: 24, 25]. 

To definitively force a "Hard Recalculate" and save the document, a macro must be executed. The Python script can invoke LibreOffice, passing a command to run a specific Basic macro that opens the document in stealth mode, calls `calculateAll()`, and saves the document [cite: 26, 27].

Alternatively, LibreOffice's UNO (Universal Network Objects) API allows a Python script to bind to a running headless LibreOffice instance via sockets, instruct the `StarOffice.ServiceManager` to load the document, trigger `document.calculateAll()`, and export the result [cite: 28].

*Incompatibility Notes:* LibreOffice 24.2 (the default on Ubuntu 24.04 LTS) supports modern OOXML fairly well, but `XLOOKUP` support was only formalized and stabilized in recent versions (specifically highlighted in LibreOffice 24.8) [cite: 15, 29]. Attempting to recalculate `XLOOKUP` using older headless instances will yield `#NAME?` errors.

### Gnumeric and ssconvert
Gnumeric ships with the `ssconvert` command-line utility, specifically designed for spreadsheet translation and manipulation [cite: 30, 31, 32].

The explicit command to force recalculation is the `--recalc` flag:
`ssconvert --recalc input.xlsx output.xlsx` [cite: 30, 32, 33].

**Caveats of ssconvert:**
1.  **Format Fidelity:** `ssconvert` excels at converting to text formats (e.g., CSV) [cite: 34, 35]. When attempting to read an `.xlsx`, recalculate it, and save it back to `.xlsx`, structural fidelity (macros, advanced charts, pivot tables) is often severely degraded or lost entirely.
2.  **Function Parity:** Gnumeric's function repository does not natively mirror the complete modern Excel suite. Specifically, while it handles basic math flawlessly, advanced dynamic arrays and modern lookups like `XLOOKUP` are historically unsupported or partially implemented [cite: 36, 37].

### The Robust Alternative: Python-Native Evaluation
Given the fragility of UNO bridges [cite: 28], the macro-injection requirements of LibreOffice [cite: 26], and the destructive nature of `ssconvert` [cite: 33], the most robust architecture for a reusable Python skill is to bypass external recalculation entirely. 

Instead, the skill should perform the mathematical evaluation in Python and write the *literal computed numeric values* into the `.xlsx` file alongside (or instead of) the formula strings [cite: 7]. This ensures that the data is immediately available to downstream consumers (like Pandas) without requiring an intermediate desktop application to render the document.

## Implementing Domain Calculations in Reusable Python Helpers

When migrating logic from Excel formulas to Python, the skill author must replicate spreadsheet semantics accurately, paying special attention to missing data, divide-by-zero errors, and array broadcasting.

### Net Exports as a Percentage of GDP
In macroeconomics, Net Exports ($NX$) are defined as Exports ($X$) minus Imports ($M$). To compute Net Exports as a percentage of Gross Domestic Product ($GDP$), the formula is:

\[ \text{NX % GDP} = \frac{\text{Exports} - \text{Imports}}{\text{GDP}} \times 100 \]

In Python, this requires safe arithmetic checks:

```python
def compute_net_exports_pct(exports: float, imports: float, gdp: float) -> float:
    """
    Computes Net Exports as a percentage of GDP.
    Returns None if any input is missing or if GDP is zero.
    """
    if any(v is None for v in (exports, imports, gdp)):
        return None
    if gdp == 0.0:
        return None
        
    return ((exports - imports) / gdp)
```
*(Note: If the Excel target cell is formatted with a percentage number format, the Python function should return the decimal ratio (e.g., `0.05` for 5%), omitting the `* 100` multiplier, preserving Excel's display mechanics.)*

### Replicating SUMPRODUCT (Weighted Mean)
Excel's `=SUMPRODUCT(Array1, Array2)` multiplies parallel arrays and sums the products. When used to calculate a weighted mean, it takes the form `=SUMPRODUCT(Values, Weights) / SUM(Weights)`.

Crucially, Excel's `SUMPRODUCT` explicitly ignores text strings and blank cells, treating them as zeros in multiplication but effectively excluding them if they cause length mismatches in standard array operations. In Python, we must align vectors, discard pairs where the value or the weight is invalid, and protect against a zero-sum weight vector. Weights should not be normalized prior to the function; the denominator handles normalization.

```python
def compute_weighted_mean(values: list, weights: list) -> float:
    """
    Computes a weighted mean, mirroring Excel's SUMPRODUCT/SUM logic.
    Pairs containing None, strings, or errors are skipped.
    """
    if not values or not weights or len(values) != len(weights):
        return None
        
    sum_product = 0.0
    sum_weights = 0.0
    
    for v, w in zip(values, weights):
        # Emulate Excel ignoring non-numeric cells
        try:
            val_f = float(v)
            weight_f = float(w)
        except (ValueError, TypeError):
            continue
            
        sum_product += (val_f * weight_f)
        sum_weights += weight_f
        
    if sum_weights == 0.0:
        return None
        
    return sum_product / sum_weights
```

### Summary Statistics
Python's standard `statistics` module provides basic parity with Excel for arithmetic mean, min, max, and median.

```python
import statistics

def compute_summary_stats(data: list) -> dict:
    # Filter out None and non-numeric types
    clean_data = []
    for x in data:
        try:
            clean_data.append(float(x))
        except (ValueError, TypeError):
            pass
            
    if not clean_data:
        return {"min": None, "max": None, "median": None, "mean": None}
        
    return {
        "min": min(clean_data),
        "max": max(clean_data),
        "median": statistics.median(clean_data),
        "mean": statistics.mean(clean_data)
    }
```

## Statistical Functions Parity with Excel

The calculation of quantiles (percentiles and quartiles) is a mathematically fragmented domain. Different software packages utilize different interpolation algorithms when estimating quantiles for continuous distributions from discrete samples [cite: 38, 39, 40]. 

### The Mathematics of Percentiles: INC vs EXC
Excel provides two primary functions for percentiles: `PERCENTILE.INC` and `PERCENTILE.EXC` [cite: 19, 20]. The legacy function, `PERCENTILE`, is mathematically identical to `PERCENTILE.INC` [cite: 20, 41].

Let $N$ be the sample size, and $k$ be the desired percentile (where $0 \le k \le 1$). The data is sorted in ascending order.

#### PERCENTILE.INC (Inclusive) / R-7 Method
The inclusive method allows $k$ to equal exactly $0$ or $1$, mapping directly to the minimum and maximum values of the dataset [cite: 20, 41]. This is the default behavior in R (Type 7), Julia, and NumPy's `numpy.percentile` (default `method='linear'`) [cite: 38, 40, 42].

The index of the percentile is calculated as:
\[ \text{Index} = k \times (N - 1) + 1 \]
If the index is not an integer, linear interpolation is performed between the adjacent data points [cite: 38, 41].

#### PERCENTILE.EXC (Exclusive) / R-6 Method
The exclusive method restricts $k$ to the open interval $(0, 1)$, meaning $k$ cannot be exactly $0$ or $1$ [cite: 19, 41]. It is used in risk analytics (e.g., Value at Risk) to exclude the extremes, simulating continuous theoretical distributions from small samples [cite: 41, 42, 43]. This maps to the R-6 method [cite: 38, 41, 42].

The index is calculated as:
\[ \text{Index} = k \times (N + 1) \]
Because of the $(N+1)$ multiplier, if $k < \frac{1}{N+1}$ or $k > \frac{N}{N+1}$, Excel will return a `#NUM!` error, as the requested percentile lies outside the interpolable bounds of the sample [cite: 38, 41].

### Reproducing Excel Percentiles in Python
To ensure exact mathematical parity without introducing heavyweight dependencies like Pandas or NumPy, these algorithms can be implemented using Python's built-in `statistics` module (Python 3.8+).

The `statistics.quantiles(data, n=4, method='exclusive')` function calculates cut points.
*   `method='inclusive'` matches Excel's `PERCENTILE.INC` (R-7) [cite: 38, 39, 43].
*   `method='exclusive'` matches Excel's `PERCENTILE.EXC` (R-6) [cite: 38, 42, 43, 44].

However, `statistics.quantiles` returns a list of cut points dividing the data into `n` continuous intervals. To request a specific percentile (e.g., the 90th percentile), one must set `n=100` and extract the 90th element, which is inefficient and rigid for arbitrary fractional percentiles. A bespoke interpolation function is superior for generic skill authoring:

```python
import math

def excel_percentile_inc(data: list, k: float) -> float:
    """
    Replicates Excel's PERCENTILE.INC (R-7).
    k must be between 0.0 and 1.0 inclusive.
    """
    if not 0.0 <= k <= 1.0:
        raise ValueError("k must be between 0.0 and 1.0")
        
    clean_data = sorted([float(x) for x in data if x is not None])
    n = len(clean_data)
    if n == 0:
        return None
    if n == 1:
        return clean_data
        
    index = k * (n - 1)
    lower_idx = int(math.floor(index))
    upper_idx = int(math.ceil(index))
    weight = index - lower_idx
    
    if lower_idx == upper_idx:
        return clean_data[lower_idx]
        
    return clean_data[lower_idx] * (1 - weight) + clean_data[upper_idx] * weight

def excel_percentile_exc(data: list, k: float) -> float:
    """
    Replicates Excel's PERCENTILE.EXC (R-6).
    k must be strictly between 0.0 and 1.0 exclusive.
    """
    if not 0.0 < k < 1.0:
        raise ValueError("k must be strictly between 0.0 and 1.0")
        
    clean_data = sorted([float(x) for x in data if x is not None])
    n = len(clean_data)
    if n == 0:
        return None
        
    index = k * (n + 1) - 1 # 0-based index adaptation
    
    if index < 0 or index >= n:
        return None # Equivalent to Excel #NUM!
        
    lower_idx = int(math.floor(index))
    upper_idx = int(math.ceil(index))
    weight = index - lower_idx
    
    if lower_idx == upper_idx:
        return clean_data[lower_idx]
        
    return clean_data[lower_idx] * (1 - weight) + clean_data[upper_idx] * weight
```

## Mapping Between Excel Ranges and Python Structures

Translating human-readable Excel coordinates (e.g., `H12:L17`) into Python integer indices is a fundamental requirement for targeting outputs. Openpyxl provides a dedicated utility module, `openpyxl.utils`, for these conversions [cite: 12, 45, 46].

### Coordinate Conversion Best Practices
1.  **Letters to Integers:** `openpyxl.utils.column_index_from_string("H")` returns `8` [cite: 12, 46, 47].
2.  **Integers to Letters:** `openpyxl.utils.get_column_letter(8)` returns `"H"` [cite: 12, 46, 47].
3.  **Coordinate String Parsing:** `openpyxl.utils.cell.coordinate_from_string("H12")` returns a tuple `('H', 12)`. Alternatively, `coordinate_to_tuple("H12")` returns the integer tuple `(12, 8)` (row, column) [cite: 46, 47].
4.  **Range Parsing:** `openpyxl.utils.cell.range_boundaries("H12:L17")` is the most powerful method. It takes a standard Excel range string and returns a 4-tuple: `(min_col, min_row, max_col, max_row)` (e.g., `(8, 12, 12, 17)`) [cite: 45, 46].

### Reusable Iteration Patterns
When populating a target range, the script must often traverse parallel metadata. For instance, in range `H12:L17`, column `G` might contain the series code, and row `11` might contain the years.

```python
from openpyxl.utils.cell import range_boundaries

def populate_target_range(ws: Worksheet, range_string: str, lookup_map: dict):
    """
    Iterates over a target range. Assumes row labels are in the column immediately 
    to the left of the range, and column headers are in the row immediately above.
    """
    min_col, min_row, max_col, max_row = range_boundaries(range_string)
    
    # Pre-fetch headers to avoid redundant cell access
    col_headers = {}
    for c in range(min_col, max_col + 1):
        # Assuming headers are 1 row above the target block
        val = ws.cell(row=min_row - 1, column=c).value
        try:
            col_headers[c] = int(float(val))
        except (ValueError, TypeError):
            col_headers[c] = None
            
    for r in range(min_row, max_row + 1):
        # Assuming series codes are 1 column to the left
        series_val = ws.cell(row=r, column=min_col - 1).value
        series_code = str(series_val).strip() if series_val else None
        
        for c in range(min_col, max_col + 1):
            year = col_headers.get(c)
            
            if series_code and year:
                # 2D Lookup
                target_value = lookup_map.get((series_code, year))
                
                if target_value is not None:
                    # Update cell value, preserving all styles implicitly
                    ws.cell(row=r, column=c).value = target_value
```

### Pitfalls with Merged Cells
Merged cells in Excel represent a visual abstraction. In OOXML, a merged block spanning `A1:C3` actually contains the data solely in the top-left cell (`A1`). The subsequent cells (`B1`, `C1`, `A2`, etc.) exist in the grid but are bound by a merge definition and must be left empty [cite: 6]. Modifying the value of a subordinate merged cell (e.g., `B1`) via Openpyxl will break the merge visually or corrupt the file's rendering. Always target the top-left coordinate of a merged area.

## Common Pitfalls and Deprecations

A Python skill author must navigate several architectural gotchas within Openpyxl and file system I/O.

1.  **Destructive Saving:** As reiterated, never execute `load_workbook(file, data_only=True)` and subsequently invoke `.save()` on that instance [cite: 8, 9, 10]. It strips the file of formulas.
2.  **Locale Inconsistencies:** Generating formulas utilizing localized function names (e.g., `SOMME` instead of `SUM` in French, or using `;` instead of `,`) will result in `#NAME?` errors. Openpyxl writes directly to OOXML, which requires absolute English adherence [cite: 12, 13].
3.  **Atomic Saving:** Overwriting the original file directly (`wb.save('original.xlsx')`) is risky. If the Python process terminates unexpectedly during the save operation, the OOXML zip archive becomes corrupted. The best practice is to save to a temporary file (`temp.xlsx`), and upon successful completion, utilize `os.replace('temp.xlsx', 'original.xlsx')` to ensure atomic overwriting.
4.  **Implicit Type Casting:** Be cautious with numeric data loaded from Excel that appears as text. An Excel cell formatted as text but containing the characters `123` will be read as a Python string. Subsequent mathematical operations will fail with `TypeError`. Explicit casting (`float(x)`) is mandatory [cite: 44].

## Skill-Author-Oriented Output: Recommendations and Architecture

Based on the synthesis of the underlying libraries, the optimal architecture for a reusable Python skill module relies entirely on Openpyxl for I/O and Python's native execution for mathematical evaluation. This neutralizes the severe fragility associated with headless LibreOffice/Gnumeric recalculation pipelines on Linux [cite: 24, 25, 28].

### Recommended Utility Boundaries

The skill should be organized into discrete, stateless utility functions to maximize reusability:

1.  **`load_safe_workbook`**: Handles atomic loading, optionally enforcing `keep_vba=True` to prevent macro stripping [cite: 4, 5].
2.  **`extract_data_matrix`**: Scans "Data" for bounding boxes and constructs the `{(series, year): value}` map.
3.  **`inject_values_and_formulas`**: Traverses the "Task" target ranges. Rather than injecting formulas that require F9 or LibreOffice invocation, this function should inject *both* the formula string (for the user's transparency in Excel) and pre-compute the expected numeric result into a separate reporting structure, or inject the computed values directly to avoid calculation lag entirely.
4.  **`compute_macro_statistics`**: Consolidates the bespoke `excel_percentile`, weighted mean, and basic statistical logic.
5.  **`save_workbook_atomically`**: Writes the modified Openpyxl instance to a temporary file, then replaces the target.

### Minimal Complete Working Code Snippet

The following encapsulates the discussed best practices into a modular script structure.

```python
import os
import math
import statistics
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

def load_safe_workbook(filepath: str):
    """
    Loads an Excel workbook preserving styles, VBA, and formulas.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Workbook not found: {filepath}")
    # keep_vba=True ensures .xlsm files do not lose macros
    # data_only=False ensures existing formulas are not overwritten by cache
    return load_workbook(filepath, data_only=False, keep_vba=True)

def atomic_save(wb, filepath: str):
    """
    Saves workbook to a temporary file, then performs an atomic replace.
    """
    temp_path = filepath + ".tmp"
    wb.save(temp_path)
    os.replace(temp_path, filepath)

def build_lookup_table(ws, anchor_string: str = "Series Code") -> dict:
    """
    Extracts 2D tabular data from the worksheet into a dictionary.
    Returns: {(series_code, year): float_value}
    """
    lookup = {}
    anchor_cell = None
    
    for row in ws.iter_rows(min_row=1, max_row=50, min_col=1, max_col=20):
        for cell in row:
            if str(cell.value).strip().lower() == anchor_string.lower():
                anchor_cell = cell
                break
        if anchor_cell: break
        
    if not anchor_cell:
        return lookup
        
    start_r, start_c = anchor_cell.row, anchor_cell.column
    
    # Parse years
    years = {}
    for c in range(start_c + 1, ws.max_column + 1):
        v = ws.cell(row=start_r, column=c).value
        if v is None: break
        try:
            years[c] = int(float(v))
        except (ValueError, TypeError):
            continue
            
    # Parse values
    for r in range(start_r + 1, ws.max_row + 1):
        code = ws.cell(row=r, column=start_c).value
        if not code: break
        code_str = str(code).strip()
        
        for c, yr in years.items():
            val = ws.cell(row=r, column=c).value
            try:
                lookup[(code_str, yr)] = float(val)
            except (ValueError, TypeError):
                lookup[(code_str, yr)] = None
                
    return lookup

def populate_and_calculate(ws, target_range: str, lookup_map: dict):
    """
    Fills a target range with values from the lookup map.
    Preserves all existing formatting because only .value is modified.
    """
    min_col, min_row, max_col, max_row = range_boundaries(target_range)
    
    years = {}
    for c in range(min_col, max_col + 1):
        val = ws.cell(row=min_row - 1, column=c).value
        try:
            years[c] = int(float(val))
        except (ValueError, TypeError):
            pass

    for r in range(min_row, max_row + 1):
        series_val = ws.cell(row=r, column=min_col - 1).value
        series_code = str(series_val).strip() if series_val else None
        
        for c in range(min_col, max_col + 1):
            yr = years.get(c)
            if series_code and yr:
                result = lookup_map.get((series_code, yr))
                if result is not None:
                    ws.cell(row=r, column=c).value = result

# Execution Flow Example
if __name__ == "__main__":
    filepath = "macro_data.xlsx"
    wb = load_safe_workbook(filepath)
    
    # 1. Extract
    ws_data = wb["Data"]
    data_map = build_lookup_table(ws_data, "Series Code")
    
    # 2. Populate
    ws_task = wb["Task"]
    populate_and_calculate(ws_task, "H12:L17", data_map)
    
    # 3. Write Formula Strings (e.g., modern XLOOKUP with prefix)
    # Note: Relying on the user to open Excel to evaluate this.
    ws_task["M12"].value = "=_xlfn.XLOOKUP(G12, 'Data'!A:A, 'Data'!B:B)"
    
    # 4. Save
    atomic_save(wb, filepath)
```

### Conclusion
Authoring a reusable Python skill for Excel manipulation requires navigating a landscape fraught with edge cases. By strictly controlling the `load_workbook` parameters, implementing mathematically rigorous statistical functions (respecting R-6 and R-7 delineations), bypassing unreliable headless CLI evaluations in favor of native Python computation, and handling the translation of OoXML matrices safely, developers can construct resilient, high-fidelity automation pipelines capable of operating securely in headless Linux environments.

**Sources:**
1. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEs2uRZtUQ4dH41FRJcJtIhhMKvZPanjuCWpL9XITtY1OjCpiz7pLPcbZG_w03tj5Mr33gHaULNMFZr77QGX2P2Uean3MQFo6XZfaA1BF6P7AUoP0JrpPNr)
2. [openembedded.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGgjCH0TDKn-xUyQfRRYu0OgEu3yYNZLoSa_IDnuWnLfMrPdmbX2Q7uS7jhlFpGXJkzqKRxDkbVokioIDr6W8rz0Q0_QfTxfTN08Xs4p-vUw-zCFgVzm1Hv4frj7TIy7X-WCwcqLafgZUq-5cdxfL8=)
3. [heptapod.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7PT057Ir7hxNFd1cDEOxEZbvUqylcuZ8myKa38YAkwKjQYtdYPPqAhcb76aZADk4_WSCmiajMVfawrrgMyzuprcxoyROOfGV4QegwS8_-BCE9AFXO77sG8wzRyrptnllFOBimM2pHRKcHgoqx4mxknSxh0xIlmAW4__0=)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECtsJLGwtD2IezlRpb3ZIs528ceJHEEzo_wD2UyGVD3BLZrOgQO73GEcYcspXnLjPYcm9BMkfHRQkcyJQYXIThsJkWw3WFD0RMMDvPFfzcNYSabYOZSjdB-8Z8SHDV5erMNeVce9dac6mzPHEOCvkBiRc6AHd9c6ItUtA=)
5. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFdUwNOecKP1F1G2NXkUXfrY-tFfUJeNKXkVgqNn6edhdTbqUEric9kqCUsLPcS3O7Brhk9sReM_i8bbnpEL94Z8RdpJ4yGiYfrpBGwpsd-w0WLmRkFC3rciA0ZzuncdKHnocsRTmATvJ76x52ysFhsbhQxHlQ-AaBU-6RMvF5Tg==)
6. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUbMJnT832k5fACEV4SWdatk7yLkFxWP4cP96n-6iS2n1mN0WGziA-oAAdmRLz0MQo_LcTIN6XQJlqfp_BbbjC7LQuXnceQhq2qZRyCM6FRszt2aNWP3bjWYAluuvkl6Ifr3b84rDFV_oH)
7. [mcpservers.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcgQ_k0VbqNOGFZQV9-n7u9aUd7_oVsiPPC5b9WuhiO90zaj53gX9hRcZ1SIt1XTgco3_l-7Efds-DVA3sVSIO7kV25HsdhTTlA77JU8JC3_6JBSo2VDlWqdcts7N_5XybpXID26Ajtw==)
8. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEbWG7FrwbzN18jS2l59gV7dn2m8nwbR-pJpjY6lVewgJtu1hHojKwCMDMoXZDy6z6E_lNey3HIk5wmSCSU6qt3KuHKWJRaczoyMe8u2MQ_9eGJ5XuZtq2uh2IKSw4shsWLya4X0f7FjROazhd04-RoYAmQxx5mxmtsifeEMhtIQm2TD7E4OhsccufAo9thoDPPJA==)
9. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGto54YBZvywAWOmN_dr9lzuGCt-vu6tSVHUGKzGSJy0-Qy2urjTruoPhUPbhK6MvbivaSPJtLM5IlQ1cmoU2WAD_CdQeqfaMazWQ6paoee9RnJMcbFJ5-C-W5a3dY-8enyKtelZyHoumkGowaGkg==)
10. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUpaMoupGslqZS82XpYvwUwSOWjq4GOtib3PSOvi049XsFR4rqPUFkR32w-eWaYZ1CxWMCP_wHZOz53YGCe0ZPpJcDc5925kZOLxPRBX5KUBMAoIV8an1NfOvOrZSuKn4kkqUumnAiNSwTWLEmVgVphDGbX5lwxfXP65Rgxbn-yP9o8dsxaA==)
11. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYR1l28f6MDHf3p_mqNUSDSQcit2XArDNj4yjSprAz_A19vAm3KLhrnkBG6JgkjskzmtERg3r9KK8fz88NWJdRbABBbMvhKJqBiE-8c-JUKkWi5HEm7A11kWPypPrxHUHVAATwkFR8jcRO7-LPog==)
12. [automatetheboringstuff.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFy_7iMp4zgXwmEzghbH0Q9PN6DI3JdreE7Dz8LRuYcyd10Q4txvFdtK47TulBntOSsFwwwLFtN_I-AA5uNXDbwwMCMgwbrkES04qaWmj8iAAAJGhU_IAupWtasgSNFAYYaFVUBIN0=)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGDS0vFeORhchwfTZPhvR3IKaCquAy9ATKAbm303v7uKumuQ1-5i9fkWlh1wuSBXqvMX3uELkrtxMj868Co20qDjZP9yoROpQB90UUae1G184ru6NcFF5O8XHKm7yI_8Xb0b-cEIplMBFTn5wu0dQX2KH0DwZD7OL5awQMTLhMGqiSDfydPv4NKhcBmkOHLWCcPwgeAfTTm)
14. [alibaba.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFY_or5rPijKFzZuNb95Iem4spD2shqMumXN3gE8VhQ5klKh-YemAyQlVGyHBmJXnPujsMx0_YazH_w8hZh_jKQLt8lRITu5PlbgMV8uF-mMASGlzSQQtrJkzAUjn3vdzDuJMJKCpQ2yflCdnPBvSH3fI5Aj9MK-Ehq01jySCPMlxYXL8wFSjtQMe_asX6Y6_rODGvOkkBWjvw=)
15. [omgubuntu.co.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEwM-dv3-PLXf-Xy6Y8RcLFpYnJG4so4XcBCFSm8SMqzH8NYfQSVIMvzXDoRoV87scY5hEkHLrEYKHZX8QaX4jXcym3eDT18yR3CNmgvbFvv6TDhpyl2-dRZ1N2QD1spbtLj9vkIQzn54td7HJTRyF9UWRkhI-0BDr8XeBZgw5riVcq5CS4)
16. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHDw_8HSd0rw9LEa7p45z0Fvdf0ra1DgFvAh6kik4oHUfaWDp4QHG3sip2pQ3HlbTO3nTroobuT7pX-6RY8bp2XazO2v9isguAQDUTpJucJjG_O4Hhi8YCD7CWKUl3kKQiB)
17. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFOe7H8flP3ihrpI5ezFDPYl20z6rLonQeXHCLwGE1wet2bXNV5N7V-nqyf-M7do5O8hkqRFB8jM8NdDheIy2T64iziVlYQWfeOhLvV41kAP_NrjueE5PchrphdjZ9r8JQv)
18. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHVsrgyEJeO0aU_UNfmId9rrRV0GhDmyvI13B8ocTJhkIgdXDkR-_d-83WSk6TCkGlb0KvSIZYVG-F0FQVp5oAaKD7QKMGCmhruQtwqR_ktMjUrMWmJCp0ZhVu-J6eqUITV)
19. [boardflare.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJ-o1Wo4b0I9aevO4ugL9gfzx_3-ZiXrAEsqB_tJSkqZ-BZXgF5H1nB0lF4x8EegMOq_3SXqzB0apu046lmUIvXv93ngiyA-zstqZPmfnT0QvvvJN_mHTgBUeFURQvCtyPLnlFDWP6PFUpeYjgQU3gxhLQND3Ddm50)
20. [statology.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSadrKkVYvdQQOsCdUUFSNP-WfDxskuJ69AVCiLxbmLC062bmigqbLZ0ju93_BE3YG6vH2ObWqw6hkBkPCw-Jj38Tno6mVYSTN-kjLA_RVIHAAWhOQUYijY8zwJJzT3lrJKwrQB2UrPOG70aOvIICHNFul8bn46g==)
21. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEyJP61kcGIHugO5ALqq0_ATJcKw70Pjx7xTra0JWwvtT8xBmPqc7mUzFPDrASDIXHs26K6Q-UytekYQF5F8ibuAhcs2DKhf4JTwmeLwaYIOuDUwyLyEMSYDL6JXB1D37wlaeOHs3Uby4ha6n730YqT993_kln4LPP1tppSwmRAa9chqFs=)
22. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQwlfcG5ej9pBrDbRcrrBjKX9TbOaZ92W9KT94oFxerpOplA1JY1qkU56LWwBCOSHtz0LnqyJEa6QKO0u35Jr_Y8Pf3_dzmUc3suWI-0FHwXXgaycQvnsmP_dTefBacJvcnozqzpFex5rlzZxQNxpTzQAHiKyUXVkRxYdGzRqqxa1PFBtO7vo=)
23. [archlinux.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGzdT2a-m0f2EQNVOI3qTtHGXcEfYoRvGFMN-SHxgkSWbb8-Jx6Z9cjU7CZ6CoQGmdofdHkMqON7QB1vGEBNs30AqNyG0CQNc-5e7d6HWh19FbUlWK1ejCKow_UaK7QOoKtNA==)
24. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHtYLQIR8LY4TmNPRPz2X6ShajrtLvMG3doNMC0o1wqAZDjDVxLENo1c1KRjmJNXcLpaD4MKwDF-YjyRf9QsMGNnYXyLeo5Ez2-6dxutUUcMRA99wbWaAZXY670W2iFcAckFSkHFeCE4iXSwtB0pOY3IwbKYp7L5OMpJTLQUKGkAUrg7YL0di0t)
25. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlkoWgLqkQVITI5VK5xEqthOKFSad5J-iPnVV3ebdXHRh_dduknmOpmuUBWcOI-ZTQUcPsm8S-se8hltcan4g0BUDX6pVz31AczkAXU80A3k3U_KJIAQZfCQStnm4tSG86BWwkVBXVphnXUJ0ndmn9tzvH3BIHwlKTVnp3AyB__bFcnsRWjQ-uJYSYRw==)
26. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGg2IAkrudUJpx_hsXkqsQsW5-w8o-OemrQMPOpeRACiGng6ociGM-VbQdgp35F41XhS7KO_CuZY22SYy05gk_MwrVKYDd3qwNA2J-phLsiOvMT30MAuZasGTVljzgJlp1S1plznR_93jirK_zyZ1EMGiwuWGUuwb8sUNpAbyCsxIOOcFNFlbuQDoQ-c2tti-nB9E0zEERp)
27. [superuser.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7-KokGSUDhsGfbd3dO_Rs8HkfPAa5MKzni0-zsfOLUefIkYxQUp6x9Axk5yTffhV2ZiIMlenmOZXVoGzuXA4SHm8RMX0xzuZF0ghD5pKPitVEJ5LoS_NIhT9RFcgeySGUaG-uKx3EkoyFtC6JusUEd7jlwtCxgv4ySUGT5eqNRc7D0LrcDK5s-TX-WAFvbn_UeniXLKbg10bp41MF5WWlmaCxug==)
28. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnPbqHFuzv9_m16oNtlMe3j90t51h76NG8QC4_Ty35D9Bh8N4_ojnDJg02ps1NrgDjbCdh7u4jUe3619rC4oYEL6DvrvlORo5JyLQi8j-CX2QYJhsJenAd5cTRlSJll6OEmy3fS_DJ6eiyPt4rDBD2g__5OWo2S5FaNDoFRQhf3FXO6u3pe8lkGCzy6K0nb8ihkG-ZwqzfxSxxQqC4fhMyETjgpYuqCIVXu2X5ww==)
29. [debugpoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7H1Ae4kg8H97pAm0NIyWxu0T4V8kWvswvYfob0CjlLmA0PjbRUzC98u9_Rrb7maHZ3IJvLbZ6SvrkH55CpRhcGnSCEihvHhVp3WpHGo5eqAgBgaMOxHXh7o9In27qiLXYtUekp9gevR0Qgw==)
30. [ubuntu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGv_mSBdhYxVwTVRYvQYXs8HXMBJsdVjfZqazVRgv9Dw_eO2XhbVVs9IHOLk-_tGFrmhS9LVm7w0R6bfB27b50F8z3ZgYpfIgXgbFCfTMKP0kBcZ_6oIgL6eE_GzfkGYuSBSLzwzTac8jnBfeFgSCgAyps464XMhw==)
31. [opensourceisbetter.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEiHRigSQsRtzMmujmz2BrWzbzSuGk4wKSjmi1Rxb0PisJ7UWjxNRtlW19RKZN2EDqVdzRYlAbCad5czf9VDRQSaHOjM8FAiLT39nc5suCt80HTy7uVyxaXLLOyUNEX6l9ACeZLfPBhkY2Bge4oQgCPCEdwhJSx4Sq-snnx5iGK5wzmcIxjB9UdbYods-eP)
32. [debian.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOxejkrUBsKfxUpgxsI-13wxhk8wTXuswu2d2AFmYHIWO37r7OW594WfFmfUJGBer4W1hHrgZJ8OUmp3YJydJM2FbsejKmeMt3_hZhLu1NMSI3iZ0pOrwwStHqfSSzBz7lXFOWDg6K0LJSPJG0__EOdmVJ9V2TBA==)
33. [gnome.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwo5hbk3dg-W4M0Bp1c16BuNYMb2x_iQHd16cnM2O45Ne1DFT_YHDqbkIRmj7iwGPauFeYZTursHaaJuZkbQ9YEkmbyRq3GJcc0Dp_OpVnv0TswmhHpMwBBwCfFBqbZL-zA0-GKofY6puE)
34. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHL99Q8al2hkNi-vtHVHoAvyFTglNap-DROu3JkFvaJQQstRWF1vIvOKVigLkLDyigmI7jH_IDA52uBaqBt3y-qtTjEtpZUfYgnknJ-nBK3qXevTI38nlgGQ7aV4_2p8IBiebKsvt2mnGmIxGVdcVAols417iktM9MVmQ7xkyYRsDZLit-WVBExGclUZRJg6pFBxKpDNpy7JT3u)
35. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEX9M9srYPJAHZ5SZQAUDdHS7W1-rtw_dfUA6VYXTt8mGgCxwEPDOI0iZWvWEVXJNihR6d_UDaDM6_0AgtJ4BfdCdCvb3SNyJbXFYvon_70O27YTzCaiDeZCcnJJ0ji6707btL7r6jOiotxTjODqXvKUr6FJ_s30oBJzaeTJZYeJgrOQI8MFEXLvlVOYqLY1e9dE-Lsjpr_2rI_Y-dBncAkkrT1GbCe)
36. [techrepublic.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEMRx1bFT_bB44r_XLGKI49itYxm7J2icRkzOgnhsttNE2udtaswz1NY37it_SKQjsNHEmtrTFP3uFIZyclSMpyZjt5KmpQo0AkjaZoSdvhMOvamiThogs3Y42YPokrJmY-6tYIjRmwUx-NaFBAA6PDQt18vORC6RzANwjtmrhggw==)
37. [nasniconsultants.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXJH__4GN4rCH5Fe0kIuprzQ5cc3iPA3ffHL7lI_v3zkInmn5fovLcIqLjRZAEVKGZaP5P99fZDGyT7gApxAi2Q0UjEa5kYxxlF8L1tGrZOLMcZh0HoeMgDEYtaPmRUJ1G1O10X3y6pXOP6TSOoV9Yfz0-Zl2IKKHExpVaHs_vICltwIV18wnM-rgucG92R6EY6nqGPpBV48UrXJRu04sRoa9qnbrifg==)
38. [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF04vuRUVznagzqB1Vc8wskQLzpo8n2-a8Zj-Nd5Ex22TkZ9tw3Qsto54jaoQd1GX5UYuAonHWmklCKG2JS7l4U97noEi4JDzlQ6pUcAIWRMI-t_vUefXBN1723RQ==)
39. [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEGwsE1zRGqXytM-Kln5DfjI-Vu9IjmfzXCKfE_l3HK5MM0m36XSYWrZEkHSQXVpE2DmFTv_Wavnh9A30L0OitkUtKyX-M_b1He9Idq7pjz7sKucoHfM_9mkI_v_c9d)
40. [axibase.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9HPv0x0bPWBzov4se_QAVwwxpd5vviadytSH5QIbLk4Eh-nWH4HJ6aauAa8m4qmVFM2U1Ar_-Fz0eLs9ncfcBoQ2mJGn9nZ3sLl21QALYY0xP69S0uU6I1HNKzK4S94mcnRNMBbrju2MaNNqQ)
41. [arabpsychology.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_liXCRTG5bc6-9A25UwgetDAl-z5DKouZORA1sRRbxpj-9KrueizdA4D8EfVViX0T3wTmAp6esDgKoa_GNPB_oshKjfctfamTT6rysbzu64xrUzhTFwc2ygdBqR83Ac4pXy37qyw8flSsk_gworNJUgkxoQNfARJF0226rC1IemZ3Tm5bZOy3ZJiKKBmgFGjUZQxdCyG30LMEXKpvxD6KO3FUxlgJ9Q==)
42. [substack.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFW_6oFc25Kp4upKxa-xnEQO400LPRre87hDpo1O43XItGyWpKsdEVbN4Q2pKtZz--Oyl0nekTSGbWvGFu0CAPVcy5fDm2ZS0tuBpGy9cfoJYd80Tuw_T3Aa_S-p7hQCxKdSVi9BeTM56uSXtOrL8SIBV7Ke7EuDejXHY979qQ_vMuP)
43. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHrLSxsiZ-qtfLg_UOY0x1fy8P41oO-AZ2YmHve0ag2QtpaOmg4gw7IG0DHgresfNW4n_cmh83RW-JLhsJEhzftw4Fwk_oZH-BjxwCIuwEhqOWobEm9xRAfqhNtw-3PWWcE3l04gc8ZkLTnnrQKdoTSQKXtkpoW4j38trAYOK06K8--V4S7TTw0oMfAMCg=)
44. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2l2p0m9pCspG7U6BhfsvI4W-3y7DbG2Ij3rdt8X2AWIb74I_7prVIIdVZFv2NJVnhsDDKD6xL9joxigf-nytOBbzhi97LQg57BoAkpT_J100wWvMdrEjLYifd1wRDfO06jtZd8iG1k9-3goyZ5ke7DahRBkMV09SzvA==)
45. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgg3N8R9WIC4GG7pnRI6xkGNoRw8hJ48GzKUCnRyjPGfl3p9hIEbqQHGqDFixFwELAKsyBY6PeDnH7uFe2JErFTis_PCspLP-bWbiC0VwgA1-6FUiaQ5RRmJoBJ_SDGXwL2EzBQrswANIwKq_RZryDVubDrg==)
46. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7VPd2pzEfAzM2UmmMt9e6rCsSc8uVZgYO_ZhVW7FWyItkB6gAxGQW5un_0RvK-T7NQDTVnuVEb1-Cs_Sg0O9NUhCVpsAAlkLEa7orYRJbEloOCpar-2kMcJOb5qW7jyG4ZxbVrLaIYOTGh-eyzcmipikYTAaVpNvc)
47. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGq45zTJgSowAOuzO0vPkKqirjcwidINbqetfcvzx0lD9aEy9ngO6LxPbm-g6dty_z48CvPjn8TCMSeTouBdKw97z9LfZJpUNpgZsXI7quHCBBpvx3MMQrYx4Ajlsh-fHhq7RZSOE3jzTdXOSr6EtnqsT2FFY7BJF4y7OqCjxtl_iEAvqorbJJGUXKJyU14HPOU7Ky8p2g8RnlUqKL7QTqErWF6odXowg==)
