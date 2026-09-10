# Programmatic Redaction and Anonymization of PDF Documents Using PyMuPDF in Python

**Key Points:**
*   **PyMuPDF 1.24.0 Capabilities:** PyMuPDF (often imported via its legacy alias `fitz`) provides comprehensive tools for opening, reading, modifying, and permanently redacting PDF documents [cite: 1, 2]. 
*   **Physical Text Removal:** Unlike simplistic visual masking, PyMuPDF's `apply_redactions()` physically purges the underlying characters from the document's content stream, ensuring sensitive data cannot be recovered by copy-pasting or automated scraping [cite: 2, 3].
*   **Regex Limitations and Workarounds:** The native `search_for()` method does not support regular expressions [cite: 4]. Advanced pattern matching requires extracting spatially-aware text outputs (`"words"` or `"dict"`) to bridge the gap between logical regex matches and visual bounding boxes [cite: 4, 5].
*   **Comprehensive Anonymization:** Achieving double-blind compliance in academic papers necessitates redacting visible text (author names, affiliations, arXiv IDs), purging document-level metadata (both standard dictionaries and XMP streams) [cite: 6, 7], and deleting identifiable hyperlinks [cite: 2].
*   **Safe Document Saving:** The redaction process is only secure if the document is saved into a new file using aggressive garbage collection (`garbage=3` or `4`) and stream deflation (`deflate=True`), which permanently strips unreferenced objects and orphaned text data [cite: 8, 9].

**Executive Summary**
The imperative for robust document anonymization is particularly acute in academic publishing, legal proceedings, and financial disclosures. The portable document format (PDF), while ubiquitous, possesses a notoriously complex internal architecture comprising cross-reference tables, deeply nested object streams, and separate visual and logical layers. Simple methods of obscuration—such as drawing black rectangles over sensitive text—do not alter the underlying text streams, leaving the "redacted" information entirely vulnerable to extraction. Programmatic, true redaction requires parsing the document's display list, calculating exact spatial bounding boxes, marking these areas, and commanding the underlying library to sever the text objects from the file structure.

**Methodological Approach**
This report explores the exact methodologies required to construct a reusable, production-ready Python utility for PDF anonymization. Utilizing PyMuPDF (version 1.24.0), we deconstruct the text extraction APIs, the redaction pipelines, and the handling of edge cases such as multi-line spans, corrupted fonts, and the preservation of crucial non-text elements like scientific figures. Furthermore, we evaluate supplemental libraries, notably `pdfplumber` and `pypdf`, to assess their complementary strengths in layout analysis and text scraping prior to redaction [cite: 10, 11].

---

## 1. Text Extraction and Search Operations in PyMuPDF 1.24.0

### Library Import and Initialization
In version 1.24.0, the package is distributed on PyPI under the name `pymupdf` [cite: 1, 12]. Historically, the library was accessed exclusively via the `import fitz` alias, a nod to the original "Fitz" rendering engine inside MuPDF [cite: 13]. Modern conventions support both `import fitz` and `import pymupdf` [cite: 12, 14]. For the sake of extensive compatibility and alignment with community codebases, `import pymupdf` is increasingly preferred, though `fitz` remains prevalent in official documentation and object references.

Opening a document is achieved via `pymupdf.open()` (or `fitz.open()`), which accepts a file path or a bytes stream [cite: 6, 13].

```python
import pymupdf

# Open a document from a local file path
doc = pymupdf.open("academic_paper.pdf")

# Iterate through pages (0-indexed)
for page_num in range(len(doc)):
    page = doc[page_num]  # Or doc.load_page(page_num)
    # Perform operations on the page
```

### Exact Text Search API
The most direct method to locate specific strings visually rendered on a page is `page.search_for(text)`. 
*   **Method Signature**: `page.search_for(text, quads=False, hit_max=16, ...)` [cite: 4, 15].
*   **Return Type**: By default, it returns a list of `pymupdf.Rect` objects [cite: 4, 16]. If `quads=True` is passed, it returns a list of `pymupdf.Quad` objects. Quads are essential if the text is rotated or skewed, but for standard academic papers, `Rect` (rectangles) are generally sufficient.
*   **Behavior**: The search is natively case-insensitive and handles multi-line hyphenations [cite: 16]. However, it strictly searches for exact substrings and *does not support regular expressions* [cite: 4].

```python
# Returns a list of Rect(x0, y0, x1, y1) representing bounding boxes
bboxes = page.search_for("John Doe")
for rect in bboxes:
    print(f"Found 'John Doe' at coordinates: {rect}")
```

### Text Extraction APIs
To extract the complete text from a page, PyMuPDF provides the highly versatile `page.get_text(opt)` method [cite: 4, 17]. The `opt` parameter dictates the level of spatial and formatting detail returned:

