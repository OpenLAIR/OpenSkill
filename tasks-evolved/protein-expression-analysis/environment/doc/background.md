# Building Resilient Python Pipelines for Quantitative Proteomics Data Using openpyxl 3.1.5

### Key Points
*   **Data Preservation**: Loading Excel files with `openpyxl.load_workbook(data_only=False)` is mandatory for preserving raw formulas when round-tripping files, whereas `data_only=True` retrieves cached computed values but destroys formula strings upon saving [cite: 1, 2].
*   **Formula Syntax**: Post-OOXML specification functions like `STDEV.S` or `STDEV.P` must be prefixed with `_xlfn.` (e.g., `_xlfn.STDEV.S`) to prevent `#NAME?` errors in Excel [cite: 3, 4].
*   **Formatting Vulnerabilities**: While basic cell formatting (colors, fonts) is preserved during a standard `wb.save()`, complex objects like charts, macros, and pivot tables are frequently corrupted or stripped due to unmapped XML namespace parsing [cite: 5, 6].
*   **Proteomic Data Transformations**: Arithmetic means and standard deviations applied directly to $\log_2$-transformed intensity data accurately yield geometric insights (e.g., $\log_2$ fold change) required by standard proteomics reporting conventions [cite: 7, 8]. 
*   **API Deprecations**: In `openpyxl` 3.1.5, legacy methods like `get_sheet_by_name()` are strictly deprecated and should be replaced with dictionary-style key access (`wb["SheetName"]`) [cite: 9, 10].

### Executive Summary
The deployment of automated computational workflows in bioinformatics frequently requires the programmatic manipulation of Microsoft Excel (`.xlsx`) files. In quantitative proteomics, these files do not merely hold static values; they contain complex metadata, sample categorizations (e.g., the CCLE "TenPx" TMT multiplexing nomenclature), highlight-color codings denoting significance, and embedded formulas for dynamically calculating fold changes and standard deviations. This report provides an exhaustive reference on using the Python library `openpyxl` (specifically version 3.1.5) to build a reusable skill module that manipulates these files. 

### Methodological Approach
The technical strategies detailed herein prioritize absolute data fidelity. We outline precise `openpyxl` API parameter configurations necessary for preserving existing cell formatting (such as background fills and fonts) while safely injecting uncomputed formula strings. We address common domain pitfalls—such as managing 1-indexed Excel sheets natively in Python's 0-indexed environment, understanding the mathematical conventions behind log-transformed fold-change calculations, and safely traversing the Office Open XML (OOXML) file specifications without corrupting pivot tables or dynamic arrays. 

---

## 1. Workbook and Worksheet Loading with openpyxl 3.1.5

Constructing a highly robust data pipeline requires a deep understanding of the initial data ingress. In `openpyxl`, the entry point for file reading is the `load_workbook()` function. The parameters supplied to this function dictate how the underlying Office Open XML (OOXML) zip archive is parsed into Python objects and, critically, what data is permanently discarded.

### 1.1 Correct `load_workbook()` Signature and Parameters

The standard signature for loading a workbook in `openpyxl` version 3.1.5 is as follows:

```python
from openpyxl import load_workbook

wb = load_workbook(
    filename='proteomics_data.xlsx',
    read_only=False,
    keep_vba=False,
    data_only=False,
    keep_links=True
)
```

The parameters uniquely interact to alter the state of the parsed document:
*   `data_only`: A boolean parameter that fundamentally alters how formula cells are interpreted. If `data_only=False` (the default), `openpyxl` reads and preserves the underlying formula string (e.g., `=AVERAGE(A1:A10)`). If `data_only=True`, `openpyxl` ignores the formula and instead reads the cached computed value generated the last time the file was saved by the Microsoft Excel application [cite: 2, 11].
*   `keep_vba`: If set to `True`, the parser attempts to preserve Visual Basic for Applications (VBA) macros (the `vbaProject.bin` file within the archive) [cite: 12, 13]. If the file is a macro-enabled `.xlsm` file, setting this to `False` will strip the macros upon saving.
*   `read_only`: If `True`, the workbook is loaded using an optimized lazy-loading parser. This vastly reduces memory consumption for massive proteomics datasets (millions of rows) but renders the workbook immutable. Formatting cannot be written, and `wb.save()` will fail [cite: 11, 12].
*   `keep_links`: Determines whether external workbook links are preserved [cite: 11].

**Which combination preserves formulas AND formatting when round-tripping a file?**
To safely read a file, edit it, and save it while preserving both the original formulas and the formatting, you must use `data_only=False` and `read_only=False`. 

**The `data_only` Pitfall**:
A significant danger arises when you write formulas programmatically using `openpyxl` and immediately attempt to read their outputs. Because `openpyxl` is not a calculation engine (it only writes the XML string representing the formula), a newly written formula has no cached computed value. If you save the file and subsequently read it with `data_only=True` without first opening and saving it in Microsoft Excel, `openpyxl` will return `None` for those cells [cite: 1, 2].

### 1.2 Accessing Sheets, Iterating Rows, and Reading Cells

In version 3.1.5, accessing worksheets utilizes standard Python dictionary key-access syntax. The legacy method `.get_sheet_by_name()` is strictly deprecated and triggers a `DeprecationWarning` [cite: 9, 10].

```python
# Recommended standard access
ws_data = wb["Data"]
ws_task = wb["Task"]

# Deprecated - DO NOT USE in 3.1.5
# ws_data = wb.get_sheet_by_name("Data") 
```

To iterate rows memory-efficiently, use the `.iter_rows()` generator. In `openpyxl` 3.1.x, the `.iter_rows()` and `.iter_cols()` methods natively support the `values_only=True` argument, which was introduced in version 2.6 and bypasses the overhead of returning full `Cell` objects [cite: 14, 15].

