# Domain Reference for evo-enterprise-doc-parser

**Responsibility**: File discovery, binary/text classification, format-specific text extraction (PDF, DOCX, XLSX, PPTX, TXT/CSV/JSON), encoding handling, and runtime dependency installation for Ubuntu 24.04 environments.

**Key functions to implement**: ensure_dependencies, discover_files, extract_text_from_pdf, extract_text_from_docx, extract_text_from_xlsx, extract_text_from_pptx, safe_read_text, process_file, extract_all_documents

---

## 1. Runtime Environment and Dependency Management


Deploying enterprise automation scripts often involves heterogeneous environments, such as Docker containers based on stripped-down operating systems. A common scenario involves executing a Python script in a bare-bones Ubuntu 24.04 container equipped only with `python3` and `python3-pip`.

### 1.1 The PEP 668 Challenge in Ubuntu 24.04

In modern Linux distributions like Ubuntu 24.04, executing a standard `pip install` command outside of a virtual environment triggers an `externally-managed-environment` error [cite: 1, 2]. This behavior is a direct implementation of PEP 668, which aims to prevent conflicts between the OS-level package manager (APT) and Python's package manager (pip) [cite: 1, 3]. When a script attempts to install a package globally, the system throws an error and advises the user to utilize `apt`, `pipx`, or a virtual environment (`venv`) [cite: 2, 4].

### 1.2 Programmatic Runtime Installation

While creating a virtual environment is the recommended standard practice [cite: 5], certain dynamic containerized workflows demand the ability to install dependencies at runtime directly within the script. The officially recommended method for calling `pip` programmatically is via the `subprocess` module, explicitly using `sys.executable` to ensure the package is installed in the current runtime context [cite: 6, 7]. 

To bypass the `externally-managed-environment` restriction in Ubuntu 24.04 programmatically, the `--break-system-packages` flag must be appended to the pip command [cite: 1, 2]. Below is a robust utility function designed to check for required libraries and install them at runtime.

```python
import sys
import subprocess
import importlib

def ensure_dependencies(required_packages: dict):
    """
    Ensures that required libraries are installed. If missing, it installs them
    using subprocess and the current python executable, bypassing PEP 668 
    restrictions common in Ubuntu 24.04 environments.
    
    Args:
        required_packages (dict): A dictionary mapping the import name to the pip package name.
                                  Example: {'fitz': 'pymupdf', 'docx': 'python-docx'}
    """
    for import_name, pip_name in required_packages.items():
        try:
            importlib.import_module(import_name)
            print(f"[INFO] '{import_name}' is already installed.")
        except ImportError:
            print(f"[WARNING] '{import_name}' not found. Installing '{pip_name}'...")
            try:
                # The --break-system-packages flag is required for Ubuntu 24.04
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", pip_name, 
                    "--break-system-packages", "--user"
                ])
                # Invalidate import caches to allow immediate use of the module
                importlib.invalidate_caches()
                print(f"[SUCCESS] Installed {pip_name} successfully.")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Failed to install {pip_name}. Error: {e}")
                sys.exit(1)

## 2. File Discovery and Binary/Text Classification


Once dependencies are verified, the next architectural step is scanning the target directory (e.g., `/root/DATA`) recursively. A common challenge during file discovery is distinguishing between plaintext files (CSV, JSON, TXT, Markdown, HTML) and binary files (PDF, DOCX, XLSX, PPTX, corrupted binaries, or executables) while correctly handling encoding anomalies [cite: 10].

### 2.1 File Discovery Implementation

The standard library `os.walk` is the optimal tool for recursive directory traversal. 

```python
import os
from pathlib import Path

def discover_files(root_dir: str) -> list:
    """
    Recursively scans a directory and returns a list of Path objects for all files.
    """
    discovered_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            discovered_files.append(Path(dirpath) / filename)
    return discovered_files
```

### 2.2 Text vs. Binary Detection

Attempting to open a binary file as text using `utf-8` decoding will result in a `UnicodeDecodeError` [cite: 11]. A naive approach is to check the file extension; however, extensions can be misleading or absent. 

A reliable heuristic for distinguishing binary from text involves reading a small chunk of the file (e.g., the first 512 or 1024 bytes) and searching for null bytes (`\x00`) or calculating the percentage of non-printable ASCII characters [cite: 10, 12]. If a null byte is encountered, or if more than 30% of the buffer consists of non-text characters, the file is highly likely to be binary [cite: 10, 12].

Alternatively, the `binaryornot` Python library offers a robust, zero-dependency decision tree model that considers byte ratios, Shannon entropy, and byte-order marks (BOM) to correctly classify edge cases like UTF-16 files (which contain null bytes but are text) [cite: 13, 14].

```python
from binaryornot.check import is_binary

