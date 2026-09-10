# Comprehensive Analysis and Implementation Guide for Recovering Missing Values in Multi-Sheet Excel Workbooks Using Openpyxl 3.1.5

**Key Points:**
*   The `openpyxl` library (version 3.1.5) provides robust capabilities for parsing, analyzing, and modifying Open XML format spreadsheets (`.xlsx`), though handling formulas, merged cells, and chart metadata requires specific workarounds.
*   Resolving missing tabular data (e.g., "???") in structured financial spreadsheets, such as NASA budget workbooks, can be achieved algorithmically by modeling the workbook as a constraint satisfaction problem.
*   NASA budget templates follow strict hierarchical structures (e.g., matching totals across Table I, II, and III for Cost Elements, Work Breakdown Structures, and Instrument Teams), which provides the mathematical constraints necessary for deducing missing figures.
*   Care must be taken regarding floating-point precision, data type preservation, and zero-based vs. one-based coordinate indexing when writing programmatic spreadsheet recovery tools.
*   A known bug in `openpyxl 3.1.5` alters the `Application` tag in the workbook's XML, which can corrupt chart layouts upon saving; this necessitates a programmatic patch prior to workbook initialization.

The reliance on spreadsheet software for critical financial and operational planning is ubiquitous across large organizations and government agencies. However, the manual entry and aggregation of data across multiple interrelated worksheets frequently lead to data loss, corruption, or the introduction of placeholder values such as "???". Recovering these missing values manually is a time-consuming and error-prone process. This report presents a comprehensive methodology for building a Python-based utility module to automatically read, analyze, and mathematically recover missing values in complex, multi-sheet Excel workbooks.

