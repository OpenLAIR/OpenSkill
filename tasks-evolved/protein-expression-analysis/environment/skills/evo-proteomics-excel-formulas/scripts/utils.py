"""
Utilities for populating Excel workbooks with proteomics formulas.
Writes Excel formulas AND caches computed values via XML patching.
"""
import statistics
import zipfile
import xml.etree.ElementTree as ET
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def load_workbook_preserving(filepath):
    return load_workbook(filepath, data_only=False, read_only=False)


def save_workbook_safely(wb, filepath):
    wb.save(filepath)


def classify_group_columns(ws_task, group_row=9, start_col=3, end_col=12):
    groups = {'Control': [], 'Treated': []}
    for c in range(start_col, end_col + 1):
        group = ws_task.cell(row=group_row, column=c).value
        if group and group.strip() in groups:
            groups[group.strip()].append(get_column_letter(c))
    return groups


def fill_expression_lookup_formulas(ws_task, data_max_row=201, data_max_col_letter='BA'):
    for row in range(11, 21):
        for col in range(3, 13):
            cl = get_column_letter(col)
            f = (f"=INDEX(Data!$D$2:${data_max_col_letter}${data_max_row},"
                 f"MATCH($A{row},Data!$A$2:$A${data_max_row},0),"
                 f"MATCH({cl}$10,Data!$D$1:${data_max_col_letter}$1,0))")
            ws_task.cell(row=row, column=col).value = f


def fill_group_stats_formulas(ws_task, groups):
    ctrl_cols = groups['Control']
    trt_cols = groups['Treated']
    for i in range(10):
        prow = 11 + i
        scol = 2 + i
        cr = ",".join([f"{c}{prow}" for c in ctrl_cols])
        tr = ",".join([f"{c}{prow}" for c in trt_cols])
        ws_task.cell(row=24, column=scol).value = f"=AVERAGE({cr})"
        ws_task.cell(row=25, column=scol).value = f"=_xlfn.STDEV.S({cr})"
        ws_task.cell(row=26, column=scol).value = f"=AVERAGE({tr})"
        ws_task.cell(row=27, column=scol).value = f"=_xlfn.STDEV.S({tr})"


def fill_fold_change_formulas(ws_task):
    for i in range(10):
        fc_row = 32 + i
        prow = 11 + i
        sl = get_column_letter(2 + i)
        ws_task.cell(row=fc_row, column=1).value = ws_task.cell(row=prow, column=1).value
        ws_task.cell(row=fc_row, column=2).value = ws_task.cell(row=prow, column=2).value
        ws_task.cell(row=fc_row, column=4).value = f"={sl}26-{sl}24"
        ws_task.cell(row=fc_row, column=3).value = f"=2^D{fc_row}"