```python
# Iterating rows for data parsing (Fast, returns raw values)
for row in ws_data.iter_rows(min_row=2, max_col=10, values_only=True):
    protein_id = row
    intensity = row[cite: 16]
    
# Iterating rows to manipulate formatting (Returns Cell objects)
for row in ws_data.iter_rows(min_row=2, max_col=10, values_only=False):
    cell = row
    if cell.value == "TargetProtein":
        cell.value = "UpdatedProtein"
```

### 1.3 Detecting Cell Fill Colors

In quantitative proteomics, Excel files are frequently color-coded by biologists (e.g., yellow for "significant but low confidence", blue for "highly significant"). Detecting a cell's fill color relies on navigating the `cell.fill` attribute.

Cells are usually filled using the `PatternFill` class. The exact attribute path to the color code is:
`cell.fill.start_color.rgb` (or `cell.fill.fgColor.rgb` in some legacy contexts) [cite: 17, 18].

```python
color_code = cell.fill.start_color.rgb
```

**Pitfalls of Theme Colors vs. RGB**:
`openpyxl` relies heavily on standard aRGB (Alpha-Red-Green-Blue) hex strings (e.g., `'FFFF0000'` for solid red) [cite: 19, 20]. However, if a user selected a "Theme Color" from the Excel palette (e.g., "Accent 1, Lighter 60%"), the `start_color.rgb` may return `None` or an invalid type. Instead, `cell.fill.start_color.theme` and `cell.fill.start_color.tint` will be populated [cite: 19]. 

Extracting exact hex codes from theme colors is notoriously difficult in `openpyxl` because it requires parsing the separate `theme1.xml` file hidden in the OOXML archive [cite: 21, 22]. For building robust skills, you must account for type coercion issues and implement fallback logic:

```python
def get_cell_color_hex(cell):
    fill = cell.fill
    if not fill or fill.patternType is None:
        return None
    
    color_obj = fill.start_color
    if color_obj.type == 'rgb':
        # Returns string like '0000FF00' or 'FFFF0000'
        return color_obj.rgb 
    elif color_obj.type == 'theme':
        # Logging a warning is recommended as converting theme to RGB 
        # requires complex cross-referencing of the theme XML.
        return f"THEME_{color_obj.theme}_TINT_{color_obj.tint}"
    return None
```

---

## 2. Writing Excel Formulas to Cells

When building a reusable skill that injects computational logic back into the spreadsheet, writing formulas correctly is critical. `openpyxl` writes formulas by simply assigning a string that begins with the equals sign (`=`) to the `value` attribute of a cell [cite: 23].

### 2.1 Formula Syntax and Evaluation

Openpyxl treats a string as a formula if and only if it explicitly begins with `=`. 

```python
# Treated as a formula
ws["C11"] = "=INDEX(Data!B:B, MATCH(A11, Data!A:A, 0))"

# Treated as literal string
ws["C12"] = "INDEX(Data!B:B, MATCH(A12, Data!A:A, 0))"
```

When formulas are assigned to pre-formatted cells, the assignment alters only the `.value` property. **The pre-existing `.fill`, `.font`, and `.border` properties of that cell remain perfectly preserved.** [cite: 19, 20]

### 2.2 Writing Specific Statistical and Lookup Formulas

**INDEX/MATCH and Absolute References**:
When constructing two-way lookup formulas programmatically, absolute references (`$A$1`) versus relative references (`A1`) must be rigorously controlled, particularly if users might copy-paste the formula downwards.

```python
# Constructing an INDEX/MATCH programmatically 
target_cell = "C11"
lookup_val = "$A11"  # Absolute column, relative row
index_range = "Data!$B$2:$XX$201"
match_range_row = "Data!$A$2:$A$201"

ws[target_cell] = f"=INDEX({index_range}, MATCH({lookup_val}, {match_range_row}, 0))"
```

**Exponent Formulas**:
To calculate standard linear fold changes from $\log_2$ fold change data, Excel requires the exponent operator (`^`).
```python
ws["D11"] = "=2^(C11)"
```

**The `STDEV` Function and `_xlfn.` Prefix Pitfall**:
A major pitfall in `openpyxl` relates to newer Excel functions. The original OOXML standard included a basic set of functions like `AVERAGE` and `STDEV` [cite: 23]. However, in modern Excel, `STDEV` is deprecated in favor of `STDEV.S` (sample standard deviation) and `STDEV.P` (population standard deviation) [cite: 24]. 

Because `STDEV.S` and `STDEV.P` are newer additions, `openpyxl` does not recognize them as core functions. If you write `=STDEV.S(A1:A10)`, Excel will corrupt the function name and display `#NAME?` (often rendering it internally as `=@STDEV.S()`) [cite: 4, 25].

To fix this, you must prepend the `_xlfn.` namespace prefix to the function name in Python [cite: 3, 4, 25]. Note: For analyzing proteomics sample expression replicates, the sample standard deviation (`STDEV.S`) is statistically appropriate as the replicates represent a sample of a broader population.

```python
# CORRECT implementation for modern Excel compatibility
ws["E11"] = "=_xlfn.STDEV.S(F11:H11)"

# AVERAGE is a core OOXML function and needs no prefix
ws["I11"] = "=AVERAGE(F11:H11)" 
```

### 2.3 Array Formulas

Array formulas execute calculations across multiple cells simultaneously. Historically, in Excel, these were executed using `Ctrl+Shift+Enter` and appeared surrounded by curly braces `{=MAX(A1:A10)}`.