def classify_file(filepath: Path) -> str:
    """
    Classifies a file as 'binary' or 'text' using the binaryornot library.
    """
    try:
        if is_binary(str(filepath)):
            return "binary"
        return "text"
    except Exception as e:
        print(f"[ERROR] Could not classify {filepath}: {e}")
        return "unknown"
```

### 2.3 Handling File Encodings

When a file is determined to be text, parsing it requires identifying its character encoding. Python defaults to UTF-8 on most modern systems [cite: 15], but legacy enterprise files often employ `cp1252` (Windows-1252) or `latin-1` (ISO-8859-1) [cite: 15, 16]. Attempting to parse `cp1252` text with a `utf-8` decoder results in `UnicodeDecodeError` or "mojibake" (garbled text) [cite: 15]. 

To build a resilient reader, one should attempt to decode using UTF-8 first, and fall back to advanced heuristics. The `charset_normalizer` library provides a modern alternative to the older `chardet` module, utilizing heuristics and linguistic detection to accurately infer the encoding without needing to map weights across all tables [cite: 17, 18].

```python
import charset_normalizer

def safe_read_text(filepath: Path) -> str:
    """
    Reads a text file safely, handling unknown encodings using charset_normalizer.
    """
    try:
        # Fast path: Try standard UTF-8
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Slow path: Detect encoding
        try:
            results = charset_normalizer.from_path(filepath)
            best_guess = results.best()
            if best_guess:
                return str(best_guess)
            else:
                # Fallback to cp1252 with replacement for unmappable characters
                with open(filepath, 'r', encoding='cp1252', errors='replace') as f:
                    return f.read()
        except Exception as e:
            print(f"[ERROR] Encoding detection failed for {filepath}: {e}")
            return ""
```

## 3. Parsing and Reading Diverse File Formats


Enterprise directories contain a mix of structured and unstructured binaries. Each requires specific libraries, import paths, and extraction methodologies.

### 3.1 PDF Files: PyPDF2 vs. pdfplumber vs. pymupdf

PDF extraction in Python has evolved significantly. 

*   **PyPDF2**: Historically the most common library, PyPDF2 has undergone massive API changes. In version 3.0.0 (released December 2022), the deprecated classes `PdfFileReader` and `PdfFileWriter` were completely removed, breaking older codebases [cite: 19, 20, 21]. The modern API utilizes `PdfReader` and `PdfWriter` [cite: 22]. It is lightweight and pure Python, but often struggles with complex layouts and embedded fonts.
*   **pdfplumber**: Built on top of `pdfminer.six`, `pdfplumber` excels at extracting tabular data and maintaining bounding box coordinates. However, it is significantly slower than its C-based counterparts.
*   **PyMuPDF (fitz)**: Currently the highly recommended industry standard. It is a Python binding for the C++ MuPDF library. It boasts blistering speed (often orders of magnitude faster than PyPDF2) and superior text layout retention [cite: 23].

**Implementation Pattern using PyMuPDF (fitz)**
```python
import fitz  # PyMuPDF correct import path

def extract_text_from_pdf(filepath: Path) -> str:
    """
    Extracts text from a PDF document using PyMuPDF.
    """
    text_content = []
    try:
        # Open the document
        doc = fitz.open(filepath)
        # Iterate over pages
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_content.append(page.get_text("text"))
        doc.close()
        return "\n\n".join(text_content)
    except fitz.FileDataError:
        print(f"[ERROR] PDF is corrupted or password protected: {filepath}")
        return ""
    except Exception as e:
        print(f"[ERROR] Failed to read PDF {filepath}: {e}")
        return ""
```

**Implementation Pattern using Modern PyPDF2 (Fallback)**
```python
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

def extract_text_pypdf2(filepath: Path) -> str:
    """
    Extracts text using the modern PyPDF2 API (v3.0.0+).
    """
    text_content = []
    try:
        reader = PdfReader(str(filepath))
        if reader.is_encrypted:
            print(f"[WARNING] {filepath} is encrypted.")
            # Attempt to decrypt with empty password
            reader.decrypt('')
            
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_content.append(text)
        return "\n".join(text_content)
    except PdfReadError:
        print(f"[ERROR] Corrupted PDF file: {filepath}")
        return ""
