# Python Utility Module for PDF Invoice Text Extraction and Cross-Reference Fraud Detection

**Key Points**
*   Automated invoice fraud detection requires a multi-stage pipeline: PDF text extraction, Regex-based field parsing, reference data ingestion, and fuzzy string matching.
*   `pdfplumber` is highly recommended for structured and semi-structured PDF text extraction due to its layout preservation capabilities, outperforming `pypdf` in complex tabular contexts.
*   Regular expressions for financial fields (such as IBANs and monetary amounts) must account for diverse formatting, including variable white spaces and locale-specific decimal separators.
*   The `rapidfuzz` library (v3.x) introduces breaking API changes from previous versions—specifically omitting default string pre-processing—which must be manually reinstated to achieve accurate fuzzy matching on vendor names.
*   Data ingestion via `pandas` requires explicit engine designation (`openpyxl` for `.xlsx` files) and careful dtype management to prevent unintended coercion of string identifiers (like PO Numbers) into floating-point numbers.
*   Cross-reference comparison logic is best structured using a "first matching reason wins" rule set, applying strict tolerances for numeric comparisons and robust cutoff thresholds for fuzzy string matches.

**Overview of Invoice Fraud Detection**
The proliferation of digital invoicing has necessitated automated mechanisms to detect fraudulent or erroneous billing. A robust Python-based utility module must bridge the gap between unstructured PDF text and structured relational databases containing vendor and Purchase Order (PO) data.

**Methodological Approach**
This report details the construction of a reusable data pipeline. It systematically covers the extraction of raw text using Python libraries, the parsing of that text using regular expressions, the loading of ground-truth reference data via `pandas`, and the application of heuristic and fuzzy matching algorithms to detect discrepancies indicative of fraud.

---

## 1. Introduction to Automated Invoice Processing

In contemporary corporate finance, the accounts payable (AP) pipeline is highly susceptible to both human error and deliberate fraud. Vendor invoices are frequently submitted as Portable Document Format (PDF) files. Because the PDF standard is primarily a visual presentation format rather than a structured data format, extracting semantic meaning—such as identifying a vendor name, an International Bank Account Number (IBAN), a Purchase Order (PO) number, or the total amount due—requires specialized software engineering [cite: 1]. 

An automated fraud detection utility must extract these fields from free-text invoices and cross-reference them against internal procurement databases. Discrepancies such as manipulated IBANs, inflated invoice amounts, or non-existent PO numbers serve as critical fraud indicators. This report provides comprehensive documentation and working code examples for building such a utility module in Python, focusing on `pdfplumber` for extraction, `pandas` and `openpyxl` for reference data ingestion, and `rapidfuzz` for entity resolution.

## 2. PDF Text Extraction Mechanisms: pdfplumber vs. pypdf

Extracting text from PDFs is complicated by the fact that PDFs contain coordinate-based printing instructions rather than continuous strings of characters [cite: 1]. Two prominent libraries for reading PDFs in Python are `pdfplumber` and `pypdf`. 

### 2.1 The pdfplumber API (Version 0.11.x)

`pdfplumber` (version 0.11.x) is an open-source library built on top of `pdfminer.six`. It is specifically designed to plumb a PDF for detailed information regarding each character, rectangle, and line, making it exceptionally powerful for extracting text while preserving the visual layout [cite: 2, 3]. 

#### 2.1.1 API Usage and Page Indexing
The primary entry point for `pdfplumber` is the `pdfplumber.open()` method, which can accept a file path or a file-like object [cite: 3]. This method returns a `pdf` object containing a `pages` attribute—a list of `Page` objects. 

Crucially, `pdfplumber` utilizes **0-based indexing** for its pages [cite: 3, 4]. Therefore, `pdf.pages` refers to the first page of the document. To convert to a 1-based page number (often required for logging or user-facing error messages), one must simply add `1` to the iteration index.

The standard method for extracting text from a `Page` object is `page.extract_text()`. By default, this function attempts to collate the page's character objects into a single string, inserting spaces where the geometric distance between characters exceeds a certain threshold (controlled by parameters like `x_tolerance`) [cite: 3].

