# Domain Reference for evo-pdf-context-extractor

**Responsibility**: Read and parse PDF files, returning extracted text for interpretation of data semantics and question context.

**Key functions to implement**: extract_pdf_text, get_all_pages_text

---

## 3. Extracting Unstructured Data: PDF Parsing with `pypdf` (5.1.0)


PDF files represent an unstructured, visually-oriented data format. Text in a PDF is stored via matrix translations and coordinate placements rather than semantic flow [cite: 20, 21]. Extracting this data requires specialized handling.

### 3.1 Migration from PyPDF2 and Import Semantics

In late 2022, the ubiquitous `PyPDF2` library reached end-of-life and was superseded by `pypdf` [cite: 22]. The upgrade to `pypdf` version 3.0+ (and currently 5.1.0) brought significant API changes and deprecations [cite: 22, 23, 24]. 

The exact, modernized import path for `pypdf` version 5.1.0 is:
```python
from pypdf import PdfReader # Correct import for pypdf 5.x [cite: 20, 25]
```
*(Crucial Note: `import PyPDF2` will result in utilizing legacy, unmaintained code that often fails on modern encryption schemas [cite: 26]).*

### 3.2 Robust Text Extraction Architecture


To extract text iterating through pages in `pypdf` 5.1.0, the `PdfReader` class is utilized alongside the `extract_text()` method associated with `PageObject` instances [cite: 20, 21, 27].

```python
from pypdf import PdfReader
from pathlib import Path

def extract_financial_pdf(filepath: str) -> str:
    """
    Extracts all text from a PDF document using pypdf 5.1.0.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {filepath}")
        
    # Instantiate the reader [cite: 20, 25]
    reader = PdfReader(str(path))
    
    extracted_text_blocks = []
    
    # Iterate through the sequence of PageObjects [cite: 28]
    for i, page in enumerate(reader.pages):
        # The extraction_mode="layout" attempts to preserve visual spacing,
        # which is vital for financial tables where column delimiters are just whitespace [cite: 20, 21]
        text = page.extract_text(extraction_mode="layout")
        
        if text:
            extracted_text_blocks.append(f"--- PAGE {i+1} ---\n{text}")
            
    return "\n\n".join(extracted_text_blocks)
```

**Breaking Changes & Deprecated APIs (5.x vs older PyPDF2):**
1.  **Naming Adjustments**: `PdfFileReader` was deprecated and removed in favor of `PdfReader` [cite: 29]. Similarly, `PdfFileWriter` became `PdfWriter`.
2.  **Property Access**: Accessing pages is now strictly via the `.pages` list attribute (e.g., `reader.pages`), replacing the older `getPage(i)` method [cite: 25].
3.  **Strictness**: By default, `pypdf` handles malformed PDFs more gracefully than older PyPDF2 versions, reducing the reliance on `strict=False` arguments [cite: 29].
4.  **Extraction Parameters**: `extractText()` was replaced by `extract_text()` [cite: 21, 25].

***