1.  **`"text"`**: Returns plain string text in the document's logical reading order (or sorted heuristically if `sort=True` is provided) [cite: 4, 5].
2.  **`"blocks"`**: Returns a list of text blocks (paragraphs). Each item contains the bounding box, text, block type, and block number.
3.  **`"words"`**: Breaks the text down into continuous strings without spaces. Returns a list of tuples: `(x0, y0, x1, y1, "word", block_no, line_no, word_no)` [cite: 18, 19]. This is extremely useful for spatial regex matching.
4.  **`"dict"`**: Returns a hierarchical Python dictionary containing `blocks`, which contain `lines`, which contain `spans`. Spans represent continuous text with identical font properties (font name, size, color, flags) [cite: 4, 5].
5.  **`"rawdict"`**: Similar to `"dict"`, but descends one level deeper to provide coordinates for individual *characters* [cite: 4].

```python
# Extracting words with coordinates
words = page.get_text("words")
for w in words:
    rect = pymupdf.Rect(w[:4]) # First 4 elements are x0, y0, x1, y1
    text_val = w[cite: 1]
```

## 2. The Redaction API in PyMuPDF

Unlike word processors, PDFs paint text characters onto specific coordinates. True redaction requires removing those painting instructions. PyMuPDF handles this via a strict, two-step API: `add_redact_annot()` and `apply_redactions()` [cite: 2].

### Step 1: `page.add_redact_annot()`
This method inserts a specific PDF annotation type (Redact) onto the page. It visually highlights the target area in the document viewer, signaling what *will* be removed.

**Exact Parameters**:
*   **`quad`**: The area to redact. This can be a `Rect` (from `search_for`) or a `Quad`.
*   **`text`**: (Optional string) Text to place over the redacted area (e.g., `"[REDACTED]"`).
*   **`fill`**: (Sequence of floats) The fill color of the rectangle after redaction. Standard RGB values range from 0 to 1. To create a black box, use `(0, 0, 0)`. White is `(1, 1, 1)`. If `None`, the background is left transparent [cite: 2, 15].
*   **`text_color`**: (Sequence of floats) Color of the replacement text. Default is black [cite: 2].
*   **`cross_out`**: (Boolean) If `True`, draws two diagonal lines across the redaction rectangle [cite: 2].

### Step 2: `page.apply_redactions()`
Calling this method processes all pending redaction annotations on the page. It physically recalculates the content stream, dropping any character whose bounding box intersects with the redaction rectangles [cite: 2]. 

**Crucial Parameters**:
*   **`images`**: Controls how images overlapping the redaction area are handled. By default (`pymupdf.PDF_REDACT_IMAGE_PIXELS` or `2`), it blanks out overlapping image pixels. If set to `pymupdf.PDF_REDACT_IMAGE_NONE` (or `0`), it explicitly ignores images, preventing the accidental deletion of scientific figures [cite: 2, 8, 9].
*   **`graphics`**: Controls vector graphics (line-art). Default is `PDF_REDACT_LINE_ART_REMOVE_IF_COVERED` [cite: 2].
*   **`text`**: Controls overlapping text. Default is `PDF_REDACT_TEXT_REMOVE` [cite: 2].

**Permanence**: `apply_redactions()` *does* permanently remove the underlying text from the page's logical structure. It is not merely a visual cover. However, the data remains recoverable in the file's historical cross-reference tables unless the document is correctly saved (see Section 7) [cite: 2, 9, 20].

### Working Example: Redacting by Text Search
```python
import pymupdf

def redact_exact_string(doc, target_string):
    for page in doc:
        # Search for all occurrences of the string
        bboxes = page.search_for(target_string)
        
        for rect in bboxes:
            # Add redaction annotation (black fill)
            page.add_redact_annot(rect, fill=(0, 0, 0))
        
        # Apply the redactions, keeping images safe
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
```

## 3. Implementing Regex-Based Text Search and Redaction

Because `search_for` does not natively parse regular expressions [cite: 4], anonymizing academic identifiers (like arXiv IDs or complex email formats) requires a custom approach. We must extract the text, run Python's `re` module, and map the matches back to their spatial coordinates.

### Strategy 1: Using `page.get_text("words")`
The `"words"` output is highly effective for regexes that do not span spaces (like emails or URLs) [cite: 18, 21].

```python
import re
import pymupdf

def redact_regex_words(page, pattern):
    regex = re.compile(pattern)
    words = page.get_text("words") # Returns (x0, y0, x1, y1, word, block, line, word_no)
    
    for w in words:
        text_string = w[cite: 1]
        if regex.search(text_string):
            rect = pymupdf.Rect(w[:4])
            page.add_redact_annot(rect, fill=(0, 0, 0))
            
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
```

