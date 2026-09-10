# Automated Document Classification and Text Extraction: A Comprehensive Guide to Python Utility Modules

**Key Points:**
*   Text extraction from common document formats (PDF, DOCX, PPTX) can be reliably achieved using a combination of Python libraries and standard libraries, though each format presents unique structural challenges.
*   For PDFs, `PyPDF2` (version 3.0.1) and `pdfplumber` (version 0.11.4) offer robust text extraction capabilities. Reading only the first few pages dramatically improves processing speed for large corpora.
*   When third-party libraries like `python-docx` or `python-pptx` are unavailable (e.g., in strict Docker environments), Office Open XML (OOXML) files can be successfully parsed using Python's built-in `zipfile` and `xml.etree.ElementTree` modules.
*   Document classification without machine learning libraries is highly feasible using keyword matching and custom Term Frequency-Inverse Document Frequency (TF-IDF) algorithms applied to the extracted text (specifically abstracts and titles).
*   File sorting operations must account for cross-filesystem behaviors. Utilizing `shutil.move()` is generally preferred, as it handles atomic renames on the same filesystem and falls back to `copy2` across different filesystems.

**Introduction**
The proliferation of digital documents necessitates automated systems for sorting and classifying scientific literature. Building a robust Python utility module to parse, classify, and sort PDFs, Word documents (DOCX), and PowerPoint presentations (PPTX) requires a deep understanding of file structures, text extraction algorithms, and filesystem operations. This guide explores the creation of such a system using both third-party libraries and built-in standard library fallbacks.

**Context**
Scientific researchers and organizations often deal with thousands of papers across diverse fields such as Artificial Intelligence, Quantum Computing, Astrophysics, Biology, and History. Manually organizing these files is impractical. By leveraging targeted text extraction—reading only the first few pages where titles and abstracts reside—an automated system can rapidly ingest content, classify the document using algorithmic text analysis, and move the file into a designated topic folder.

**Summary of Approach**
This report outlines the theoretical and practical methodologies for constructing a Python-based document processing pipeline. It provides exhaustive code examples, API documentation, and comparative analyses of extraction libraries (`PyPDF2`, `pdfplumber`, `pdftotext`). It details fallback mechanisms for OOXML parsing using standard libraries, implements a pure-Python TF-IDF classification engine, and discusses robust file management techniques to ensure data integrity during the sorting phase.

---

## 1. PDF Text Extraction Strategies and Implementations

The Portable Document Format (PDF) is notoriously difficult to parse because it is fundamentally a presentation format, not a semantic text format. Text is stored as rendering instructions (characters placed at specific X/Y coordinates) rather than a continuous string of words or paragraphs [cite: 1]. Consequently, extracting text requires libraries that can interpret these spatial instructions and reconstruct the reading order.

### 1.1 PyPDF2 (Version 3.0.1)

PyPDF2 is a pure-Python library that has undergone significant modernizations in its 3.x releases. A major breaking change from the 2.x era is the deprecation of `PdfFileReader` in favor of the `PdfReader` class [cite: 2, 3].

#### API Usage and Signatures
To extract text using PyPDF2, the correct import path is `from PyPDF2 import PdfReader`. The extraction should be constrained to the first 1-3 pages to ensure optimal performance when processing hundreds of files.

```python
import os
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

def extract_text_pypdf2(filepath: str, max_pages: int = 3) -> str:
    """
    Extracts text from the first `max_pages` of a PDF using PyPDF2.
    
    Args:
        filepath (str): The absolute or relative path to the PDF file.
        max_pages (int): The number of pages to parse. Defaults to 3.
        
    Returns:
        str: The extracted text, or an empty string if extraction fails.
    """
    extracted_text = []
    try:
        # The file stream should be opened in read-binary ('rb') mode
        with open(filepath, 'rb') as file:
            reader = PdfReader(file)
            
            # Determine the number of pages to extract (safeguard against short PDFs)
            num_pages_to_read = min(len(reader.pages), max_pages)
            
            for i in range(num_pages_to_read):
                page = reader.pages[i]
                # extract_text() is the correct method call in PyPDF2 3.0+
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
                    
    except (PdfReadError, FileNotFoundError, Exception) as e:
        print(f"PyPDF2 Extraction error for {filepath}: {e}")
        return ""
        
    return "\n".join(extracted_text)
```

#### Known Issues and Pitfalls in PyPDF2
1. **Empty Strings:** When executing `extract_text()`, PyPDF2 will return an empty string (`""`) rather than `None` if it cannot find extractable text [cite: 1, 4]. This is most common with "Scanned PDF files" (where the document is just a container for a scanned image) or when dealing with unmapped, custom fonts [cite: 1]. PyPDF2 does not possess Optical Character Recognition (OCR) capabilities and cannot read text embedded in images [cite: 1].
2. **Encrypted PDFs:** If a PDF is encrypted, attempting to read it will raise an error or return gibberish. PyPDF2 supports decryption if the password is known (`reader.decrypt("password")`), but for automated pipelines, encrypted files are usually skipped or flagged.
3. **Memory/DoS Vulnerabilities:** PyPDF2 3.0.1 has known vulnerabilities relating to excessive iteration and memory allocation with excessively large `/Size` values in the PDF trailer [cite: 5]. In a production environment handling untrusted PDFs, wrapping the extraction in a timeout mechanism is highly recommended.

