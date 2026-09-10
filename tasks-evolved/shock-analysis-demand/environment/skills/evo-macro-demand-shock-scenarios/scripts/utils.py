import openpyxl
import subprocess, os, time

BELL_SHAPE = [0.02, 0.07, 0.15, 0.22, 0.24, 0.18, 0.09, 0.03]
TOTAL_INVESTMENT = 6.5
EXCHANGE_RATE = 2.746
PROJECT_START = 2026
PROJECT_YEARS = 8

def setup_na_assumptions(ws, ar, multiplier=0.8, ics_formula="='SUT Calc'!C46"):
    ws.cell(ar, 3).value = 'Assumptions'
    ws.cell(ar+2, 3).value = 'total investment'
    ws.cell(ar+2, 4).value = TOTAL_INVESTMENT
    ws.cell(ar+3, 3).value = 'import content share'
    ws.cell(ar+3, 4).value = ics_formula
    ws.cell(ar+4, 3).value = 'demand multiplier'
    ws.cell(ar+4, 4).value = multiplier
    ws.cell(ar+5, 3).value = 'Project allocation'
    ws.cell(ar+5, 4).value = 'bell shape'

def build_scenario_table(ws, hdr, ds, ar):
    inv = f'$D${ar+2}'
    ics = f'$D${ar+3}'
    mlt = f'$D${ar+4}'
    ex = EXCHANGE_RATE
    ws.cell(hdr, 2).value = 'Year'
    ws.cell(hdr, 3).value = 'Real GDP'
    ws.cell(hdr, 4).value = 'Project Allocation (%)'
    ws.cell(hdr, 5).value = 'Project Investment'
    ws.cell(hdr, 6).value = 'Imports'
    ws.cell(hdr, 7).value = 'GDP impact'
    ws.cell(hdr, 10).value = 'Baseline GDP Growth'
    ws.cell(hdr, 11).value = 'Projected Growth'
    ws.cell(hdr+1, 7).value = 'I-M'
    ws.cell(hdr+1, 8).value = 'Multiplier'
    ws.cell(hdr+1, 9).value = '% of GDP'
    ws.merge_cells(start_row=hdr, start_column=7, end_row=hdr, end_column=9)
    for i, year in enumerate(range(2020, 2043)):
        r = ds + i
        weo_r = year - 2020 + 2
        ws.cell(r, 2).value = year
        ws.cell(r, 3).value = f"='WEO_Data'!B{weo_r}"
        ws.cell(r, 10).value = f"='WEO_Data'!C{weo_r}"
        pidx = year - PROJECT_START
        if 0 <= pidx < PROJECT_YEARS:
            ws.cell(r, 4).value = BELL_SHAPE[pidx]
            defl = f"'WEO_Data'!D{weo_r}"
            ws.cell(r, 5).value = f'={inv}*D{r}*{ex}'
            ws.cell(r, 6).value = f'=(E{r}/({defl}/100))*{ics}'
            ws.cell(r, 7).value = f'=(E{r}/({defl}/100))*(1-{ics})'
            ws.cell(r, 8).value = f'=G{r}*{mlt}'
            ws.cell(r, 9).value = f'=H{r}/C{r}*100'
            ws.cell(r, 11).value = f'=J{r}+I{r}'
        else:
            ws.cell(r, 11).value = f'=J{r}'

def create_scenario_tables(wb):
    ws = wb['NA']
    # Scenario 1: existing layout
    build_scenario_table(ws, hdr=1, ds=3, ar=28)
    setup_na_assumptions(ws, ar=28, multiplier=0.8, ics_formula="='SUT Calc'!C46")
    # Scenario 2: multiplier=1.0
    gap = 2
    s2_hdr = 36
    s2_ds = 38
    s2_ar = 63
    ws.cell(s2_hdr-1, 2).value = 'Scenario 2: Demand Multiplier = 1.0'
    build_scenario_table(ws, hdr=s2_hdr, ds=s2_ds, ar=s2_ar)
    setup_na_assumptions(ws, ar=s2_ar, multiplier=1.0, ics_formula="='SUT Calc'!C46")
    # Scenario 3: import share=0.5
    s3_hdr = 71
    s3_ds = 73
    s3_ar = 98
    ws.cell(s3_hdr-1, 2).value = 'Scenario 3: Import Content Share = 0.5'
    build_scenario_table(ws, hdr=s3_hdr, ds=s3_ds, ar=s3_ar)
    setup_na_assumptions(ws, ar=s3_ar, multiplier=0.8, ics_formula=0.5)

def recalculate_workbook(filepath):
    subprocess.run(['pkill', '-f', 'soffice'], capture_output=True)
    time.sleep(1)
    ap = os.path.abspath(filepath)
    md = os.path.expanduser('~/.config/libreoffice/4/user/basic/Standard/')
    os.makedirs(md, exist_ok=True)
    with open(os.path.join(md, 'Module1.xba'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">\nSub RecalcAndSave(sPath As String)\n    Dim oDoc As Object\n    Dim props(0) As New com.sun.star.beans.PropertyValue\n    props(0).Name = "Hidden"\n    props(0).Value = True\n    oDoc = StarDesktop.loadComponentFromURL(ConvertToURL(sPath), "_blank", 0, props())\n    If Not IsNull(oDoc) Then\n        oDoc.calculateAll()\n        oDoc.store()\n        oDoc.close(True)\n    End If\nEnd Sub\n</script:module>')
    with open(os.path.join(md, 'script.xlc'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<library:library xmlns:library="http://openoffice.org/2000/library" library:name="Standard" library:readonly="false" library:passwordprotected="false">\n<library:element library:name="Module1"/>\n</library:library>')
    with open(os.path.join(md, 'dialog.xlc'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<library:library xmlns:library="http://openoffice.org/2000/library" library:name="Standard" library:readonly="false" library:passwordprotected="false"/>')
    return subprocess.run(['libreoffice','--headless','--norestore','--calc',f'macro:///Standard.Module1.RecalcAndSave({ap})'], capture_output=True, text=True, timeout=60)
