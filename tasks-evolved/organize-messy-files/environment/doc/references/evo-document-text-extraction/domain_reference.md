# Domain Reference for evo-document-text-extraction

**Responsibility**: All text extraction from any supported document format. No classification or file movement logic.

**Key functions to implement**: extract_text, extract_text_pdf, extract_text_docx, extract_text_pptx, extract_text_pdftotext_cli

---

## 1. PDF Text Extraction Strategies and Implementations


The Portable Document Format (PDF) is notoriously difficult to parse because it is fundamentally a presentation format, not a semantic text format. Text is stored as rendering instructions (characters placed at specific X/Y coordinates) rather than a continuous string of words or paragraphs [cite: 1]. Consequently, extracting text requires libraries that can interpret these spatial instructions and reconstruct the reading order.

### 1.1 PyPDF2 (Version 3.0.1)


PyPDF2 is a pure-Python library that has undergone significant modernizations in its 3.x releases. A major breaking change from the 2.x era is the deprecation of `PdfFileReader` in favor of the `PdfReader` class [cite: 2, 3].

### 1.2 pdfplumber (Version 0.11.4)


Built atop `pdfminer.six`, `pdfplumber` offers superior accuracy in text and table extraction by deeply analyzing the spatial layout of characters [cite: 6, 7].

### 1.3 Performance Comparison and Best Practices

For a corpus of 100+ documents, performance is a critical factor. 
*   **Speed:** `PyPDF2` is remarkably faster than `pdfplumber`. PyPDF2 operates using a relatively simple parsing algorithm that reads the text stream objects directly. `pdfplumber`, however, performs complex geometric calculations to rebuild the visual layout (evaluating character coordinates, overlapping lines, and spacing) [cite: 6].
*   **Accuracy:** `pdfplumber` handles multi-column scientific papers significantly better than PyPDF2, which may mix text from adjacent columns.
*   **Recommendation:** Because scientific paper titles and abstracts usually span the full width of the top half of the first page, `PyPDF2` is often sufficient and much faster. A recommended architecture is to try PyPDF2 first; if it returns less than 50 characters (indicating a potential spatial extraction failure or an image), fallback to `pdfplumber` or `pdftotext`. Limiting extraction to `max_pages=2` reduces processing time by up to 90% for 30-page papers, as the most discriminatory keywords for classification are concentrated in the abstract and introduction.

---

## 2. DOCX Text Extraction Methodologies


The `.docx` format is a ZIP archive containing XML files that conform to the Office Open XML (OOXML) standard.

### 2.2 Fallback: Native Python stdlib Extraction (Zipfile + XML)


Because `.docx` files are essentially ZIP containers, you can bypass external dependencies entirely using Python's built-in `zipfile` and `xml.etree.ElementTree` [cite: 11, 12, 13]. The main textual content is housed in `word/document.xml`.

## 3. PPTX Text Extraction Methodologies


Similarly, PowerPoint (`.pptx`) files are OOXML ZIP containers.

### 3.2 Fallback: Native Python stdlib Extraction (Zipfile + XML)


Since `python-pptx` is omitted from the Dockerfile, the standard library fallback is required [cite: 15, 16]. The slide data is distributed across multiple files located at `ppt/slides/slide1.xml`, `ppt/slides/slide2.xml`, etc. [cite: 16, 17].

## 4. Command-Line Interface (CLI) Extraction Methods


When dealing with highly complex layouts or corrupt OOXML/PDF documents, native Python implementations might fail. System-level CLI tools provided in the Docker container serve as robust alternatives.

### 4.2 pdftotext (Poppler-Utils) via Python Subprocess


`pdftotext`, part of the `poppler-utils` suite, is an industry-standard C++ utility for parsing PDFs [cite: 22]. It is exceptionally fast and resilient. To bypass the filesystem and pipe the output directly into Python's memory, you can instruct `pdftotext` to output to `stdout` by using the `-` argument in place of an output file name [cite: 23, 24].