### 1.2 pdfplumber (Version 0.11.4)

Built atop `pdfminer.six`, `pdfplumber` offers superior accuracy in text and table extraction by deeply analyzing the spatial layout of characters [cite: 6, 7].

#### API Usage and Signatures
The entry point for this library is `pdfplumber.open()`.

```python
import pdfplumber

def extract_text_pdfplumber(filepath: str, max_pages: int = 3) -> str:
    """
    Extracts text from the first `max_pages` of a PDF using pdfplumber.
    
    Args:
        filepath (str): Path to the PDF file.
        max_pages (int): Pages to parse. Defaults to 3.
        
    Returns:
        str: The extracted text. Returns an empty string on failure or blank page.
    """
    extracted_text = []
    try:
        with pdfplumber.open(filepath) as pdf:
            num_pages_to_read = min(len(pdf.pages), max_pages)
            
            for i in range(num_pages_to_read):
                page = pdf.pages[i]
                # extract_text() returns a string or an empty string in modern versions
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
                    
    except Exception as e:
        print(f"pdfplumber Extraction error for {filepath}: {e}")
        return ""
        
    return "\n".join(extracted_text)
```

#### Return Types and Edge Cases
In `pdfplumber` 0.11.4, calling `page.extract_text()` on a page with no text or a purely image-based page will return an empty string (`""`) [cite: 4, 8]. In earlier versions, it sometimes returned `None`, requiring strict type checking, but this has been unified to return an empty string to avoid `TypeError` exceptions during string concatenation [cite: 4, 8]. For PDFs with non-intersecting lines or watermarks that disrupt layout engines, `pdfplumber` may struggle unless configured with custom extraction arguments like `layout=True` or `laparams` [cite: 9].

### 1.3 Performance Comparison and Best Practices
For a corpus of 100+ documents, performance is a critical factor. 
*   **Speed:** `PyPDF2` is remarkably faster than `pdfplumber`. PyPDF2 operates using a relatively simple parsing algorithm that reads the text stream objects directly. `pdfplumber`, however, performs complex geometric calculations to rebuild the visual layout (evaluating character coordinates, overlapping lines, and spacing) [cite: 6].
*   **Accuracy:** `pdfplumber` handles multi-column scientific papers significantly better than PyPDF2, which may mix text from adjacent columns.
*   **Recommendation:** Because scientific paper titles and abstracts usually span the full width of the top half of the first page, `PyPDF2` is often sufficient and much faster. A recommended architecture is to try PyPDF2 first; if it returns less than 50 characters (indicating a potential spatial extraction failure or an image), fallback to `pdfplumber` or `pdftotext`. Limiting extraction to `max_pages=2` reduces processing time by up to 90% for 30-page papers, as the most discriminatory keywords for classification are concentrated in the abstract and introduction.

---

## 2. DOCX Text Extraction Methodologies

The `.docx` format is a ZIP archive containing XML files that conform to the Office Open XML (OOXML) standard.

### 2.1 Using python-docx

The standard third-party library for handling Word documents is `python-docx`.
*   **Import Signature:** The package must be installed via `pip install python-docx`, but the import statement is `import docx` or `from docx import Document` [cite: 10].

```python
from docx import Document

def extract_text_python_docx(filepath: str) -> str:
    """Extracts text from a DOCX file using python-docx."""
    try:
        doc = Document(filepath)
        # Iterate through paragraphs and join the .text attributes
        full_text = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
        return "\n".join(full_text)
    except Exception as e:
        print(f"Error reading DOCX {filepath}: {e}")
        return ""
```
If `python-docx` is not installed in the Docker image, attempting to run this code will immediately throw a `ModuleNotFoundError`. 

### 2.2 Fallback: Native Python stdlib Extraction (Zipfile + XML)

Because `.docx` files are essentially ZIP containers, you can bypass external dependencies entirely using Python's built-in `zipfile` and `xml.etree.ElementTree` [cite: 11, 12, 13]. The main textual content is housed in `word/document.xml`.

#### XML Structure and Namespaces
In the OOXML standard, text is buried within a hierarchy of XML tags:
*   `w:body`: The main body of the document.
*   `w:p`: A paragraph.
*   `w:r`: A text run (a contiguous segment of text with identical formatting).
*   `w:t`: The actual text token.

The namespace `w` maps to `http://schemas.openxmlformats.org/wordprocessingml/2006/main` [cite: 11, 14].