In `openpyxl`, you should never manually write curly braces into the formula string [cite: 23]. Doing so forces Excel to interpret the formula as a literal string. Instead, `openpyxl` provides an `ArrayFormula` class. However, as of version 3.1.x, managing dynamic array formulas (which spill across cells automatically in modern Office 365) can be highly erratic, often requiring explicit manipulation of the `ws.formula_attributes` dictionary to map the formula reference coordinates correctly [cite: 26]. 

For maximum stability in automated skills, it is strongly advised to utilize standard mathematical formulations over complex Array Formulas whenever possible, relying on row-by-row standard formulas generated programmatically in loops.

---

## 3. Preserving Formatting on Save

A fundamental requirement of the skill module is that it must preserve existing user formatting. 

### 3.1 Confirmed Behavior of `wb.save()`

When `wb.save()` is executed on a workbook loaded with `data_only=False`, `openpyxl` flawlessly preserves the following for all untouched cells:
*   Cell fills (colors/patterns)
*   Fonts (size, bold, italic, colors)
*   Conditional formatting rules
*   Merged cells
*   Column widths and row dimensions
*   Named styles [cite: 19, 20]

As previously noted, writing a new formula into a pre-formatted cell updates the `cell.value` element of the XML but leaves the `cell.fill` and `cell.font` elements completely intact [cite: 19].

### 3.2 File Corruption: Charts, Images, and Pivot Tables

The primary Achilles heel of `openpyxl 3.1.5` is its handling of complex native Excel objects. Because `openpyxl` reconstructs the XML archive upon `save()`, any XML namespaces or schema extensions it does not understand are stripped out or corrupted [cite: 5, 6].

*   **Pivot Tables**: `openpyxl` provides read-support for pivot tables so they are allegedly preserved [cite: 27], but modifying the data ranges feeding those pivot tables often results in severe corruption, leading Excel to present a "We found a problem with some content..." recovery prompt upon opening [cite: 5, 28].
*   **Charts**: Complex charts, particularly those relying on new Excel features or external data links, are frequently lost or their formatting is irreparably altered upon save [cite: 6].
*   **Data Validations**: `openpyxl` preserves data validations, but heavy editing of columns containing list-validations can sometimes break the reference links [cite: 29].

**Mitigation Strategy**:
To avoid corrupting the user's analytic files, the ideal pipeline pattern involves isolating the raw data.
1. Instruct biologists to keep Pivot Tables and Charts on a completely separate worksheet (e.g., `Analysis_Dashboard`).
2. Only write data and formulas to the raw `Data` worksheet.
3. Save the file. Excel will natively recalculate the pivot tables and charts pointing to the `Data` worksheet without the need for `openpyxl` to touch the chart XML directly [cite: 6].

---

## 4. Data Pipeline Patterns for Quantitative Proteomics

To process large matrixed data formats standard to quantitative proteomics (e.g., TMT 10-plex/16-plex data arrays), the python code must dynamically resolve row and column coordinates.

### 4.1 Indexing Headers and Categories

Proteomics output files typically contain a header row with sample IDs (e.g., in Row 10) and a label column with protein accession numbers (e.g., in Column A). Additionally, a category row (e.g., Row 9) often categorizes samples into groups (e.g., "Control" vs. "Treated") [cite: 8].

Building dynamic lookup indices involves converting Python's 0-indexed enumeration into Excel's 1-indexed coordinate system, alongside column letters.

```python
from openpyxl.utils import get_column_letter, column_index_from_string

def build_pipeline_indices(ws):
    header_row_idx = 10
    group_row_idx = 9
    
    # 1-indexed coordinate arrays
    sample_columns = {}
    group_map = {"Control": [], "Treated": []}
    
    # Iterate through columns in the header row
    # Let's assume data starts at column B (column=2) and ends at XX (column=600)
    for col_idx in range(2, ws.max_column + 1):
        sample_name = ws.cell(row=header_row_idx, column=col_idx).value
        group_name = ws.cell(row=group_row_idx, column=col_idx).value
        
        if sample_name:
            col_letter = get_column_letter(col_idx) # e.g., converts 2 to 'B'
            sample_columns[sample_name] = col_letter
            
            if group_name in group_map:
                group_map[group_name].append(col_letter)
                
    return sample_columns, group_map
```

### 4.2 Cross-Sheet Formula Generation

When generating summary tables on a separate "Task" sheet that cross-references a "Data" sheet, standard `INDEX`/`MATCH` formulas are vastly superior to `VLOOKUP`. A critical pitfall here involves sheet names that contain spaces (e.g., `Raw Data`). Excel syntax requires single quotes around the sheet name: `'Raw Data'!$B$2:$B$200`.

```python
def write_lookup_formula(ws_target, target_cell, lookup_val, data_sheet_name, max_row):
    # Properly quote sheet names
    safe_sheet_name = f"'{data_sheet_name}'" if " " in data_sheet_name else data_sheet_name
    
    # Construct =INDEX(Data!$B$2:$XX$201, MATCH($A11, Data!$A$2:$A$201, 0), ...)
    formula = (
        f"=INDEX({safe_sheet_name}!$B$2:$XX${max_row}, "
        f"MATCH({lookup_val}, {safe_sheet_name}!$A$2:$A${max_row}, 0), "
        f"MATCH(C$10, {safe_sheet_name}!$B$1:$XX$1, 0))"
    )
    ws_target[target_cell] = formula
```

---

## 5. Quantitative Proteomics Domain Conventions

Automated skill generation for bioinformatics must adhere to the mathematical and ontological conventions of the scientific domain to ensure validity. 

### 5.1 Arithmetic vs. Geometric Means on Log2 Data

Modern mass spectrometry proteomics quantifies protein abundance via tandem mass tags (TMT) or Label-Free Quantitation (LFQ) [cite: 8, 30]. Protein intensity data spans massive dynamic ranges and is heteroscedastic, meaning variance scales with intensity. Consequently, data is almost universally $\log_2$-transformed prior to statistical analysis to normalize distributions [cite: 7, 31, 32].

