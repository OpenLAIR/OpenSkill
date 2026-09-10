# Programmatic Financial Modeling: Integrating Python's openpyxl, Pandas, and LibreOffice for Advanced Spreadsheet Automation

**Key Points:**
*   **Formula Evaluation is Application-Dependent:** Python libraries like `openpyxl` can write Excel formulas, but they do not compute them. An external application (Excel or LibreOffice) must evaluate the formulas to cache the results.
*   **Data Exploration vs. Manipulation:** `pandas` is ideal for initial data exploration and structural analysis of messy financial spreadsheets, whereas `openpyxl` is required for precise cell-level manipulation that preserves formatting and formulas.
*   **Financial Standardization:** Standard conventions in financial volatility calculation dictate the use of sample standard deviation (`STDEV.S`) over population standard deviation (`STDEV.P`).
*   **LibreOffice Compatibility:** Modern spreadsheet formulas such as `XLOOKUP` are supported natively in LibreOffice Calc starting from version 24.8, closing the functional gap with Microsoft Excel.

**Overview of the Workflow**
Automating financial data workflows often requires a bridge between programmatic data extraction and traditional spreadsheet-based financial modeling. Analysts frequently deal with structured datasets, such as International Monetary Fund (IMF) commodity prices, which must be extracted, processed, and injected into reporting templates. This report explores a hybrid approach: using `pandas` for structural discovery, `openpyxl` for non-destructive data injection and formula writing, and a headless LibreOffice instance for automated formula recalculation.

**Addressing the Complexity of Spreadsheet Automation**
Spreadsheets are notoriously unstructured in their raw form. Variable header rows, merged cells, and complex formula dependencies present significant challenges for automated parsing. Research suggests that a multi-step pipeline—combining programmatic reading, strategic formula placement, and programmatic recalculation—offers the most robust solution for maintaining data integrity without manual intervention.

***

## 1. Introduction

The automation of financial calculations—specifically regarding central bank asset management, commodity price exposure, and risk metrics like Reserves at Risk (RaR)—demands high precision. Institutions frequently rely on Excel `.xlsx` files as the standard medium for financial reporting. However, processing these files programmatically requires careful handling to preserve existing formulas, formatting, and structural integrity [cite: 1, 2]. 

The Python ecosystem offers two primary libraries for this task: `pandas` and `openpyxl`. While `pandas` excels at ingesting tabular data and performing vectorized computations [cite: 3, 4], it is not designed to read or write native Excel formulas or preserve the complex formatting of template files. For non-destructive editing—where data is injected into specific cells and formulas are written as strings to be evaluated later—`openpyxl` is the industry standard [cite: 5, 6]. 

This comprehensive report details the methodologies for reading complex IMF commodity datasets, writing advanced financial formulas (such as logarithmic returns and annualized volatility), executing cross-sheet data transfers, and ultimately forcing formula recalculation using a headless LibreOffice environment. 

## 2. Initial Data Exploration with Pandas

Before manipulating an unfamiliar Excel file with `openpyxl`, it is highly recommended to inspect its structure. Financial reports, such as IMF commodity price datasets, rarely start neatly at cell A1. They often contain metadata, merged headers, or blank rows at the top of the file [cite: 7].

### 2.1 Using `pandas.read_excel()` for Structural Discovery
The `pandas.read_excel()` function provides powerful parameters to bypass irregular formatting and isolate the target data [cite: 3]. The underlying engine used for modern `.xlsx` files is `openpyxl`, whereas the older `xlrd` engine is restricted to legacy `.xls` formats [cite: 4]. 

To locate specific data (e.g., "Gold" prices) within an unfamiliar file, you can utilize parameters like `skiprows`, `usecols`, and `header`:

```python
import pandas as pd
from pathlib import Path

# Define file path
file_path = Path.cwd() / "imf_commodity_prices.xlsx"

# 1. Read a sample of the file to discover the structure
# We read the first 20 rows without assuming a header to find where the data begins
df_preview = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20, engine='openpyxl')
print(df_preview.head(15))

# 2. Once the row containing "Gold" or the true headers is identified (e.g., row 5)
# We can skip the metadata rows. Note that skiprows is 0-indexed.
# If the header is on row 5, we skip the first 4 rows.
df_clean = pd.read_excel(
    file_path, 
    sheet_name="Commodities", 
    skiprows=4,          # Skips rows 0, 1, 2, and 3 [cite: 3, 8]
    header=0,            # Row 4 becomes the new header [cite: 7]
    usecols="A, C:F",    # Selects specific columns using Excel range notation [cite: 7]
    engine='openpyxl'
)

# 3. Search for the row containing Gold
gold_data = df_clean[df_clean['Commodity Name'].str.contains("Gold", case=False, na=False)]
print(gold_data)
```

