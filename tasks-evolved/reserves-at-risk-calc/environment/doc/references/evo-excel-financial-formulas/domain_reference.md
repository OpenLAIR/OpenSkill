# Domain Reference for evo-excel-financial-formulas

**Responsibility**: Writing all Excel formulas (LN, STDEV.S, SQRT, XLOOKUP/INDEX+MATCH) into the correct cells, populating gold price data into the Gold price sheet, filling Answer sheet blanks, handling cross-sheet references, computing Gold Price Exposure and RaR formulas, saving the workbook, and running LibreOffice headless to force formula recalculation.

**Key functions to implement**: write_gold_price_sheet, write_log_return_formulas, write_volatility_formulas, write_answer_sheet_step1, write_answer_sheet_step2, write_answer_sheet_step3, write_lookup_formulas, recalculate_with_libreoffice

---

## 4. Writing Excel Formulas with openpyxl


One of the most potent features of `openpyxl` is its ability to inject Excel formulas directly into cells [cite: 10]. Because `openpyxl` is not a calculation engine, it does not evaluate the mathematical output of the formula; it simply writes the formula string into the XML structure of the file [cite: 11, 17].

### 4.1 Syntax for Writing Formulas

To write a formula, you assign a string beginning with the equals sign (`=`) to the `value` attribute of a cell [cite: 18]. 

```python

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

## 6. XLOOKUP and INDEX+MATCH Formula Syntax


When dynamically linking datasets, lookup formulas are essential. Historically, `=INDEX(..., MATCH(...))` was the gold standard, but modern spreadsheet applications have adopted `=XLOOKUP()`.

### 6.1 XLOOKUP Compatibility in LibreOffice

A critical consideration when generating files for automated environments is application compatibility. While `XLOOKUP` was introduced to Microsoft Excel in 2020, it was notably absent from LibreOffice for several years, requiring workarounds like the `Lox365` extension [cite: 31, 32]. 

However, **LibreOffice Calc officially implemented native support for XLOOKUP starting in version 24.8** [cite: 33]. If the target environment runs LibreOffice 24.8 or newer, `XLOOKUP` can be safely written via `openpyxl` without compatibility issues.

**XLOOKUP Syntax:**
`=XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found], [match_mode], [search_mode])` [cite: 33]
```python

### 6.2 The INDEX + MATCH Alternative

If backward compatibility with older versions of LibreOffice (pre-24.8) is required, the `INDEX` and `MATCH` combination must be used [cite: 34].

**INDEX/MATCH Syntax:**
`=INDEX(return_array, MATCH(lookup_value, lookup_array, 0))`
```python

## 7. openpyxl API for Copying Data Between Sheets


A common requirement in financial reporting is aggregating calculations from multiple raw data sheets into an "Answer" or "Summary" sheet. `openpyxl` provides simple dictionary-style access to move between worksheets seamlessly [cite: 1, 15].

```python
import openpyxl

wb = openpyxl.load_workbook("financial_model.xlsx")

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