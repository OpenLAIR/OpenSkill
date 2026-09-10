---
name: evo-enterprise-doc-parser
description: Provides utility functions to discover files recursively in a directory and extract text content from diverse enterprise document formats including DOCX, XLSX, PPTX, PDF, and plain text files. Handles dependency installation, merged cells in Excel, presenter notes in PowerPoint, headers/footers in Word documents, and encoding detection.
---

# evo-enterprise-doc-parser

Utility functions for discovering and extracting text from enterprise document formats.

## Key Functions

- `ensure_dependencies(required_packages)` - Install missing Python packages at runtime (handles PEP 668/Ubuntu 24.04)
- `discover_files(root_dir)` - Recursively scan directory, return list of Path objects
- `extract_text_from_pdf(filepath)` - Extract text from PDF using PyMuPDF (fitz)
- `extract_text_from_docx(filepath)` - Extract text from DOCX including headers, footers, tables
- `extract_text_from_xlsx(filepath)` - Extract text from XLSX handling merged cells
- `extract_text_from_pptx(filepath)` - Extract text from PPTX including presenter notes
- `safe_read_text(filepath)` - Read text files with encoding detection fallback
- `process_file(filepath)` - Route file to appropriate extractor based on extension
- `extract_all_documents(root_dir)` - Discover and extract text from all files in directory

## Usage

```python
import sys
sys.path.insert(0, "/app/environment/skills/evo-enterprise-doc-parser/scripts")
from utils import ensure_dependencies, extract_all_documents

# Install dependencies first
ensure_dependencies({
    "fitz": "pymupdf",
    "docx": "python-docx",
    "openpyxl": "openpyxl",
    "pptx": "python-pptx",
    "yaml": "pyyaml",
    "charset_normalizer": "charset-normalizer",
    "tiktoken": "tiktoken"
})

# Extract all documents
docs = extract_all_documents("/root/DATA")
for doc in docs:
    print(f"{doc['filename']}: {len(doc['content'])} chars")
```