```python
import zipfile
import xml.etree.ElementTree as ET

def extract_text_docx_stdlib(filepath: str) -> str:
    """
    Extracts text from a DOCX file using only standard libraries.
    The DOCX is unzipped in memory, and word/document.xml is parsed.
    """
    WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    PARA_TAG = f'{WORD_NAMESPACE}p'
    TEXT_TAG = f'{WORD_NAMESPACE}t'
    
    extracted_text = []
    
    try:
        with zipfile.ZipFile(filepath, 'r') as docx_zip:
            # Read the XML content containing the main document text
            xml_content = docx_zip.read('word/document.xml')
            
            # Parse the XML tree
            tree = ET.fromstring(xml_content)
            
            # Iterate through all paragraph nodes
            for paragraph in tree.iter(PARA_TAG):
                # Extract text from all text nodes within the paragraph
                texts = [node.text for node in paragraph.iter(TEXT_TAG) if node.text]
                if texts:
                    # Join the text runs to form a complete paragraph
                    extracted_text.append(''.join(texts))
                    
    except zipfile.BadZipFile:
        print(f"Error: {filepath} is not a valid ZIP/DOCX file.")
        return ""
    except KeyError:
        print(f"Error: word/document.xml not found in {filepath}.")
        return ""
    except Exception as e:
        print(f"Unexpected error parsing DOCX {filepath}: {e}")
        return ""
        
    return "\n\n".join(extracted_text)
```
This native approach is highly performant, requires no third-party installations, and is exceptionally reliable for standard text extraction [cite: 12, 13].

---

## 3. PPTX Text Extraction Methodologies

Similarly, PowerPoint (`.pptx`) files are OOXML ZIP containers.

### 3.1 Using python-pptx
The external package is named `python-pptx`, and the import path is `from pptx import Presentation`. To extract text, one must iterate through slides, then through shapes, checking if the shape has a `text_frame`, and finally extracting the text.

### 3.2 Fallback: Native Python stdlib Extraction (Zipfile + XML)

Since `python-pptx` is omitted from the Dockerfile, the standard library fallback is required [cite: 15, 16]. The slide data is distributed across multiple files located at `ppt/slides/slide1.xml`, `ppt/slides/slide2.xml`, etc. [cite: 16, 17].

#### XML Structure and Namespaces
Text in PPTX is found within shape trees. The specific tag containing text is `<a:t>`, which relies on the DrawingML namespace: `http://schemas.openxmlformats.org/drawingml/2006/main` [cite: 16].

```python
import zipfile
import xml.etree.ElementTree as ET
import re

def extract_text_pptx_stdlib(filepath: str) -> str:
    """
    Extracts text from a PPTX file using only standard libraries.
    Iterates through all ppt/slides/slide*.xml files.
    """
    DRAWING_NAMESPACE = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    TEXT_TAG = f'{DRAWING_NAMESPACE}t'
    
    extracted_text = []
    
    try:
        with zipfile.ZipFile(filepath, 'r') as pptx_zip:
            # Find all slide files using a regex matching ppt/slides/slide[n].xml
            slide_files = [f for f in pptx_zip.namelist() if re.match(r'^ppt/slides/slide\d+\.xml$', f)]
            
            # Sort slide files by slide number to maintain logical order
            # e.g., slide1.xml, slide2.xml ... slide10.xml
            slide_files.sort(key=lambda x: int(re.search(r'\d+', x).group()))
            
            for slide_file in slide_files:
                xml_content = pptx_zip.read(slide_file)
                tree = ET.fromstring(xml_content)
                
                slide_text = []
                for node in tree.iter(TEXT_TAG):
                    if node.text:
                        slide_text.append(node.text)
                
                if slide_text:
                    extracted_text.append(' '.join(slide_text))
                    
    except zipfile.BadZipFile:
        print(f"Error: {filepath} is not a valid ZIP/PPTX file.")
        return ""
    except Exception as e:
        print(f"Unexpected error parsing PPTX {filepath}: {e}")
        return ""
        
    # Join slides with double newlines
    return "\n\n".join(extracted_text)
```
This implementation seamlessly avoids the need for `python-pptx`, dynamically discovers however many slides exist, and successfully extracts all text frames [cite: 15, 18]. 

---

## 4. Command-Line Interface (CLI) Extraction Methods

When dealing with highly complex layouts or corrupt OOXML/PDF documents, native Python implementations might fail. System-level CLI tools provided in the Docker container serve as robust alternatives.

### 4.1 LibreOffice Headless Conversion

LibreOffice provides a headless mode that does not require a Graphical User Interface (GUI), allowing it to be invoked programmatically to convert DOCX and PPTX files to PDF, or extract text directly [cite: 19, 20].