### Strategy 2: Multi-Word Regex via Text Mapping
If the regex targets multi-word phrases (e.g., `"Accepted at [A-Za-z\s]+"`), checking individual words fails. The recommended workaround is to extract the full plain text, execute the regex search to find the matching literal strings, and then feed those strings back into `page.search_for()` [cite: 4].

```python
def redact_regex_multiline(page, pattern):
    regex = re.compile(pattern, re.IGNORECASE)
    full_text = page.get_text("text")
    
    # Find all exact string matches of the regex in the full text
    for match in regex.finditer(full_text):
        exact_string = match.group()
        
        # Now search the page for the exact visual locations of this string
        bboxes = page.search_for(exact_string)
        for rect in bboxes:
            page.add_redact_annot(rect, fill=(0, 0, 0))
            
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
```

## 4. Handling PDF Elements: Headers, Footers, and Metadata

### Redacting Headers and Footers
Academic papers frequently feature repeating author names in the header or footer. Because these are just text objects positioned near the top or bottom of the page, they are naturally caught by spatial or string redactions. However, if you wish to blank out *all* headers/footers indiscriminately, you can redact by geometric area [cite: 2, 8].

```python
def redact_headers_footers(page):
    page_rect = page.rect # Rect(0, 0, width, height)
    
    # Define header area: Top 10% of the page
    header_rect = pymupdf.Rect(0, 0, page_rect.width, page_rect.height * 0.1)
    
    # Define footer area: Bottom 10% of the page
    footer_rect = pymupdf.Rect(0, page_rect.height * 0.9, page_rect.width, page_rect.height)
    
    page.add_redact_annot(header_rect, fill=(0, 0, 0))
    page.add_redact_annot(footer_rect, fill=(0, 0, 0))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
```

### Accessing and Modifying Standard Metadata
The PDF specification maintains a standard metadata dictionary natively accessible via PyMuPDF.
*   **Read**: `doc.metadata` returns a dictionary [cite: 14, 22].
*   **Exact Keys**: `'format'`, `'title'`, `'author'`, `'subject'`, `'keywords'`, `'creator'`, `'producer'`, `'creationDate'`, `'modDate'`, `'trapped'`, `'encryption'` [cite: 17].
*   **Write**: `doc.set_metadata(new_dict)`. Omitted keys remain unchanged; to clear a key, pass an empty string `""` [cite: 14, 22].

```python
def scrub_standard_metadata(doc):
    clean_meta = {
        "author": "",
        "title": doc.metadata.get("title", ""), # Keep title, or wipe it
        "subject": "",
        "keywords": "",
        "creator": "Anonymized via PyMuPDF",
        "producer": "Anonymized via PyMuPDF"
    }
    doc.set_metadata(clean_meta)
```

### Handling XML/XMP Metadata
Modern PDFs (especially those generated by Adobe or LaTeX suites) contain an auxiliary XML metadata stream (eXtendable Metadata Platform - XMP). This stream duplicates the standard metadata and often retains information even if `doc.set_metadata()` is used.
*   **Access**: `doc.get_xml_metadata()` [cite: 23].
*   **Modification**: While `doc.set_xml_metadata(xml_string)` allows arbitrary XML replacement [cite: 24], the safest anonymization route is total deletion using `doc.del_xml_metadata()` [cite: 7].

```python
def scrub_all_metadata(doc):
    scrub_standard_metadata(doc)
    doc.del_xml_metadata() # Safely purge the XMP stream [cite: 7]
```

## 5. Academic Paper Anonymization: Specific Patterns

To automate double-blind review preparation, the utility must target specific academic identifiers using targeted regex and keyword lists.

### 1. Institutional Affiliations and Email Addresses
Emails consistently follow standard patterns. Institutions often end in `.edu`, `.ac.uk`, or contain words like "University", "Institute", or "Department".
*   *Email Regex*: `r"[A-Za-z0-9\.\-+_]+@[A-Za-z0-9\.\-+_]+\.[A-Za-z]+"`
*   *Affiliation Keywords*: `["University", "Institute", "Laboratories", "Dept.", "Department"]`

### 2. arXiv Identifiers
Papers pre-published on arXiv carry distinctive identifiers.
*   *Current Format Regex*: `r"arXiv:\d{4}\.\d{4,5}(v\d+)?"`
*   *Legacy Format Regex*: `r"arXiv:[a-z\-]+/\d{7}"`

### 3. Conference/Venue Acceptance Statements
Headers often leak acceptance strings.
*   *Regex*: `r"(Accepted|Published|To appear|Presented) (at|in|for) [A-Za-z0-9\s]+"`