### 2.2 Advanced Parsing Arguments
*   **`skiprows`**: Accepts an integer (number of lines to skip), a list of specific 0-indexed row numbers to skip (e.g., `[cite: 1]`), or a callable lambda function (e.g., `lambda x: x in [cite: 1]`) [cite: 4, 8].
*   **`usecols`**: Accepts a string of Excel column letters (e.g., `"B:F"`), a list of integers, or a list of column names [cite: 7].
*   **`true_values` / `false_values`**: Can be used to map specific strings to boolean values during import [cite: 4, 9].
*   **`thousands`**: Setting `thousands=','` ensures that financial figures containing commas are correctly parsed as floats rather than strings [cite: 9].

## 3. Reading IMF Commodity Data with openpyxl

While `pandas` is excellent for ingestion, it destroys formulas and formatting when writing back to Excel. To perform surgical extractions and insertions, `openpyxl` must be used [cite: 5, 10]. 

### 3.1 Loading the Workbook
The `load_workbook()` function is the entry point. A critical parameter here is `data_only`. 
*   `data_only=False` (default): Returns the actual formula string (e.g., `=SUM(A1:A2)`) [cite: 11, 12].
*   `data_only=True`: Returns the *cached value* of the formula from the last time Excel or LibreOffice evaluated and saved the sheet [cite: 13, 14]. 

```python
import openpyxl

# Load workbook preserving formulas and formatting
wb = openpyxl.load_workbook("imf_commodity_prices.xlsx", data_only=False)
ws = wb['Commodities'] # Access specific sheet by name [cite: 15]
```

### 3.2 Iterating Through Rows and Handling Merged Cells
When reading structured data, you can iterate through a designated range using `ws.iter_rows()`. This is significantly more memory-efficient than calling `ws.rows` on a massive sheet, as accessing unpopulated cells dynamically creates them in memory, potentially bloating the application footprint [cite: 15].

Merged cells pose a unique problem: only the top-left cell of a merged range contains the value; all other cells in the range return `None` [cite: 6]. To extract data from merged cells reliably, you must check if a cell's coordinates fall within any merged range boundaries [cite: 16].

```python
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string

def get_real_value(sheet, cell):
    """
    Returns the value of a cell. If the cell is part of a merged range,
    it returns the value of the top-left cell of that range. [cite: 16]
    """
    if cell.value is not None:
        return cell.value
        
    for merged_range in sheet.merged_cells.ranges:
        if cell.coordinate in merged_range:
            # Get the top-left cell of the merged range
            top_left_coord = merged_range.start_cell.coordinate
            return sheet[top_left_coord].value
            
    return None

# Find the row corresponding to Gold
gold_row_index = None
time_series_data = []

# Iterate through rows 1 to 100, looking at column A (index 0 in 0-indexed tuple)
for row in ws.iter_rows(min_row=1, max_row=100, min_col=1, max_col=15):
    commodity_cell = row 
    
    # Check actual value accounting for merged cells
    val = get_real_value(ws, commodity_cell)
    
    if val and isinstance(val, str) and "Gold" in val:
        gold_row_index = commodity_cell.row
        # Extract the time series data from columns B onwards (index 1 to 14)
        for data_cell in row[1:]:
            time_series_data.append(data_cell.value)
        break

print(f"Gold data found on row {gold_row_index}: {time_series_data}")
```

### 3.3 Handling Date-Formatted Cells
`openpyxl` automatically detects cells formatted as dates in Excel and converts them to Python `datetime` objects [cite: 5]. If you are writing dates back into Excel, you can simply assign a Python `datetime.date` or `datetime.datetime` object to `cell.value`, and `openpyxl` will apply the default date formatting. You can also explicitly set the number format:

```python
import datetime

date_cell = ws['B1']
date_cell.value = datetime.datetime(2025, 1, 1)
date_cell.number_format = 'YYYY-MM-DD' # Enforce specific date formatting [cite: 5]
```

## 4. Writing Excel Formulas with openpyxl

One of the most potent features of `openpyxl` is its ability to inject Excel formulas directly into cells [cite: 10]. Because `openpyxl` is not a calculation engine, it does not evaluate the mathematical output of the formula; it simply writes the formula string into the XML structure of the file [cite: 11, 17].

### 4.1 Syntax for Writing Formulas
To write a formula, you assign a string beginning with the equals sign (`=`) to the `value` attribute of a cell [cite: 18]. 

```python
# Standard arithmetic and basic functions
ws['D2'].value = "=B2/C2"
ws['D3'].value = "=SUM(A1:A10)" [cite: 18]

# Financial functions
ws['E2'].value = "=LN(B3/B2)*100"
ws['F2'].value = "=STDEV.S(C3:C14)"
```

### 4.2 Formula Locale and Compatibility Pitfalls
Formulas written via `openpyxl` must be written using **English function names** and standard US-locale separators (comma `,` for arguments, period `.` for decimals) regardless of the local language settings of the user's Excel or LibreOffice installation. When Excel or LibreOffice opens the file, it automatically translates the English XML function names into the user's local language (e.g., translating `=SUM()` to `=SOMME()` in French) [cite: 1, 18]. 