The exact command syntax for converting a document to PDF via LibreOffice CLI is:
```bash
libreoffice --headless --convert-to pdf input.docx --outdir /path/to/output
```
*Note:* The `--outdir` parameter dictates where the resulting PDF will be saved [cite: 21]. If omitted, it saves to the current working directory. LibreOffice can also convert directly to text using `--convert-to "txt:Text (encoded):UTF8"` [cite: 21].

### 4.2 pdftotext (Poppler-Utils) via Python Subprocess

`pdftotext`, part of the `poppler-utils` suite, is an industry-standard C++ utility for parsing PDFs [cite: 22]. It is exceptionally fast and resilient. To bypass the filesystem and pipe the output directly into Python's memory, you can instruct `pdftotext` to output to `stdout` by using the `-` argument in place of an output file name [cite: 23, 24].

#### Command-Line Usage
To extract only the first 2 pages:
```bash
pdftotext -l 2 input.pdf -
```

#### Python `subprocess` Integration

```python
import subprocess

def extract_text_pdftotext(filepath: str, max_pages: int = 2) -> str:
    """
    Calls the system pdftotext utility to extract text from a PDF.
    Pipes the output directly to stdout and captures it in Python.
    """
    # -l specifies the last page to convert. - represents stdout.
    cmd = ['pdftotext', '-l', str(max_pages), filepath, '-']
    
    try:
        # bufsize=0 ensures we don't hit buffering blocks; capture stdout and stderr
        process = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            timeout=15, 
            text=True,     # Decodes bytes to strings automatically
            check=True     # Raises CalledProcessError if return code is non-zero
        )
        return process.stdout
        
    except subprocess.TimeoutExpired:
        print(f"pdftotext timed out for {filepath}")
        return ""
    except subprocess.CalledProcessError as e:
        print(f"pdftotext failed for {filepath}. Error: {e.stderr}")
        return ""
    except FileNotFoundError:
        print("pdftotext is not installed or not in the system PATH.")
        return ""
```
This is often the most reliable method for complex PDFs [cite: 25, 26, 27]. Passing `-layout` as an argument can also preserve the visual spacing of the document, which can prevent multi-column text from blending [cite: 28].

---

## 5. Keyword-Based Document Classification

Once text is extracted, the next stage is classification into predefined categories: LLM/AI, Quantum Computing, Astrophysics, Biology, and Music History. 

### 5.1 Classification Scope: First Page vs. Full Text
For scientific papers, using the **first page (title + abstract)** is overwhelmingly the best practice. 
*   **Signal-to-Noise Ratio:** The abstract densely packs domain-specific keywords. Parsing the full text introduces immense noise—for example, an Astrophysics paper might use algorithms drawn from AI, causing full-text keyword searches to misclassify the document based on the methods section rather than the core topic.
*   **Performance:** Processing 1,000 words (abstract) is computationally trivial compared to processing 15,000 words (full text).

### 5.2 Discriminating Keywords per Domain
To construct a robust keyword matcher without Machine Learning models, establishing a dictionary of highly discriminating, mutually exclusive keywords is essential:

*   **LLM/AI:** `["large language model", "transformer", "neural network", "deep learning", "machine learning", "nlp", "attention mechanism"]`
*   **Quantum Computing:** `["trapped ion", "qubit", "quantum entanglement", "quantum state", "superposition", "quantum error correction", "qiskit"]`
*   **Astrophysics:** `["black hole", "event horizon", "gravitational wave", "galaxy", "neutron star", "dark matter", "accretion disk"]`
*   **Biology:** `["dna", "genome", "crispr", "protein folding", "rna", "nucleotide", "amino acid", "gene expression"]`
*   **Music History:** `["baroque", "sonata", "mozart", "polyphony", "concerto", "ethnomusicology", "renaissance music"]`

### 5.3 Implementation: Term Frequency-Inverse Document Frequency (TF-IDF)
While simple keyword frequency matching works (counting the occurrence of words), it treats all words equally. A lightweight TF-IDF algorithm assigns higher mathematical weight to rare, domain-specific words and diminishes the weight of common cross-domain words.

Below is an implementation of a TF-IDF scorer utilizing purely the Python standard library (`math`, `collections`):