```

### 3.2 DOCX Files: Extracting Paragraphs, Tables, Headers, and Footers

Microsoft Word documents (`.docx`) are XML archives. The `python-docx` library allows programmatic reading [cite: 24, 25]. A robust extraction pipeline must traverse the document's body paragraphs, any embedded tables [cite: 24, 25], and critically, the headers and footers that often contain important metadata such as author, confidentiality level, or document IDs [cite: 26, 27].

Headers and footers are tied to `sections` in the document. An extraction script must iterate through `document.sections`, accessing `section.header` and `section.footer` [cite: 26, 27]. 

```python
from docx import Document

def extract_text_from_docx(filepath: Path) -> str:
    """
    Extracts text from paragraphs, tables, headers, and footers of a DOCX file.
    """
    text_content = []
    try:
        doc = Document(filepath)
        
        # 1. Extract Headers and Footers
        for section in doc.sections:
            # Header
            header = section.header
            for paragraph in header.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())
            # Footer
            footer = section.footer
            for paragraph in footer.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())

        # 2. Extract Document Paragraphs
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text.strip())
                
        # 3. Extract Tables
        for table in doc.tables:
            for row in table.rows:
                row_data = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_data.append(cell.text.strip().replace("\n", " "))
                if row_data:
                    text_content.append(" | ".join(row_data))
                    
        return "\n".join(text_content)
    except Exception as e:
        print(f"[ERROR] Failed to read DOCX {filepath}: {e}")
        return ""
```

### 3.4 PPTX Files: Extracting Text from Slides, Shapes, and Notes

The `python-pptx` library enables PowerPoint processing. Extracting text from presentations requires iterating over `Presentation.slides`, then over `slide.shapes`. Not all shapes contain text; checking `shape.has_text_frame` prevents runtime errors [cite: 32, 33].

A common enterprise pitfall is missing the speaker notes (Presenter Notes), which often hold the richest contextual data. Notes reside in `slide.notes_slide.notes_text_frame.text` [cite: 34, 35].

```python
from pptx import Presentation

def extract_text_from_pptx(filepath: Path) -> str:
    """
    Extracts text from all slides, text frames, shapes, and presenter notes in a PPTX.
    """
    text_content = []
    try:
        prs = Presentation(filepath)
        for i, slide in enumerate(prs.slides):
            text_content.append(f"--- Slide {i+1} ---")
            
            # Extract main slide shapes (titles, text boxes, etc.)
            for shape in slide.shapes:
                if shape.has_text_frame and shape.text.strip():
                    text_content.append(shape.text.strip())
                    
            # Extract Presenter Notes
            if slide.has_notes_slide:
                notes_slide = slide.notes_slide
                if notes_slide.notes_text_frame and notes_slide.notes_text_frame.text.strip():
                    text_content.append(f"[Presenter Notes]: {notes_slide.notes_text_frame.text.strip()}")
                    
        return "\n".join(text_content)
    except Exception as e:
        print(f"[ERROR] Failed to read PPTX {filepath}: {e}")
        return ""
```

### 3.5 Consolidated Extractor

By mapping file extensions to their respective parsers, we build a robust, scalable factory:

```python
def process_file(filepath: Path) -> dict:
    """
    Determines file type and routes it to the appropriate extractor.
    Returns a dictionary with metadata and extracted text.
    """
    result = {
        "filepath": str(filepath),
        "filename": filepath.name,
        "extension": filepath.suffix.lower(),
        "content": "",
        "error": None
    }
    
    ext = result["extension"]
    
    try:
        if classify_file(filepath) == "binary":
            if ext == '.pdf':
                result["content"] = extract_text_from_pdf(filepath)
            elif ext == '.docx':
                result["content"] = extract_text_from_docx(filepath)
            elif ext == '.xlsx' or ext == '.xls':
                result["content"] = extract_text_from_xlsx(filepath)
            elif ext == '.pptx':
                result["content"] = extract_text_from_pptx(filepath)
            else:
                result["error"] = f"Unsupported binary format: {ext}"
        else:
            # File is text-based (CSV, JSON, TXT, HTML, MD, etc.)
            result["content"] = safe_read_text(filepath)
    except Exception as e:
        result["error"] = str(e)
        
    return result