**Standard Practice Rule**: 
When data is already $\log_2$-transformed, you must use the standard arithmetic mean (`AVERAGE`) and standard deviation (`STDEV.S`) algorithms [cite: 7, 8]. 

A common mathematical misconception is that one should use geometric means. However, the arithmetic mean of log-transformed values is mathematically equivalent to the log of the geometric mean of the original raw values [cite: 8, 33]. 

\[ 
\text{Arithmetic Mean of } \log_2(X) = \frac{1}{n} \sum_{i=1}^n \log_2(X_i) = \log_2 \left( \left( \prod_{i=1}^n X_i \right)^{\frac{1}{n}} \right) = \log_2(\text{Geometric Mean of } X)
\]

Thus, calculating `AVERAGE()` on $\log_2$ expression matrices seamlessly computes the correct statistical location. 

### 5.2 Calculating Log2 Fold Change

Fold change represents the ratio of expression between a Treated group and a Control group [cite: 34]. 
On a linear scale, this is $\frac{\text{Mean}(\text{Treated})}{\text{Mean}(\text{Control})}$.
On a $\log_2$ scale, due to logarithm quotient rules, division becomes subtraction [cite: 8]. 

\[
\log_2(\text{Fold Change}) = \text{Mean}(\log_2(\text{Treated})) - \text{Mean}(\log_2(\text{Control}))
\]

To compute the linear fold change back from the $\log_2$ scale, use base 2 exponentiation:
\[
\text{Linear Fold Change} = 2^{\log_2FC}
\]

**Formula Generation Implementation**:
```python
# Assuming treated log2 mean is in E11, control log2 mean in F11
ws["G11"] = "=E11 - F11" # Calculates Log2 FC
ws["H11"] = "=2^(G11)"   # Calculates Linear FC
```

### 5.3 TenPx and Sample Nomenclature Parsing

Major consortium datasets, such as the Broad Institute's Cancer Cell Line Encyclopedia (CCLE) and the DepMap 20Q2 proteomic release, utilize a specific tandem-mass-tag naming convention: `[CELL_LINE]_[DISEASE]_TenPx[CHANNEL]` [cite: 16, 35]. 

For example: `MDAMB468_BREAST_TenPx01` [cite: 35, 36, 37].
*   `MDAMB468`: Cancer cell line identifier.
*   `BREAST`: Primary disease lineage.
*   `TenPx`: Denotes a 10-plex TMT MS experiment.
*   `01`: The specific multiplex channel the sample was run on.

When building parsing logic, regex should be utilized to dynamically split and extract these metadata headers for categorization:
```python
import re

def parse_ccle_sample_name(sample_name):
    # Matches MDAMB468_BREAST_TenPx01
    pattern = r"^(?P<cell_line>[A-Z0-9]+)_(?P<lineage>[A-Z_]+)_TenPx(?P<channel>\d{2})$"
    match = re.match(pattern, sample_name)
    if match:
        return match.groupdict()
    return None
```

---

## 6. Common Pitfalls and Troubleshooting Reference

### 6.1 1-Indexed vs. 0-Indexed Coordination

Python lists and arrays are strictly `0-indexed` (the first element is `0`). 
`openpyxl` worksheet coordinates (rows and columns) are strictly `1-indexed` (the first row is `1`, the first column is `1` = 'A') [cite: 38]. 
Failing to account for this $+1$ offset during loop iterations is the leading cause of "Off-By-One" errors in `openpyxl` data pipelines.

### 6.2 Deprecated APIs in 3.1.5

As of version 3.1.x, several legacy methods have been aggressively deprecated [cite: 9, 39]. If your skill runs in an environment enforcing strict warnings, these will fail:
*   **DEPRECATED**: `wb.get_sheet_by_name("Name")` -> **USE**: `wb["Name"]` [cite: 10, 40]
*   **DEPRECATED**: `ws.iter_rows()` without arguments used to behave differently; `values_only` was added in 2.6 and is highly recommended [cite: 15, 41].
*   **DEPRECATED**: `ws.cell(row=1, column=1).value` quirks. Accessing cells dynamically should always use the keyword arguments `row=` and `column=` explicitly, as positional arguments have changed behavior in recent versions [cite: 29, 42].

### 6.3 Saving over Open Files

`openpyxl` cannot interact with Windows file-locking mechanisms seamlessly. If the `proteomics_data.xlsx` file is currently open in a user's desktop Microsoft Excel application, calling `wb.save("proteomics_data.xlsx")` will result in a `PermissionError`. A robust skill module must implement `try/except` blocks to handle file locks gracefully, potentially saving to a uniquely timestamped output filename `proteomics_data_out_{timestamp}.xlsx` to prevent crashes.

### 6.4 Locale and Decimal-Separators

Excel relies heavily on the operating system locale for parsing mathematical formulas. In Europe, `,` is the decimal separator and `;` is the formula argument separator. However, **`openpyxl` dictates that you MUST write formulas using the standard English/US syntax**: utilizing commas `,` to separate arguments and periods `.` for decimals [cite: 23]. Microsoft Excel's XML translation engine will automatically convert these strings into localized formats when the user opens the file. Using semicolons inside `openpyxl` formula strings will corrupt the output.

---

## Complete Working Code Pattern

The following class demonstrates the synthesized best practices for a reusable proteomics skill module:

