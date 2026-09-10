import sys
import subprocess
import importlib
import os
from pathlib import Path

def ensure_dependencies(required_packages: dict):
    """Install missing Python packages at runtime, handling PEP 668 on Ubuntu 24.04."""
    for import_name, pip_name in required_packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"[WARNING] '{import_name}' not found. Installing '{pip_name}'...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", pip_name,
                    "--break-system-packages", "--quiet"
                ])
                importlib.invalidate_caches()
                print(f"[SUCCESS] Installed {pip_name}.")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Failed to install {pip_name}: {e}")

def discover_files(root_dir: str) -> list:
    """Recursively scan directory and return list of Path objects for all files."""
    discovered = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            discovered.append(Path(dirpath) / fn)
    return discovered

def safe_read_text(filepath: Path) -> str:
    """Read text file with encoding fallback."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            import charset_normalizer
            results = charset_normalizer.from_path(filepath)
            best = results.best()
            if best:
                return str(best)
        except Exception:
            pass
        try:
            with open(filepath, 'r', encoding='cp1252', errors='replace') as f:
                return f.read()
        except Exception:
            return ""
    except Exception:
        return ""

def extract_text_from_pdf(filepath: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    import fitz
    text_parts = []
    try:
        doc = fitz.open(filepath)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_parts.append(page.get_text("text"))
        doc.close()
    except Exception as e:
        print(f"[ERROR] PDF {filepath}: {e}")
    return "\n\n".join(text_parts)

def extract_text_from_docx(filepath: Path) -> str:
    """Extract text from DOCX including headers, footers, tables."""
    from docx import Document
    parts = []
    try:
        doc = Document(filepath)
        for section in doc.sections:
            for p in section.header.paragraphs:
                if p.text.strip():
                    parts.append(p.text.strip())
            for p in section.footer.paragraphs:
                if p.text.strip():
                    parts.append(p.text.strip())
        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_data = [c.text.strip().replace("\n", " ") for c in row.cells if c.text.strip()]
                if row_data:
                    parts.append(" | ".join(row_data))
    except Exception as e:
        print(f"[ERROR] DOCX {filepath}: {e}")
    return "\n".join(parts)

def extract_text_from_xlsx(filepath: Path) -> str:
    """Extract text from XLSX handling merged cells."""
    import openpyxl
    from openpyxl.utils import range_boundaries
    parts = []
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=False)
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            parts.append(f"--- Sheet: {sheet_name} ---")
            for row in sheet.iter_rows():
                row_data = []
                for cell in row:
                    val = ""
                    if cell.value is not None:
                        val = str(cell.value)
                    else:
                        for mr in sheet.merged_cells.ranges:
                            if cell.coordinate in mr:
                                min_col, min_row, _, _ = range_boundaries(mr.coord)
                                anchor = sheet.cell(row=min_row, column=min_col).value
                                val = str(anchor) if anchor else ""
                                break
                    if val.strip():
                        row_data.append(val.strip())
                if row_data:
                    parts.append(" | ".join(row_data))
        wb.close()
    except Exception as e:
        print(f"[ERROR] XLSX {filepath}: {e}")
    return "\n".join(parts)

def extract_text_from_pptx(filepath: Path) -> str:
    """Extract text from PPTX including presenter notes."""
    from pptx import Presentation
    parts = []
    try:
        prs = Presentation(filepath)
        for i, slide in enumerate(prs.slides):
            parts.append(f"--- Slide {i+1} ---")
            for shape in slide.shapes:
                if shape.has_text_frame and shape.text.strip():
                    parts.append(shape.text.strip())
            if slide.has_notes_slide:
                ns = slide.notes_slide
                if ns.notes_text_frame and ns.notes_text_frame.text.strip():
                    parts.append(f"[Notes]: {ns.notes_text_frame.text.strip()}")
    except Exception as e:
        print(f"[ERROR] PPTX {filepath}: {e}")
    return "\n".join(parts)

def process_file(filepath: Path) -> dict:
    """Route file to appropriate extractor based on extension."""
    result = {
        "filepath": str(filepath),
        "filename": filepath.name,
        "extension": filepath.suffix.lower(),
        "content": "",
        "error": None
    }
    ext = result["extension"]
    try:
        if ext == '.pdf':
            result["content"] = extract_text_from_pdf(filepath)
        elif ext == '.docx':
            result["content"] = extract_text_from_docx(filepath)
        elif ext in ('.xlsx', '.xls'):
            result["content"] = extract_text_from_xlsx(filepath)
        elif ext == '.pptx':
            result["content"] = extract_text_from_pptx(filepath)
        elif ext in ('.json', '.txt', '.csv', '.md', '.html', '.htm', '.xml', '.yaml', '.yml'):
            result["content"] = safe_read_text(filepath)
        else:
            # Try reading as text
            result["content"] = safe_read_text(filepath)
    except Exception as e:
        result["error"] = str(e)
    return result

def extract_all_documents(root_dir: str) -> list:
    """Discover and extract text from all files in directory."""
    files = discover_files(root_dir)
    results = []
    for f in files:
        doc = process_file(f)
        results.append(doc)
    return results