```python
import math
import re
from collections import Counter, defaultdict

class DocumentClassifier:
    def __init__(self):
        # Category Definitions with initial seed keywords
        self.categories = {
            "AI": ["llm", "transformer", "neural network", "deep learning", "machine learning"],
            "Quantum": ["trapped ion", "qubit", "quantum", "superposition", "entanglement"],
            "Astrophysics": ["black hole", "astrophysics", "gravitational wave", "galaxy"],
            "Biology": ["dna", "genome", "crispr", "protein", "rna", "biology"],
            "Music_History": ["music", "baroque", "sonata", "mozart", "polyphony", "concerto"]
        }
        
        # Build the vocabulary set
        self.vocab = set(word for keywords in self.categories.values() for word in keywords)
        
        # Inverse Document Frequency (Simulated heuristic for offline processing)
        # In a real TF-IDF, IDF is calculated across the entire corpus. 
        # Here, we hardcode IDF weights to strongly favor highly specific terms.
        self.idf = {
            "llm": 4.5, "transformer": 3.0, "neural network": 3.5,
            "trapped ion": 5.0, "qubit": 4.5, "quantum": 2.5,
            "black hole": 4.0, "astrophysics": 4.5, "gravitational wave": 4.5,
            "dna": 3.0, "genome": 4.0, "crispr": 4.5,
            "baroque": 4.5, "polyphony": 5.0, "sonata": 4.0,
            # Assign a baseline score to other terms
        }
        for word in self.vocab:
            if word not in self.idf:
                self.idf[word] = 2.0 

    def preprocess(self, text: str) -> list:
        # Convert to lowercase and extract words/phrases
        text = text.lower()
        # For simplicity in this demo, we check exact phrase matches by keeping the text as a single string 
        # for phrase counting, and tokenizing for single words.
        return text

    def classify(self, text: str) -> str:
        if not text.strip():
            return "Unclassified"
            
        processed_text = self.preprocess(text)
        scores = defaultdict(float)
        
        for category, keywords in self.categories.items():
            for kw in keywords:
                # Term Frequency (TF): Count occurrences of the keyword/phrase
                tf = processed_text.count(kw)
                if tf > 0:
                    # Score = TF * IDF
                    weight = tf * self.idf[kw]
                    scores[category] += weight
                    
        if not scores:
            return "Unclassified"
            
        # Handle edge cases where multiple topics overlap (e.g., Quantum Machine Learning)
        # Select the category with the highest aggregated TF-IDF score
        best_category = max(scores, key=scores.get)
        return best_category
```

#### Edge Cases
Papers titled "Quantum Machine Learning Algorithms for DNA Sequencing" span three domains. The TF-IDF weight mitigates this. Since "quantum" and "dna" might have specific weights, the scoring system will aggregate the mathematical dominance of the words found in the abstract to break the tie. In highly contentious multi-disciplinary papers, one may implement a secondary threshold: if the top two categories are within 10% of each other, route the document to a `Multidisciplinary_Review` folder.

---

## 6. Robust File Operations and Folder Management

Once a document is successfully classified, it must be physically routed to its corresponding directory.

### 6.1 Creating Destination Folders
The `os.makedirs()` function is the optimal tool for creating directory trees. Using the parameter `exist_ok=True` ensures that no `FileExistsError` is thrown if the directory was created in a previous script run [cite: 29].

```python
import os

def create_folders(base_dir: str, categories: list):
    for category in categories:
        folder_path = os.path.join(base_dir, category)
        os.makedirs(folder_path, exist_ok=True)
```

### 6.2 The Anatomy of `shutil.move()` vs `shutil.copy2()` + `os.remove()`

When moving files, developers often debate between using `shutil.move(src, dst)` versus performing a manual `shutil.copy2(src, dst)` followed by `os.remove(src)`.

#### Theoretical Mechanisms
*   **`shutil.move(src, dst)`:** This is the high-level, standard approach. Under the hood, `shutil.move` checks if the source and destination reside on the exact same mounted filesystem [cite: 29, 30]. If they do, it executes `os.rename(src, dst)`, which invokes the operating system's native rename capability. This is an **atomic** operation (POSIX requirement) that takes virtually zero seconds, as it only alters file pointers on the disk without physically moving the byte data [cite: 30, 31].
*   **Cross-Filesystem Fallback:** If `shutil.move` detects that the `src` and `dst` are on different filesystems (e.g., moving a file from a local Docker volume `/data` to an external mounted NFS `/mnt/storage`), `os.rename` will raise an `OSError` (`EXDEV`) [cite: 30, 31]. `shutil.move()` smartly catches this and automatically falls back to `shutil.copy2()`, copying the file data and metadata, and finally executing `os.remove(src)` once the copy is verified complete [cite: 29, 31].

#### Recommendation
Using `shutil.move()` is drastically superior and safer. It preserves filenames, utilizes atomic operations wherever possible, and manages metadata automatically via `copy2` fallback. Writing a custom `copy2` + `remove` script is essentially reinventing the wheel and runs the risk of leaving orphaned files if the process crashes midway between the copy and the remove [cite: 31].

#### Handling Special Characters in Filenames
Scientific papers downloaded from the internet often contain special characters in their filenames (e.g., `%20`, `:`, `,`, non-ASCII characters). Before moving, it is advisable to sanitize the filenames to prevent OS-level path parsing errors.