```python
import os
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

class ProteomicsExcelSkill:
    def __init__(self, filepath):
        self.filepath = filepath
        # data_only=False preserves formulas; read_only=False allows saving
        self.wb = load_workbook(self.filepath, data_only=False)

    def inject_statistical_formulas(self, sheet_name, start_row, max_row, ctrl_cols, trt_cols):
        """
        Injects AVERAGE, STDEV.S, Log2FC, and Linear FC formulas for proteomics data.
        """
        ws = self.wb[sheet_name]
        
        # Determine the columns to write outputs to (assuming right after the data)
        avg_ctrl_col = ws.max_column + 1
        avg_trt_col = ws.max_column + 2
        stdev_ctrl_col = ws.max_column + 3
        stdev_trt_col = ws.max_column + 4
        log2fc_col = ws.max_column + 5
        linfc_col = ws.max_column + 6

        # Write Headers
        ws.cell(row=start_row - 1, column=avg_ctrl_col, value="Avg_Log2_Control")
        ws.cell(row=start_row - 1, column=avg_trt_col, value="Avg_Log2_Treated")
        ws.cell(row=start_row - 1, column=stdev_ctrl_col, value="StDev_Control")
        ws.cell(row=start_row - 1, column=stdev_trt_col, value="StDev_Treated")
        ws.cell(row=start_row - 1, column=log2fc_col, value="Log2_FoldChange")
        ws.cell(row=start_row - 1, column=linfc_col, value="Linear_FoldChange")

        for row_idx in range(start_row, max_row + 1):
            # Construct ranges: e.g., C2,D2,E2
            ctrl_range = ",".join([f"{get_column_letter(c)}{row_idx}" for c in ctrl_cols])
            trt_range = ",".join([f"{get_column_letter(c)}{row_idx}" for c in trt_cols])
            
            # Formulas
            avg_ctrl_letter = get_column_letter(avg_ctrl_col)
            avg_trt_letter = get_column_letter(avg_trt_col)
            
            # 1. AVERAGE (Core Function)
            ws.cell(row=row_idx, column=avg_ctrl_col, value=f"=AVERAGE({ctrl_range})")
            ws.cell(row=row_idx, column=avg_trt_col, value=f"=AVERAGE({trt_range})")
            
            # 2. STDEV.S (Extended Function requires _xlfn.)
            ws.cell(row=row_idx, column=stdev_ctrl_col, value=f"=_xlfn.STDEV.S({ctrl_range})")
            ws.cell(row=row_idx, column=stdev_trt_col, value=f"=_xlfn.STDEV.S({trt_range})")
            
            # 3. Log2 Fold Change (Treated - Control on log2 scale)
            ws.cell(row=row_idx, column=log2fc_col, value=f"={avg_trt_letter}{row_idx}-{avg_ctrl_letter}{row_idx}")
            
            # 4. Linear Fold Change (2^Log2FC)
            log2_letter = get_column_letter(log2fc_col)
            ws.cell(row=row_idx, column=linfc_col, value=f"=2^({log2_letter}{row_idx})")

    def save_workbook(self, output_filepath):
        try:
            self.wb.save(output_filepath)
            print(f"Successfully saved to {output_filepath}")
        except PermissionError:
            print(f"ERROR: {output_filepath} is open in Excel. Close the file and try again.")
            
# Execution Example
if __name__ == "__main__":
    skill = ProteomicsExcelSkill("raw_proteomics.xlsx")
    # Assuming Control samples are in cols 2,3,4 and Treated in 5,6,7. Row 2 to 1000.
    skill.inject_statistical_formulas(sheet_name="Data", start_row=2, max_row=1000, 
                                      ctrl_cols=[cite: 27, 37, 43], trt_cols=[cite: 29, 44, 45])
    skill.save_workbook("processed_proteomics.xlsx")
```