### 4. Self-Referential Citations and Grant Acknowledgments
Grant identifiers are uniquely sensitive. Words like "Supported by grant", "NSF", "ERC", or "Funded by" indicate a grant block.
*   *Regex for grants*: `r"(Grant|Funded by|Supported by) [A-Za-z0-9\-]+"`
*   *Regex for self-citations*: `r"(In our previous work|As we showed in|We previously demonstrated)"`

## 6. Managing Links and Annotations

URLs embedding author names or institutional identifiers represent a major breach of anonymity. PDF hyperlinks are treated as Annotations (type `LINK`).

### Finding and Deleting Links
*   `page.get_links()` (or `page.links()`) returns a list of dictionaries. Each dictionary contains a `"uri"` key (the web address) and a `"from"` key (the `Rect` describing where the link is clickable) [cite: 2, 25].
*   `page.delete_link(link_dict)` removes the clickable area from the page [cite: 2, 25].

```python
def scrub_hyperlinks(page):
    links = page.get_links()
    for link in links:
        uri = link.get("uri", "").lower()
        # Remove specific link types or all links
        if "arxiv.org" in uri or ".edu" in uri or "github.com" in uri:
            page.delete_link(link) # Removes the interactive link [cite: 25]
            # Redact the underlying blue text visually
            page.add_redact_annot(link["from"], fill=(0, 0, 0))
            
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
```

## 7. Common Pitfalls, Edge Cases, and Document Saving

### Pitfall 1: Visual vs. Extracted Text (Ligatures and Encoding)
Sometimes `search_for()` fails to find text visible to the eye. This occurs when:
1.  **Broken Fonts**: The PDF uses custom font encodings without providing a `/ToUnicode` map. The text extracts as replacement characters (`U+FFFD`) [cite: 1, 4]. Diagnostic check: extract text with `"rawdict"` and look for `0xFFFD`. If broken, OCR is the only fallback [cite: 4, 10].
2.  **Ligatures**: "fi" or "fl" might be encoded as single characters.
3.  **Rasterized Text**: Text rendered as images cannot be searched natively.

### Pitfall 2: Multi-line Text Spans
If a redacted target spans across a line break, `search_for` returns multiple `Rect` objects (one for each line segment) [cite: 16]. The script must ensure it iterates over the entire list returned by `search_for` and applies annotations to each rectangle.

### Pitfall 3: Batching `apply_redactions()`
While you can add multiple redaction annotations sequentially on a page, `apply_redactions()` processes all pending annotations at once. It is highly efficient to batch `add_redact_annot()` calls and invoke `apply_redactions()` *only once per page* at the end of the page-processing loop [cite: 9]. Calling it repeatedly per word causes extreme document bloat and performance degradation, as it continually decompresses and recompresses the page stream [cite: 9].

### Pitfall 4: Preserving Figures (`images` parameter)
By default, `apply_redactions()` blanks out image pixels if a redaction rectangle overlaps an image [cite: 9]. In academic papers, text search bounding boxes often inadvertently graze the transparent bounding boxes of nearby mathematical figures or charts. Passing `images=pymupdf.PDF_REDACT_IMAGE_NONE` (which corresponds to integer `0`) explicitly safeguards all images from modification [cite: 2, 8].

### Pitfall 5: Saving the Modified PDF (Critical Security Step)
Using `doc.saveIncr()` (Incremental Save) simply appends changes to the end of the PDF file. The original, unredacted objects remain perfectly intact and accessible via PDF historical viewers [cite: 9].

To ensure permanent, secure destruction of the redacted data, you **must** use `doc.save()` with aggressive garbage collection and deflation:
*   **`garbage=3`** or **`garbage=4`**: Rebuilds the cross-reference tables, merging duplicate objects, and thoroughly removing unreferenced objects (like the text you just redacted and XML metadata) [cite: 6, 9].
*   **`deflate=True`**: Compresses the PDF streams, which helps mitigate the file size bloat caused by text-rebuilding and ensures no plaintext fragments linger uncompressed [cite: 9].

```python
# The ONLY secure way to save a redacted PDF
doc.save("anonymized_output.pdf", garbage=4, deflate=True)
```

## 8. pypdf and pdfplumber as Supplementary Extraction Tools

Before applying physical redactions with PyMuPDF, one might wish to use highly specialized layout-aware libraries to perform complex analysis (e.g., distinguishing between an author block and the abstract).

### pypdf (Version 4.0.0+)
`pypdf` is a pure-Python library, entirely free of C-dependencies [cite: 26]. While it excels at basic PDF manipulations (merging, splitting, encryption) and standard metadata extraction, its text extraction capabilities are linear. It extracts text streams blindly, making it highly susceptible to mixing columns in academic papers [cite: 10, 27]. It **cannot** perform physical redactions [cite: 11, 28].