**Working Code Example: PDF Text Extraction**
```python
import pdfplumber
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_invoice_text(pdf_path: str) -> List[Dict[str, str]]:
    """
    Opens a PDF and iterates over its pages to extract text.
    Returns a list of dictionaries containing the 1-based page number and text.
    """
    extracted_pages = []
    
    try:
        # pdfplumber.open() is the exact API for loading the document
        with pdfplumber.open(pdf_path) as pdf:
            # pdf.pages is a 0-indexed list of page objects
            for index, page in enumerate(pdf.pages):
                # Convert 0-based index to 1-based page number
                page_number = index + 1
                
                # page.extract_text() extracts the text. 
                # layout=True can be used to preserve physical spacing, 
                # but layout=False (default) is often better for regex processing.
                text = page.extract_text(layout=False)
                
                if text:
                    extracted_pages.append({
                        "page_number": page_number,
                        "text": text.strip()
                    })
                else:
                    logger.warning(f"Text extraction returned None on page {page_number}.")
                    
    except Exception as e:
        logger.error(f"Failed to process PDF {pdf_path}: {e}")
        
    return extracted_pages
```

#### 2.1.2 Common Pitfalls with pdfplumber
1. **Extraction Returning None:** If a PDF page consists entirely of scanned images (i.e., it is a rasterized document rather than a machine-generated text document), `page.extract_text()` will return `None` or an empty string [cite: 3, 5]. In such cases, Optical Character Recognition (OCR) tools like `Tesseract` are required as a fallback [cite: 5].
2. **Whitespace and Newline Handling:** `pdfplumber` interpolates whitespaces based on the physical distance between characters (`x_tolerance`). Invoices with wide kerning or justified text might result in words being arbitrarily split (e.g., "I N V O I C E" instead of "INVOICE") [cite: 3]. 
3. **Tables vs. Plain Text Differences:** When extracting text from tabular data using `extract_text()`, columns may be mashed together without explicit delimiters. For rigorous table extraction, `page.extract_tables()` or `page.extract_table()` using strategies like `"lines"` or `"text"` should be employed, but for general field parsing, plain text extraction is usually sufficient if robust regex is applied [cite: 1].
4. **Encoding Issues:** PDFs may utilize custom font encodings. `pdfplumber` 0.11.x includes mechanisms to handle `PDFDocEncoding` failures, but corrupted fonts can still yield garbled text or `UnicodeDecodeError`s [cite: 6]. Setting `raise_unicode_errors=False` in newer versions can help bypass fatal crashes [cite: 6].

### 2.2 Alternative Extraction via pypdf (Version 6.6.x+)
`pypdf` (currently iterating through version 6.x) is a pure-Python library capable of splitting, merging, and extracting text from PDFs [cite: 4, 7, 8]. The API relies on the `PdfReader` class:

```python
from pypdf import PdfReader

reader = PdfReader("invoice.pdf")
text = reader.pages.extract_text()
```

**When is pypdf better than pdfplumber?**
`pypdf` is significantly lighter and faster than `pdfplumber` because it does not attempt complex geometric layout analysis [cite: 4]. It is superior when processing large volumes of purely textual documents where exact geometric positioning is irrelevant, or when the task strictly involves metadata extraction, document splitting, or encryption handling [cite: 4, 7]. However, for invoices—which are heavily reliant on multi-column layouts and visual separation of key-value pairs—`pdfplumber` is vastly superior due to its sophisticated handling of coordinate-based character placement [cite: 1].

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

## 4. Ingesting Reference Data: pandas and openpyxl

To detect fraud, the extracted invoice data must be cross-referenced against ground-truth databases (Vendor Master and PO tables). `pandas` is the optimal library for tabular data ingestion, working in tandem with engines like `openpyxl`.

### 4.1 Excel File Ingestion using openpyxl (openpyxl 3.1.5, pandas 2.3.3)
`pandas.read_excel()` requires the `openpyxl` engine to parse newer `.xlsx` file formats, as the default `xlrd` engine was restricted to legacy `.xls` files in newer `pandas` versions [cite: 11, 13].

