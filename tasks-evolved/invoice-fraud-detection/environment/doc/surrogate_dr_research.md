To verify the invoice fraud detection logic independently, you can use the following verification anchors and invariants. These are designed to be implemented as `pytest` assertions to validate the output of your fraud detection script without needing to know the "correct" answer for every specific invoice in advance.

### 1. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the specific content of the invoices, serving as a sanity check for your data processing pipeline.

*   **Completeness of Fraud Reporting**: Every invoice page identified as fraudulent must have a `reason` field that matches one of the five allowed categories: `["Unknown Vendor", "IBAN Mismatch", "Invalid PO", "Amount Mismatch", "Vendor Mismatch"]`.
    *   *Assertion*: `assert all(item['reason'] in valid_reasons for item in report)`
*   **1-Based Indexing**: The `invoice_page_number` must be an integer greater than or equal to 1.
    *   *Assertion*: `assert all(item['invoice_page_number'] >= 1 for item in report)`
*   **PO Nullability**: If `po_number` is not `null`, it must be a string (or the expected format). If it is `null`, the `reason` must be consistent with a missing PO (e.g., "Invalid PO" or "Unknown Vendor").
    *   *Assertion*: `assert all(isinstance(item['po_number'], (str, type(None))) for item in report)`

### 2. Independently Computable Reference Values
You can create a "Golden Set" of test cases by manually extracting data from a small subset of the files.

*   **Manual Verification of Known Entities**:
    *   **Input**: Pick one vendor from `vendors.xlsx` (e.g., "Acme Corp", IBAN "US1234567890").
    *   **Test Case**: Create a mock invoice PDF page containing "Acme Corp" and a different IBAN (e.g., "US0000000000").
    *   **Expected Output**: The fraud report must contain an entry for this page with `reason: "IBAN Mismatch"`.
    *   *Assertion*: `assert any(item['vendor_name'] == "Acme Corp" and item['reason'] == "IBAN Mismatch" for item in report)`

### 3. Cross-Validation Approaches
Use alternative tools to verify the logic of your Python script.

*   **Pandas/SQL Verification**:
    *   Load `vendors.xlsx` and `purchase_orders.csv` into a SQLite database or a separate `pandas` script.
    *   Perform a `LEFT JOIN` between the extracted invoice data and the reference tables.
    *   **Logic Check**:
        *   `Unknown Vendor`: `invoice_vendor_name` NOT IN `vendors_list`.
        *   `Invalid PO`: `invoice_po_number` NOT IN `po_list`.
        *   `Amount Mismatch`: `abs(invoice_amount - po_amount) > 0.01`.
    *   *Verification*: Compare the output of your Python script against the result of this SQL/Pandas join.

### 4. Pytest Implementation Example
You can hard-code these checks into a `test_fraud_detection.py` file:

```python
import pytest
import json
import pandas as pd

# Load the generated report and reference data
with open('/root/fraud_report.json') as f:
    report = json.load(f)

vendors = pd.read_excel('/root/vendors.xlsx')
pos = pd.read_csv('/root/purchase_orders.csv')

def test_fraud_reasons_are_valid():
    valid_reasons = {
        "Unknown Vendor", "IBAN Mismatch", "Invalid PO", 
        "Amount Mismatch", "Vendor Mismatch"
    }
    for entry in report:
        assert entry['reason'] in valid_reasons, f"Invalid reason: {entry['reason']}"

def test_amount_mismatch_threshold():
    # Verify that any reported Amount Mismatch actually exceeds 0.01
    for entry in report:
        if entry['reason'] == "Amount Mismatch" and entry['po_number']:
            po_amount = pos.loc[pos['PO Number'] == entry['po_number'], 'Amount'].values[0]
            assert abs(entry['invoice_amount'] - po_amount) > 0.01

def test_page_number_indexing():
    for entry in report:
        assert isinstance(entry['invoice_page_number'], int)
        assert entry['invoice_page_number'] > 0
```