### pdfplumber (Version 0.11.0)
Built atop `pdfminer.six`, `pdfplumber` is an exceptional tool for layout-aware data mining [cite: 26, 28]. 
*   **Strengths**: It analyzes the spatial positioning of text elements, understanding column structures, table grids, and visual reading orders [cite: 29]. If you need to accurately parse an academic paper's two-column format to reliably extract the Affiliation block (which often sits immediately below the Author names), `pdfplumber` is vastly superior for the initial coordinate detection [cite: 27, 29].
*   **Weaknesses**: `pdfplumber` is significantly slower than PyMuPDF due to character-level processing [cite: 11]. Furthermore, it has **zero capabilities** for writing, editing, or redacting PDFs [cite: 11]. 

**Synergistic Use**: A sophisticated pipeline uses `pdfplumber` to safely parse the complex logical layout of an academic paper's front page, identifies the bounding box coordinates of the author/affiliation tables, and then passes those coordinates back to PyMuPDF to execute the physical `add_redact_annot()` and `apply_redactions()`.

---

## 9. Complete End-to-End Code Pattern

The following module implements a complete, reusable Python utility designed for academic PDF anonymization. It incorporates all best practices: exact text matches, robust regex processing, metadata scrubbing, hyperlink sanitization, proper page batching, and secure garbage-collected saving.

```python
import pymupdf
import re
import os

class AcademicPDFAnonymizer:
    """
    A utility module for programmatically redacting and anonymizing academic 
    PDF files using PyMuPDF >= 1.24.0.
    """
    
    def __init__(self, exact_strings=None, regex_patterns=None):
        """
        Initialize the anonymizer with patterns to target.
        """
        self.exact_strings = exact_strings or []
        
        # Default academic regex patterns
        default_regexes = [
            r"arXiv:\d{4}\.\d{4,5}(v\d+)?",               # Modern arXiv ID
            r"arXiv:[a-z\-]+/\d{7}",                      # Legacy arXiv ID
            r"[A-Za-z0-9\.\-+_]+@[A-Za-z0-9\.\-+_]+\.[A-Za-z]+", # Email addresses
            r"(Accepted|Published|To appear) (at|in) [A-Za-z0-9\s]+", # Acceptance text
            r"(Supported by grant|Funded by) [A-Za-z0-9\-]+" # Grants
        ]
        
        self.regex_patterns = regex_patterns or default_regexes
        self.compiled_regexes = [re.compile(p, re.IGNORECASE) for p in self.regex_patterns]

    def anonymize_document(self, input_path: str, output_path: str):
        """
        Process the entire document: redact text, clear links, purge metadata.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
            
        try:
            # 1. Open the document
            doc = pymupdf.open(input_path)
        except Exception as e:
            raise RuntimeError(f"Failed to open PDF, document may be corrupted: {e}")

        # 2. Iterate pages
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Step A: Find and annotate exact string matches
            self._annotate_exact_strings(page)
            
            # Step B: Find and annotate regex patterns
            self._annotate_regex_patterns(page)
            
            # Step C: Scrub sensitive hyperlinks
            self._scrub_hyperlinks(page)
            
            # Step D: Apply all redactions for the page as a single batch
            # images=0 (PDF_REDACT_IMAGE_NONE) protects mathematical figures and images
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
            
        # 3. Purge standard dictionary and XML/XMP Metadata
        self._scrub_metadata(doc)
        
        # 4. Save securely
        # garbage=4: Remove unreferenced objects, merge duplicates, rebuild xref
        # deflate=True: Compress streams to ensure text fragments are erased
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
        
    def _annotate_exact_strings(self, page):
        """Marks exact literal strings for redaction."""
        for target in self.exact_strings:
            # search_for returns a list of Rect objects
            bboxes = page.search_for(target)
            for rect in bboxes:
                # Black fill: (0,0,0)
                page.add_redact_annot(rect, fill=(0, 0, 0))

    def _annotate_regex_patterns(self, page):
        """
        Uses get_text("text") to find regex matches, then uses 
        search_for() to find their bounding boxes on the page.
        """
        try:
            full_text = page.get_text("text")
        except Exception as e:
            # Handle corrupted fonts causing extraction errors
            print(f"Warning: Text extraction failed on page {page.number} - {e}")
            return
            
        for regex in self.compiled_regexes:
            for match in regex.finditer(full_text):
                exact_match_string = match.group()
                
                # Retrieve bounding box for the dynamically matched string
                bboxes = page.search_for(exact_match_string)
                for rect in bboxes:
                    page.add_redact_annot(rect, fill=(0, 0, 0))

    def _scrub_hyperlinks(self, page):
        """Removes interactive links and redacts their visual footprints."""
        links = page.get_links()
        for link in links:
            uri = link.get("uri", "").lower()
            
            # Target identifying links
            if "arxiv.org" in uri or ".edu" in uri or "github.com" in uri or "mailto:" in uri:
                # 1. Delete the interactive clickable area
                page.delete_link(link)
                # 2. Add visual redaction box over the link text
                page.add_redact_annot(link["from"], fill=(0, 0, 0))

    def _scrub_metadata(self, doc):
        """Wipes tracking, author, and XMP metadata."""
        clean_meta = {
            "author": "Anonymized",
            "title": doc.metadata.get("title", ""), 
            "subject": "",
            "keywords": "",
            "creator": "Anonymization Script",
            "producer": "PyMuPDF Utility"
        }
        # Overwrite standard metadata
        doc.set_metadata(clean_meta)
        
        # Purge deeply nested XML/XMP metadata streams
        doc.del_xml_metadata()


# ==========================================
# Example Usage Execution
# ==========================================
if __name__ == "__main__":
    
    # 1. Provide exact strings to nuke (e.g., Authors and Institutions)
    known_authors = [
        "Dr. Jane Smith", 
        "John Doe", 
        "Massachusetts Institute of Technology"
    ]
    
    # 2. Instantiate the utility
    anonymizer = AcademicPDFAnonymizer(exact_strings=known_authors)
    
    # 3. Process the file
    input_pdf = "original_submission.pdf"
    output_pdf = "anonymized_submission.pdf"
    
    if os.path.exists(input_pdf):
        print("Starting comprehensive anonymization...")
        anonymizer.anonymize_document(input_pdf, output_pdf)
        print(f"Successfully saved anonymized PDF to: {output_pdf}")
```