```python
import shutil
import re
import os

def sanitize_filename(filename: str) -> str:
    # Keep alphanumeric characters, dots, dashes, and underscores
    sanitized = re.sub(r'[^\w\.\-]', '_', filename)
    return sanitized

def route_file(src_path: str, dest_dir: str):
    filename = os.path.basename(src_path)
    safe_filename = sanitize_filename(filename)
    dest_path = os.path.join(dest_dir, safe_filename)
    
    # Handle filename collisions
    counter = 1
    while os.path.exists(dest_path):
        name, ext = os.path.splitext(safe_filename)
        dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")
        counter += 1
        
    try:
        # Move the file, handling atomic OS renames and cross-filesystem copies automatically
        shutil.move(src_path, dest_path)
    except Exception as e:
        print(f"Critical error moving file {src_path}: {e}")
```

---

## 7. Integrated Pipeline Architecture

To combine the methodologies outlined in this report, the following logic models an integrated pipeline:

1.  **File Ingestion:** Iterate over all files in an incoming directory. Identify the file extension using `os.path.splitext()`.
2.  **Text Extraction Stage:** 
    *   If `.pdf`, use PyPDF2 for speed. If extracted text length < 50, use the `pdftotext` subprocess.
    *   If `.docx`, use native `zipfile` extraction.
    *   If `.pptx`, use native `zipfile` extraction.
3.  **Classification Stage:** Pass the extracted string to the `DocumentClassifier.classify()` method.
4.  **Routing Stage:** Sanitize the filename, check for collisions, and execute `shutil.move()` to place the file in the designated topic folder.

This structure forms a cohesive, fault-tolerant Python utility module capable of operating purely on standard libraries where necessary, while capitalizing on efficient C++ binaries (`poppler-utils`) and optimized Python packages (`PyPDF2`) to parse massive document datasets for classification and sorting.