```

## 8. Final Considerations on Common Pitfalls

*   **Memory Constraints**: Loading enormous `.xlsx` workbooks into RAM with `read_only=False` can result in Out Of Memory (OOM) errors [cite: 28]. If extraction of merged cells is not strictly necessary for a specific massive file, falling back to `read_only=True` drastically reduces footprint [cite: 28].
*   **Corrupted / Password Protected Files**: Using `try/except` structures to catch `fitz.FileDataError` for PDFs and `BadZipFile` for OOXML formats (.docx, .xlsx, .pptx) is mandatory to prevent pipeline termination on a single bad file [cite: 23]. 
*   **Deprecation Audits**: Because Python libraries like PyPDF2 [cite: 20, 22] and FuzzyWuzzy [cite: 38] face structural rewrites or rebrands (e.g., FuzzyWuzzy renaming to `TheFuzz`), pegging package versions using `==` in your script's dependency injector (Section 1) secures the codebase against future breakages.

**Sources:**
1. [ubuntuhandbook.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoJih6mk2zSngZxVh7J6TOeF6h1jHJ6N347qYwUFcxhbhqQp0O6qofxSwi2_Gzp7r1s3ZI69wu6xfa7r5bRHnWL4zdLuvQMDMft1SlrnXZirZA_f09U4ZhW-PVaT7AUHiYYCFBNTtiz2YyRiq7ObLYLERmE8xeY5Zy1DXlV9pMsUQ=)
2. [jeffgeerling.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGGufdD7OH5c5nmFhkewoEgXzkCIt2rigKt-N1RUQyXappTLtTyZssHkPqG4YP4jhAidH_A5k0LcLQueUkrR3-kTdGKKx-6kWKoS6Y6f-uXjeoco6y7LUxj7Z6fMGltcTZUJwCiXzD7kdO700F6eu41SoE36_cWXGCeSnk4KHKiDkO-3QBjyfcPPH2uTZlhIz8YfM3COuAL4ry0WAy_QEQ2Sw==)
3. [dnanexus.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFdoMAR0Zfbind28W4UJzCZh3w0sA5TCuNZMqqvBPplCYwVh-MqSWU-jNaqWLLG5p7jKNBfHGzJoxQ_GmC89ng_32AhShY06bBsbUqXoyvfZp3TqeDhRA0bg-SYaDwPc4nocdbtU7KGIw4UiXy4JwgSrldkQL98C-coCBUjl5URG9DR8baqo1HA2rpLu1qA07X5j1QdZnH3NynU-cBNukzUdZICULnTCp9KK98sew==)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_8m_kcJR0pF_wkvNn41VCwnPLTb5Y1BCNMsUnme5MeFdZFyn06SCGZ3QvtwAFV7kM7zHbuUK3MBZTUnL009WH7rN3fcdp5vrNCZOU2Vc6VzzgHmjKUXUa9-o5czLdXu0QVqJcXXU1EPwziA==)
5. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFOIw1PqBdE4sBme6GwZjF5yYE3V-0ru2-eYrFVrG6xjJWYhzmGZmD78XIfpYOSMPw0QDZZ5k7lWl1mkjXSfSJ8QHiVSdLzhzGR46FaigoeTnK3H9gdTEn1RT7l584PMfe5VJSLDUUGh0i1YQmmTyJxqESsmNhxuKW-8ylM6d5Yeqmrk0Eywq1QPwvsD4XyCIOO4DsDecEWCKg=)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG8mNkg62WiAKpcLZKSvn17sduxhC73zXoJqdkNAFg0XE0c54OCxRw5_EiYxwIFdwPB4CjOdb1kBgJF_QGvFYroISEA2ZLa3mN7g80mlFl2aexH3oSMe5gA5WdX_D1rk4LZhXc_baIuUQMuKI277kVRheUhpzFQtcOztVmiaHvYp6-YD6DcSqh4atDl5lQg6tVJDM8-Q--i9WjRM4fSkj6nqIWR4sON2NFuVKc=)
7. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHP-WEbdcZyaON_l_8iV2tLOFawslgVBsEN7ps1FFh9VOn6o9mtVRd4YbEnVEkVwnWOCiRX-ledWuDC5w6R0yI6W4F1mxLosXY0822TORrBgFmnN7y7_wDfjcon53T4q2KL)
8. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHW-GQ1uW-eREr_yCNpI9Rr1kOH-3R5d3sCp536XKOpNa6x3Db--igKiaqtaMR6h9T_DlU1bpx_SpHWGlJW2w6bLbND0XDWozHRYcC_99LzLLc-Y92fUlUOXKGqdLxG9mmvP2SP4ofZxzuiu-cYhDsRbCKjzNQomVAfd183k4xTUifSyZhMRFB5I4P-dzRzr9xnhg==)
9. [rpdev.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYpC23_vAh4UlTSoG-seY_8vBKOZI2SWRWEHw36228t5wbKKK_YBHVwIZXwRrace_nyE94goc-KEDW3EsjythR6djuTozHH3x9N_gPIEVBUY_UeS069d2SwrOUAyXal52bWiw0c0YcHE9FBkgNPd5-doIzuvRtLs2whSPGIeg50cgC-LMSr0yX65ttjv41sp681s8fx8Gx2orluv51)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGEj3-KsYPUWgm7x3ersdNl1yxusIwZ8Gy9vNkZ7PjJABGobZCo0x5F_PJjOEDZhOs_n5T7Uw-hQw5oJ-ulZuPJQg9_bUJ2pUOW3uWs5pZvvH43W6jkjLZ75K4lB95NZxx7jLU06_F8uhAPfdohgcnfLK3YWtrFx3SWNbnlWQ==)
11. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG49ms8vrMiX8w_yo5CUfdOgLkENK36TGUgfkJ-kcM167J12UEjgPCM58ipe9K00wmksdf2yOKPiwoJFH7YZFdq-049y_0GP3JLrCfVX4uc9JBYHjKfuB81otlqI7GhrOl9J8_cCQExarCEguzsIgpOc0t7_XUvAuqeTy327tbxVbnXu4nHlL57AcBdFJlMxwP8DVWWhrwywA==)
12. [activestate.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGz9-SjiIU7eZfpl4IBQqP8LEc74GZwnTZGjpYJeTIlNFBeRciBjPJ4rWtHqJBZxPkhvSmcP4Kax6YjpDwvUnqGXrmP5NbFZfse7L_f2bC7R_IcvvWjLBSbA0waVQSJDOZk7DL5-HXm9nrWbVL2Rijh4nGquE5oPXW9Vp4lIiwt51CNpmnhLIYBwuBMXbM=)
13. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjoWpDdafstt63nmDA75x5IZdWaPGY8dKP97TY0u5uTB9SETX7b9i32N8VEz11X3Bl7FexdwHDw0z072YgSlcwjNBVHuaHAIbLN0d4auYuUVJT8HjbQDfrC7qI)
14. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHylJU3EuuzoCl8b2peqekqukXDWd7lnAK-H3awywyoAUO9jIuRga4UVfykAdScuokvpnm5HsUchFKdjPil2egeAjZA5J8N5qsdXeQ3gX9IsDfFaP2mLqB6YXZlbu4NUO0=)
15. [ssojet.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEziXUEV8etzBxGEmPHPqYPmH0Bf9HkO-jHJi_DuNeq33ShtI6bVEgvpF983Pog8Dpe9kB5eQ5u0k3Nag8mjdPG1uCDz5SICHbckCawax5-fzijj0QIwz-e0CC3G2mD0J0Jyx0Es3eTjexC-FEwQzzklK2qtk4pfuCBRVc=)
16. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGmF2SonBTKDKBLQSD_DmW-u8CoSnk7yq2PWJv8sVcZWpXIRw-SHENf6Abz2uUitjnYBCAvJ1F75wSMx4rpY-Kbdv7kjmaPgPZ0IedyPYqSl2AYw0gWRWmypvkT73BNByLiqPI8Rbqg_xk6N1OLqUQnf7yp191CuF_9GltrbkePU0OAJj3FuJyrjnjz)
17. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFmE5vzFPTpeXbDWFdppcuOqOC7YgwFYZVi7Y4js3ePD2h_AzHt96w-yJMsQOQaIQcr2VRvwvc-toC1gibP0l7tonSG0dynafJOH86YrnGu6UT1ub2RYSApZvfqR0j4J9S9o68rKD-Esaw=)
18. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdZo8AFLEfMSCXne2x_9xfWHs_GS688F96nFteXlW47UFydvhpSNsP5-KDQrhwZU1wZn1FzJvcLWMXoS2Mf3e5ZHTwS1gAt7iJcy9SMCc89S1NJQvhT1VbljiLOaA7KdVBkw==)
19. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEd6qOy72alzSisRA5tkfE1D8rVXI3p3BiZGksVaXr6ZoaBfRGJm4HNKSP7108v2tImXkbb3Urf606b82V8YfAmWQKq-Am4M4DGN78jmRim1-oCROrF0NiTfn13CEZolMH_SUw=)
20. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFQGeBTQjFOR0yDnDkV_uZrTZ3H-4E5wa-VuuuR9dzWPRpownxCrXtSXAhvM7XX83QZ49p_HUeP1nO4lqClEqK5w37EepgzH0CN90mCoMrl5vTRAZgK_M5w_96-3X2YYhsNXMvVnqORZ0coA4U_e8TANFgaCN_7e9BbKt0fkA7-nZNg_2qva9-hCu4vaXupUHJmti6svsYjB_Cnt9mvnz5EhE2bts4t53qQjuCvUW1Fgmea)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLCPeBM6MP_bPaY6V3n2Ig51BEh3mjNuZzZ1jpEsce9e9Qyz3PPvJrRR3RTJBo4KTaUs5HpyYf4mgdlO0YVec-eN0rRkN43PWSM8MNslUz08FKMmFAeWgEV5TqDKY_gS-tiheuIVZN)
22. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-5T3ZwpG2sK-eRt-wF4I6tEuQBC90sRgrSapEROkKrPBkqN0PtQmJD8ltZIEMnYo5LyJdnZ6D7qCA_JezSCILvk17dyGaqR8QojddJ0_6VPskAkwETjctQ-MhiQ8ScH5JYY6Rl2rM78t64JgiTsS5K7lLlX4=)
23. [substack.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4i0nkTh7ZC5tsnuOpi6V4F2eA-hSNWxwytaOUQo91Z1w1YSIkvBYxjhHk_M_Ku_fvxsRGt6T1TuK5mhtAVmQTDVqoylHVtDBpAsfxTkITe_jLfOXRxISWXjiyvZ48VLiWl8Zvl88ZW9co84ovB7XlqZAk6_Qsmiu95Vv7)
24. [w3resource.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEMs6GyYDsfHlIVOxsYWFwJdSQubtqTGlj6BWZ8HaDUfz5kIsMzHxpP_R_ft7YMxhd3Fi9XNmQYdF1Fs6zIIwKO6BndIKVbyegx-EvJb2XR18bbmIrRscbpktr0I-IGwrRvn6qSwRMQ0QGEJmYvGggikQ==)
25. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVajbwTyawh9bQYRuGkKxJ80YQFWmmh2M5wqbeEEJIV5nYt0YpvWIt_X1I43GQQPCoTNsZsHFqxFgHjlQOkYBWF-jyFS53wBUFS35L7kE0QBhbEW4OLp2UFt5FakkJ6YhzzFBRZ7pyYdsJBjZFS-zJyKZuaLaBL2G4lQLYqzXwznsoxDkb0fLGyZS82qdNOi1rAW7M309NE7caXEB03BjEx0uAyA0ancbtOsT4P0sVBafnp0Dw_jqe6rE=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyzF6chzLl1Wjmdh-R-BpceiaVhbZ3rrhaqfCghivPGC0u2rr-TRuwWKWQXTRhZfZJN0-J9OZRZFVq6w0PO7BJeupnvAIO6EnTDDH0kvyfg84nfh-Jipik7lWoQAezitAVWSfMe9FfZGVnyPdkb5CLRK7A32G4fvt6IrOL8QU=)
27. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7DW7pfywxbwnGpysd194rViSZX3qxUvUQho-q8NVQpAIXwbUn2XqnvTyTsjJvPDVR0UBB-Dxo-Id0URIOozShHtixzDwyMeI1ZWPCDcOmuCkRTo0_KoeGKvp0tonUurtZ0llyk9UmtWgEniCjjBAlta-rYTUjanb0eRCsh94MbITvSE0FSmHnh-Cuj8AS3Xzv7w==)
28. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGnSOwyoekpsQaJsyJixAm4P9yaQ8OMORMU8w0NWnf09bXBO_YsEBpX-fmFXGoXjuHJjNnCfmcw__ViYt8zbto1USNj9CWL6Gv4hu1soieUHdBMtuC7zUbr9fTOMAqJIhLKCMhERvACEHy4q5YfYA8Jd-MT2-UYaA9O0YkNnt43_y-x-j6OZ7toAmbsezCRyQ==)
29. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGrDf2I7rESn4nBlQ5ObQ8LP4LNhpWGVijnjo7vaMFuG6vRpekHoxqYY6iG_EyVWZejPGa5Bz3OpXrcbWX1N9GRsu8djPte-rIB6KOqucGAj82tlgBLll3r8OSi_YMgIZ94PgoaIaWy5V4d1oRYuzRv_5NzM4z5tLZW3olC1oGP78u3TsaHvXYGai0mCA==)
30. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJ7MQnUAsBkS0PJcF_Cu4uhhSp-jssAI2L_2WrlqCyD5gbeJGiHhSaq8yU4WaNiwthEvzbPyDIdsztZmpJ7rZ39QhaIEVfnUpcKFez573MaKDFRHTg7mtzFwratjpLSMWXlHENvGGqQ0n-0bfnOPs-mkG56-WRGfX74CRX0kwmiSIt_L06VovFPYnm6UszjKwYoAfP)
31. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyIjrZgJE6AHtagmpzCAAk43gi8z6MUi0j_NqG7HEMeFNseKJznbAvfM3Kpq0bAPLmu4EzXYY6h779p4vAyeM_wudwLBS-sE_SjfHcMf7IInwKJp9TN7wZgccbnnsWxuUnljHe05VnQXRCqUj7pwy5bpfivA==)
32. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGAYHXvwZigqoFyppOi6IdyKrGgZ9QiO8Ith3eQwfVtnvL9vswBqVX7qJ0kK0lEUYcja9_zBJSlAXzFq6QvdSqzOU4_NdBe7tL9onlWDNqCdbCoSS5qWL-w6fL6IrLt7fMgdD9zqUmLSX19F7cGbTceQwE4B2y5OGZC4mG-AaFXFz3yHKTGxFsvlmLc4b8=)
33. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6nUTMZh37qHNC2irDdcr051W4t5pVXWY5BOoGkb67rzpjTvJls0LZ2gg0CIVFp3_KBQBy1pe0znzUuOoqqx5C7Lz36Fp0BPm5MMYm-nqh4BipdhJABJEddq_mJEZHBK-qrDaVa9-aVnrXLmu2hb8gr8_Wqxig4ETfpwIKIivP1fID1uhxR5Uas13-KNpsm0FFmeSR8Lx-cswYukyVfMAjM729zOL_)
34. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESwsCO3LGJh8joMuIurmJRnPTVBG0MG2636g0Yz1OEzmQXSzZYKUnPW8Mhn4wpX6M4beN6-I1lfZfVX3Vbde6_YyEQyaHFr2B1fYEmUQL2_FUhCSmIUhIbRIqSZg5bWw==)
35. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUpcqL2b8YUbaoAGNEF7ILoKdhzb4cAJNdMT236gwr7QvpvQLgehL_7dzfzzjYMV8jeeJOvNXBB5aNFHvRzqxVyzx18icx1JvQJiQ95m_DNZYI2A8X_WqP037dW4JNmIFGO0cVszVluxuVwwgyxQjG-TuHKd2QXE3NnD5_3DViIbfmwb9lA0565fSITGt3n7h-JoXa)
36. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFWQRDW0-JXhDA2Ov_cqK5VA6QYCi40CWU1FrytcAD0o13CSZKroxOwL7bQF9rpVikOpHPVb_rUgTwdedEPFZ4W5WudMNHwNjVpSRs_zjbZ9jPwbY0kT20TYrEqvxLKwFV3Y21pA4DbU8ZYWJPwV17nIWsN1mwveSsILcQXs_48VEbGZisD5FNy5b3qd399RvQVHxzgyA==)
37. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF6nMDQeIZZSIPs2vl1PvU9AimYr-4jSJjRRfQ0piNrrHIImoTd73fFcJiHa98Pmoy8B7P83pIzdOGSS7eJxo5jBF2IeJgeXqrzfB-Ve1qWNVS3ABFpgEviRAj-OUUXHQlj6WaTb7wTvMdGiOD2sn7XVK1l-xAn0ycG5GXP8fyjmXf-UL_zcRX5dg==)
38. [datacamp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZJCPL6PCprHzPPcST608Jrx_n0gNBsCl-6AWY2PnNVw6ZQ6JOqLQfG5RK0PnkwdoHRKjDHtFwq3Ywh7X0yvTJEaVkgKv2jUZt2vJ5tY6TGiLdqDabe7wUXyjejID77HmLCAbyWJFLFgX0kQ==)
39. [plainenglish.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMMuLAPN1YM7O5Es_C-LtI1o3TPBmVy99uYHK9sHI8S6bNdBJvbrCUTSRieRH6M6Jq2HyE1bTSL19rHp4UTK2fmuazf2CfgEEjcXX79qWSN6uOaePSGm06Wfw6UzLC3ojSbNfXzqYlAojmq3SYJIxgGYrbdA==)
40. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEhTOYXkcfN9_1QODKYj1gA_u05Sr8u_v3WQZwhEFXE2BTLsQpEbBkjVrL_iNlaIMdXKbe4BkNRZh4A5-V_SUr36gWvbJ_0DRVyGt_Q29sfsBKPWJ2nKG3ZNpPFnlMoMNdg)
41. [ijeedu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGLe98oZJNB8e9YSFi8e9zpycu9pbN2OWsjTfdZID0RQsCwgYepwYc8ZANeVmBs-6oWRdyn9X2p8ObABLCDkt1lyy6NVmhvCafBfotudzfsZH0QHkPxuKzoU82l4Oiz0nSQ0krZhXYdu_luim2vxToM7YA6zTM=)
42. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFbZpUD8waRfnNoXBBmqJ6L6KnaNhn1NLpjyKG8yMEu10UjvOKGmTD_1uc8KFYWWuIztFvDBgz6hKX0U0hspw_GYt7ZbDsK6WuFyIkNn1PbH4_4DNHkE38Ky7AtfdqKREkWqPTjKBgpWhH7HXETsrzez-skhDio6mvFYZM-mIJ)
43. [zyte.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEA1_nngk5iXtsWB_8Eys5avoAIdiZme8rFaw9fHQ-SKiFLfIM4O5QaUZPVX3UE1lwQp4GTy1-6TPXL9lQGcZXJ5QPWjEO3QJ1-ZoTFoizZ7hlUEgvYZdvqDYBO5bajmvTEwPAv3G6gnl4=)
44. [codesignal.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1FIAeDui_9GtIv06Fqps9Q24SkUZZW4xsQOX6PSt6dejar8-pvgkAFbTKdhYP2nXJaQTeL5uw_BjDna8CZnT2oZjEoVoLKAIoB9PuY9BLdkypyw1PKaG1sKOZwtwoF9rLmVV_353XmDMYSoAbx_MZ747aVLvVPUJnciXagzpTQ9H_k3eyLCnLjQbwcOfnOX5Z4CLlsymRHuUl9KAKjELd_iY2WB241JE=)
45. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHkF_3cKLqF-zOn6n4p6TbJVlSYjXyGV4Q8xvasKaB7e-AlNC2SmqkwM_e2Xnom7C3gyqvpP1makTcb0r65EYzZQk_eV3FVCz__Pe4tynJqeBGtJ-7JwyJ8CTY8dZjxDfvZJPb4kB7hY1zOEsTDpdBjakwO5Ow_4ieiL3ylSeAbQn8BGErJQ==)
46. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFlAxHSJyVX7XHibMFwR1IUBAq_0TOzSKbauXdxh_5nZJkrw2RqT2TEhXfhO_vrYtOsj91S6fZdeUXwkH67KhbgCAdAuJBGfdQrxe9cu2BnBxFDUT7Z_zUsfd3ejfUuslTWQAZtBZ512rxBBFmaLi-T1HFe4ny0m2QAREhgRbrjIDF3R4re3Q-QPOuW6tpydriGdLb52lYpLbbz86XZL_HVJXAMMcx1CfSe8g==)
47. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsZPc6-yuZvi1hzsdTFjG2nvS5BePhA9jDsfBoeTviWdceWyvloe81izi4ognhnqMiskHh0To7WjNg0FdQmyh8Cvs-MbiwJSAPkvVOcTeGxhDN_Odui7FQzDo09LrE23tt123bF1TAKMWYlU8-9kTbFwXofafTDK5yZfPSQvh8j9nAzu2bA4rvDRKASPwS-eAW89KhFHa7No5FpPxULAdDYTeymiWk0D09Ut9PxQ==)
48. [realpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKoL0QOEC0UY2Hqn7jkNb5Y_bDgeEC7dd-KaXjApgCDbeC-lnZYAY0ga2ruYqiY7Un8-VYcFvSZK3eLADuJn1WD2ZaLhHwUjm7eY4MSKKd8l59ZuPz8A6zag==)
49. [vellum.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHVJvcyDdsWRrT5u-SCJRly6p8MBnjscGAlA0wl8csybPN70FTZ-9_H5SU57FSxiIx2ekI2XnKrIwpqO1GJNPjSgPX5vmnm1-d_An69Zr1xIehtg83DlRsNXGKPAWW0qFRuyzO9v2nx4HANRlAnt0xHbxcOcfLNExjdB7wNVkX4MddwEtopFkZ_NKBE8mKq)
50. [openai.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoRvWfZ4RWXLoAUYY1f3gvENO_nz678jhL3tUGPSQB7HTGaO_qqESAkBaophbZdhIVoTaYe3ftpA7NKDz_nNLuIDh0XNydCsXxbUtulc3v8VCmqEWvgZ3ayoxkeIPZ-hbf8EXZmlxr039rdtYA3aopUNTdEgvys0OV7owvu9BGJwzZkXIMMlA=)
51. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGvZKLXO4JnGsaIQ20a2mXOZp5DEsPHSj7IH5jJ-BlrgksIQVhF8Vh4YXyEi2DV_9900Jduyjc8ZqURF71bpphau5yTk3tMh83g8lvkxLzPciNAo6czotGz6Bj29A==)
52. [dsdev.in](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHkc1moTsTRcU34l4PNrqeF3lBPUzJUC2qSHXOet7N1aWSf0yA6JojHWu1qRlKw3aB4yyK3AWzFiVGgAKJ59wCcrIbIkN_S_oJS8UesJzNP1PnXEjc0Vxy7kaE27uvWDob34QFjrD0vBfUWpCOOvDXFQUg=)