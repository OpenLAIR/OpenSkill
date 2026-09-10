---
name: evo-invoice-fraud-detector
description: Implements fraud detection pipeline with fuzzy vendor matching via rapidfuzz, priority-ordered fraud checks, and JSON report generation.
---

# evo-invoice-fraud-detector

Detects invoice fraud using 5 priority-ordered rules.

## Fraud Rules (Priority Order)
1. Unknown Vendor - vendor name not in vendors database (fuzzy match score < 85)
2. IBAN Mismatch - vendor exists but IBAN doesn't match
3. Invalid PO - PO number doesn't exist in PO database
4. Amount Mismatch - PO exists but amount differs by > 0.01
5. Vendor Mismatch - PO valid but linked to different vendor ID

## Key Functions

- `find_vendor_match(vendor_name, vendor_dict)` - Fuzzy match using token_set_ratio, cutoff=85
- `check_invoice_fraud(invoice, vendor_dict, po_dict)` - Check single invoice
- `run_fraud_detection_pipeline(invoices, vendor_dict, po_dict)` - Check all invoices
- `save_fraud_report(flagged, output_path)` - Save JSON report

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-pdf-invoice-parser/scripts')
sys.path.insert(0, '/app/environment/skills/evo-reference-data-loader/scripts')
sys.path.insert(0, '/app/environment/skills/evo-invoice-fraud-detector/scripts')

from utils import extract_all_invoices
from utils import load_vendor_database, load_po_database  # name collision - use aliases

# Better approach: import modules directly
import importlib
parser = importlib.import_module('utils')  # depends on sys.path order
```
