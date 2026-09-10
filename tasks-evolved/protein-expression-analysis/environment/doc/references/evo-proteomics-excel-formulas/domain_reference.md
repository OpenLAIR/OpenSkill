# Domain Reference for evo-proteomics-excel-formulas

**Responsibility**: Provide utilities to load/save .xlsx files preserving formulas and formatting, detect group/category cells by fill color, build sample/protein coordinate indices, and emit correctly-formatted Excel formulas (INDEX-MATCH, AVERAGE, _xlfn.STDEV.S, log2FC, 2^FC) for proteomics analysis.

**Key functions to implement**: load_workbook_preserving, save_workbook_safely, get_cell_fill_hex, build_sample_column_index, classify_group_columns, build_index_match_formula, build_average_formula, build_stdev_s_formula, build_log2_fold_change_formula, build_linear_fold_change_formula

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

### 2.2 Writing Specific Statistical and Lookup Formulas


**INDEX/MATCH and Absolute References**:
When constructing two-way lookup formulas programmatically, absolute references (`$A$1`) versus relative references (`A1`) must be rigorously controlled, particularly if users might copy-paste the formula downwards.

```python

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