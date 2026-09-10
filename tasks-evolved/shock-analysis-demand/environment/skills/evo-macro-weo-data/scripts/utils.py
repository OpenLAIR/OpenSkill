"""
evo-macro-weo-data utility functions
Populates WEO_Data sheet, extends projections, copies SUT sheets.
"""
import openpyxl
import csv
import copy
from openpyxl.utils import get_column_letter


def populate_weo_data(wb, csv_path='/root/data/weo_georgia.csv'):
    """
    Create and populate WEO_Data sheet from the IMF WEO CSV file.
    CSV columns: Year, Real GDP (bn Lari), Real GDP Growth (%), GDP Deflator
    WEO_Data sheet layout:
      Row 1: headers
      Row 2+: data for years 2020-2043
      Col A: Year
      Col B: Real GDP (bn Lari) - NGDP_R
      Col C: Real GDP Growth (%) - NGDP_RPCH  
      Col D: GDP Deflator - NGDP_D
    """
    # Create or get WEO_Data sheet
    if 'WEO_Data' in wb.sheetnames:
        ws = wb['WEO_Data']
    else:
        ws = wb.create_sheet('WEO_Data', 0)
    
    # Read CSV data
    data = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    
    # Headers
    ws['A1'] = 'Year'
    ws['B1'] = 'Real GDP (bn Lari)'
    ws['C1'] = 'Real GDP Growth (%)'
    ws['D1'] = 'GDP Deflator'
    
    # Populate from CSV (2020-2027, rows 2-9)
    for i, row in enumerate(data):
        r = i + 2  # Excel row
        ws.cell(r, 1, int(row['Year']))
        ws.cell(r, 2, float(row['Real GDP (bn Lari)']))
        ws.cell(r, 3, float(row['Real GDP Growth (%)']))
        ws.cell(r, 4, float(row['GDP Deflator']))
    
    # The CSV has 8 rows (2020-2027), so last CSV row is row 9
    # Now extend years 2028-2043 (rows 10-25)
    last_csv_row = len(data) + 1  # row 9 for 2027
    
    for year in range(2028, 2044):
        r = year - 2020 + 2  # row number
        ws.cell(r, 1, year)
    
    return ws, last_csv_row


def extend_real_gdp_projection(ws, last_csv_row):
    """
    Extend Real GDP from 2028 to 2043 using 2027 growth rate (held constant).
    2027 growth rate is in the last CSV row (row 9), col C.
    For 2028+: Real GDP = prev * (1 + growth_rate/100)
    Growth rate stays at 2027 value (5.0%) for all future years.
    """
    # Row 9 = 2027 (last CSV data)
    # Growth rate for 2028+ = same as 2027 = cell C9
    # Real GDP growth: C10 onwards = C9 (constant)
    # Real GDP: B10 = B9 * (1 + C10/100)
    
    for r in range(last_csv_row + 1, 26):  # rows 10-25 (2028-2043)
        # Growth rate = same as 2027 (row 9, col C)
        ws.cell(r, 3).value = f'=C{last_csv_row}'
        # Real GDP = previous year * (1 + growth/100)
        ws.cell(r, 2).value = f'=B{r-1}*(1+C{r}/100)'


def extend_deflator_projection(ws, last_csv_row):
    """
    Extend GDP Deflator using average growth rate of recent 4 years.
    Recent 4 years from WEO data: the last 4 years of actual/projected data.
    With data 2020-2027 (rows 2-9), the last 4 deflator growth rates are:
    2024/2023, 2025/2024, 2026/2025, 2027/2026 -> rows 7,8,9 relative to 6,7,8
    
    Average deflator growth = average of (D_t/D_{t-1} - 1) for last 4 years
    = AVERAGE(D6/D5-1, D7/D6-1, D8/D7-1, D9/D8-1)
    where rows 6-9 = years 2024-2027, rows 5-8 = years 2023-2026
    
    Then for 2028+: D_t = D_{t-1} * (1 + avg_growth)
    """
    # The 4 most recent deflator growth rates use the last 4 pairs
    # With rows 2-9 for 2020-2027:
    # Growth rates: D3/D2-1 (2021), D4/D3-1 (2022), ..., D9/D8-1 (2027)
    # Last 4: D6/D5-1 (2024), D7/D6-1 (2025), D8/D7-1 (2026), D9/D8-1 (2027)
    # That's rows 6,7,8,9 vs 5,6,7,8
    
    # We'll put the average deflator growth formula in a helper cell
    # or compute it inline. Let's use inline in each deflator extension.
    
    # avg_growth formula: AVERAGE(D6/D5-1, D7/D6-1, D8/D7-1, D9/D8-1)
    lr = last_csv_row  # 9
    avg_formula = f'AVERAGE(D{lr-3}/D{lr-4}-1,D{lr-2}/D{lr-3}-1,D{lr-1}/D{lr-2}-1,D{lr}/D{lr-1}-1)'
    
    for r in range(last_csv_row + 1, 26):  # rows 10-25 (2028-2043)
        ws.cell(r, 4).value = f'=D{r-1}*(1+{avg_formula})'


def copy_sut_sheets(wb, sut_path='/root/data/geostat_sut_2024.xlsx'):
    """
    Copy SUPPLY and USE sheets from GeoStat SUT file into the workbook.
    Keep original sheet names unchanged.
    """
    sut_wb = openpyxl.load_workbook(sut_path, data_only=True)
    
    for sheet_name in sut_wb.sheetnames:
        # Create new sheet in target workbook
        if sheet_name in wb.sheetnames:
            del wb[sheet_name]
        
        src_ws = sut_wb[sheet_name]
        dst_ws = wb.create_sheet(sheet_name)
        
        # Copy all cell values and basic formatting
        for row in src_ws.iter_rows(min_row=1, max_row=src_ws.max_row,
                                     min_col=1, max_col=src_ws.max_column):
            for cell in row:
                new_cell = dst_ws.cell(row=cell.row, column=cell.column,
                                       value=cell.value)
                # Copy number format
                if cell.number_format:
                    new_cell.number_format = cell.number_format
        
        # Copy merged cells
        for merged_range in src_ws.merged_cells.ranges:
            dst_ws.merge_cells(str(merged_range))
        
        # Copy column widths
        for col_letter, dim in src_ws.column_dimensions.items():
            dst_ws.column_dimensions[col_letter].width = dim.width
    
    sut_wb.close()
    return wb