def compute_and_patch_cached_values(filepath):
    """Compute values in Python and patch xlsx XML to add cached <v> elements."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    wb = load_workbook(filepath, data_only=False)
    ws_data = wb['Data']
    ws_task = wb['Task']

    # Build data indices
    scol = {}
    for c in range(4, ws_data.max_column + 1):
        n = ws_data.cell(row=1, column=c).value
        if n: scol[n] = c
    prow = {}
    for r in range(2, ws_data.max_row + 1):
        p = ws_data.cell(row=r, column=1).value
        if p: prow[p] = r

    samples = [ws_task.cell(row=10, column=c).value for c in range(3, 13)]
    proteins = [ws_task.cell(row=r, column=1).value for r in range(11, 21)]

    cache = {}  # cell_ref -> str_value
    expr_vals = []
    for pi, prot in enumerate(proteins):
        row_vals = []
        for si, samp in enumerate(samples):
            val = None
            if prot in prow and samp in scol:
                val = ws_data.cell(row=prow[prot], column=scol[samp]).value
            row_vals.append(val)
            if val is not None:
                cache[f"{get_column_letter(3+si)}{11+pi}"] = str(val)
        expr_vals.append(row_vals)

    # Group indices (C-G = 0-4 = Control, H-L = 5-9 = Treated)
    ctrl_idx = [0, 1, 2, 3, 4]
    trt_idx = [5, 6, 7, 8, 9]

    for i in range(10):
        vals = expr_vals[i]
        ctrl = [vals[j] for j in ctrl_idx if vals[j] is not None]
        trt = [vals[j] for j in trt_idx if vals[j] is not None]
        sl = get_column_letter(2 + i)
        if ctrl:
            cache[f"{sl}24"] = str(statistics.mean(ctrl))
        if len(ctrl) >= 2:
            cache[f"{sl}25"] = str(statistics.stdev(ctrl))
        if trt:
            cache[f"{sl}26"] = str(statistics.mean(trt))
        if len(trt) >= 2:
            cache[f"{sl}27"] = str(statistics.stdev(trt))
        if ctrl and trt:
            l2fc = statistics.mean(trt) - statistics.mean(ctrl)
            cache[f"D{32+i}"] = str(l2fc)
            cache[f"C{32+i}"] = str(2 ** l2fc)

    # Register XML namespaces
    ET.register_namespace('', ns)
    for p, u in [('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'),
                 ('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006'),
                 ('x14ac', 'http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac')]:
        ET.register_namespace(p, u)

    # Read zip contents
    with zipfile.ZipFile(filepath, 'r') as z:
        allfiles = {i.filename: z.read(i.filename) for i in z.infolist()}

    # Find Task sheet XML file
    wb_root = ET.fromstring(allfiles['xl/workbook.xml'])
    rns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    task_rid = None
    for s in wb_root.findall(f'.//{{{ns}}}sheet'):
        if s.get('name') == 'Task':
            task_rid = s.get(f'{{{rns}}}id')
            break

    pns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    ET.register_namespace('', pns)
    rels_root = ET.fromstring(allfiles['xl/_rels/workbook.xml.rels'])
    task_file = None
    for rel in rels_root.findall(f'{{{pns}}}Relationship'):
        if rel.get('Id') == task_rid:
            target = rel.get('Target')
            # Handle absolute paths (leading /) or relative paths
            if target.startswith('/'):
                task_file = target.lstrip('/')
            else:
                task_file = 'xl/' + target
            break

    if not task_file or task_file not in allfiles:
        print(f"ERROR: Task sheet file not found: {task_file}")
        return 0

    # Re-register main namespace after parsing rels
    ET.register_namespace('', ns)

    # Patch the XML
    root = ET.fromstring(allfiles[task_file])
    patched = 0
    for c_el in root.findall(f'.//{{{ns}}}c'):
        ref = c_el.get('r')
        if ref in cache:
            for v in c_el.findall(f'{{{ns}}}v'):
                c_el.remove(v)
            v = ET.SubElement(c_el, f'{{{ns}}}v')
            v.text = cache[ref]
            patched += 1

    allfiles[task_file] = ET.tostring(root, encoding='UTF-8', xml_declaration=True)

    # Write back
    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as z:
        for fn, data in allfiles.items():
            z.writestr(fn, data)

    return patched


def populate_proteomics_task(filepath):
    """Main: write formulas + cached values to Task sheet."""
    wb = load_workbook_preserving(filepath)
    ws_task = wb['Task']
    ws_data = wb['Data']
    dmr = ws_data.max_row
    dmcl = get_column_letter(ws_data.max_column)

    fill_expression_lookup_formulas(ws_task, dmr, dmcl)
    groups = classify_group_columns(ws_task)
    fill_group_stats_formulas(ws_task, groups)
    fill_fold_change_formulas(ws_task)
    save_workbook_safely(wb, filepath)
    print("Formulas written.")

    n = compute_and_patch_cached_values(filepath)
    print(f"Patched {n} cached values. Done!")