### Conclusion
By leveraging the low-level stream modification capabilities of PyMuPDF 1.24.0, academic institutions and publishers can automate the rigorous requirements of double-blind peer review. Proper application of `apply_redactions()`, careful handling of the `images` flag, meticulous parsing of XMP metadata, and the utilization of `garbage=4` during save operations guarantees that sensitive information is permanently purged from the document structure, satisfying the strictest standards of data privacy.

**Sources:**
1. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHCetfW7UrjXibjtMDk0iul9mbuT_I467smk52t6rNuFxR7gT2gJSlPRlwxUo6V_5XCNVrhimvGxomeWZzVphAYBN83o5MX0a0X8pMVr3j84oVHaHFUopulPkflk5iUa6JhB729GQEI_mY=)
2. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFmjbTm1Q5tmLQih3t62dfFTgFzJP4XpCXOIqBYXBMLr2hc6FlzfCFAuXJe4BZKQIZKxlooX2ktoNkO-6woNkvZtuNo-6Yis8OIkZW-UkP4N6xk8FsVmzer7aD3UjjlA6mpzq87l8doA==)
3. [artifex.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7IFCj-3Z-x8ofkJ5J8HcsEraq_g2LCHvqt55Xz1WrBxi9zTUaxFf1CrE0w1NLH4l0ODPz7qMxj2j6RlFcOuYYgwxC5zRhDfnM4tXp4amiNht4VrymTIL2WzYNAdNsN308p8lNDscOyRZown3bS5_nERw0emNsEumOrZKesr9MAzFgKQ==)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG2kvEKSAYKWtxgs2xdwHSInUy4GjCycz-vWb6Ea66BDGuozSG2KeiuHOTBRk_GIoF4mFJ8VFSTxtFcSeP7VHZw75ghIE9lhNqeoi22dRbYYBVEU4JI2NOU8IWyIM_Rh-Cw-bwE7uNu0EHF87lD)
5. [nutrient.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGup0STKSF4FUIsMKBMp0ANZfYom0LUFyhyVaRp4DocQYn34sFD7pim4kDti4AZoe-Fzjt_N2ti5GvBggvgXJH_hr57KLaI3UqNMIX9YVElJQUqmCxBE4bi4usrLbzq1iyFKoN33bQiA_Vv7CXjbS6OmA==)
6. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHeLqjwUX-QosDagixx0zes5XtlGVp4f1Qy_XVkBozMnAvmWrRVGS25FL7lsaf28RLneHE41GeHCdGnmem_nsd3D4P8pQjNHqwgOFr7Pwqcsm5flCw7sbzHiXXd5bQeLCV5TvQQQm6DYxiG8EE=)
7. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLxjEbXY_4pce9AY7uhmTRI0up68hZ0oce2TW5-DFJdcjCIzpUyD7Ym4Psmxu1j7glk1bXAoGNuuqEWm8sQXYiyDRQXfc9UO1Es48v4Nf59naJW07a7infIq5ahxpuWTcdHBBMgfdaoYSVs6rV)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEC8v15HC-lPWwy6uEpVFSW62Ty9H7sLDUG_11E025kNdtUSwphNHCceoRPSrGw7ZfSZLoX2dvpz4Pj7uL34TOiuoXdXD0ZxV_rY9l5rsNpvho-aeCE8cv_2n6YtSlGU8mSaocHY9SoMq8=)
9. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoPcHWNJfUMSL-j3A6-hosgMfSRvn_IMMcStmabytQz-dYujYBpIG7EOpCJXIVOI0l_o0mO46ZJgXfzM2FlRfROGqLNUr1Xf1_VsdZPgTSx8pgIKie01Ptr0CVMeKdIcQFENPona2joaZmptVcZIHAXDRoZl2MwDovIvOh1Gm9a5euDc7Jvz794jkhpvV-Fm8lEgY=)
10. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFQ0DSbunUlGtkAwORd8FIcuI1ThJrki30CGa2rj0W2MsQZ9UrHgpekPgHeLUWzEI9_9ybAycJGTY1EDTWJJJTgFCc_fHO0YYuF_Jm8bxxktSNqJM1HP_G2MYZ29QHhHvkWAAIbFOHIJWt9kT4poj1UifJ-g5I3dtUGCI1cF_kz14juEPHcUkL_6T7jQ8qRP69kvLkyXmXT9sFfHtpiyK1jqk5G)
11. [nutrient.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0Ywq-D_HEQBg_YPbDWMhdOq54m71Ys_7F8oK35NDvAK0apsl9PIUIvX3TZAoZfCcsGkMXsuiaHjCh8RV4ObfezvsYp4VMtgvthx7k31r5bJrw2gxqCIDbIU4y-f8hNk-qAXD8I6nRC1LXmm6M)
12. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9u68BgvxkAXT_yr48DHgmxPrbyy-MxmaBgZBthNxPOTkbQqjcimZb33FEYjel-LcAAzfrlg_Ce4tOU4-GPBXellbQC0Vr3l9yMdI505HXj7vkZOzePQD2r6367JkUSa4bqOUL2qvtSVPnNopMKvowUde_YNoEU3SDhVfnPNNdKtQOAFMYBtDsbIvxj4GfigaTADvZlj_sDlVc9QDqselQkKwRurPVRwyqBWAtXFtUZe0tznK0TeSwGFtqwA==)
13. [csdn.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsy_BkqBRM5_PxTrPDbE0vMFr3kJ6eFtJ_0Ktnwbcpf0AcrX8TcYYExKR-i7F1_3qB2Wk6MQq6jw-jdGQRFxP6caWTsa5vVJqaHMU_-n0OVahgCnGFnjtqvgc1cg3SQbpoRIEAgKbqqA0cNAY=)
14. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyZnwuWSJi7iuXr8Hf1YtcSjJ506ZvSbHp9eE7mauq03d3erBVzedZxQzHs0jtnpiHXmCXyovNe0FWtg9G6pPRRkoMv4BjawhkqZrTK0MjD7aF11E74EsgbcEltKwpD8JdePsS4Hx_Gg_-JAUvd_6pgcinn0cDX9ccujCAEXex9SYciCksrNpTuB0EUmpMH07jV_uHzTExvWx8Hvf7CqMrLA==)
15. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqiIRVJc6aPp6dAERpcSKNaAi3MZ39wOgWFMrJsx7FtfHsUFFcvwu9GKHzSq8qBpspmG0U_b9CYu1Xc0yH_TO3Rujr1MF-Si5EgSn5uwLd9CnYvXLsn5UY97mruyqyPKhN6eoM)
16. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFpLr92ZOB451pBLKm21wHbYrVRNbNAp5PkigJ4oPUYWhxH53hBIRxueO_fvkse6GLTeraWyfHHV7Y1mDsJx7hqGOOBccukMpR1mv5wLFNNJkny7bAeLrZmTCnN8p4XUL-HH58YTcZRDd5oSqoxMnmffaSB5QD3k3N5eBBZM3s5Qzsn8qvFOw0=)
17. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3wY7tdx_kLUJlc9R6GTFMEA29eBw9LnKue8t3ptEDqRqS0H9bvW1IVIkcZtRJ1-koicBh5oZhGbFu0TiV1bQ-TaRce8aPVtGwmTq4Q4BoLI41Hzc33b3j8L-ESKOWEqXlhF8Fs-Ou5p7S7Ws=)
18. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG4Pfw7I6k-2wWm4TRPLCoJAAPm-mSXVppJTfr3WkAkBSD5XWRuiWbmgEDXH9-u_YlAi5iw6MTMJB30lMV1ZPx2qBZ6aiZhOxMHqUA0y5aDLp8j971JxICtHjwVrmQTtDn549XEyRrgEDeWuy8J0R3WFIoF)
19. [analyticsvidhya.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTGMVLqd0wPzpsB1kSWG-pPf_tA8-3Stc3CVW6gRTKEg4gh7Cr0BsgBIlYqlCDlrjGuq1omeOX62Vyxs0Rplwu3bF7_VxxhJbygAnWeBtFNy32nvxtRqxi7HqEGbQ6MnMoBwRfmDK5LwCAZ5toyqvlVSUVwQmVBLhWf_e2u7ER0vZlYmNYYqGf_RE=)
20. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyzzAHtZN2tdeNgkZv2Y_NyNf3Dq9Iq2GOz28_OdiS7q8VbjYa8frmsx2xaxGS7cdBni3PBYEks6gPZfQ57-jfYOPC7tt60jrWFF7RefomontjKSFO31Pir0UFKtntPnKtp4FaDeujWMs21GMF-w==)
21. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGXZr3YIzVMiICnS08ruXPnSFTgXhDQSNKLEjpn2Vj8ggyQncUlp2RO6U_mgjsLOFZVG0VWSSJmKZM1W3Vs6ttvkqCMptFEIPzrAsEe6DM4gjCyrtZeHGne0MhSK_S97XdQ2kxJwWFwvqTGuVhOG5w9)
22. [artifex.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3ty5nqX5lIKDH1m0nRme_o5vhKWj-CuViA0vNBHdTi3G9QS4yO9aRSUYxDzeDGV5hursU-n2uaHWW9qV_kIZBLrvir7KB2FhF5GVcAnJmQZBHTXC-aKQzNVuQ0IP6mdxxJkyywcBQQ46H-Qf6CTUJk_xJ5WDz_EknJ2Ni-SIjJ-kkB280ZbTJulCnHc49_Dzb)
23. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzW-6DzqO8fL_MDp3zxR8mY4ROAGFCghGHnClWsEgB1TSMXODX42yiqvmG4eeHr7dLKszgF4rtfPmPnzF_d4pDqm4kkB2ajz1MgH4pVvbLVbA_2pbxkPJCdxfa7Dv1xX5jaa0R1713uVMdPoQAONtnN6qz97iwHLQ7rmCh29Qxrw==)
24. [documentprocessing.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERod6L4lB7uixDP31h3YTja6pZktfVt8oIqfZ9UkcvSwlLSc28SjKB5h6Zxd8Ds30HSF22N2P2vwXyCwl2JicUTwc67StxiA-BXwQQLAV6Qf1pFAYBH-Q8jPLwEWOx5R1-WwdYahVZ2vFLLXD--zo8m4MJqigF)
25. [documentation.help](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFL-lwHAZ_JWx6FPYPTOUvUr8jVGZo7BJ35or6o8T3L0OqtWXl_JsSoUK6lQQa1qm4tXs9esjOLE8AwsBayA_S9-73k4B-2HflyAXCxIJ7-2lOOVKRo9jZ0_wttt2ppi-ii8Q==)
26. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEFW3ESDabvFBJziji2Mpf3uEwNq0fij-TnlkzcZqys4AjQmnY8lBcEE91I_VzWwbajFY8mQxanNYGEIpWphn3R4RQsd2SNkRFMKgQh0GM9CS8nVWrJ1tDexEbb_QMGsEJCNN0Du4A8iMNlI98VrPl5Jw0=)
27. [lynote.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHkUsolx43cc3eDINCCuJhI2tGUIHyS7-CtPdiCKgWFlzPwuzn4CP-hGp9GOWvd9zCf44TC7znNOoS6XrrOk1oprL8T_4We5kLEmiCmYw0xkbZXwTYLx-cqKzwsV_vxR2ezX3wuEWyGoi4=)
28. [ai-bites.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLXPWRtChHEvB82wIdHHYVjfnr7KCSFjeGonBXw7Uqu5gFTVx_-BV0ENtSiRw0mpGn4Qz0gYWd1nTvsaqi180al5IyFvdvAwmlPZbl1CksA207P653JT2ZBw0N5vSSEH1BTYJOQzos1gXKgnLrwkXFPQewMvXhg8zPFhE3FurozK4=)
29. [pdfplumber.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF6FRPCOa1WWzFrrlQnWi-9j2JONxAyZGaGUWgagF8cRxUo0sKYkiPGqvcuL6jw9rtCWsG_-up19vnj6WxryiIlPPxR4xDXlkm4EeASAb0ZJkSTU_BwNB1eG9aOgydhLM96BszA7LhaMEOhp2Bg3ZXAMvURGhTEtuOM1MWwtyGwF2w1joZeViylMhk-cme6e47KZ6qP-TvmycLWAe6DG6pskA==)
