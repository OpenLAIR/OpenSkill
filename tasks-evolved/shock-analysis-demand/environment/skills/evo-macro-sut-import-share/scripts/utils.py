import openpyxl

SUPPLY_SHEET = 'SUPPLY (38-38)-2024'
USE_SHEET = 'USE (38-38)-2024'
SUPPLY_IMPORT_COL = 'AR'
SUPPLY_TOTAL_COL = 'AS'
USE_GFCF_COL = 'AT'
PROD_START = 4
PROD_END = 41
TOTAL_ROW = 42

def create_sut_calc_sheet(wb):
    if 'SUT Calc' in wb.sheetnames:
        del wb['SUT Calc']
    ws = wb.create_sheet('SUT Calc')
    ws['A1'] = 'SUT Calculation - Import Content Share'
    ws['A3'] = 'Code'
    ws['B3'] = 'Product'
    ws['C3'] = 'Total Supply (TotPP)'
    ws['D3'] = 'Imports (P7)'
    ws['E3'] = 'Import Share (mu_i)'
    ws['F3'] = 'GFCF (P51)'
    ws['G3'] = 'Imported GFCF'
    ws['H3'] = 'Product Share of GFCF'
    return ws

def link_sut_to_calc_sheet(ws):
    sn = f"'{SUPPLY_SHEET}'"
    un = f"'{USE_SHEET}'"
    for r in range(PROD_START, PROD_END+1):
        ws.cell(r,1).value = f"={sn}!A{r}"
        ws.cell(r,2).value = f"={sn}!B{r}"
        ws.cell(r,3).value = f"={sn}!{SUPPLY_TOTAL_COL}{r}"
        ws.cell(r,4).value = f"={sn}!{SUPPLY_IMPORT_COL}{r}"
        ws.cell(r,5).value = f'=IF(C{r}=0,0,D{r}/C{r})'
    ws.cell(TOTAL_ROW,1).value = 'Total'
    ws.cell(TOTAL_ROW,3).value = f'=SUM(C{PROD_START}:C{PROD_END})'
    ws.cell(TOTAL_ROW,4).value = f'=SUM(D{PROD_START}:D{PROD_END})'

def compute_import_shares(ws):
    un = f"'{USE_SHEET}'"
    for r in range(PROD_START, PROD_END+1):
        ws.cell(r,6).value = f"={un}!{USE_GFCF_COL}{r}"
        ws.cell(r,7).value = f'=E{r}*F{r}'
        ws.cell(r,8).value = f'=IF(F${TOTAL_ROW}=0,0,F{r}/F${TOTAL_ROW})'
    ws.cell(TOTAL_ROW,6).value = f'=SUM(F{PROD_START}:F{PROD_END})'
    ws.cell(TOTAL_ROW,7).value = f'=SUM(G{PROD_START}:G{PROD_END})'
    ws.cell(TOTAL_ROW,8).value = f'=SUM(H{PROD_START}:H{PROD_END})'

def calculate_import_content_share(ws):
    ws['A44'] = 'Import Content Share Calculation'
    ws['A46'] = 'Estimated Import Content Share (theta)'
    ws['C46'] = f'=G{TOTAL_ROW}/F{TOTAL_ROW}'
