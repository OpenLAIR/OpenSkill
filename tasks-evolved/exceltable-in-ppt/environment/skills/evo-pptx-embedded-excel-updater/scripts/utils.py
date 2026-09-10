"""
Utility functions for manipulating embedded Excel OLE objects in PPTX files.
Handles: OLE shape identification, Excel blob extraction, text box reading,
exchange rate parsing, Excel modification with formula preservation, and
blob replacement.
"""

import io
import re
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from openpyxl import load_workbook


def find_embedded_ole_excel_shapes(slide):
    """
    Find all embedded OLE Excel shapes on a slide.
    Returns list of (shape, ole_format) tuples where prog_id contains 'Excel'.
    """
    results = []
    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT:
            ole = shape.ole_format
            if 'Excel' in ole.prog_id:
                results.append((shape, ole))
    return results


def extract_excel_blob_from_ole_shape(shape, slide):
    """
    Extract the Excel binary blob from an OLE shape.
    Uses ole_format.blob for direct access.
    Also returns the relationship ID and target part for later replacement.
    
    Returns: (excel_bytes, r_id, target_part)
    """
    ole = shape.ole_format
    excel_blob = ole.blob
    
    # Get relationship ID for writing back
    ole_obj_list = shape._element.xpath('.//p:oleObj')
    r_id = None
    target_part = None
    if ole_obj_list:
        ole_obj = ole_obj_list[0]
        r_id = ole_obj.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        if r_id:
            target_part = slide.part.rels[r_id].target_part
    
    return excel_blob, r_id, target_part


def read_text_boxes_from_slide(slide):
    """
    Read all text boxes from a slide.
    Returns list of (shape_name, full_text) tuples.
    """
    text_boxes = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            text_boxes.append((shape.name, shape.text))
    return text_boxes


def parse_exchange_rate_from_text(text):
    """
    Parse an exchange rate update from text like:
    'Updated rate: \nUSD to CNY=7.02'
    
    Returns: (from_currency, to_currency, rate) or None if not found.
    The rate is returned as a float.
    """
    # Handle various formats: "XXX to YYY=value" or "XXX to YYY = value"
    # Text may contain newlines (\n or \x0b)
    clean_text = text.replace('\x0b', ' ').replace('\n', ' ')
    
    pattern = r'([A-Z]{3})\s+to\s+([A-Z]{3})\s*=\s*([\d.]+)'
    match = re.search(pattern, clean_text)
    if match:
        from_curr = match.group(1)
        to_curr = match.group(2)
        rate = float(match.group(3))
        return (from_curr, to_curr, rate)
    return None


def load_excel_from_blob(excel_bytes):
    """
    Load an openpyxl workbook from bytes, preserving formulas.
    Uses data_only=False to keep formula cells intact.
    
    Returns: (workbook, active_worksheet)
    """
    wb = load_workbook(io.BytesIO(excel_bytes), data_only=False)
    ws = wb.active
    return wb, ws


def find_cell_by_currency_pair(ws, from_currency, to_currency):
    """
    Find the cell coordinate for a currency pair in the exchange rate table.
    The table has:
    - Row 1: headers (Exchange Rate, currency1, currency2, ...)
    - Column A: row currency labels
    - Cell (row, col) = exchange rate from row_currency to col_currency
    
    Returns: cell coordinate string (e.g., 'B3') or None if not found.
    """
    # Find column index for to_currency (in row 1)
    col_idx = None
    for col in range(2, ws.max_column + 1):  # Start from column B
        if ws.cell(row=1, column=col).value == to_currency:
            col_idx = col
            break
    
    # Find row index for from_currency (in column A)
    row_idx = None
    for row in range(2, ws.max_row + 1):  # Start from row 2
        if ws.cell(row=row, column=1).value == from_currency:
            row_idx = row
            break
    
    if col_idx is not None and row_idx is not None:
        return ws.cell(row=row_idx, column=col_idx).coordinate
    return None


def update_excel_cell_preserve_formulas(ws, cell_coordinate, new_value):
    """
    Update a specific cell in the worksheet.
    Only updates if the cell is NOT a formula (safety check).
    Formula cells (starting with '=') are left untouched.
    
    Returns: (old_value, was_updated)
    """
    cell = ws[cell_coordinate]
    old_value = cell.value
    
    # Safety: don't overwrite formulas
    if isinstance(old_value, str) and old_value.startswith('='):
        return old_value, False
    
    cell.value = new_value
    return old_value, True


def save_excel_to_blob(wb):
    """
    Save an openpyxl workbook to bytes.
    Returns: bytes of the xlsx file.
    """
    out_stream = io.BytesIO()
    wb.save(out_stream)
    return out_stream.getvalue()


def replace_ole_blob_in_pptx(target_part, modified_excel_bytes):
    """
    Replace the embedded Excel blob in the PPTX part.
    This modifies the part in-place; call prs.save() afterward.
    """
    target_part._blob = modified_excel_bytes


def process_pptx_exchange_rate_update(input_path, output_path):
    """
    End-to-end function: reads a PPTX with an embedded Excel exchange rate table
    and a text box with an updated rate, updates the table, and saves.
    
    Steps:
    1. Open presentation
    2. Find embedded Excel OLE object
    3. Read text boxes to find updated exchange rate
    4. Extract Excel blob and load with openpyxl
    5. Find the cell for the currency pair
    6. Update the cell (preserve formulas)
    7. Save Excel blob back and save presentation
    """
    prs = Presentation(input_path)
    
    for slide in prs.slides:
        # Find Excel OLE shapes
        excel_shapes = find_embedded_ole_excel_shapes(slide)
        if not excel_shapes:
            continue
        
        # Read text boxes for updated rate
        text_boxes = read_text_boxes_from_slide(slide)
        rate_info = None
        for name, text in text_boxes:
            parsed = parse_exchange_rate_from_text(text)
            if parsed:
                rate_info = parsed
                print(f"Found update: {parsed[0]} to {parsed[1]} = {parsed[2]}")
                break
        
        if not rate_info:
            print("No exchange rate update found in text boxes")
            continue
        
        from_curr, to_curr, new_rate = rate_info
        
        # Process the first Excel shape found
        shape, ole = excel_shapes[0]
        excel_blob, r_id, target_part = extract_excel_blob_from_ole_shape(shape, slide)
        
        # Load Excel
        wb, ws = load_excel_from_blob(excel_blob)
        
        # Find the cell
        cell_coord = find_cell_by_currency_pair(ws, from_curr, to_curr)
        if not cell_coord:
            print(f"Could not find cell for {from_curr} to {to_curr}")
            continue
        
        # Update the cell
        old_val, was_updated = update_excel_cell_preserve_formulas(ws, cell_coord, new_rate)
        if was_updated:
            print(f"Updated {cell_coord}: {old_val} -> {new_rate}")
        else:
            print(f"Cell {cell_coord} contains a formula, skipping: {old_val}")
            continue
        
        # Save back
        modified_blob = save_excel_to_blob(wb)
        replace_ole_blob_in_pptx(target_part, modified_blob)
        
        # Save presentation
        prs.save(output_path)
        print(f"Saved to {output_path}")
        return True
    
    print("No updates performed")
    return False