**Exact Function Signature and Implementation:**
```python
import pandas as pd

def load_vendor_database(excel_path: str) -> dict:
    """
    Loads vendor data from an Excel file and creates a lookup dictionary.
    """
    try:
        # Exact pandas read_excel signature specifying engine, sheet, header, and types
        df = pd.read_excel(
            io=excel_path,
            engine='openpyxl',
            sheet_name='Vendors', # Can be string or 0-indexed integer
            header=0,             # First row is the header
            dtype={'Vendor ID': str, 'Name': str, 'IBAN': str},
            keep_default_na=False # Prevents empty cells from becoming NaN float objects
        )
        
        # Clean string columns: strip trailing/leading whitespace
        for col in ['Vendor ID', 'Name', 'IBAN']:
            df[col] = df[col].str.strip()
            
        # Create lookup dictionary: {Vendor ID: {"Name": Name, "IBAN": IBAN}}
        vendor_dict = df.set_index('Vendor ID').to_dict('index')
        return vendor_dict
        
    except ImportError:
        logger.error("Missing optional dependency 'openpyxl'. Please install it.")
        return {}
```

**Common Pitfalls:**
1. **Integer Columns Read as Float:** If an Excel column contains numeric Vendor IDs (e.g., `1001`) alongside empty cells, `pandas` will by default cast the entire column to `float64` (e.g., `1001.0`), which breaks string matching [cite: 12]. Specifying `dtype=str` and `keep_default_na=False` forces `pandas` to load everything as strings and empty cells as empty strings (`""`) [cite: 14].
2. **Trailing Whitespace:** Data entered by humans in Excel frequently contains trailing whitespace. Applying `.str.strip()` to all string columns immediately after loading is mandatory [cite: 14].
3. **Engine Declaration:** Failing to specify `engine="openpyxl"` may result in `ValueError` or fallback attempts to missing engines. Explicit declaration guarantees stability [cite: 13, 15].

### 4.2 CSV File Ingestion and Cleaning
Loading Purchase Orders from a CSV file relies on `pandas.read_csv()`. The principles of dtype management apply similarly.

```python
def load_po_database(csv_path: str) -> dict:
    """
    Loads PO reference data from a CSV file.
    """
    df = pd.read_csv(
        csv_path,
        dtype={'PO Number': str, 'Vendor ID': str},
        # Amounts must be floats for numeric comparison
        converters={'Amount': lambda x: float(x.replace(',', '')) if x else 0.0}
    )
    
    # Normalize column names: lowercasing and replacing spaces with underscores
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    
    # Clean strings
    df['po_number'] = df['po_number'].str.strip().str.upper()
    df['vendor_id'] = df['vendor_id'].str.strip()
    
    return df.set_index('po_number').to_dict('index')
```

## 5. Fuzzy String Matching with rapidfuzz (Version 3.14.x)

Vendor names extracted from invoices rarely match the Vendor Master database perfectly. Variations in legal suffixes ("Acme Ltd" vs. "Acme Limited"), punctuation, and minor typos require algorithmic entity resolution.

`rapidfuzz` (version 3.14.x) is a C++ based, drop-in replacement for `fuzzywuzzy` (and `thefuzz`), offering 10x to 100x speedups by utilizing SIMD instructions and Bitwise parallel algorithms (BitPal) [cite: 16, 17, 18].

### 5.1 API Specifications and Import Paths
The exact import path for the matching functions and processors is:
```python
from rapidfuzz import fuzz, process, utils
```

### 5.2 Scorer Selection for Corporate Entity Names
`rapidfuzz` provides several scorers under the `fuzz` module:
*   `fuzz.ratio`: Calculates the standard Levenshtein distance. Very strict; fails if words are reordered [cite: 19].
*   `fuzz.partial_ratio`: Matches the shorter string against substrings of the longer string. Good if the invoice says "Tech Solutions" and the database says "Tech Solutions Incorporated".
*   `fuzz.token_sort_ratio`: Tokenizes the strings, sorts them alphabetically, and calculates the ratio. Handles word reordering.
*   **`fuzz.token_set_ratio`**: Tokenizes the strings, identifies the common intersection, and calculates ratios based on the remaining differences. 

