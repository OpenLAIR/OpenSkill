# Domain Reference for evo-reference-data-loader

**Responsibility**: Ingesting, cleaning, and structuring reference data from vendors.xlsx and purchase_orders.csv into Python dictionaries suitable for lookup operations.

**Key functions to implement**: load_vendor_database, load_po_database

---

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