**Sources:**
1. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3Qh18UA40mOlk4EO7I9GiRF8LZvv0dyeyt_ucn-LQ5zwqSmCp5xTU29EMruWU6rNpX2ZPXSlungRxmlIRajLkXTYrkcFAVJJlHqrDRj0ToZ1lOC9eAt4XnES823ieqya9suyISaN7_t5hnz9GKkI0qQ5flpIDMUoG8Cnxy-tEFo0Kz2ti64oNQcemExWaCt0=)
2. [databricks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZgtHuHxREayEUDcgGvzH_dpXJZYjXy2s_c96fi2d83hVRFJTUVPHcYI6PGoHZUXEj4k73dVk9AKHixPO3EUeMftykvpcplTNGjs52QbjLW4OsiEu0Z_QocQxbHkuY6MRHMyp3lzTFys4FiTNn1gJ9a2mzy83gBz2r7jVnTyXYej2UbWrlDCFgD5XRGaB1-5P2p-nhtVjZF85H8h1FjfxMuNgktdNF41g7enXgrL1c_7qc82n2aJ__)
3. [githubusercontent.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9UsvGz2we95BVbCnYIsr3Ho1TZbjorN35ayNbJX7EgL4SovmC-K4hpn1Sjw-KnA1qHdvUg5blC2OTN1eU9UADdT7fFxLs1gl4sue1AEKIU-4E_JrvAzmPQ01TdRdnJ5X0AzagF1Yo24TfVk0_hYOQ7Q0zdsR5vbo-8Ti4b-xQSX9wHb6QwMU=)
4. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESsiNlOcZlvg-RLSayV2YglNMnX1q5Nj0QIFHBom5TV5kx5EI8brF6OClnAigvJQ4Do11OkthFbJ0By6M_MVimBH9qi6DK-subdI949wfvCQQtBcZxmeN3uBf6hKK0e7SC3uw8JF8pKkOouF-iJM4nIE3e_ynYjspyouPOS2XGaJNJ)
5. [heptapod.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE5By6IsV5mL4befjK7jE9u_VyPjK08_5r_jLn3kg8ut-hRjQTJFQGc2-rbzvoRMX6LyRCgVaURKeupE4WgOC2-LT7-L4q0VW45pv3hPnePgJ1hN5Vu-PvJXlu6NfOGKtPlwTbHXO7S5ECQJq_xow==)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEyZkPJgc_U-7EYtERAnW1Pgvl3pWQCPzZ2a2XmejWXVEOpaqnEDMwYB0VIbpn-YgmecSWvrUNc-m1jUjwhunmtGiFWNgDHAUiJ5K3BNaCdpOYPssZpntvsj-KqQ_0pxIzd0b_LR8Uj2zIa27EoWapA0ZXmlIOrzKfNIWCrquKd6zkmeRQODyus72n3RQ8HC5bUWU1ULX_NPw9t28MWrS4)
7. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGRODf2pZt6NHWcqA1p1dc_NfUyDu6s3tgOLdabezJ1YHXaRnY5-edWPIRLHCRc7md9IZTn_hBThn-MdyHX6BuCH5zQj0EiC0IflhkcSnnxntdHwnxKlqcbjT9t5JSLF0mVNCo6aCSu)
8. [frontiersin.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE5x9_qPfmHNy_FGui5S1-hWUJVqjhv-lABFQ-2qkO_vwpfga_5TMtJqpG8-gWC68kIPfLXIJOjx-0Ts6fKlfRNGfytzYd8Cr6bTmCwtKXDFiVvrJsVAZGPE7tFhy8Og6i0scbFQRxqFn71_tI9IKMKvR0ZTjRAVojKEtUPAUGoeKhwOQ3CIOZXbj4pUZakhbjIO8qSew==)
9. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGCQZdHvopS_m81mUCWNGyvooBrmQmpBQe-bTfbPGo89tjsUyqkKLFr--6p5AQnnwexbgQ-cgw2z_ppZjmcYp4MPDctPrMIh6V_DXmLEu1KaqOWH1U5pDy83jLPYyvtm-srMEwxUb-HsQP0Kfj6vfPnMFbAgeMTugbr6x0MRknnsVoXSuTyOfp2OKHYaN8O6bM8ghIf-2tGUgiCqSq7QLzgVnqGOJFjCT3KUOdvPF2qyGo=)
10. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGYjjjmaE82wmUpW_F20-380c-MHl0WsJrFRgJSKnDM0kXeiYTJeBqwKPjQbaineDtlOUorm3rfToXWLnADE45R6HZYQIwAjf4LRntAJvuKTEABNKEiSfwDsl0jzd2ESuR9tlqsgnvhRbg-b_84s3-5bpFrd7hw_rjBDVGuwL975R24d2Swf2U=)
11. [baidu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGGJgG5kzyOYvX5BZ0-iVPtYPj5e0q2JwoFc4PKPyP4Xdj3T4cLxScgTpKiKpzksT52sZqG7jfsXcIN_eyAyyBb92moGF4KW5ah9OSEbZJ9U2ikR1ILWc3gWTgx5uIMtyzBkA==)
12. [cnblogs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFspx2aqVGzQWEASs5hX03bvUQGQM159G549YOgoJxE9e0FMEPhCQ48naVIOHqu5IJGag1PPmYVCVe2pY7gPmzG77y27PBblgyCdpinPfp8Ww0lrVbjlaX1Kthw87_VY_quMQ==)
13. [heptapod.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQENLXb6noDOreVgv__cAFB77MwBxsME5IP_ld7SAA-PYw0rhNejV0WD7bhNzqA53ZIKnd7fqlXlGrt8-woBM5_ObRV7ZayPYsL0eanq_mu4mMQFr2n5YaqA7y5_WzEBInp41dTlVL71ison0axA3mk=)
14. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQELIauN3YFEzbC_OOpQIyy41b26rVb7ITnJStx1NMb-TiW7XPA6KHBok6pqzJxM4XqhUBeiNWhKzSPg8XIBZzSUosDqW2sKWfRaDFm1dKfI6ovm47fRj10WUnep9am7Zwmxg81SuPCnpgOk)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJjzuRwrlcvBZnGHf3bk_VQSSkf1dfHSefPSErTmOdy_j_zD4eVzrlc8g9fmsOjfOzEdVOCN7zDVSzJwd5dvQeeO6UFoPkvIRjk_NWZENftqYhGMgG3XrifSc9zhkNju6Uj6O99Cp_-xD3JTC2eTrkcpeLx02JCKnGq7gmBI3s5GCym1GAAz0xyv8niGb6Pzh102vlM0lNTn_1EQEw-J87g0G9jlb0E9AUIVVndodW)
16. [bioconductor.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwOEUNjcdAgXg6qyAjOgbaPliK3DruGIB3ansu2aAA0Yw7daTKOKi9LA1OAB2PbChwsn37mg-9TE6edJ_UjmY7d7wVYdfFP88_qrUxP8IhZ1bniDV-NeJ95MkSLMo-7vZQJLULBi4oSRpuq8wY8i3gH5vDYydaoIm0Ag4g00bNDE-ddYiFFwnPUwGWna80sP-b1A==)
17. [pythonlibrary.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0T63dPPtycZ7jNIZP8rFE_4UB-rul4HnFNTyvtVCkOsBYTs0RZPGbKbEELkwMeMfRjNUWjoluGsJyTutu8b1lar6iYlJwmQh6hcvdb-9lWynjRAY1FIuzq5yE9p4Bbikiz8cHEqW0zrgz-ouAshEZhyaJubDeJmgxIxDDc_SD3vC7XnnKM2UrEeRtKC0=)
18. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGuXPt_dxO0RdoryVNZcBBQlKKlOIpVybXn_pTiJ_vp8DbtjqkuvINIXj_43-kWhnCfmYnJy8y9PVe1MSroHnbOWpEq8dWRmbjJg9U5Qde1yPxSZmkE0zA6UEbquyu1eMHYarOh4PON6w==)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpnup-CEwtxAqfkGs0wbfRtTJ0S6o-rfM3AjC6f7N6kxE0Ntz8Wyr_3xGgDEM7iVz_1iqBD4MkIUt3_HujZqT5UT0Zp47yUON94I-jo3pMlCMSG6GX56uscSj7At_vSZkP8aOkNwhm0Sl9)
20. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHThL4rtx4byP-AmlKX1-_3lbJkILZ9HZL9foRGnUcjTwU_fj6hnls79t-5m5gecUF5zx3NwV4caq7BQHMPZLFWkfqdhuuLuKGEYwcVXwJ3DhhOX9MrELvDXPoVjELjj6YkAIngH1wtcw==)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTMHHIoL5Jsj3KLh3nGEzf4vHK9O_7jvo5kk6edldxgNqp5M6lZ7vi04-61fkdc-qwP5QPD-HSRka1eWOenic6sD3WKeEmL1YMw3tv9PmaW1Q2I-bFhNz_6YxqkHC5iYEh2w==)
22. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_-QFAXdTxc3N2VAxZ_PIBSRhnQ3eAzLsTQGyOKVUJA2qJTFKPlr4A2m_z8LrwKGeyFh1GaBkvIJQx8x8270Ywbkmoq7CCJPSGlGzc10seauOJdhSET--WrH4y65F42NtMrLLQQkw-cXIM2qz9S3REIu4UgwYJItLNhQ_UGh6xolcqEa6BS_T8cZXVrKXtUhg3ihOd97i2k4sBbisV8vLrrFY4m3K7I7yXNQ==)
23. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQETBnf9zYVJB_oRAFvrDeptd57Zo5epZQu0V-nDp10mXi1BHUITU2pWC-fWp3RHi0ZkBOqUAjWS1MDse2vRUWRij-ZBHlLjHG_sAC29OSyO7OrYTSZHQ3Qu_0QuIDLg0FdN5FL1uH9eGPzFVFqNCvKCcg==)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjG7Ov_adNZx4a_wq4_KcdW5IKozSMjY222ArhvjrXPIKs1MhVhKfG2R5dk6f6LnSGPrT8S6EKIqKUv_f1WQNzg4qVfHZ7QNE100pWkjW9v2K2sThkLJkGmtFMd8yDL2DB8xxB6gmG89FdMtGoxe4PtOd0UjDH0VppJaK6qhqLGGVSQy7EjWq0Y2SoBZeI9eU7JRwEBvRSa2pfSOkAWeDnnpx3zJr8wOzTuo_C5dOyRK_e)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERt7A2t6D_8bWCDgKTNrtqd5Xuo4BBRoL-7dyTKNW2JMkm4C0SrkyBVHJ5EQvSn1gAIHklqoLWFV-DPSewEzCSaBOQZOr5Xi4G6kqzA6pYsC7h2EYv9NxPx1sClfnRj3QdZ8LyGF-dgujeGCg82d9VrWiKNZhkFCclifusfwqiFduCxJrat7FzP5lB_yg=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGblLPVAQwCBziFf_CrWAIFwzWvJlTyGf7GsLy2G4a9imrUk3OFv106_jiQHe9Vn92XDl3az_ShyLhT8mV2bXaXid62mbb0VPok9oxhBsecXrqs5hw6yuvhEmoYue7ND3Ug3Y_f24kA3Ju4b-9C5Jc1ftjNNsjfv5nvEuI2izYb_fdiVgZQzjsjR8E2oAkcVXuHZuhOq4-YfseIno4MCw==)
27. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGxHcMfhej_t0NRVGmy_wb4FrJtWgRjdrMXIJgkRlzIFgBLSs87QSrVEG1ZHFASoY-bS7UiSm-5mdODgINK33Rk6MX4PAp3mRS2uI66O0e8WDh6jDNvpt8llUsGgZxktiohIBlMJt-kRicD)
28. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHowD5tbCZztCiguZBS8PCLrI3zJnbqksluRtzx7kPXZYtudCEnGBR4IodyqkUC3xkRtr_uaJEXRXBGMPIYuBd-U4u0KjTJsZLDQU3o78JfyJDB2scboiyYl7lNv-rgVgjk5Rnad-bH4JFiP_hzatkKtjATIDxQVQguVR3aOhzz9BBr8_s_jA2doo7QL9gIk4AI8Q==)
29. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE97MUKcTWXHSPUTNXkp6oIwmRhwJpPeGXzSIvjHb56b2riIoh0JhvGrC9azYfIBDABSVx9aoNEyZtHZDXrTmNiu_yOLlXDdzcXv7TGo41ePvalvGNvuhxiQ32l06BSCuhzXHwg_aG-UNP-Kg==)
30. [acs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGEDPfP7Cpjernp6ZLRisRna09NttmGPOSoWtMbpcy0F6a77Gn5ZxCejfdsye2lsNDGrl-8QKfuaqPCiJK7uqPr0PZyL9jZAl4B8qFndE-moNzZf9pmdx6Jacj76NZ39A-RTm9JAimgsxkK09M=)
31. [acs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHSWfSCvulbwqngbhODSI3tpeFNjY7HaQURdbP4IJmaQJIWHWLD1uOksJu9BZcHfQMtl1V-hq1SAWJDYfI7rix41qA60ooCykdVLC8xrcCJVSg2D8w55AhP8WG2tkpdUA0=)
32. [biorxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPiNSNY4XK0AGETLJW1-bx08F56pLJ7iaLzcLo6FWughCKil66sxTuWWogEj0VzmEnhGggYFgIJaLBPeI-gHUMzN3r-A39y_d0flcy6A5ut36pjxGEAH_IT_wyuu9HgjxyKfImKFsGmdV9jXhXO50ufJ9o6Q==)
33. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHT-45Kz35-soNiUTUregx_7T_1mVn_ZRsl8cCge6PHeHNEjTsWOAUkF7ucuXdr-5hZ1u4Z9whfxBzKCwPCQxXi97-zvaU00syL5jKOtRi18mu8dVGjeeFEmL90L3NeJ9a5z16Im0jQtA==)
34. [acs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHimBLwvU6Efi2IrxBHZQOp0au18Fpztfmc2ehAKGZz88bEC6t7wum80vou1YO0AaKk-HXPCSgqMe9HTaH4gNwozClJjYBoekZtsOdc79SQoUVxycTK5ERjLeg0HZIqAIk=)
35. [rdrr.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBNkcpAWqIt6MMPIPq01nW7sBXODJYSwgn9B3kBPQ_jVN_w-CU9TW3PpvzdAK-jR6KLRMjFDZmZmhe0UNlliOXb84jVEwNg0IbBjpE-PFBaiWjAbxbHpG2X1z1zBRrdgWy3J9HeqrwiNARenU4FU5ShXxmSLo=)
36. [sjtu.edu.cn](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-Z9EDyX0e9J363sgo_0DKe1h2cZ-fibboB7Mr5KhE9ydeU6VsUfgIMcAOwgkINs1yzUsH9MAONW80UpJ5tC7Vtw33dVDXFkqF6VHxcsa-W7-B9hSMs12C0I6_HG-EJFnIvLMkzel0zdHfTHd8Ki0cQuXusg9uhK_3MCxq3d6ruAibGGuzASBle4Z4w-iO5YjsZ0aqgsdSgDaTCab-J_iGFJ-syB_QfmCiStASckz1qQBfjv6JkDsyH7to)
37. [ubuntu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUe8WKsAZ3SZKZl1n2D00xfcT8mRCt3nKt2drl988XsQ_xjZeSXxA0yi9QqHr_SyWsB1GsHc2CIFfzjzXFHvlQtySDrJ2zCLjcsnFY-MpB9ymmJcdLUbQqKHNdKLLry3na7vHCMP1pyvnUb0OHYonV6Sokzj91008-EuKSvl0XPZgJUADuJMgqxrRcN8zIdafylGF6gNX_NeA6pcHk)
38. [danial.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVYJGr92SueCLbqLS8PqIehAJ0peNPN4PQzB5_exdiuS5ZSAO0OyWDMHkpYHcOVkEL9Yl5KTHcTcHy56KhpafeeC-BynOvnOPAZv9hlhQuXq0DD-ZL0xlrv6Diqm323VVFxDd2OkYNvsxJrFomquzfBEtXQtq8XIqBttU=)
39. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEfK1XyAy74LhiaNV_eRHIJWpgV9uW-y3g0k0FmPpQdZWkUrs8prYbgFquEprMYJU0WYRgi_ROSysZV8pB_pg481n4aAhrhiG4GKD30Ky8I4NXuOozOlTVmTBVYiCCKzZ2ruVMkAPec-KnkINoQTxuWLn18eTVJYwrorDgZm130kCRewt7783ogXR5fkIDw1KHrTs7GMZeQiyvaICT1OHiZ8s6qw23aw7ifMGJCcnHjPg==)
40. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGID9NOS7eYJ2B4xvLkyZ93axKQlLxlN2EPftZoLl30tmFi-i2_yLmaap6wE0Sfi3X21NWsIDqV9jGqtUX3_kIzN_MYwSNewvwL-3dnEv22a8LAfIV-0D487WNRfFVHJJVMYFb_3W4mIppmzdFq1avDx-ugqzybkXu6bXiccQc-_aSg_tUu)
41. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOtegdA17G4u0r61HXVzkBGuPHhHLXAFOCqTXgGKlRcr7Nq70y72-pOuggavzyfJ3P_m3NSFPpqsatlbd-gVjm6M3o8QpZueKAIgLWJU0yev2mFwU36yrmDghGsCajATkZ3x6-45JZObo=)
42. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGmLpN4A5XSxr7ZrrCOmoeUudV1ecymgUEtEs6VrXwVAaTYiI2hKRiK4wYpFdWj-Oho68PEOQT5kWJ1UHKBzayWLJbdUUnNKMuRyJhrCRwHd5m-HrgKLr5pT6xpIh4yh9C9gSvQCU7bsYzMUA==)
43. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEBLC7TzVcwL05UTZ9pMyluA9xUmebmVl05Dl7QUCzNI2fV4aBxdhKOQPom1ldgglH9VjUR9z5FZOsFQIQANJXRIVbWT6OiJG-ReH3gAsE3Hlnl8muHKfkM4Dst6ZtARr8m8Apx6BY8qjw_rrBasWrCBHNUYnjehoR3jRaLuxEgXXCb3RdrBC1bxwtlwACTZAxJaUhRuDn5w==)
44. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTiAwKg8Zjo5-gWMUM9we3s6XrnsOkvIIfAfgEzFNClppKO81Rp2m3j_SCH0ndAyY_qPiaGQkKk3MfY8pW45Yv7LPE5-tszWvZGygPMkWQf1C_o2xDjMXdsoEb62DaSDZf6v_X-FLprpj1Gg4SMrbKpOupOB6I0gm7Og==)
45. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGIUTm_0Br5fzLY6V8WdrYyDoaimFDaE1VzBlYHQqYLiHVJm2nep8YGO7qPakoKW6xTeWbsh_HZGfC18Ru24PzOzhUk5shBPmLdbwzpGuhicvdbWIR5y9Gy2vKfypBMnj0Rmko3_vKTAZWnm6B2AZM-jp9ESnM=)
