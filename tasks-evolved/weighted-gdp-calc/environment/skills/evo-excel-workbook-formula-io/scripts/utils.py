from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict

from openpyxl import load_workbook
from openpyxl.workbook import Workbook


def load_editable_workbook(path: str) -> Workbook:
    return load_workbook(filename=path, read_only=False, data_only=False, keep_vba=False, keep_links=True)


def load_cached_workbook(path: str) -> Workbook:
    return load_workbook(filename=path, read_only=False, data_only=True, keep_vba=False, keep_links=True)


def verify_required_sheets(wb: Workbook, required_sheets: list[str]) -> None:
    missing = [s for s in required_sheets if s not in wb.sheetnames]
    if missing:
        raise ValueError(f"Workbook is missing critical sheets: {missing}")


def write_formula_block(ws, formula_map: Dict[str, str]) -> None:
    for cell_ref, formula in formula_map.items():
        if not isinstance(formula, str) or not formula.startswith('='):
            raise ValueError(f"Formula for {cell_ref} must start with '='")
        ws[cell_ref] = formula


def save_workbook(wb: Workbook, path: str) -> None:
    wb.save(path)


def _wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError('LibreOffice UNO listener did not start in time')


def _recalc_via_uno(file_path: str, port: int = 2002) -> bool:
    import uno
    from com.sun.star.beans import PropertyValue
    from com.sun.star.connection import NoConnectException

    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local_ctx)
    ctx = resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext')
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)

    in_props = []
    p_hidden = PropertyValue(); p_hidden.Name = 'Hidden'; p_hidden.Value = True; in_props.append(p_hidden)
    p_update = PropertyValue(); p_update.Name = 'UpdateDocMode'; p_update.Value = 1; in_props.append(p_update)

    url = uno.systemPathToFileUrl(str(Path(file_path).resolve()))
    doc = desktop.loadComponentFromURL(url, '_blank', 0, tuple(in_props))
    try:
        doc.calculateAll()
        if hasattr(doc, 'store'):
            doc.store()
        if hasattr(doc, 'storeSelf'):
            doc.storeSelf(())
    finally:
        doc.close(True)
    return True


def force_recalculate_libreoffice(file_path: str, out_dir: str | None = None) -> bool:
    soffice = shutil.which('libreoffice') or shutil.which('soffice')
    if not soffice:
        return False
    port = 2002
    proc = subprocess.Popen([
        soffice,
        '--headless',
        '--nologo',
        '--nodefault',
        '--nolockcheck',
        '--norestore',
        f'--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_for_port('127.0.0.1', port, timeout=20.0)
        try:
            return _recalc_via_uno(file_path, port=port)
        except Exception:
            pass
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    # fallback convert pass
    src = Path(file_path).resolve()
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        staged = tmpdir / src.name
        shutil.copy2(src, staged)
        subprocess.run([soffice, '--headless', '--nologo', '--convert-to', 'xlsx', '--outdir', str(tmpdir), str(staged)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        recalced = tmpdir / src.name
        if recalced.exists():
            shutil.copy2(recalced, src)
            return True
    return False


import re
import zipfile
import xml.etree.ElementTree as ET


def inject_formula_cached_values(xlsx_path: str, sheet_name: str, cell_value_map: dict[str, float]) -> None:
    src = Path(xlsx_path)
    ns = {
        'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'rel': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }
    with zipfile.ZipFile(src, 'r') as zin:
        wb_xml = ET.fromstring(zin.read('xl/workbook.xml'))
        rels_xml = ET.fromstring(zin.read('xl/_rels/workbook.xml.rels'))
        sheet_rid = None
        for s in wb_xml.find('main:sheets', ns):
            if s.attrib.get('name') == sheet_name:
                sheet_rid = s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                break
        if sheet_rid is None:
            raise ValueError(f'Sheet not found: {sheet_name}')
        target = None
        for rel in rels_xml:
            if rel.attrib.get('Id') == sheet_rid:
                target = rel.attrib.get('Target')
                break
        if target is None:
            raise ValueError(f'Sheet rel target not found for: {sheet_name}')
        sheet_path = 'xl/' + target.lstrip('/') if not target.startswith('xl/') else target
        sheet_xml = ET.fromstring(zin.read(sheet_path))
        archive = {name: zin.read(name) for name in zin.namelist()}
    for c in sheet_xml.findall('.//main:c', ns):
        ref = c.attrib.get('r')
        if ref in cell_value_map:
            v = c.find('main:v', ns)
            if v is None:
                v = ET.SubElement(c, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
            v.text = repr(float(cell_value_map[ref]))
    archive[sheet_path] = ET.tostring(sheet_xml, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(src, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in archive.items():
            zout.writestr(name, data)


def patch_sheet_formula_text_and_cached_values(xlsx_path: str, sheet_name: str, formula_text_map: dict[str, str], cell_value_map: dict[str, float]) -> None:
    src = Path(xlsx_path)
    ns = {
        'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'rel': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }
    with zipfile.ZipFile(src, 'r') as zin:
        wb_xml = ET.fromstring(zin.read('xl/workbook.xml'))
        rels_xml = ET.fromstring(zin.read('xl/_rels/workbook.xml.rels'))
        sheet_rid = None
        for s in wb_xml.find('main:sheets', ns):
            if s.attrib.get('name') == sheet_name:
                sheet_rid = s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                break
        if sheet_rid is None:
            raise ValueError(f'Sheet not found: {sheet_name}')
        target = None
        for rel in rels_xml:
            if rel.attrib.get('Id') == sheet_rid:
                target = rel.attrib.get('Target')
                break
        if target is None:
            raise ValueError(f'Sheet rel target not found for: {sheet_name}')
        sheet_path = 'xl/' + target.lstrip('/') if not target.startswith('xl/') else target
        sheet_xml = ET.fromstring(zin.read(sheet_path))
        archive = {name: zin.read(name) for name in zin.namelist()}
    for c in sheet_xml.findall('.//main:c', ns):
        ref = c.attrib.get('r')
        if ref in formula_text_map:
            f = c.find('main:f', ns)
            if f is None:
                f = ET.SubElement(c, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f')
            formula = formula_text_map[ref]
            if formula.startswith('='):
                formula = formula[1:]
            f.text = formula
        if ref in cell_value_map:
            v = c.find('main:v', ns)
            if v is None:
                v = ET.SubElement(c, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
            v.text = str(cell_value_map[ref])
    archive[sheet_path] = ET.tostring(sheet_xml, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(src, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in archive.items():
            zout.writestr(name, data)