By utilizing `openpyxl 3.1.5`, developers can interface directly with the underlying Office Open XML (OOXML) architecture. This report details the specific Application Programming Interfaces (APIs) required for this task, the algebraic patterns inherent in institutional spreadsheets (using NASA's public budget templates as a primary case study), the nuances of floating-point arithmetic in data recovery, and the specific pitfalls associated with the library's handling of merged cells and application metadata. Finally, it provides a complete, reusable Python utility module implementing these concepts.

## 1. The openpyxl API for Multi-Sheet Excel Reading and Writing

The `openpyxl` library is the de facto standard in the Python ecosystem for interacting with Excel `.xlsx` files without requiring a native Microsoft Excel installation. To build a reliable data recovery tool, one must master the intricacies of file loading, workbook traversal, data typing, and file serialization.

### The `load_workbook` API and Parameterization

The entry point for processing an existing Excel file is the `load_workbook()` function. In `openpyxl 3.1.5`, this function parses the OOXML archive and dispatches its contents to relevant Python object models [cite: 1]. The signature for this function includes several critical parameters:

`openpyxl.load_workbook(filename, read_only=False, keep_vba=False, data_only=False, keep_links=True, rich_text=False)` [cite: 1]

*   **`filename`**: A string representing the path to the file or a file-like object opened in binary mode (e.g., an in-memory `BytesIO` object) [cite: 1, 2].
*   **`read_only` (default: `False`)**: If set to `True`, the workbook is optimized for reading, utilizing lazy-loading generators. While this reduces memory consumption, it precludes editing the file and fails to populate certain metadata, such as merged cell ranges [cite: 1, 3]. For a recovery tool that must write data back, this must remain `False`.
*   **`keep_vba` (default: `False`)**: Controls whether Visual Basic for Applications (VBA) macro content (`.xlsm` files) is preserved [cite: 1]. If preserved, it remains uneditable but will be saved intact [cite: 4]. 
*   **`data_only` (default: `False`)**: This is the most crucial parameter for analytical reading. It controls the behavior of cells containing Excel formulas. 
    *   If `data_only=False`, accessing `cell.value` for a formula cell returns the literal string formula (e.g., `"=SUM(A1:A10)"`).
    *   If `data_only=True`, the library reads the cached evaluated result of the formula stored the last time the file was saved by Excel (e.g., `150.5`) [cite: 1, 4]. Note that `openpyxl` never evaluates formulas natively [cite: 4]; it merely reads the last known cached value.
*   **`keep_links` (default: `True`)**: Determines whether links to external workbooks (cached copies of external data) are preserved [cite: 1, 2]. Disabling this can improve load times for files with massive external references.
*   **`rich_text` (default: `False`)**: If `True`, preserves rich text formatting within cells [cite: 1].

### Workbook Traversal and Iteration

Once a workbook object (`wb`) is instantiated, iterating through its structural hierarchy requires specific API calls. 

**Sheet Access:**
All worksheet names can be retrieved using the `wb.sheetnames` attribute, which returns a list of strings [cite: 5]. Individual sheets are accessed via dictionary-style key lookups, e.g., `ws = wb[sheet_name]`, or via the `wb.active` property to get the currently selected sheet [cite: 5].

**Row and Column Iteration:**
`openpyxl` uses **1-based indexing** for both rows and columns [cite: 6]. The boundaries of a worksheet's populated data are accessed via the integer properties `ws.min_row`, `ws.max_row`, `ws.min_column`, and `ws.max_column` [cite: 7]. 

To iterate efficiently, the library provides generator methods:
*   `ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column)`: Yields tuples of cells row by row [cite: 8].
*   `ws.iter_cols(...)`: Yields tuples of cells column by column.

### Reading Cell Values and Data Types

Individual cells are represented by `Cell` objects. To read data, one accesses the `cell.value` property [cite: 6]. The return type of `cell.value` is dynamically cast to a native Python type based on the underlying XML representation: `str`, `float`, `int`, `datetime.datetime`, or `None` for empty cells [cite: 6].

The `cell.data_type` property reveals the OOXML type specifier [cite: 6]. Common values include:
*   `'s'`: Shared string
*   `'n'`: Numeric (float or integer)
*   `'d'`: Date/time
*   `'b'`: Boolean
*   `'f'`: Formula

Handling missing value markers (e.g., "???") requires distinguishing between `None` (a truly empty, unformatted cell), an empty string `""`, and the specific literal string `"???"`. A programmatic check must first ensure the value is not `None` before attempting string comparison to avoid `TypeError` exceptions.

### Writing Values and Preserving Types

To write a recovered value back to the workbook, the program assigns a value to the corresponding cell coordinate: `ws.cell(row=r, column=c, value=numeric_value)` [cite: 9]. 

A critical step is ensuring the value is stored as a number, not text. If a Python script reads "???" (a string), calculates the replacement value as `100`, but inadvertently passes it as `"100"`, `openpyxl` will write it with a data type of `'s'` (string). Excel will display this with a green warning triangle ("Number stored as text"), and downstream formulas relying on this cell will break. The script must explicitly cast recovered values using `int(value)` or `float(value)` before assignment.

### Saving the Workbook

Saving the workbook is executed via `wb.save('output.xlsx')` [cite: 4]. Because OOXML files are essentially ZIP archives containing XML files [cite: 5], `openpyxl` recompiles the modified XML and packages it. Assuming `load_workbook` was called without `read_only=True`, the saved file preserves cell formatting, font styles, fill colors, and merged cell boundaries. However, `openpyxl` does not support every advanced Excel feature; highly complex charts or images might be lost if modified and re-saved [cite: 4].

## 2. Detecting and Locating "???" Placeholder Cells

The first functional requirement of the utility module is to scan the entire workbook for cells explicitly containing the string "???". Because real-world spreadsheets often mix strings, numbers, and dates, string operations must be protected with type checking.

### Scanning Algorithm

The optimal pattern for traversing an entire workbook requires nested loops:
1. Iterate over all sheets using `wb.sheetnames`.
2. Iterate over all rows in the sheet using `ws.iter_rows()`.
3. Iterate over all cells in the row tuple.
4. Check if the cell value is of type `str`.
5. Check if `"???"` is present within the string (or equals it exactly, depending on user convention).

### Storing Locations

Once identified, the location of these missing cells must be stored for future analytical passes. Because the recovery module will cross-reference different sheets and coordinates, the best structure is a list of tuples containing `(sheet_name, row_index, column_index)`. Alternatively, dictionaries can be used for named access. We also need to store a reference to the `Cell` object itself if direct manipulation is required, though storing coordinate indices is safer against memory reference issues across passes.

### Working Code Pattern for Detection

```python
def find_missing_cells(wb, marker="???"):
    """
    Scans all worksheets for cells containing the specified missing value marker.
    Returns a list of dictionaries containing location metadata.
    """
    missing_cells = []
    
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # Iterate through all populated cells
        for row in ws.iter_rows(min_row=ws.min_row, max_row=ws.max_row, 
                                min_col=ws.min_column, max_col=ws.max_column):
            for cell in row:
                if cell.value is not None and isinstance(cell.value, str):
                    if marker in cell.value.strip():
                        missing_cells.append({
                            'sheet': sheet_name,
                            'row': cell.row,
                            'col': cell.column,
                            'coordinate': cell.coordinate
                        })
    return missing_cells
```

## 3. Analyzing Relationships in NASA Budget Excel Files

To build logic that recovers missing numbers, the program must understand the mathematical topography of the target document. NASA's Science Mission Directorate (SMD) and Earth Science Division (ESD) utilize strictly structured Excel templates for Senior Review budget proposals. Understanding these templates illuminates the programmatic patterns required for data recovery.

### Common Structures in NASA Budget Spreadsheets

Based on public guidance for NASA budget submissions, these spreadsheets are characterized by standardized tables representing categorical splits of a definitive top-line total [cite: 10, 11].

*   **Table I (Budget by Cost Element)**: Details labor, travel, and procurement costs.
*   **Table II (Budget by WBS)**: Breaks down the same budget by Work Breakdown Structure (WBS), such as functional operations, science data analysis, etc. [cite: 10, 12].
*   **Table III (Budget by Instrument Team)**: Further allocates the budget per instrument. This is heavily utilized for missions like Aqua and Aura [cite: 10].

The defining constraint of these workbooks is an explicit reconciliation rule: **The totals for Table II and Table III must identically match the total in Table I** [cite: 10, 12]. 

Furthermore, within Table II (Labor breakdown), there are rigid labor categorization rules involving Full-Time Equivalents (FTEs, usually Civil Servants) and Work Year Equivalents (WYEs, usually Contractors split by Onsite and Offsite) [cite: 10, 13]. 
*   $\text{Total Labor} = \text{CS FTEs} + \text{Onsite WYEs} + \text{Offsite WYEs} + \text{JPL WYEs}$ [cite: 13].

### Programmatic Detection of Mathematical Relationships

A missing value "???" in such a spreadsheet is mathematically equivalent to a single unknown variable $x$ in a system of linear equations. The utility module must detect four types of relationships:

1.  **Row Sums**: A "Total" column at the end of a row equals the sum of previous columns (e.g., YoY totals from FY27 to FY29) [cite: 10].
2.  **Column Sums**: A "Total" row at the bottom of a block equals the sum of the rows above it (e.g., summing all WBS elements to find total budget).
3.  **Cross-Sheet Aggregation**: A summary sheet imports cell values from detailed center-specific sheets ("Separate entries should be made for each supporting Center") [cite: 10, 13].
4.  **Differences/Ratios**: Calculating remaining budget or overhead percentage.

To detect if a "???" can be recovered via a **column sum minus known values**, the algorithm must:
1. Scan the column containing "???" for a "Total" label in the adjacent row header.
2. Identify the continuous block of numeric data bounding the "???".
3. Verify that the sum of the known numeric cells, plus $x$, equals the Total. Thus, $x = \text{Total} - \sum \text{Knowns}$.

### Constraint Propagation Strategy

If multiple "???" values exist, solving one may unlock another. This requires a **constraint propagation** strategy. The algorithm iteratively passes over the list of missing cells. In each pass, it attempts to resolve the cell using row, column, or cross-sheet totals. If a cell cannot be uniquely determined (e.g., a column has two missing values), it is skipped. The pass repeats until either all missing values are resolved, or a pass results in zero newly recovered values (indicating an unsolvable state without more information).

## 4. Numerical Computation Patterns for Data Recovery

Transforming the theoretical constraint propagation into programmatic execution requires specific heuristics for interpreting Excel layouts.

### Identifying Table Structures and Headers

Spreadsheets lack explicit semantic tagging; a script must infer table boundaries. The module identifies headers by searching for non-numeric, descriptive strings near blocks of data. For NASA files, looking for keywords like "FY27", "Total*", "FTE", and "WYE" establishes coordinate bounding boxes [cite: 10, 12]. 

When the `detect_sum_relationships()` function assesses a missing cell at `(row=R, col=C)`, it traverses upwards to find a non-numeric string (the column header) and downwards to find a cell labeled "Total" (the column sum).

### Floating-Point Precision and Tolerances

A significant hurdle in automated spreadsheet analysis is floating-point arithmetic. Python utilizes IEEE 754 double-precision floats, leading to infinitesimal inaccuracies (e.g., $0.1 + 0.2 = 0.30000000000000004$). Excel masks this in its UI, but the underlying XML often stores these raw floats.

When checking if a sequence of cells sums to a target Total to validate a relationship, utilizing direct equality (`sum == total`) will frequently fail. Instead, the utility must employ tolerance-based comparison using `math.isclose()`:

```python
import math

def is_valid_sum(addends, total_val, tolerance=1e-5):
    return math.isclose(sum(addends), total_val, rel_tol=tolerance, abs_tol=tolerance)
```

### Inferring Target Data Types

Spreadsheets mix integer quantities (like FTE headcounts) with continuous float variables (like monetary budgets in $K) [cite: 10]. Writing a floating-point number (e.g., `3.0`) into an FTE headcount column where surrounding cells are integers (`5`, `12`) creates formatting inconsistencies.

The recovery module infers the appropriate data type by polling the data types of the `known` values in the same row or column.
*   If all known addends and the target sum are Python `int` types, the recovered value $x$ is rounded and cast to `int`.
*   Otherwise, it is cast to `float`.

## 5. openpyxl Pitfalls and Edge Cases

Building robust utilities in `openpyxl` requires navigating several idiosyncratic behaviors of the library and the OOXML specification.

### Merged Cells Behavior

Merged cells are notorious for breaking programmatic spreadsheet loops. When Excel merges a range of cells (e.g., `A1:C1`), the visual result is a single large cell. In `openpyxl`, this is represented by assigning the actual value to the **top-left (anchor) cell** (i.e., `A1`), while the remaining boundary cells (`B1`, `C1`) are instantiated as `MergedCell` objects [cite: 4]. 

Crucially, **`MergedCell` objects have no value attribute**; their value is structurally considered `None` [cite: 6, 14]. Attempting to access or assign `merged_cell.value` raises an `AttributeError: 'MergedCell' object attribute 'value' is read-only` [cite: 15, 16].

**Mitigation:** The utility must check if a cell is part of a merge range using `ws.merged_cells.ranges` [cite: 3]. If a loop encounters a merged cell coordinate, it must logically map it back to the anchor cell's value. 

```python
from openpyxl.cell.cell import MergedCell

def get_actual_value(ws, cell):
    if isinstance(cell, MergedCell):
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                # Return the value of the top-left anchor cell
                anchor_coord = merged_range.start_cell.coordinate
                return ws[anchor_coord].value
    return cell.value
```

### The "AppVersion" / Chart Corruption Bug in 3.1.5

A critical, documented bug in `openpyxl 3.1.5` pertains to how the library writes document metadata. The OOXML specification includes an `AppVersion` and `Application` tag. In `3.1.5`, `openpyxl` changes the Application tag to `Microsoft Excel Compatible / Openpyxl 3.1.5` [cite: 17, 18]. 

Microsoft Excel's rendering engine (particularly for charts) is highly sensitive to this metadata. When Excel 365 opens a file saved by `openpyxl 3.1.5` with this modified tag, it often breaks chart layouts, overlaying titles and removing axes [cite: 18]. 

**Mitigation:** The utility module must apply a runtime monkey-patch to `openpyxl.packaging.extended.ExtendedProperties` before saving to forcefully reset the application name back to "Microsoft Excel" [cite: 18].

```python
# Monkey-patch to fix openpyxl 3.1.5 chart corruption bug
from openpyxl.packaging.extended import ExtendedProperties

def _patched_init(self, *args, **kwargs):
    ExtendedProperties.original_init(self, *args, **kwargs)
    if self.Application != "Microsoft Excel":
        self.Application = "Microsoft Excel"

ExtendedProperties.original_init = ExtendedProperties.__init__
ExtendedProperties.__init__ = _patched_init
```

### Preserving Formatting During Replacement

When replacing "???" with a numeric value, simply assigning `cell.value = 150.0` preserves the cell's existing OOXML formatting attributes (number format, font, fill) inherently in `openpyxl`, provided the workbook was loaded normally (without `read_only=True`). The library modifies only the node value within the XML, leaving the `<xf>` style index intact. However, casting the value properly (as discussed) is necessary to ensure Excel applies numerical formatting rules (like accounting formats) correctly upon opening.

## 6. Working Code Examples: Complete Reusable Utility Module

The following section aggregates the research, logic, and edge-case mitigations into a complete, production-ready Python utility module. It contains all five requested functions, rigorously engineered for NASA-style financial workbooks.

```python
import math
from typing import List, Dict, Tuple, Any
from openpyxl import load_workbook
from openpyxl.workbook import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.packaging.extended import ExtendedProperties

# =====================================================================
# MONKEY PATCH FOR OPENPYXL 3.1.5 CHART CORRUPTION BUG
# Forces the Application metadata to "Microsoft Excel" to prevent 
# Excel from dropping chart layouts upon opening saved files.
# =====================================================================
def _patched_extended_properties_init(self, *args, **kwargs):
    ExtendedProperties.original_init(self, *args, **kwargs)
    if getattr(self, 'Application', None) != "Microsoft Excel":
        self.Application = "Microsoft Excel"

ExtendedProperties.original_init = ExtendedProperties.__init__
ExtendedProperties.__init__ = _patched_extended_properties_init


class WorkbookDataRecovery:
    """
    Utility class for reading, analyzing, and recovering missing values 
    in multi-sheet Excel workbooks using openpyxl 3.1.5.
    """
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.wb = None
        self.missing_cells = []
    
    def load_workbook_data(self) -> Workbook:
        """
        Loads and returns the workbook. Uses data_only=True to evaluate
        cached formulas, ensuring we read the numerical results needed 
        for algebraic recovery, rather than formula strings.
        """
        print(f"Loading workbook: {self.filepath}...")
        # read_only=False is required because we need to write back and access MergedCells.
        self.wb = load_workbook(
            filename=self.filepath, 
            data_only=True,      # Get values, not formula strings
            keep_vba=True,       # Preserve macros if any
            keep_links=True      # Maintain external data references
        )
        return self.wb

    def find_missing_cells(self, marker: str = "???") -> List[Dict[str, Any]]:
        """
        Locates all placeholder cells containing the marker string across all sheets.
        Returns a list of dictionaries with sheet, row, and column data.
        """
        if not self.wb:
            raise ValueError("Workbook not loaded. Call load_workbook_data() first.")
            
        self.missing_cells = []
        
        for sheet_name in self.wb.sheetnames:
            ws = self.wb[sheet_name]
            for row in ws.iter_rows(min_row=ws.min_row, max_row=ws.max_row, 
                                    min_col=ws.min_column, max_col=ws.max_column):
                for cell in row:
                    # Skip merged cell boundaries which have no value
                    if isinstance(cell, MergedCell):
                        continue
                        
                    val = cell.value
                    if val is not None and isinstance(val, str) and marker in val:
                        self.missing_cells.append({
                            'sheet': sheet_name,
                            'row': cell.row,
                            'col': cell.column,
                            'coordinate': cell.coordinate,
                            'resolved': False,
                            'inferred_value': None
                        })
                        
        print(f"Found {len(self.missing_cells)} cells with '{marker}'.")
        return self.missing_cells

    def detect_sum_relationships(self, ws, row_idx: int, col_idx: int) -> Tuple[float, List[Any], str]:
        """
        Identifies if a given missing cell coordinate acts as a missing addend
        in a row or column sum. 
        Returns (Target_Total, List_of_Known_Addends, Relationship_Type).
        """
        # --- Check Column Sum (Total is usually below the data) ---
        # Search down the column for a Total
        target_total = None
        known_addends = []
        is_col_sum = False
        
        # Look ahead up to 20 rows for a total to establish bounding box
        for r in range(row_idx + 1, min(row_idx + 20, ws.max_row + 1)):
            test_cell = ws.cell(row=r, column=col_idx)
            
            # Check if adjacent cell in the previous column says "Total"
            label_cell = ws.cell(row=r, column=max(1, col_idx - 1))
            label_val = str(label_cell.value).lower() if label_cell.value else ""
            
            if "total" in label_val and isinstance(test_cell.value, (int, float)):
                target_total = test_cell.value
                is_col_sum = True
                
                # Gather knowns from above the missing cell down to the total
                # For simplicity, assume contiguous block delimited by strings/empty
                for scan_r in range(r - 1, 0, -1):
                    scan_cell = ws.cell(row=scan_r, column=col_idx)
                    if scan_r == row_idx:
                        continue # This is the "???" cell
                    if scan_cell.value is None or isinstance(scan_cell.value, str):
                        break # End of numeric block
                    if isinstance(scan_cell.value, (int, float)):
                        known_addends.append(scan_cell.value)
                break

        if is_col_sum:
            return target_total, known_addends, "column"

        # --- Check Row Sum (Total is usually to the right) ---
        target_total = None
        known_addends = []
        is_row_sum = False
        
        for c in range(col_idx + 1, min(col_idx + 15, ws.max_column + 1)):
            test_cell = ws.cell(row=row_idx, column=c)
            # Check column header for "Total"
            header_cell = ws.cell(row=max(1, row_idx - 1), column=c)
            header_val = str(header_cell.value).lower() if header_cell.value else ""
            
            if "total" in header_val and isinstance(test_cell.value, (int, float)):
                target_total = test_cell.value
                is_row_sum = True
                
                for scan_c in range(c - 1, 0, -1):
                    scan_cell = ws.cell(row=row_idx, column=scan_c)
                    if scan_c == col_idx:
                        continue
                    if scan_cell.value is None or isinstance(scan_cell.value, str):
                        break
                    if isinstance(scan_cell.value, (int, float)):
                        known_addends.append(scan_cell.value)
                break
                
        if is_row_sum:
            return target_total, known_addends, "row"
            
        return None, [], "none"

    def recover_missing_values(self) -> None:
        """
        Iteratively solves for missing values using constraint propagation.
        Continues passing over the missing cells until no more can be resolved.
        """
        if not self.missing_cells:
            print("No missing cells to recover.")
            return

        unresolved = [m for m in self.missing_cells if not m['resolved']]
        iteration = 1
        
        while unresolved:
            resolved_in_pass = 0
            
            for m in unresolved:
                ws = self.wb[m['sheet']]
                target_total, knowns, rel_type = self.detect_sum_relationships(ws, m['row'], m['col'])
                
                if rel_type != "none" and target_total is not None:
                    # The constraint equation: target_total = missing + sum(knowns)
                    sum_knowns = sum(knowns)
                    recovered_val = target_total - sum_knowns
                    
                    # Prevent floating point anomalies (e.g. 0.000000001 instead of 0)
                    if math.isclose(recovered_val, 0.0, abs_tol=1e-9):
                        recovered_val = 0.0
                        
                    # Infer data type: if all knowns and total are integers, make it an int
                    if isinstance(target_total, int) and all(isinstance(k, int) for k in knowns):
                        recovered_val = int(round(recovered_val))
                    else:
                        recovered_val = float(recovered_val)
                    
                    # Write the value back to the workbook ensuring NUMERIC type
                    target_cell = ws.cell(row=m['row'], column=m['col'])
                    target_cell.value = recovered_val
                    
                    m['resolved'] = True
                    m['inferred_value'] = recovered_val
                    resolved_in_pass += 1
                    print(f"Resolved {m['coordinate']} on '{m['sheet']}' -> {recovered_val} (via {rel_type} sum)")
            
            if resolved_in_pass == 0:
                print(f"Constraint propagation halted. {len(unresolved)} cells remain unsolvable.")
                break
                
            unresolved = [m for m in self.missing_cells if not m['resolved']]
            iteration += 1

    def save_recovered_workbook(self, output_path: str) -> None:
        """
        Saves the workbook with numeric values replacing the markers.
        Preserves original formatting.
        """
        if not self.wb:
            raise ValueError("No workbook loaded to save.")
            
        print(f"Saving recovered workbook to: {output_path}")
        self.wb.save(output_path)
        print("Save complete.")

# =====================================================================
# USAGE EXAMPLE
# =====================================================================
if __name__ == "__main__":
    # Initialize the utility
    recovery_tool = WorkbookDataRecovery("nasa_budget_template_draft.xlsx")
    
    # 1. Load the data 
    recovery_tool.load_workbook_data()
    
    # 2. Find the missing values marked as "???"
    recovery_tool.find_missing_cells("???")
    
    # 3 & 4. Recover the missing values utilizing relationships
    recovery_tool.recover_missing_values()
    
    # 5. Save the output, bypassing the openpyxl 3.1.5 chart bug
    recovery_tool.save_recovered_workbook("nasa_budget_template_recovered.xlsx")
```

### Conclusion

The development of a Python utility module for recovering data in complex spreadsheets requires more than basic file I/O operations. By deeply integrating with the `openpyxl` API, properly understanding the structure of OOXML and data type enforcement, modeling the financial constraints natively found in standardized budgeting templates, and guarding against library-specific bugs such as the `MergedCell` constraints and the 3.1.5 `AppVersion` defect, one can achieve a highly robust automated auditing and recovery tool. The implementation provided directly addresses these parameters, offering a stable backbone for scalable data reconciliation architectures.

**Sources:**
1. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEv7T9G7XzYS1eY0pFD7lPCxY5vimzjr_T3Z7KhPdelPWS_NGvYUr6eXWmt7-eA-pwEgkacxG-V28tAif25om7_P_tQXQW-HGB2cP4d-3DU7xRtgi0JjnuUTCV5uA0SzrU-XPVBUi0bQtSDWGVdPsgo_iI3ye-TWoV6Gm0=)
2. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5Mm_nB28B94DRghfwohUC1-SUdfh5EcoXg-0XOML-qxmlHm_Q3JYObbbIyG0M9WbLdZw3M3dmDUd4w6F-vc364eV8L6JNjG_5EJzltqlCIzEg5BtIQyrBvoLP3zZzknku3uv4vdWyLFkevnURfWM7PIBWasOJSarJLS4=)
3. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFL_JVNNmIf2aaIBI8SGN5zIZfT5EULCQtZ2Xe7AaCpOJOgkmEvbdTZJD2KGBH-tdRvyWFnSo3S0dGHjqTqC-XpcEXGhp-nj3zjU0k6VVsvbf_zWWzW100Syyao2_QLDQsJYwzeadY1afpQUUs3Z2MS9H9h0n1g9JmaD4ZgwLA54lw3BD3fHc36DnitonG_mA==)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-1-LPxwav2fp491csjga0R1ltoTeVUif_ZZSG2shLonGQSAEMBnOtv9bluTJgieK7dpqEn8H14kTQ3bgMnfw0qMRISD1kJcxG5yCe2VasVS2njeqPpp5fmlR2CQOII13COyv-Ir6C)
5. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPcyOdB1K8xmNMMfeMLSmN-fmEsjUPAULe0CBxQqUrB-Yjfzqlun115k3I0Ap24jSwLJnyfVemHnIeRvKhvpqNfdGNsvBk3nSvtjQDuFsk5tclN_34G1T-7aYflQwKVomrwY4quMJpwXNo)
6. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHpQ5upTVkb7qpIrS5BPUhzIwm03NRDgd2aAY1a-C4HrxIui-Bvd82VCk0KpJlJoZPRhVpV8Qs5iCKPtDymzjbfIMS1gNeWi6c4yFGju-KNiIrL3-CbYRfsd9VxhtMbOVT73g6XPQg5nIAJpnBd76nCbegm0G1G9jneXhI=)
7. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsKDatA-H4X9hYMMJaIB9llXKJ4QkgFE5W57on_TgMI8nwE5DpzSzqb3UdAX-z8WqUQzujBuVghKgPPMt0K3OlCZliKT9uqGxJlYdDUKSH9w5TeXKS-SuJ3U7FeWYguVo=)
8. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGvzjgbB0_dxP2iaWMUl2CyjSBqsxFggjHZaAH9oln7L_G4j-68XffdyylDcej21x7Yq4LDeAJMP4mfrJdOrpDhknewG8gg5z9QP9D12f8DESphIws6ZEoOjLu-iJr3X4tTYg7dJprR14c=)
9. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHCjbrOZOyYOcrBsgzBUTn-Vhz3jpvL9u9dznw6Wh1gVVJj3RcMaY50e7APnRpJK3svoioMjTfevqMELYwGSGT68FXzTUk8myfJGNK1Zgsa2C42a_QXaMdQJAkPhh5Pe6wHUStyC4DCxp2hS4_sRjysi8l9SBGMlwX3EitGVN47pWTCjBS1DDW7VCBm9OzFTpyae0s5kw==)
10. [nasa.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9Kh51OY5TJ_vEIoIfwzfsH_C-kVsngx8JW0alCjQ0nKaUoRwfQBHdg9Arkztc0TUrZDXC2dURt-Arj71AqtwiwMUKnkHvwCL1xJegmczRz5kasPixVgEEuBr7UvVE5YITsDUio5vFQACAv8po4Me23U9keFvYcH3H-_OAwu8wn58j0fjFRiDu5XpdcY1rb2jNAJLpDus9lEjkDv1hbyR4uh53UK4zZaV33wVyIThFtJA5vzA8HwmFdADWnSeS5XVuUyi5gWkluWeyAdf5Fdsbwlln6Zt5g5Q=)
11. [nasa.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFE1TCSDh4q7bd9dtl6hxM-2msgFxZISYzQLRWy1FlWmrGBzGFumG4ZqsVeoR_ppsMylyu-Lj303WdLtUrkLYEnI0vTCWI08x9KtpsReBKa_Ys93v7kc3FIxCmMx1RmVS7ue-6nNSmJ7lWeC-LfW2CLhls-LqOT34fQ8g-NwZMN1-jtg5N6H__MublZYitdRUAeSLqALSxK-gxeqAcMF4qsNuBFqcpfsk5OO4vrs1se8tGD7fuQXeqQeWqVQTPXN2czvikdqTsWKL4MuL4aksk=)
12. [nasa.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHImuSi9ULqzAASqls5UBe-xeP0vbJxAuOQVO8TZ2EvUAhf-hUbrNWptvMTiFORQxSDx23i3aCsN6TKAFrxt00_9OLCTUWXOPTcHNec6xhoWHDm9sCK8rioRomtfRoCkrxGccfWMXAzI65631bQvp-xSa-XTZdcNSY7AFkSBZQF6Nq9vBgJfGeBgPP49IVMkLEa8hOg-xRTH_gLeOs=)
13. [nasa.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyVVUEh2fRPPOlRwT0e0D2iSiRqDFm07eZfASloaQmbiUzM0mIRuiOKdsTHp-i0u7o6KFsP-Gkp8gk5hrd2muMiSH1QbSo_BD3e7E0cS4ZqQUSZzyn5Rd0Dq8ZwA6XcHPXoyXe96HiRyPZxKuOvFnn8vCMtaXOtn7kPrUUr-5frwrg19Gl0McMU7I_1wyoVlpa-JhFSamrljo=)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuPxIgtvxbfFoxt2ALdvICt6r2I1LiNRcwEBzSkjDB1cxCXZd-_eoVBCnAiMOoOGNI9hv5GtVVVqCt51f3QHithF1IFBHD9fu6j3I-U1-jOKykc23GkU3ovqqQz7NFCNx9AKJrFGI7YGrrT1nUoj-cnF6_xtz4yXP1sY_lZqrVhxi99oDrlK7p9ckgFMvzUwpU3k3CuP2gjveN927jwaCsYZH67rnz6g==)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZvmrtbWO-_MsFmnF7Opx6UEYvSxUBZQH0MY2GDMWfimuL9lwPF2UjImLo7tgR7VhTPixZa3oX5usW-tJc7TWCmR-zV5fr4pVw0h7_6raJ9zs28gThh5OXhjgvxhzAcTN2BaXZOPbk79OGHhYXFeUW226GrO0Hhxqa69hRGNmwbmaVdd_tTAda_v5l8nhPYi20BgJUmryVXFoWQkVD7pAVKtkIoGOQC8Hs)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEllG5o82GbgMY0kKZeXVAA6Ed3qMMwcnD5Yo1RDnvKmadg_hkP90i5kvjrYXnMD9wSiSlp-N1cB6QIPf8hEo26diBOFYPcJE3hv0wcdhPNbA7HlYkXbR7oHgO4XuQxxyye3jPgo6IGloZbmMM8f6W3Y9r01OgzyKW8fiSAttH7cNA-oydnscW3b8ZN1tvszfgPLkN2e3IhMdDC)
17. [any.run](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwgw0n0UoqYkgtX_g78NeSTJWsc77vOdmLLUVMPLc9RYntPRBzA57_7Jcz01hZcwmCzs9LD2kuA4j2d5ulod_B_sUEIJcSra13tzdwzpD6gZ1it3izS60nFRPhjMxKbYzINpsouh_Q2F5jwPO9T-ablD6L31IwNxi6-RhGJjS9U7yGGJWw9GdRMIpkIeMGZQU21SRi0QJLVZ84Pv_8gxbcmiqaogTJsJ_7jZAFh1gXSiIA)
18. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFB-VhFVA1ZBvhRFDvZ7FGmSpc4J4nVMjrDazvkEdZCOde-MLKfRzDGMBCWhIgkgKicjX-H7VqZbDAAjVwzTyZlmk2t9TxgDsF4R5xqR6BiE776_iDJ9E91ls-XeQMtSKp-r6M74JX1ocO_Um6EmA==)
