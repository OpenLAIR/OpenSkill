"""
Utilities for exploring and extracting data from complex, multi-sheet Excel workbooks.
"""
import openpyxl

def get_real_value(sheet, cell):
    """Returns cell value, handling merged cells."""
    if cell.value is not None:
        return cell.value
    for merged_range in sheet.merged_cells.ranges:
        if cell.coordinate in merged_range:
            return sheet[merged_range.start_cell.coordinate].value
    return None

def normalize_country_name(desc):
    """Extract and normalize country name from column description."""
    if not desc or not isinstance(desc, str):
        return None
    name = desc.split(':')[0].strip()
    # Normalize known variants
    norm_map = {
        'Kyrgyz Rep': 'Kyrgyz Republic',
        'Czechia International Reserves': 'Czechia',
        'Czechia Intl Reserves': 'Czechia',
        'Czechia International Reserves (EOP, NSA, Mil.US$)': 'Czechia',
    }
    if name in norm_map:
        return norm_map[name]
    # Handle any Czechia variant
    if name.startswith('Czechia'):
        return 'Czechia'
    return name

def extract_gold_price_series(filepath, sheet_name='Sheet1'):
    """Extract gold price time series from IMF commodity prices file.
    Returns list of (date_str, price) tuples."""
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb[sheet_name]
    gold_col = None
    for cell in ws[1]:
        if cell.value == 'PGOLD':
            gold_col = cell.column
            break
    if gold_col is None:
        wb.close()
        raise ValueError("PGOLD column not found")
    series = []
    for r in range(5, ws.max_row + 1):
        date_str = ws.cell(row=r, column=1).value
        price = ws.cell(row=r, column=gold_col).value
        if date_str is not None:
            series.append((date_str, price))
    wb.close()
    return series

def extract_country_reserve_data(filepath, sheet_name, year_row=18):
    """Extract country gold reserve data from Value or Volume sheet.
    Returns dict: {normalized_country: {value, col, desc, has_2025, data_type, raw_name}}"""
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb[sheet_name]
    countries = {}
    for col in range(3, ws.max_column + 1):
        desc = ws.cell(row=1, column=col).value
        if desc is None:
            continue
        raw_name = desc.split(':')[0].strip()
        country_name = normalize_country_name(desc)
        data_type = ws.cell(row=7, column=col).value
        val_2025 = ws.cell(row=year_row, column=col).value
        has_2025 = val_2025 is not None and str(val_2025) != '#N/A' and val_2025 != ''
        countries[country_name] = {
            'value': val_2025 if has_2025 else None,
            'col': col,
            'desc': desc,
            'has_2025': has_2025,
            'data_type': data_type,
            'raw_name': raw_name
        }
    wb.close()
    return countries

def extract_total_reserves_data(filepath, year_row=18):
    """Extract total reserves for 2025 from Total Reserves sheet."""
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb['Total Reserves']
    countries = {}
    for col in range(3, ws.max_column + 1):
        desc = ws.cell(row=1, column=col).value
        if desc is None:
            continue
        country_name = normalize_country_name(desc)
        data_type = ws.cell(row=7, column=col).value
        val_2025 = ws.cell(row=year_row, column=col).value
        has_2025 = val_2025 is not None and str(val_2025) != '#N/A' and val_2025 != ''
        countries[country_name] = {
            'value': val_2025 if has_2025 else None,
            'col': col,
            'col_letter': openpyxl.utils.get_column_letter(col),
            'desc': desc,
            'data_type': data_type,
            'has_2025': has_2025
        }
    wb.close()
    return countries

def compute_jan_sep_avg_gold_price(gold_series):
    """Compute Jan-Sep 2025 average gold price for volume-to-value conversion."""
    prices = []
    for date_str, price in gold_series:
        if date_str and '2025' in str(date_str) and price is not None:
            # Extract month number
            month_part = str(date_str).split('M')[1] if 'M' in str(date_str) else None
            if month_part and int(month_part) <= 9:
                prices.append(price)
    if prices:
        return sum(prices) / len(prices)
    return None