**Sources:**
1. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEeTqa9Kg8RCx1XhmyENiwrwJ8w8miTlLXAunIx4500yzBFr3dnM5QVkm66KwKptjxeJMXFOxRyrAFU7gcZxdoyp3WV7Z6Q7i4zxgqh7qHIkVGNWI6pKkSRDtlljpuVI3i5m-ndAOqjKrBkOwddBcgGg==)
2. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7QE2rPk9HQv1AMQMywUXOYTZoh2ORmIPIlDQuHs5Q6fE1Wv-FLI9pEP6o6dGfdVXpaRV0ubWAxEM4b3sQ-S3VDTnBwVfvFMjZFSvUfb_ykHSpLhfXdlRySweOXNH9CEBcJm6F0o1eFcKXK40Mdw==)
3. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG97Gaq9JbLWIKLZp8hrRBPB1q7WZ2tOKG40OTm6ZGMFUa3CsOH4HUU-J7xqSjnVlAxtYGJEUXdgr0R5_vW9jomM4s5nEjSEBgbei7i5QHLcnQbNfwGww==)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGQol6_zsOUzkS2mLapuIOYJYvbbCdjiz8WAe2vF7W13n5JPA-yfODM4-7g7vdd581PUlygbRf-TjiReaM5gIt5_L_rV6Qr2SgJtTqdG17jujtfAXckE3HHmZD3TEAtbxBt8EiPeQ==)
5. [snyk.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-84-VS2lfpv-6eXGD_e90lD--IKOPe_Cy47UM7nrCRJyRg94RzYhVkCZudxBUOO8sQ0m5RiAynG1wwqncNJv7O5nqbWufnaqK6ErKlfdTzeyu9WMrlSTeNyShBpmrtPIGP31J8K16)
6. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHC_yStKVPsao-qqSDLMbJHKpaRcAVGEJdwyb75v4th8xzLn6-Mz2Po-IlvkEqytfCx6V1xhkmdE3l4n0z8EiGSLiHjaP6Ip5KL5lZrb26agcmnJdr_Ct_fBAQ=)
7. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSRoJosmhYfpr_ra_Uq85gfIFLKxfcVcFf8GNh9VkVD0-kka2RM1bkzUzCXxvV_7W5CAT8czrRDBlMzIF3ss966_TL6NBUbMXmmuXGToW3Tx27DdGcRVbhetxAwr6ioa2XfOrs8w==)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdJjXfqXK7hdeAvyD5lIlnCmPPLS1jNC7pxYhBn1tvXpUV_w9svoua79vl5Bn_DaBhJl3Tog4no9Ru2LvW-bZeS3NYWTJOM2lUjXbqzps5glBOxP7Rq1bRsDg7NsXz0YUgUeb1Mw==)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcNGgbmFeTRDNDOop8CszTGAd9OaGE2oJ3W5Y-q8F_7hx2gLbXn2rquw6-GvEj78WAsVjeaVf2C2Bk9zRhAZyMe78KUZXfh5kGyBjnMU0RHOr2eLHPepP8HiklZbktv5nrnLz_wI8vwmHoOQ==)
10. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE03qkKc-KODVgiKjRAbH9TFeiuBRU7VBrewl-FlxYUcMiOuNLoqsHMwZw59XqchpSaAFUOKtvVpuaOTGZhDiIGISgX0UXA313dVUUsPG8pXzNTKyQPu8_eYpHXzT5Q6a9aQcjA0_9HQD08LV7cWki0H4NJbEU_DcDItTKeaCAOehNy7gHNcK-5hnfOxy4t7b4g7kGx8hKkKqa9sLo=)
11. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG5PZL1gORlsFLqMtcMWHq6lBbw3N8USlqfnadnB829oWGZAUQLObYaIdbERjmsGc0uoxNGnmpozqQQIzJYAPySF1vVms0L8k3bx1pXp9c3Cgg8DCvmV1l-Ta_jMSsFjlz0jPxca5el8lbGfv5qV9PK9j-Vr5jSkyg_w5P2fRkpWultODrJLs7oWjAWt1APChwsHGQXxpfG8iLjEVb_ANYg)
12. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCu1gRH0XCXQ4448cNd2787ZvGk1LHqGGJmTBn_QzsLSq99anjYNcTRBMjXHQVRs8OTalb6sbkKDoIeo7Uovn1Br5qr9gbIKv-X8XXXsG4aoO-A15wIpFP2lTjuj5cee04JmHB6J0pvOow2ZfngdH93tWPWuuQlhB-JGYg9gw3x2AWcM1qnwU8p17ivXDd2PLGlYzeFMKMaoRU)
13. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6VnBV5nADfLYNSFEbcfXuN2L1vX9URrhJBHLE-0inVApNLApTz2pTzMuHZxBw4IlbAf21dwTMJZnQ_iAQBzaKCr7B8OYZiOssz6-EUjTYYOdRhghpXotXehwFxy7evwMfWqIEcK5OnDOQheWZ_efeGBBMfnRMl8el)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhnsNC0vaXVqxHjPsgQfn3i-Hdb0LddWr8XRS3ymHaakthMtk3JeFsoXQbAxNrahcpG5ZyASIAqTxog7EjA5Xdpyj6uldWqHvByBXavTpaRc73LOBonTGf24lTY_EK2bYVNnsha4tgsosKNDeZP3US5wUi7sb4pA_XhYm7AZ1yo_pSA5pbuITGI5vR_dTu)
15. [quora.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXjfP88Lik768VY5QtfGGkK4S6TrgmAuz0WpEegYTGLteKsbnvMZ_XpDO_hnQXZWQqgVDviq7ufPmFHQQFxWV6v9ZxPFVTBELZ4IFd7XI_PYdyxGTf3MAIR3BDuMNG65trIqvMzZqst45VrLT61Vza921l)
16. [otranslator.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF237Md5Dg2BM4YvZeZ76PcxmqZlSaJWiuTKJPysUrz8ySS9rDTyF0Rq4UVWq0a4S1GBE8J_Px-sna1jAYL-OAMujK2uAikFb2UrYYoSe9TGTuGjrnyU4rqwGwZLDd6rZWnRHFxLAubA3ruzh9nnU4POIfupHAet97HouOJkyHOxwYJXA==)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFppMCc5pmX523EWypQTy81ZVFb-e1Rq7neBctmwZr7tGHRrom7AY93e6-zzc4NhECF6pogxlLy9WvdnlO_D0yp6Rkv3pSvxDEdObnobLXoS4lm-gbhC10BZT5Cr1X7HJqgJqRjfDpO7jFgqr9nEmY7NcmIXisIn_oF7LeI97dYCZJwGSoJymaEB_BJLvqy38JHxMFjXG7xuFGYl4FKerXEQyB-JIZLhT-lWOcFxdHL)
18. [superuser.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG9H-LSeq2LNgEEN_jbbrd0adwBRz88ouKgdDlVquBPALGF8QUPm1_VT3F0v4slsz0fRJDMFpa5wB41K7ACdleMKZ6qnTQJ01Ud8wzNQm7MNQxbsL6MvdeTedOIq-OkdR90faf4ppdcV_VBldoI0WVF91MNFw==)
19. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFE6coJRbWHl5rE25euU5RwbY5YpMESYYeEqDpL95ACjCUayiJxHBodjBEMNErsfHy6CRguYVe0ct3WMOunXa24_km1294ytiudWxXu_XJIZK5bNvckEiUjBd-viZjnasGp171L3sYCivGE9zrs79b2PLc3YVIE5Q==)
20. [xbwbc.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHt9_xYWst-9y4b8ZYmdcMO7L312z4wzl1x1epky8Ezy6w6aU_LSy5saOJ6Fc7tEUoqP3olFl4WfYE2UqcI89ubakXLvkiAz8HjEVFDXwKC94NbGInQl0MCUwuxkX8DeWfGz6ld7JM=)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFcOhTXfFcY8Xg0altDsJc63_c008-9wqe9e_1UPSlgDsAVDULWj2qxxrkBTaCMkeB-GpMRbodr7PXDdmNr6FHbMC3mFexpmvqyRed6wqFTPQoi2_8W8HFXRjbyH-dYFREiFO5QeoTnXYLsRMcmgi64x5q3SpKHhedQemt4Hi2ITlNVSoLdtXDjKVlgeYiUt40O4uZ8TrHUGkUAPHyuQldwUqOGcrAQAIE_Q==)
22. [linuxcommandlibrary.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgeI5j_811qa8hpf_VpHqcIYeziPO5YwTOdcBrKsJ9P_sRjhG3SJ3SONA4DKdptGOX445PBp2TGnuU8xF4yqeY4vku034kbGDWkh3EoQUp2yf5XDsq5TVys6Fj7VmqOwuX5EI=)
23. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUc55PDNQFH48LJZByOTp1ThqaMrNFqp0-53JPrMU10wF-6hKPT1cpITuP8_6WXJhqUIk3wG-mvYJwWFczMKv9_bLlXyxzRz2wzG4_xB2W23odKr10p8aWkpi3_1H0XUy8KBsBNGbFJLymBds0CmOF)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9F-e5X63Qqz8G9jzLnhCh_fuDUMMWFqHL2zNmOyIGDPI1fTRWnaRDvF8A_AuwGfkksexturW4h0ohf4vUqtlbQiiznavshHxQlyV35BK2ZqMDYFLIiB_tyrlLg13R-GeltoUXc_Zi_Hxy6pbAN8n7tz-wXSwmjSL0qcFZoCtUfDoJPb11E4jHkX4zI6M=)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHAPV61jkgHyY27IXdMcmZ-Ny8AwE39VrSKahEkPol676xbOVyXKItDcm8u1ca1tcyLkX3ll4vf7KzTlmR_nnr2O4rqYywE1wxIEVRc5IcYFZzzdGBg24Xb79f70-zCO_zfT7nXIADBrLXzXfPs-rrybm7Gjz5-x0xYkRhxYymqDwO0HZ0GwdBWiBvHkzyGxXAAxUFnd5YMV2PFLbbTpzQzkO5a0q7iJdxQn6r7T0mLnRwf)
26. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7o8f74GYPQrktJaS3FiummWPx5ojFx_ui_3izB9UEubV3ItgaWzN7XdlpvyFWYY7_GLgmQPjQ47cs8_SBTrC96t1_LdBA9BDJHj2CYvsZ79HSTCCDb6-FEpqV9M9PLCi1QShnNvghhLKKCnpXQOOudC9Bu1BsnJg5wttre1jXTA_5_JkgPx-LCXVRNnRJaMBYnSORli5Hssnmvg==)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE3PlidRyrfLs4Wjn8R-DMxmvj7-_79rULrTmMpDrzAgLZcnM_7GeyJNq3CWRh4zGwimh9PSc3TaTyOrPSzLbPCBO9a2Wcz6c_R8NSMTSC7GkL5YR5Ocmex3rPt3nlGcBmM8Wl8PxotQxFq3vB_HK-URSTNU81BtwTaV7T9ni_DvuF0vjR0zvbSVg5HEK_y)
28. [torrocus.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEy394r4aIrJFNQC1T23fws_c9AE5UKijkzUGnIYGZzc_OWTo17_xyY14LCfgeHULf--Kg2h23KPwlObJInp36m6dz4VWy-LBbore2Ym-OkCYWUZqk0iSciRZW9I1hHpcDncHxRQOSXEbkF0Rf65WvKFuI=)
29. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG9zoS-O1jCtIf0ZKXZnPyQ1sWEgaTyxMbOXHJ0tFSi3BfoidCLNavxsdfzY3TGLkGfxXmrzgqt3cHqsupdWdFzab8Z2xl1yg78a8jPupL3crqJHeJUyLll86fP6tmd5f6hNcPpMKsVOhduEeAEAMr42oNr)
30. [giedrius.blog](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7ffJCmqsx0k-duyPFeop-TrZO00PFVx1mUmDYrJbbmBVkoPF0vWrJjF59FXXD8RFIwlJDPqq5sJG66WZjqq0vgdWsNKUINtGlX7n5an-xKhDIaIib2qYhID8wef_VVXotYz58EikFzxYc2LDIy4hA3rHuSNipt_5xFs3Mwl28Y5AzB-aC3cumEtp0JhTFYS33kBeAe_WTav5OkwLI)
31. [alexwlchan.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEuV8qwxa84Gr0BwXjikoMh66yfsH2SYw_4gkJ0zhSseMxmHaAxIJP1XuB_skq9l-ccPz2ngrMchtwkc17NZTk8QXJGvlW8F7Vl1B3plBksV_Ok_5bhlr5B7-mdUXoEMf5CplHY-kh-LpqsWjaXPR0LYmAceOPmjwkJA==)