**Which is best for company names?**
`fuzz.token_set_ratio` is unequivocally the best scorer for corporate names. It seamlessly handles missing or extra legal abbreviations. 
*   Example 1: "Acme Ltd" vs "Acme Limited". `token_set_ratio` yields ~90+.
*   Example 2: "Tech Solutions Inc." vs "Tech Solutions". `token_set_ratio` yields 100, because the shared tokens ("Tech", "Solutions") perfectly match, overshadowing the missing "Inc." [cite: 16, 17].

### 5.3 Execution and Return Types
The most efficient method for finding the best match in a reference dictionary is `process.extractOne()`. 

**Full Function Signature:**
```python
process.extractOne(
    query, 
    choices, 
    scorer=fuzz.WRatio, 
    processor=None, 
    score_cutoff=0
)
```

**Breaking Pitfall in RapidFuzz 3.x:**
A major architectural change occurred in `rapidfuzz` 3.0.0. In version 2.x, `rapidfuzz` automatically pre-processed strings (lowercasing, removing non-alphanumeric characters). In version 3.x, **the `processor` argument defaults to `None`** [cite: 20, 21, 22]. If a user does not explicitly pass `processor=utils.default_process`, the comparison becomes strictly case-sensitive, severely degrading fuzzy match scores.

**Return Type:**
In `rapidfuzz`, `process.extractOne()` returns a tuple containing three elements: `(match, score, index)` [cite: 23]. If the choices are a dictionary, the `index` will be the dictionary key. If no match exceeds the `score_cutoff` threshold, the function returns `None` [cite: 18, 23].

**Appropriate Score Cutoff:**
For vendor names, a `score_cutoff` between `85` and `90` is appropriate. Setting it to 85 prevents false positives while still capturing variations like "Technologies" vs "Tech". RapidFuzz utilizes the `score_cutoff` argument algorithmically to exit early from Levenshtein calculations if it mathematically determines the threshold cannot be reached, dramatically improving pipeline speed [cite: 18, 23].

**Working Code Example: Fuzzy Matching Vendors**
```python
def find_vendor_match(extracted_text: str, vendor_dict: dict) -> Optional[str]:
    """
    Fuzzy matches the extracted text against known vendor names.
    vendor_dict format: {"V100": {"Name": "Acme Ltd", "IBAN": "..."}}
    """
    from rapidfuzz import fuzz, process, utils
    
    # Create a mapping of vendor names to their IDs for the choices parameter
    # dict format: {"Acme Ltd": "V100", "Tech Solutions": "V101"}
    choices = {v_data["Name"]: v_id for v_id, v_data in vendor_dict.items()}
    
    # Extract the best match
    result = process.extractOne(
        query=extracted_text,
        choices=choices.keys(),
        scorer=fuzz.token_set_ratio,
        score_cutoff=85,
        # CRITICAL for rapidfuzz 3.x: Must pass default_process for case-insensitivity
        processor=utils.default_process 
    )
    
    if result is not None:
        matched_name, score, dict_key = result
        # Since we passed a dict.keys() view or dict, the behavior maps to the choice.
        # To get the ID, we look it up from our mapping
        return choices[matched_name]
    
    return None
```

## 6. Output Formatting and Serialization via JSON

After processing invoices, the output must be serialized into JSON for downstream consumption (e.g., passing to a web interface or an API). 

`json.dumps()` is used to convert the Python dictionary to a JSON formatted string.

```python
import json

def format_output(results: dict) -> str:
    """
    Serializes pipeline results into a JSON string.
    """
    return json.dumps(
        results, 
        indent=2, 
        ensure_ascii=False # Preserves characters like € or £ instead of unicode escapes
    )
```

