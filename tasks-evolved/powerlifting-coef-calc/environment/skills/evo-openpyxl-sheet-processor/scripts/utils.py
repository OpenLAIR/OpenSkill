"""
openpyxl Sheet Processor Utilities

Provides functions for loading Excel workbooks, finding column indices,
copying columns between sheets, appending formula columns, and saving.
"""

from openpyxl import load_workbook as _load_workbook


def load_workbook_safe(filepath):
    """Load an Excel workbook safely.
    
    Args:
        filepath: Path to .xlsx file
    
    Returns:
        openpyxl Workbook object
    """
    wb = _load_workbook(filepath)
    return wb


def find_column_indices(sheet, column_names):
    """Find column indices (1-based) for given column names in a sheet's header row.
    
    Args:
        sheet: openpyxl Worksheet object
        column_names: list of column name strings to find
    
    Returns:
        dict mapping column_name -> 1-based column index
    
    Raises:
        ValueError if any column name not found
    """
    header_map = {}
    for cell in sheet[1]:
        if cell.value in column_names:
            header_map[cell.value] = cell.column
    
    missing = set(column_names) - set(header_map.keys())
    if missing:
        raise ValueError(f"Columns not found in sheet: {missing}")
    
    return header_map


def copy_columns_to_sheet(source_sheet, dest_sheet, column_names):
    """Copy specified columns from source sheet to destination sheet.
    
    Preserves the order of column_names. Copies header row and all data rows.
    Columns are written starting at column 1 in dest_sheet in the order given.
    
    Args:
        source_sheet: openpyxl Worksheet to read from
        dest_sheet: openpyxl Worksheet to write to
        column_names: list of column name strings in desired output order
    
    Returns:
        int: number of data rows copied (excluding header)
    """
    # Find source column indices
    col_indices = find_column_indices(source_sheet, column_names)
    
    max_row = source_sheet.max_row
    
    # Write headers
    for dest_col, col_name in enumerate(column_names, 1):
        dest_sheet.cell(row=1, column=dest_col, value=col_name)
    
    # Copy data rows
    for row in range(2, max_row + 1):
        for dest_col, col_name in enumerate(column_names, 1):
            src_col = col_indices[col_name]
            value = source_sheet.cell(row=row, column=src_col).value
            dest_sheet.cell(row=row, column=dest_col, value=value)
    
    return max_row - 1  # number of data rows


def append_formula_column(dest_sheet, col_index, header_name, formula_builder, num_data_rows):
    """Append a column with Excel formulas to a destination sheet.
    
    Args:
        dest_sheet: openpyxl Worksheet to write to
        col_index: 1-based column index for the new column
        header_name: Header string for the new column
        formula_builder: callable(row) -> formula string. Called for each data row.
        num_data_rows: number of data rows (rows 2 through num_data_rows+1)
    """
    dest_sheet.cell(row=1, column=col_index, value=header_name)
    
    for row in range(2, num_data_rows + 2):
        formula = formula_builder(row)
        dest_sheet.cell(row=row, column=col_index, value=formula)


def save_workbook(wb, filepath):
    """Save workbook to file.
    
    Args:
        wb: openpyxl Workbook object
        filepath: Output file path
    """
    wb.save(filepath)
    print(f"Workbook saved to {filepath}")


def get_column_letter(col_index):
    """Convert 1-based column index to Excel column letter.
    
    Args:
        col_index: 1-based column index (1='A', 2='B', etc.)
    
    Returns:
        Column letter string (e.g., 'A', 'B', 'AA')
    """
    from openpyxl.utils import get_column_letter as _gcl
    return _gcl(col_index)
