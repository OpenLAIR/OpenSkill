# Domain Reference for evo-pdf-redaction-engine

**Responsibility**: Applying redaction annotations to identified text regions, removing sensitive hyperlinks, purging standard and XMP metadata, batch processing redactions per page with image preservation, and securely saving the output PDF.

**Key functions to implement**: redact_exact_strings, redact_regex_patterns, redact_page_region, scrub_hyperlinks, scrub_metadata, anonymize_pdf, save_redacted_document

---

## 2. The Redaction API in PyMuPDF


Unlike word processors, PDFs paint text characters onto specific coordinates. True redaction requires removing those painting instructions. PyMuPDF handles this via a strict, two-step API: `add_redact_annot()` and `apply_redactions()` [cite: 2].

## 3. Implementing Regex-Based Text Search and Redaction


Because `search_for` does not natively parse regular expressions [cite: 4], anonymizing academic identifiers (like arXiv IDs or complex email formats) requires a custom approach. We must extract the text, run Python's `re` module, and map the matches back to their spatial coordinates.

## 4. Handling PDF Elements: Headers, Footers, and Metadata



## 6. Managing Links and Annotations


URLs embedding author names or institutional identifiers represent a major breach of anonymity. PDF hyperlinks are treated as Annotations (type `LINK`).

## 7. Common Pitfalls, Edge Cases, and Document Saving



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