**Handling Missing Data and Floats in JSON:**
*   **None to Null:** In Python, missing values are denoted as `None`. The `json.dumps()` method automatically and seamlessly serializes Python `None` to the JSON `null` type. For instance, if an invoice lacks a PO number (`"po_number": None`), the JSON output will read `"po_number": null`.
*   **Float Formatting:** Python float serialization in JSON can result in varying precision (e.g., `1000.0` or `1000.000000001`). To ensure monetary amounts preserve exactly two decimal places, they should be formatted as strings prior to serialization or wrapped in a custom JSON encoder, though standard `float` rounding (`round(amount, 2)`) usually satisfies basic JSON output requirements.

## 7. Data Pipeline Architectural Patterns for Fraud Detection

Structuring the comparison logic for fraud detection requires a systematic application of business rules. The standard architectural pattern is a priority-based "First Matching Reason Wins" evaluation matrix.

### 7.1 "First Matching Reason Wins" Algorithm
Fraud checks are evaluated sequentially, from the most severe to the least severe. As soon as a condition fails, the invoice is flagged with that specific failure reason, and the module moves to the next invoice. This reduces unnecessary computation.

1.  **Priority 1: Vendor Existence.** Does the vendor exist in the Master Database? (Handled via RapidFuzz).
2.  **Priority 2: PO Validity.** If a PO is extracted, does it exist in the PO database? Does the PO belong to the matched vendor?
3.  **Priority 3: IBAN Match.** Does the IBAN extracted from the invoice exactly match the IBAN on record for that Vendor ID?
4.  **Priority 4: Amount Tolerance.** Does the invoice amount exceed the maximum authorized amount on the PO?

### 7.2 Edge Cases and Tolerances
*   **IBAN Comparison:** Before checking equality, both the extracted IBAN and the database IBAN must have all spaces stripped. `extracted_iban.replace(" ", "") == db_iban.replace(" ", "")` [cite: 9, 10].
*   **Float Comparison Precision:** Floating-point arithmetic in Python can yield precision issues (e.g., `0.1 + 0.2 != 0.3`). Direct equality checks (`amount_a == amount_b`) for money are a significant pitfall. Instead, an absolute tolerance approach must be utilized:
    ```python
    if abs(invoice_amount - po_amount) > 0.01:
        flag_invoice("Amount mismatch")
    ```

**Working Code Example: Complete Pipeline Logic**
```python
def validate_invoice(invoice_text: str, vendor_db: dict, po_db: dict) -> dict:
    """
    Pipeline pattern implementing 'first matching reason wins'.
    """
    result = {
        "status": "APPROVED",
        "fraud_flag": None,
        "extracted_data": {}
    }
    
    # 1. Extraction Phase
    vendor_id = find_vendor_match(invoice_text, vendor_db)
    iban = extract_iban(invoice_text)
    po_number = extract_po_number(invoice_text)
    amount = extract_invoice_amount(invoice_text)
    
    result["extracted_data"] = {
        "vendor_id": vendor_id,
        "iban": iban,
        "po_number": po_number,
        "amount": amount
    }
    
    # 2. Validation Phase (First matching reason wins)
    
    # Rule 1: Unknown Vendor
    if not vendor_id:
        result["status"] = "REJECTED"
        result["fraud_flag"] = "UNKNOWN_VENDOR"
        return result
        
    # Rule 2: IBAN Mismatch (Bank Account Fraud)
    # Ensure spaces are stripped for robust comparison
    db_iban = vendor_db[vendor_id].get("IBAN", "").replace(" ", "")
    if iban and db_iban and iban != db_iban:
        result["status"] = "REJECTED"
        result["fraud_flag"] = "IBAN_MISMATCH"
        return result
        
    # Rule 3: PO Validation
    if po_number:
        if po_number not in po_db:
            result["status"] = "REJECTED"
            result["fraud_flag"] = "INVALID_PO_NUMBER"
            return result
            
        po_record = po_db[po_number]
        
        # Rule 4: PO belongs to a different vendor
        if po_record["vendor_id"] != vendor_id:
            result["status"] = "REJECTED"
            result["fraud_flag"] = "PO_VENDOR_MISMATCH"
            return result
            
        # Rule 5: Invoice amount exceeds PO amount (with 0.01 tolerance)
        if amount and abs(amount - po_record["amount"]) > 0.01:
            result["status"] = "REJECTED"
            result["fraud_flag"] = "AMOUNT_EXCEEDS_PO"
            return result

    elif po_number == "":
        # Our regex designated "" as an extraction failure
        result["status"] = "MANUAL_REVIEW"
        result["fraud_flag"] = "PO_EXTRACTION_FAILURE"
        return result
        
    return result
```

