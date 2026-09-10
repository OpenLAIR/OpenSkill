# Domain Reference for evo-pdf-invoice-parser

**Responsibility**: PDF text extraction and regex-based field parsing for invoice data. Returns a list of parsed invoice records with page numbers.

**Key functions to implement**: extract_all_invoices, extract_invoice_fields_from_text, extract_iban, extract_invoice_amount, extract_po_number, extract_vendor_name

---

## 2. PDF Text Extraction Mechanisms: pdfplumber vs. pypdf


Extracting text from PDFs is complicated by the fact that PDFs contain coordinate-based printing instructions rather than continuous strings of characters [cite: 1]. Two prominent libraries for reading PDFs in Python are `pdfplumber` and `pypdf`.

### 2.1 The pdfplumber API (Version 0.11.x)


`pdfplumber` (version 0.11.x) is an open-source library built on top of `pdfminer.six`. It is specifically designed to plumb a PDF for detailed information regarding each character, rectangle, and line, making it exceptionally powerful for extracting text while preserving the visual layout [cite: 2, 3].

#### 2.1.2 Common Pitfalls with pdfplumber

1. **Extraction Returning None:** If a PDF page consists entirely of scanned images (i.e., it is a rasterized document rather than a machine-generated text document), `page.extract_text()` will return `None` or an empty string [cite: 3, 5]. In such cases, Optical Character Recognition (OCR) tools like `Tesseract` are required as a fallback [cite: 5].
2. **Whitespace and Newline Handling:** `pdfplumber` interpolates whitespaces based on the physical distance between characters (`x_tolerance`). Invoices with wide kerning or justified text might result in words being arbitrarily split (e.g., "I N V O I C E" instead of "INVOICE") [cite: 3]. 
3. **Tables vs. Plain Text Differences:** When extracting text from tabular data using `extract_text()`, columns may be mashed together without explicit delimiters. For rigorous table extraction, `page.extract_tables()` or `page.extract_table()` using strategies like `"lines"` or `"text"` should be employed, but for general field parsing, plain text extraction is usually sufficient if robust regex is applied [cite: 1].
4. **Encoding Issues:** PDFs may utilize custom font encodings. `pdfplumber` 0.11.x includes mechanisms to handle `PDFDocEncoding` failures, but corrupted fonts can still yield garbled text or `UnicodeDecodeError`s [cite: 6]. Setting `raise_unicode_errors=False` in newer versions can help bypass fatal crashes [cite: 6].

## 3. Parsing Invoice Fields via Regular Expressions


Once the unstructured text is extracted from the PDF, regular expressions (regex) must be utilized to parse out structured data. Semi-structured invoice text is notoriously inconsistent, making robust regex design critical.

### 3.1 Extracting International Bank Account Numbers (IBAN)

IBANs are internationally agreed-upon alphanumeric sequences that uniquely identify bank accounts [cite: 9]. An IBAN begins with a two-letter country code, followed by two check digits, and up to 30 alphanumeric characters.

A major pitfall in IBAN extraction is that human-readable invoices often format IBANs with arbitrary spaces (e.g., grouping by 4 characters: `DE12 3456 7890 1234 5678 90`) [cite: 9, 10]. A naive regex like `[A-Z]{2}\d{20}` will fail on spaced IBANs.

**Robust IBAN Regex Pattern:**
```python
import re

def extract_iban(text: str) -> Optional[str]:
    """
    Extracts an IBAN from text.
    Matches a 2-letter country code, followed by 2 digits, 
    and up to 30 alphanumeric characters, allowing for optional spaces.
    """
    # Pattern explanation:
    # \b          : Word boundary
    # [A-Z]{2}    : 2 uppercase letters (Country code)
    # \s?[0-9]{2} : 2 digits (Check digits), preceded by optional space
    # (?:\s?[A-Z0-9]){11,30} : 11 to 30 alphanumeric characters, optional spaces
    # \b          : Word boundary
    pattern = r'\b[A-Z]{2}\s?[0-9]{2}(?:\s?[A-Z0-9]){11,30}\b'
    
    match = re.search(pattern, text)
    if match:
        # Clean the matched IBAN by removing all whitespaces
        return re.sub(r'\s+', '', match.group(0))
    return None
```
This pattern actively permits optional whitespace `\s?` between characters and captures the full sequence [cite: 10]. Post-processing strips the whitespace to normalize the IBAN for database comparison [cite: 10].

### 3.2 Parsing Monetary Amounts

Monetary amounts vary heavily by locale. For example, "Five thousand dollars and fifty cents" might be written as `$5,000.50` (US/UK) or `5.000,50 EUR` (EU) [cite: 11, 12]. 

**Regex for Monetary Amounts:**
```python
def extract_invoice_amount(text: str) -> Optional[float]:
    """
    Extracts the highest monetary amount indicating the total due.
    Handles both '1,234.56' and '1.234,56' formats.
    """
    # Looks for terms indicating a total
    # Then looks for numbers with commas or periods
    pattern = r'(?i)(?:total|amount due|balance due)[\s:$-]*((?:[0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+)(?:[.,][0-9]{2}))'
    
    matches = re.findall(pattern, text)
    if not matches:
        return None
        
    # Take the last match assuming the final total appears at the bottom
    raw_amount = matches[-1]
    
    # Normalization: convert to standard Python float
    # If the string ends with a comma and two digits (EU format), swap comma and period
    if re.search(r',[0-9]{2}$', raw_amount):
        raw_amount = raw_amount.replace('.', '').replace(',', '.')
    else:
        # Standard US format, just remove commas
        raw_amount = raw_amount.replace(',', '')
        
    try:
        return float(raw_amount)
    except ValueError:
        return None
```
This function successfully bridges locale differences by checking the termination of the string (`,[0-9]{2}$`) to determine the decimal separator logic.

### 3.3 Extracting Purchase Order (PO) Numbers

PO numbers are highly specific to the issuing company but generally follow alphanumeric patterns, such as "PO-1001" or "PUR-2023-445". 

**Detecting Absence vs. Extraction Failure**
A critical distinction in fraud detection is whether a PO number is missing because the invoice is a non-PO invoice (e.g., a utility bill), or if the extraction simply failed. 

```python
def extract_po_number(text: str) -> Optional[str]:
    # Look for PO indicators followed by the actual identifier
    pattern = r'(?i)\b(?:PO|Purchase Order|PO Number)[\s:#-]*([A-Z0-9]{4,15})\b'
    match = re.search(pattern, text)
    
    if match:
        return match.group(1).upper()
    
    # Differentiating absence vs. failure:
    # If the text mentions "PO" but our regex didn't capture the value, 
    # it's a failure. If the text lacks the phrase entirely, it is absent.
    if re.search(r'(?i)\b(?:PO|Purchase Order)\b', text):
        logger.warning("PO indicator found, but value extraction failed.")
        # We return an empty string to denote extraction failure
        return ""
    
    # We return None to denote complete absence of a PO number
    return None
```
By returning `None` for a valid absence and `""` (empty string) for an extraction failure, downstream pipeline logic can correctly assess the fraud risk.

### 3.4 Vendor Name Extraction

Extracting vendor names strictly via regex is notoriously unreliable because company names lack standardized structural boundaries in free-text. However, a heuristic approach is to look for text succeeding "From:", "Vendor:", or the largest text block at the top of the invoice. Due to this unreliability, the pipeline relies on **fuzzy matching** the entire extracted text (or the top 20% of the text) against a known vendor database.