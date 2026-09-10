# Domain Reference for evo-invoice-fraud-detector

**Responsibility**: Fuzzy vendor matching, priority-ordered fraud rule evaluation, and JSON report generation. Orchestrates parsed invoice data against reference data to produce the final fraud_report.json.

**Key functions to implement**: find_vendor_match, check_invoice_fraud, run_fraud_detection_pipeline, save_fraud_report

---

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