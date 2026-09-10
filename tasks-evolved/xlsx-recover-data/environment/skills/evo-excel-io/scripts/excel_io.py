"""
evo-excel-io utility functions for Excel I/O with openpyxl 3.1.5.
Handles loading, scanning for markers, safe cell access, writing, and saving.
"""
import math
from openpyxl import load_workbook as _load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.packaging.extended import ExtendedProperties

# =====================================================================
# MONKEY PATCH FOR OPENPYXL 3.1.5 CHART CORRUPTION BUG
# Forces Application metadata to "Microsoft Excel"
# =====================================================================
_original_init = ExtendedProperties.__init__

def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    if getattr(self, 'Application', None) != "Microsoft Excel":
        self.Application = "Microsoft Excel"

ExtendedProperties.__init__ = _patched_init


def load_workbook_safe(filepath, data_only=True):
    """
    Load an Excel workbook safely with appropriate parameters.
    Uses data_only=True to get cached formula values (not formula strings).
    read_only=False to allow writing and merged cell access.
    
    Args:
        filepath: Path to .xlsx file
        data_only: If True, read cached formula values instead of formula strings
    
    Returns:
        openpyxl Workbook object
    """
    wb = _load_workbook(
        filename=filepath,
        data_only=data_only,
        keep_vba=True,
        keep_links=True,
        read_only=False
    )
    return wb


def get_cell_value_safe(ws, row, col):
    """
    Safely read a cell value, handling MergedCell objects.
    For merged cells, returns the value of the anchor (top-left) cell.
    
    Args:
        ws: Worksheet object
        row: 1-based row index
        col: 1-based column index
    
    Returns:
        The cell value (could be str, int, float, None, etc.)
    """
    cell = ws.cell(row=row, column=col)
    if isinstance(cell, MergedCell):
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                anchor = ws.cell(row=merged_range.min_row, column=merged_range.min_col)
                return anchor.value
        return None
    return cell.value


def find_missing_cells(wb, marker="???"):
    """
    Scan all worksheets for cells containing the marker string.
    
    Args:
        wb: Workbook object
        marker: String to search for (default "???")
    
    Returns:
        List of dicts with keys: sheet, row, col, coordinate
    """
    missing = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=ws.min_row, max_row=ws.max_row,
                                min_col=ws.min_column, max_col=ws.max_column):
            for cell in row:
                if isinstance(cell, MergedCell):
                    continue
                val = cell.value
                if val is not None and isinstance(val, str) and marker in val.strip():
                    missing.append({
                        'sheet': sheet_name,
                        'row': cell.row,
                        'col': cell.column,
                        'coordinate': cell.coordinate
                    })
    return missing


def write_recovered_value(ws, row, col, value):
    """
    Write a recovered numeric value to a cell, preserving formatting.
    Ensures the value is stored as a proper numeric type.
    
    Args:
        ws: Worksheet object
        row: 1-based row index
        col: 1-based column index
        value: Numeric value to write (will be cast to int or float)
    """
    cell = ws.cell(row=row, column=col)
    # Ensure numeric type
    if isinstance(value, (int, float)):
        cell.value = value
    else:
        cell.value = float(value)


def save_workbook_safe(wb, output_path):
    """
    Save workbook with the AppVersion monkey-patch already applied.
    
    Args:
        wb: Workbook object
        output_path: Path for output .xlsx file
    """
    wb.save(output_path)


def is_numeric(value):
    """Check if a value is numeric (int or float, not bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_missing(value, marker="???"):
    """Check if a cell value is the missing marker."""
    return value is not None and isinstance(value, str) and marker in value.strip()