## 8. Common Pipeline Pitfalls

Throughout the construction of this pipeline, several programmatic and data-oriented pitfalls commonly manifest, leading to false positives in the fraud detection logic.

1.  **Unexpected Line Breaks Breaking Regex:** `pdfplumber` attempts to faithfully reproduce the visual layout of a PDF. If an IBAN wraps across two lines on the physical document, the extracted text will contain a newline character (`\n`) in the middle of the string [cite: 1, 3]. If the regex `r'\s?'` does not explicitly match newlines, or if the string isn't normalized via `text.replace('\n', ' ')` prior to regex execution, the extraction will fail.
2.  **Missing Engine Declaration in Pandas:** Upgrading `pandas` without adjusting legacy codebase configurations results in `xlrd` attempting to read `.xlsx` files and crashing. The `engine="openpyxl"` argument is strictly mandatory [cite: 15].
3.  **Deprecation of Default Pre-Processing in RapidFuzz 3.x:** As detailed in Section 5, moving from older fuzzy matching libraries to `rapidfuzz` 3.x requires a deep understanding of its API changes [cite: 20, 21]. Passing `processor=utils.default_process` is absolutely required to ensure vendor matching is agnostic to capitalization and special characters. Failure to do so will result in legitimate invoices being flagged as "UNKNOWN_VENDOR".
4.  **Locale Specific Decimal Separators:** Applying a hardcoded `.replace(',', '')` on financial amounts will destroy data accuracy on European invoices, transforming `1.000,50` into `1.00050`, which parses as 1.0005, triggering severe amount mismatch false positives. Dynamic detection of the fractional separator is a prerequisite for a globally viable utility module. 

## 9. Conclusion

Building a Python utility module for PDF invoice extraction and cross-reference fraud detection relies heavily on composing distinct tools efficiently. `pdfplumber` enables robust text extraction from coordinate-based PDF structures, while `pandas` coupled with `openpyxl` establishes the programmatic link to ground-truth procurement databases. By leveraging finely tuned regular expressions and the high-performance `rapidfuzz` string similarity library, organizations can automate the detection of invoice manipulation and discrepancies at an enterprise scale. Implementing a "first matching reason wins" logic pipeline further streamlines this architecture, ensuring precise categorization of suspected fraud.

