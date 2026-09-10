import os, subprocess, zipfile, re
import xml.etree.ElementTree as ET
try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

def extract_text_pdf_pypdf2(filepath, max_pages=3):
    if not HAS_PYPDF2: return ""
    try:
        with open(filepath,'rb') as f:
            reader = PdfReader(f)
            parts = []
            for i in range(min(len(reader.pages), max_pages)):
                t = reader.pages[i].extract_text()
                if t: parts.append(t)
            return "\n".join(parts)
    except: return ""

def extract_text_pdftotext_cli(filepath, max_pages=3):
    try:
        r = subprocess.run(['pdftotext','-l',str(max_pages),filepath,'-'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,text=True)
        return r.stdout if r.returncode==0 else ""
    except: return ""

def extract_text_pdf_pdfplumber(filepath, max_pages=3):
    if not HAS_PDFPLUMBER: return ""
    try:
        with pdfplumber.open(filepath) as pdf:
            parts = []
            for i in range(min(len(pdf.pages), max_pages)):
                t = pdf.pages[i].extract_text()
                if t: parts.append(t)
            return "\n".join(parts)
    except: return ""

def extract_text_pdf(filepath, max_pages=3):
    text = extract_text_pdf_pypdf2(filepath, max_pages)
    if len(text.strip()) >= 50: return text
    text2 = extract_text_pdftotext_cli(filepath, max_pages)
    if len(text2.strip()) >= 50: return text2
    text3 = extract_text_pdf_pdfplumber(filepath, max_pages)
    if len(text3.strip()) > len(text.strip()): return text3
    return text if text else text2

def extract_text_docx(filepath):
    NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    try:
        with zipfile.ZipFile(filepath,'r') as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            parts = []
            for p in tree.iter(f'{NS}p'):
                texts = [n.text for n in p.iter(f'{NS}t') if n.text]
                if texts: parts.append(''.join(texts))
            return "\n".join(parts)
    except: return ""

def extract_text_pptx(filepath):
    NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    try:
        with zipfile.ZipFile(filepath,'r') as z:
            slides = [f for f in z.namelist() if re.match(r'^ppt/slides/slide\d+\.xml$',f)]
            slides.sort(key=lambda x: int(re.search(r'\d+',x.split('/')[-1]).group()))
            parts = []
            for sf in slides:
                tree = ET.fromstring(z.read(sf))
                txt = [n.text for n in tree.iter(f'{NS}t') if n.text]
                if txt: parts.append(' '.join(txt))
            return "\n".join(parts)
    except: return ""

def extract_text(filepath, max_pages=3):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf': return extract_text_pdf(filepath, max_pages)
    elif ext == '.docx': return extract_text_docx(filepath)
    elif ext == '.pptx': return extract_text_pptx(filepath)
    return ""