If you attempt to write a localized formula string (e.g., `=SOMME(A1;A2)` with a semicolon separator) via `openpyxl`, the spreadsheet application will likely fail to parse it, resulting in a corrupted formula or a `#NAME?` error.

## 5. Financial Calculations as Excel Formulas

Central bank asset management, particularly the assessment of Reserves at Risk (RaR) regarding gold holdings, relies on standard statistical measures of volatility.

### 5.1 Monthly Log Returns
In quantitative finance, returns are typically calculated logarithmically rather than as simple percentage changes. Log returns are time-additive and assume continuous compounding, making them statistically robust for time-series modeling [cite: 19].

**Formula:** \( R_t = \ln\left(\frac{P_t}{P_{t-1}}\right) \times 100 \)

In Excel, the correct function for the natural logarithm (base *e*) is `LN()`. The `LOG()` function, if used without a second argument, defaults to base 10 in Excel. Therefore, the exact formula string to inject via `openpyxl` is:
```python
ws['C3'].value = "=LN(B3/B2)*100"
```

### 5.2 Rolling Standard Deviation: `STDEV.S` vs `STDEV.P`
Volatility is formally defined as the standard deviation of returns [cite: 20]. Excel provides multiple functions for standard deviation:
*   `STDEV.P()`: Calculates the population standard deviation, dividing by \( N \).
*   `STDEV.S()`: Calculates the sample standard deviation, dividing by \( N-1 \) (Bessel's correction) [cite: 21, 22].

**The Standard Convention in Finance:** When analyzing historical market data (like commodity prices), you are almost always analyzing a *sample* of a continuous, infinite time series. Using `STDEV.P` will systematically underestimate the true volatility. Therefore, **`STDEV.S()` is the strictly correct and standard convention for financial volatility calculations** [cite: 19, 23].

For a 3-month rolling standard deviation of monthly log returns:
```python
# Assuming log returns are in column C
ws['D5'].value = "=STDEV.S(C3:C5)"
```

### 5.3 Annualized Volatility
Volatility scales with the square root of time. To convert a monthly standard deviation into an annualized volatility metric, the standard financial formula is to multiply by the square root of 12 [cite: 24, 25].

**Formula:** \( \sigma_{ann} = \sigma_{monthly} \times \sqrt{12} \)

To express this as a single Excel formula calculating annualized volatility from a 3-month rolling sample:
```python
ws['E5'].value = "=STDEV.S(C3:C5) * SQRT(12)"
```

### 5.4 Central Bank Gold Price Exposure and Reserves at Risk (RaR)
In the context of central bank reserve management, "Gold Price Exposure" represents the financial risk—the potential loss in the portfolio's value due to the inherent volatility of gold prices over a specific time horizon [cite: 26, 27, 28].

**Reserves at Risk (RaR)** is an application of the Value at Risk (VaR) framework applied to sovereign reserves. It quantifies the maximum expected loss of the reserve portfolio at a given confidence interval [cite: 29].

A simplified, standard approach to calculating the standalone RaR for gold exposure is to multiply the current market value of the gold reserves by the annualized volatility of gold, divided by the total value of all national reserves (foreign exchange, SDRs, and gold) [cite: 26, 30]. 

*   **Gold Price Exposure:** `gold_reserves_value * annualized_volatility`
*   **Reserves at Risk (RaR):** `(gold_reserves_value * annualized_volatility) / total_reserves`

Translating this into an Excel formula via `openpyxl`:
```python
# Let B2 = Total Reserves, B3 = Gold Reserves Value, E5 = Annualized Volatility
ws['F5'].value = "=(B3 * E5) / B2"
```

## 6. XLOOKUP and INDEX+MATCH Formula Syntax

When dynamically linking datasets, lookup formulas are essential. Historically, `=INDEX(..., MATCH(...))` was the gold standard, but modern spreadsheet applications have adopted `=XLOOKUP()`.

### 6.1 XLOOKUP Compatibility in LibreOffice
A critical consideration when generating files for automated environments is application compatibility. While `XLOOKUP` was introduced to Microsoft Excel in 2020, it was notably absent from LibreOffice for several years, requiring workarounds like the `Lox365` extension [cite: 31, 32]. 

However, **LibreOffice Calc officially implemented native support for XLOOKUP starting in version 24.8** [cite: 33]. If the target environment runs LibreOffice 24.8 or newer, `XLOOKUP` can be safely written via `openpyxl` without compatibility issues.

**XLOOKUP Syntax:**
`=XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found], [match_mode], [search_mode])` [cite: 33]
```python
# Writing XLOOKUP with openpyxl
ws['B10'].value = "=XLOOKUP(A10, 'Data'!A:A, 'Data'!C:C, \"Not Found\", 0)"
```

### 6.2 The INDEX + MATCH Alternative
If backward compatibility with older versions of LibreOffice (pre-24.8) is required, the `INDEX` and `MATCH` combination must be used [cite: 34].

**INDEX/MATCH Syntax:**
`=INDEX(return_array, MATCH(lookup_value, lookup_array, 0))`
```python
# Writing INDEX+MATCH with openpyxl
ws['B10'].value = "=INDEX('Data'!C:C, MATCH(A10, 'Data'!A:A, 0))"
```
*Note on LibreOffice Array Formulas:* In versions of LibreOffice prior to 7.0, complex array functions required special keystrokes (Ctrl+Shift+Enter) to evaluate properly. However, standard `INDEX/MATCH` combinations generally evaluate as standard formulas without array forcing [cite: 34].

## 7. openpyxl API for Copying Data Between Sheets

A common requirement in financial reporting is aggregating calculations from multiple raw data sheets into an "Answer" or "Summary" sheet. `openpyxl` provides simple dictionary-style access to move between worksheets seamlessly [cite: 1, 15].

```python
import openpyxl

wb = openpyxl.load_workbook("financial_model.xlsx")

# Accessing different sheets
ws_raw = wb['Raw_Data']
ws_calc = wb['Calculations']

# Check if Answer sheet exists, create if not
if 'Answer' not in wb.sheetnames:
    ws_answer = wb.create_sheet('Answer') [cite: 15]
else:
    ws_answer = wb['Answer']

# Approach 1: Copying static values from one sheet to another
val_to_copy = ws_calc['F5'].value
ws_answer['B2'].value = val_to_copy

# Approach 2: Writing a formula that references another sheet
# This is preferred if you want the Answer sheet to update dynamically
ws_answer['B3'].value = "='Calculations'!F5"

# Save the workbook
wb.save("financial_model_output.xlsx") [cite: 1, 6]
```

**Avoiding File Corruption:** When adding data to existing sheets that already contain formulas, ensure you do not inadvertently overwrite the formula cells. Using `ws.insert_rows(idx)` can push existing data down safely, and `openpyxl` will attempt to automatically adjust Excel cell references in existing formulas. Furthermore, to avoid corrupting complex files, always ensure that `keep_vba=True` is set if dealing with `.xlsm` files, and be cautious that unsupported visual elements (like advanced charts in newer Excel versions) might occasionally be dropped by `openpyxl` during the save process [cite: 15].

## 8. Using LibreOffice Command Line to Recalculate Formulas

This is arguably the most critical step in an automated headless pipeline. When `openpyxl` writes a formula like `=LN(B3/B2)*100`, the XML simply contains the string. If a subsequent Python script attempts to read this file using `data_only=True`, it will return `None` because the formula has never been evaluated by an engine to generate a cached value [cite: 13, 17].

To force the generation of cached values without opening the GUI, you can utilize LibreOffice in headless mode. 

### 8.1 The `--convert-to` Caveat
The most commonly cited command is:
```bash
libreoffice --headless --convert-to xlsx:"Calc MS Excel 2007 XML" input.xlsx --outdir /tmp/ [cite: 35, 36]
```
However, testing and community bug reports indicate a significant pitfall: the `--convert-to` command does not reliably force a full recalculation of complex formulas or inter-sheet dependencies before saving [cite: 37, 38]. Output files may still contain `0` or `None` for calculated cells.

### 8.2 The Robust Solution: Headless Macro Execution
To guarantee that all formulas are computed and the results are written to the XML cache, you must instruct LibreOffice to open the file, explicitly execute a `calculateAll()` command, and save the file [cite: 39, 40]. 

First, create a LibreOffice Basic macro (which can be saved in the global `My Macros` library of the environment running the script):

```basic
Option Explicit
Sub RecalculateAndSave(sSourcePath As String)
    Dim sPath As String
    Dim oDoc As Variant
    Dim loadComponentProperties(0) As New com.sun.star.beans.PropertyValue
    
    ' Run in hidden mode
    loadComponentProperties(0).Name = "Hidden"
    loadComponentProperties(0).Value = True
    
    GlobalScope.BasicLibraries.LoadLibrary("Tools")
    sPath = ConvertToURL(sSourcePath)
    
    If FileExists(sPath) Then
        oDoc = OpenDocument(sPath, loadComponentProperties)
        ' Force recalculation of all formulas
        oDoc.calculateAll() [cite: 39]
        ' Save and close to cache values
        oDoc.store()
        oDoc.close(True)
    EndIf
End Sub
```

You can then trigger this macro from the command line (or via a Python `subprocess` call):
```bash
libreoffice --headless --nologo "macro:///Standard.Module1.RecalculateAndSave($(pwd)/financial_model_output.xlsx)" [cite: 39]
```
Once this command completes, the `.xlsx` file will contain fully cached values. A subsequent Python script can now call `openpyxl.load_workbook('financial_model_output.xlsx', data_only=True)` and successfully extract the computed floats [cite: 11, 13].

## 9. openpyxl Pitfalls and Edge Cases

When deploying this architecture in production, several edge cases must be navigated carefully.

### 9.1 The `data_only` Dilemma
As discussed, the `data_only` parameter is mutually exclusive per load [cite: 11, 12]. 
*   If you load with `data_only=False`, modify a cell, and save, the formulas are preserved, but newly triggered formula results are not computed.
*   If you load with `data_only=True` and save, **all formulas in the workbook are permanently destroyed** and replaced by their hardcoded cached values [cite: 11]. 

**Best Practice:** Never call `.save()` on a workbook that was loaded with `data_only=True` unless your explicit goal is to "flatten" the workbook and remove all formulas. Always maintain two separate `load_workbook` instances in memory if you need to read values and write formulas simultaneously [cite: 11].

### 9.2 Version-Specific Issues
In `openpyxl` versions around 3.1.x, developers must ensure they manage memory correctly. Accessing `ws.iter_cols()` or `ws.iter_rows()` without bounds (e.g., iterating entirely through `ws.rows`) on sparsely populated sheets can cause openpyxl to instantiate millions of empty `Cell` objects in memory, leading to out-of-memory crashes [cite: 15]. Always use `min_row`, `max_row`, `min_col`, and `max_col` limits.

### 9.3 Preserving Existing Sheets and Formats
When `openpyxl` saves a workbook, it generally preserves existing sheets, background colors, borders, and fonts. However, it does not copy charts or images when using `wb.copy_worksheet()` [cite: 15]. To avoid corrupting external links, ensure `keep_links=True` is maintained during loading [cite: 12].

## 10. Conclusion

Integrating Python with LibreOffice provides a highly capable, open-source pipeline for advanced financial modeling. By utilizing `pandas` for initial data exploration [cite: 3], `openpyxl` for precise formula injection [cite: 5, 18], and a headless LibreOffice macro for deterministic recalculation [cite: 39], developers can automate complex macroeconomic risk assessments—such as central bank Reserves at Risk calculations. 

Adhering to financial statistical conventions, particularly the use of `STDEV.S` for rolling volatilities [cite: 19] and correct continuous compounding formulas, ensures the analytical output remains rigorous. With the introduction of `XLOOKUP` in LibreOffice 24.8 [cite: 33], the functional parity with Excel is nearly absolute, allowing for seamless cross-platform spreadsheet automation.

**Sources:**
1. [automatetheboringstuff.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHMVTZycoU9G2m3YbnA_N8DIfg0pCVCUJV0d5HzWxv6kYl-nydKo4Vcm2YEhdrTJWpaOPKd6z9wuCx_2Yh8vn6mIMQ8-5zi_cwHs_mwW_Ja3g9nYsY_qcK58roOyQSYg6NHMXu39_xcOG1t)
2. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4NBubvZg8EoYgyQ22hOh7FMWF8fyI6LQWoK3UpA3vJGLfEbcSdv0f8HC0_XqRpNhEnF7Ivl-8TWq_v7MYV3l_3LznnxXSpbN5R4zuWHBU7bWF_QUOWw==)
3. [askpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF1rcARj1C3DcNTB7OtRPDv3v2Ooaun4s_PqeKavrXsXHC5WWn_a1D7fJrJLSQoscPq9cOcj6vcQtSnbmZJCMn_lNNx_mPhjSy5kHCKnlr2tnrDpTFp8i-v6BzXdkd4M2_6KKerW7h1XClFdIuRUWePl3gqg6o36w==)
4. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGy23OX_UDPw4qu746huJLGUnljo4486cQcaCWfMxmdXugiyxdhWxgP85Kq9skFL8r_HIfhicszbCVxWIHtCWcImnC6xGT2WCxQ3QSb_IjBcyDxg6HNSPwfs3kdTD1AjkAUrFqXJ-ysuDzYDaYT32AXYMRlUinU8RgW)
5. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5GB5RmYGHmVNIk-jyA3BIi9-LfrCXpM7IfI-ln1iIduPxjkOvd3RZIcn1qck3SLXhYiGI7GCMw-MFTzVg2v53UeZecbF2Qf1u1fMm5ztraaYPbIzT30QJx8CIjzHP4mJJQriGIaeP2sBacG9kqBhXHMaLxuGywUubZ6ApL7alqNEz7fGErOj-nmywPrCkuIk6r9Y1PcC6UA==)
6. [zetcode.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEg3g5UVhDjp5A3-7V8f9hxqJhTY74afll40_UqltDODLt4BHiUMq9QgH4hKlxg4-LAHHDoKxmUu73hHK7OskllwLALOzyIYAd-1BMyfZ3l-4AGRauipEYl41o=)
7. [pbpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF0qULEIEPA2a1o6KMS6KV4ul6k9jE7lQbGx6Qj6hsroA-Bc-0Fd546UvHqX1t4Y8wrtDVe_2_8YYPEgO3tkqj4sVZ9zA2O2G1RFsCUwCCBwimhRw5VhCgqw_shG_xJTjmmwg==)
8. [statology.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4ygMbZ4hCc1bvCQ3XDpgDCUEBk7C0jXnpb3HCm7rHLAOnvnsDQkQHcCU-n4AEuEy4ZnXZsQ1k4OthqZv97G_KS9xN3u11ZKMhGWd-qJZSyltShmgH08Dgk-FYb1cr6bxThp9r5BrskYheCSk=)
9. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGXwo0TKMRQ67LwXb9m-PzOXxTfubheFOB3aP-7kwLwqeXRB4YQfKpv8EkphaOM5-QwefYivocF2dwHlaD2JuXpYgioANVEoHmAPgccRbgciOhmc_RO4hGFV_jV1pn9cMnu)
10. [realpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFc8MWvgTfId6FCAgr93pQ331A9pgDl1e2HCFaLjfIiXnEIQfaN5dMdn2UtXpt1ar2afgCSY-yoQEJrpOVbcNwqGExWRq6IRs6sBwijve2XGJ8Ansah8piJSr5XbFdSalrJxW9LVFHTXjIqvicd6YlY)
11. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUXckDfMedUI84FUuv3kCvco8cu28TCydHBEo3FiJ9CEGR5oIfm6Z9TNsZW2G4LSVmg4PRAjzgcDstjVN4XWY4mhKhygI_WQx-g_t1IJZWCNatluCiROvGM0ZmB4-KKU95OgFcpJiQGgHoIFlx2Q==)
12. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWVKUZm6jfvPr7kvTMmJsmrW1hCywqdGi4jyq6_QsasWNXsKpljjV0wIa4vXolXnRZx_K2wWENBKfT7tMV4xAQ6nwNWsl3nujlEE7yiO4f1ZHvap9TIxZLYJ6qMEqWeAiWXdKgCXrSjBeZ93FBt67xsBSWFkPqNz_Cu-0=)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYVH-kAWczIKg459RH1kD4vozg8G9IZIY8P91w0Ds7rvcd9jkCmydqDFdxJ7wwyY9DVI49SEFhhkYjzcKZElpZa3ymFcY4YM1ndrvwZRabi8yUPDS2xkLMEKLebMF4tJT3s-FJMPNBmGudE4a63J0pn0tGb5dHVhBiZaGQdNS7Kfk6ax0D6OmSYsY2OdEIV-g=)
14. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9_VFNcBfYZTZZLLExPQu5pV3L-xXu5yYeGGM3R2TRsgz0BkweSQZ6O-JsKtQFUz61QIaWOK7OR4mOkJF4kOAvDmeVh3amK3OlzF8bMT_MOLmvraqwDXMWGXxe-BunwRa6)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-egf1l8cDVKvKs_UlU0CilIoExKjZlyAgc8YjnbzjdtT7SP4lykpRuPg02tGbXq5OmbhZ26tVgR3VJfAYnUFYddErLoQrMNis8AeIe-xHuQuNeri-TKV3SAQSf3lALpLO0ANV0f1HK1wk)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2_aJMM2-_4vvwFbe-e9IFyASqit-QjrOd6k0QsqMZR-kOd-iaQG5_RKN1qkgbYxiyAg6Eum3Rhgvku7Pg7qlIflhXulovx6Teo8dqvQ-WkJx6adzWPkfmgKbFdIJUz05LFX3yPSUtA7DT9imHd0F--ASi4x92HLh59F69h3BCVEIGiooE-t9tgNokBM8SpKe4bxyD)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAV2xtYGyKkzxqAa8kh6hwG4UqhSo_PLiqh1IZ6aNHFhXG5khSHCd3NawQIv2sGgHQWHuyWZkOVYII6T12v7-E-HG-2L--QarjI-A56IiCDZfk7rF5L7lDvW64XdmwTGHtTqSZuOqWf-1efs9Hrr23o6zL69OPF079BY5KMV7CbLxh4-4-tssQi-HO22V7rZ6dR6LxFVaRtPugvGOyTy8eV1gqlHu1wR2zYc3nbwMCeht2OQ==)
18. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGp-f3fDqwe7RG1ZVXbNBw7RsUAvZlio_bU8Dql9bDJSb4POl5L_mTIH1GNINzclX8VBLTC35wxxLH1E36aLlF0kyN7ZDdqesKd3Kh_UXpTQxcZuxm6xSpnKWV___cY9mEx)
19. [ryanoconnellfinance.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF024haziCzHMwQ-wPrqf7q01hxpqH4NXYHmUqD9_pWVxCPrN9FfFIeOmF5Htg5bbQbNxA1S9Rz7m7h5wbn3qJqlLH-wHrdLpwSsWahfrM_JY6bRxTZKu327ih3Vo4MUd17_pCbNCJrlHlht8skYgp5_6Ue9A==)
20. [scaler.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTQxx5fvd3cDRockg3Yc9nkT_82jPUosuTNIiYT0p0-lhiRQv0hIUgL7wduXy_U6GqyStPF-rtU23JOLVb479T8Hnt6iSnx8DBGtqvsBh4p60LAa5rolcR-Ww73HhI6kWC8qk5mQ==)
21. [numerous.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEzXMc6a_Ew77vcZnppPBis2shi2KxuVO0dVL2yr_KpkfqLRk5g99r7TvN_i5XekhGSP6oqHaJsi0Wu6plMq6mT2S04-5J8VJXvQBU539EUD9C53V9YBlfIDVPrGwBAoClyOYsL4c300xnOKWqfCoJTBGQJjHsvfS1ISJTIHlA=)
22. [liveflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpwfqedWGrbUyllOpjcwODVYOb96CMuBVbFuGqx7aqC8gi07nEWQk2LMbx7eNI4B8rn3mW-EVC-np3Z6zLUit6TpgKYmniZTXRZvqOFjYDr4pLqPEWZWhj9aC11EQzJug8pO6XXysFIIal6DYhIiVYVpLx3lJ7H3mHN7d0o6_brY0=)
23. [simular.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGKDfZjeWBa3NBpncC4CxD9t7EukTkGCHdcSxfu7Jhu82sl7V8ADmznynjxaFTPWKxcFZgS3R6fSfPMV-aezVR31mc5zQ89WLuF0zEKrUhHnzuzBMLVOG-ERBnNaSRxADWIMSYEmRIcoMY9BGhwiYGHCMuQwDaN-zEqr0Xm07BvlbhpsCT-sxnwRD0EKoh9ZQKJ6A==)
24. [hcmwealthadvisors.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOgrkTiqSrkbKsy4O1PUr49O4DUAP4Yb6sw6xK-YyUH8_Zjxp33flbk43uerXuqDf9hOGQ2icFdi70Ftet-BDfYCkVnNxTZIxdTtm9fcAykkPLuwXCp71I-0iQ09WwV3MeKJ7tMcuSoSNqGFsU5927ohiDRI1_vsQIF_VJlP31a_wJ)
25. [crafinancial.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGowVnPf7cVBMEIsfbKX6VPRycKgZOjks9rq6dVMNCQ525cemLPruriBdnzEoz_Y6T-1ntZUV6TzyEUISJdC7v8dWKClbxWADEGU9GNBaudqIx5kqix2K5GIAI70me8cUmYq0eWVbQU8s5jeMRbiOg34_YrwCBRFhDYJtd8wod6KOVJjyfTOjI_ZmLXsDCzYXFU57aS)
26. [cgdev.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHh1dPuJAEMunD6zaJMlrCIceysAEosWFD-Jl0HUOoFmI90Px1jzQUsf7XuzW4zFWf5_NlT_Yl7ozGyUlZGINdI0DXNNwfUaHSi2Bq2G9FMFF4jhkBVMXpnZctV7fzMf7TzuKOPj99PGKO_hPCM-mM1uLjy1lgNwqa3uV7L-1lF4WaKfyRcLAFk-T7X6kYH)
27. [bankofengland.co.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEE2oaVJQZv3a6UYFmrw_DDhLjvxoasCExfy_VnDrbZZXUG-MDHxfyRlJcD-K61tH55EIxUi7UhQ-icjmn3rTcrO8bLmyEYfa5AYAmCb_faCN5FmyeXE33GtYgXZtl7dQvdwD95rPse-TR_IKNv68YNqMv6StAWX5Smmr8lM31UIIKOWZxjX6cd5ONJOy1herUCE5SNEgccjcPd1SmTfqSAtwpFvuQ3ysKvWakM4NEzHZPu0R4=)
28. [europa.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnTzHWqFFvQrTq-_1pXa_h-huCP0K3v-Tfz7udVYq-H9f-lbsxMsRZsbGOe0u8GL0pDs-kMBOfmwDj05TZWaTYwmvx19xecPVr8YFg9fX36KPLgmgWBLRr6DnKSTYv6z_5DBe86XCaoOibxmiSD7InGDnH-Ig1HsE4U7bSz_PSUEdThamGN0vJeef64EHOSStMOWnTiqXhi1o9EXU=)
29. [garp.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQENC9p6Dg9EVwek2vep2vDEza1O1i4cOyqu9fJ8Ze52PMJD6mUwNRKEOECxqYtBF5CgF_EU3kDijcALJVKC_K0lLm50OQiwqIMdoRgJbzH7NDTt195JG5uooIkfJzItjd_wXscnpDygySqQKC0yxO-X4XKr)
30. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGB-qToF_u-W4jPouiMCeaE55AZ1M-VVgXi-IALeePoqJsx9BL3WW_qULJnfP65oMMndOhIEIiJpJR2XvD56WLATVOF0TsyQFOwAg_neRyXj5jiUSxWuLlzLw==)
31. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLW9uKvEliw5TFUQRkj0jmnrDC7mJEO9iqo8qVYwd4kRM22an0ra2jX4sy3-YbJQsXzEd4DzaFv-wrdWmvd2WAKWtViYPyxbvIW-HvE_3VbrxjosBp4QoLLL6Zk4Pnu5TtJF9oZFKtFTbYyIrh8K7LUP-ybIk=)
32. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEIvP5iME9vx-1ts_NMUiSIhy36jmE3SXUyx15jgM9P3tYC2bqDW33zggVpfYXZZtO-28iOQETkXFD0e4jZJmZbi_NGE8v74RCIvJ74N86AAvSyRFncBf348A4f)
33. [documentfoundation.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEckqY_BFd-5UH8_xJ18lEmkMqeY6BbUhC6mkw5nhDg3YOilK3tGV-Zjq6gf9oXouZuAH1gwLKNOMaZqZEdhjsQbJIr8qw8OjVQE3mcs2U7Bb3mgqSiYH2p34djUS719pY8Zs1Ibrpaa9_V49u5N53J2TwjYvSYvQShl8e-QJs=)
34. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE3m_oA8n0l58_Ee-UiQVzhtIPdiMceE1_Eq-UMlINSF9KqOvPCONKMg5-buplPRep8R3UB4irAyqJNeiaXjBqhbf3H17dV5YF6UtgNCdmIX7RLHrG_y-CBXEctQ32m4MgmVHNQ5a7mmiqPqqKia_7JSuSt6IaKxf1K65yr_FaNBebzXUAFp_9ISWoGVgVFCFq3ah5Pd5qisqTWw0FXlNXCY9jNSIOanA==)
35. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQpxGKqPX1Q_3DEHl9caDSbEXfyEkY9i1gXTS1uR28E-J8or3mMfxCmU24xSx6u1uP-ePzngj0fa3VmWacQT81nT8xbMufraJB6afduu6m3-6NcdXar8_NBf-7Ue_4TAxUNsh_3I9FRaPqL_j1VMZrp4q_xr6E0BZWhM_C4eHDP9z3M8_WH6GoftE5AtdQCLvBwnrlCBc=)
36. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxvAOPchZDY66_b2y68LXlpl1ULhTQSPys_On4PpsGeTS85Dw3wotYpwsCmQ7e2qhG8_IQoRmtQ5BdwAlhnp5ETe1qQNrdiJYocnDBKkKKo2AXNVOZOrZu70VZxjcQxrzLi0-0Z_4HMoxcUYWwh7KVZjI7Ig==)
37. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGifXZLZsjFGP4CH8sxw3li6ypssspcdw1cShGvuJ59rHG-iVxTcvHhKmIaLTk34BriaPpr5jY-Mt-_oAWxAsa-sIh_DpsobJXRsE99grvAlkTW_FH5ufgqJqcnnpgRjOVqRDtNtg2YXUT37OYg6YhBUGJbMcIE0b005lIdAEgOsFzqp8_Mt1sK)
38. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxrHDOyVhRNSUvXWIuIPJq2MNag09Nnch1riGqA15tRdLY3gPDYverFDaZ03dXt6Cb9CndD-oqhu4r2vh7Ca1FNEmFI4qLSPsL_-L-VWtZNIzwF7O3r1c5DlN5SOiu-pr_rkp5b9niHUZSZian9NmY5sum5zdOBZzwsRCEeSuMP9U=)
39. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHWKm_Fv24RzIhrugGppM83S7GsURRu34Q3KV8usEYdp00cpRbBbRwnuHLkcy-MuHfPkjV5cxCI1HALfo2HaxGMYxb-R0NLZE-5iTMw94RBUyUspakdeXD1dhixuPLgtZVT__U8Gbg9suxiCT3z5OFrJ1gTcE94s0X2b2xc48oxjNbc0esFzx_4XELpMUiA3J6sIkaYa8ng)
40. [askubuntu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVSDkDHbMG0DrTBP3ZXIuFvOAT6DKbZr0C4K308NgMlV6kQhwYwEV-XsLFIyp448i4jwkS8Zq9EG3VXer0NC-JHLlfFmjhTjU7ydSO1xdN2zoHK9iDok5qIpaAOTgq52tD1-p6xguRQZJB-_w5q1qKau40pwl87fKYofrDqOCElICBtYuuEV5cMSWyPquiLu8w0sOrTPBp)