**Sources:**
1. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGV-aosfvpBfPq4NdbFYK6zfisF0IBqQddA16a8x4Rgnp2dS-knS9tXTa4sC_CpF_bZSB5JTo_1bgD8iRHRyz2gzcXEtg8D0K_MIyw92sgrN13I1QZBanE_buR0At7Hb3veOrXCQTjJWN8fqWTECitwFIjK4wlnxc7cFb_nEmJk3ax3qXtrvvg=)
2. [tessl.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxPdx2LbzQEWa0NOCLw9gZXMssFfMDo6HORGtLEay120aEX5nqbbX8g-EfgYNfMDV34YJ0JjBIHXKs027-lnRpNKJZd1tPP3IMzvPs7-23x3pPUoPf157lsYFWvrRCrpP-BvxREEHrS8A3UaA=)
3. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxhPtjlXr_DkE7vlam1jyI9J_ly8h3md5br153efb2xIYd9TZFbBjtXBOGbcA3bsvmQoeFnV8ZHK9ZNY67yA5IKtoCrXLTweuWAIjBq4bNlPJSFCzIpIvRYAA=)
4. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEHnJTBMZjLr9BAo8pMVfjI_ICmUKmHbNCq9A0lFWIKndVf9kU6YQqFhM_VoE1SFF6RyLutUEZ5uIkO_TrjGTE02jTlF4JoDrp1bLsnUuQlLiAVtzk1)
5. [pdfplumber.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmxz8Ej3xtptLWde4hiVpb6VE9FDHjWVBbK20XJ18uq46ou3l0g6Wl8Jc4GxVsiqziHfavyKpLewPTKn-t6Tq2JPuzTvAnsIuLktrEdoHJsNM=)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMpDHTaaUkplWKnuzQvfSr67WgG_a87jjnXgdxCq6r8RyjYhIJwD8wWnvA3zXGG-UAEfMsNglhICuXRXCVW7CVmDWjQ6hd8exJ0zI4agTGVnmrMd_Du3ilyotgmKwh9e4ICtBh9jibI-HNR4zRXZzPN1ee)
7. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE9qHbKx3BFSwEYx_EzAr39NQgwuq2nOClFdg0n8RFqEorIjW3IsaVplFM2f4aR5zkkyRwIk3iL5ul5LCwqGlhC6dMu7EejRbLM1DOHAxKU-fchXg==)
8. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7VWjNFMSOrTVwk4uibU_gVpy0MQY5uX208DksyYP_JKvvyr5iAM0i2HVtOUwnV-rRBjiJNE-_94yiXOdrdmKg7u8ckYVsW7CPVP6y6pz1PY4yF12NBcPOpj6qKRbS31vMgWyNqc6IqGAy5W5Vzfp9TFdi)
9. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7q_xV8V517Z8cVm9zPW68vLX1cVJX5x9o0u7hRgJkStVtzRTmxF2ZnVrD4ahnjTPa0U9Yiok_gjoTdQLOQ1Mz2RPENCLumKxIskC0qVnmUVNDTLnFlMTEi2CcWXFBIolaYJbxvze0Wk-VDkri2RGIl3k=)
10. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUbmPxJiKf2wRjOFIkVoQTRCeOh2JzcRWcVeJUgpEQHrYz6giSuNme79kC5C4V3LJFZSxG-7dCw7iwmNTI0eWQlZlUiAb6CI8_NNv8xBmvZAMAiF1ilN7cWW5MthLW7DxVJuwLXi6EQ2ZJ29T8csoIcw9JL2ETuU0I-bW3_IW-u6Mgr_n3)
11. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwkQdmAyQOh0OkfZFkbkh7V4j5ExfRz_dDS1rUzA1Sp5WMvaC3I-1nIMHt9MgWqgru9987WvnfwCBZaMEFgi4OPBZRgsnKNZe-mR7JPpgtWDAAoQM7aT5wGARnvyyVPxP9Y_ZLQ1LCn8aHyyiaspii7LpKuF4N-IGJ)
12. [askpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyHXFIP4Cu39yVhNQA4vmAwUZ4K89Xsz7nBtKJVbeGX9k57cYTRlPQmJ3PBhdMIefXYmfrFD8UCbg2fgNW-XJQvMsKO2_n6hiU8HoYeFGVY9jx-FNFzTV2bgYlvJI3oRdf_IwJXgn0OAE7b3FcSkE60uPbNk1JR_pTrIt8w0A=)
13. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyZiYsQccwyde8PBNRBkHSkw0jbTiHQKM_oAxXwji99Nsbls4gbN-m6Jho3k7s-vy0aV7CBUfch6t_bBTQJRZ14tlD9KKuKYVKlQIvayjo8F-AJvM8AoJ7FIjnIEdF4yKiJRq8K56oVaIghZ9DFo4yKvhdogBFhe5Yan84QVO__s1_fjEw8yzkqC4H4Q==)
14. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFL3f0r5X9Q00LHC6ATPsV5DGx-CDfZN8gKFi5zPfjPBwAzDEnD9pkEc2bvDhpqo2JkLzXgR2YJJL2I_j-_prH8jiBVKA-2dYa3vQfIZEG53CsDzIY_1_-0bJ2nQiKjGJJ4ZO8TMkscXmt41wZGfuC_1g==)
15. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnh01wUcC0rFffp01s16EvNLiNfK7CIr-Ol-D5AvcpXUHUeTyqty3XJoNsyGK7imOwZAhe4IlOPM-wOkl848C8ZIQSzG0sOcbhlLC59vGbDsXKdU4_rlF6Wcx4DajDqjPSl2JApnMApvBdrSXQ1SWa3G57eSHek11UwjcYTC-hH727cZ4LBzVACdRhuQypOw==)
16. [letsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyoEwJbZ7SR1LWkv3BBUkeyv7_YmA0M4XT-z9WEePwVmq6pipqTf7sb8Te955QD8CwrFy54VmNX77tre5qczPDIxy6ZnChlNEOoRMcHSGhpsm9Dukk6IQeoQOSnkyu7SUSjd2qSun65QLCk7P5AwAhHRvWrYW_1E6f1saw0o-qFSjO_fJL-W5uSLTqBmMtFhKZ9GnV8QXK)
17. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1i0bggKj9zjNvkABqWM3O-BbXyYHTNY615fVWj9AyVjEtCGfitsgddwgqOwgzrynBFmiNe1OGlw-wdvYttues7CgadG1Sv6Iau-pgwax6d2a4k_ODhns7ag==)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGO6lbmFhxgoIyco4j5HInnGqryMbbTDrhfEhj95KEJJagnp7VHUdnjey-aXC3z0QCjwu5hCGNwfMtex5BIGA1ZKFtY1oRdHd_LANlpLsnwrZzKYHIx54H6ts_DV5HNzfb32rOWAghGPRYDU5XXiMLVqDionYkot_OY0g63syiNBlxVSImTK38ApfsbwsgMneyGHqTBPwsyB36OYVmLOU5-EnSvuhFrAH6l)
19. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwF15ZurQ_z3V6HNWXs01QfHqSimqr5LGtVBgVlDM-adP_QQiNc8NFOamq9FFgVtAOWK6kt3joPq6lSPzfc7aypD34QxIsPqnWuYRhi4Zrd20p74BHJU6re09rwDMHMyMBHcqxpnnw6ZkDeIKluxY1cvltbzxoJKOm5L5NZpBz1l2kzP4WxpsHZ7P_S32Uewey44ZI6r2jn0VcyYdOjWwrBw4RgA==)
20. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGrnlSC1jO380ITkc3Vd9opvx030zeUTaKQc2YltKCtV_sB9toLD7GpDGXJ6MOINNzULHwiFoIHyE_JhLkLqezzm-InTSgOZav_OiRKeeTqe1te-y63XkQTgfyNvP4zbuLVCJqO-myp0IW1_18TynMUpyfGCQ==)
21. [newreleases.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEcMv-MWNlLGhPPJy74Tpa-igFbkmVrh3CnRu-LUFUAep6jmfYSLErC3aco37_37gww4ZKPHNqd63eM-mKWtC8WqYXBEf1ECbxNFMFFw6f4aihXGVNS3T6NRtxnKhtBQSAJ2d5be--QrGpQRq70WOFO9OdlL_H8mrIv1zBaZgY=)
22. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-kQzWWr0cg7Xh0RN-2VhaqKpVFbNtkZ_ILvgyIQe273XYiqQwCRNggzDP9uAdMqQncL6HwTElLV8fYiR1SPSJTyX7dyvSIRjBWAEcN60bA825HhPHhEFSgCH5cA==)
23. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlIJ7Q6Z9aBGbZKqswMKSFPBOFyF-4gzurg1qkRw8ryd2hpwPbl_-NGGHPN-3TT3eU7u-6SoMaWuRvrkdss9bUVr2AI1R8PLsctfu3A3UogD4KqmXZCTSaCqA5FpCNmcrDNq-yPbxaLHvD4C7rRqjVQDeoEcRImazH4FbagB2Zqyfi0aBsaGuXVGkiz_8X6PyG1YN7L0DKOyW3p2UJL6P7cjRdIWhUaUs4LEGP0HP4W9i2yw==)
