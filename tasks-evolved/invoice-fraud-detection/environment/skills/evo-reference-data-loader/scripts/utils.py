import pandas as pd
import logging
from typing import Dict

logger = logging.getLogger(__name__)

def load_vendor_database(excel_path: str) -> Dict:
    """
    Loads vendor data from Excel file.
    Returns dict: {vendor_id: {"name": name, "iban": iban}}
    Note: column names in the xlsx are lowercase: id, name, iban
    """
    df = pd.read_excel(
        io=excel_path,
        engine='openpyxl',
        header=0,
        dtype=str,
        keep_default_na=False
    )
    # Strip whitespace from all string columns
    for col in df.columns:
        df[col] = df[col].str.strip()
    
    # Build lookup dict keyed by vendor id
    vendor_dict = {}
    for _, row in df.iterrows():
        vendor_dict[row['id']] = {
            'name': row['name'],
            'iban': row['iban']
        }
    return vendor_dict

def load_po_database(csv_path: str) -> Dict:
    """
    Loads PO data from CSV file.
    Returns dict: {po_number: {"vendor_id": vid, "amount": float}}
    CSV columns: po_number, vendor_id, amount
    """
    df = pd.read_csv(
        csv_path,
        dtype={'po_number': str, 'vendor_id': str}
    )
    # Strip whitespace
    df['po_number'] = df['po_number'].str.strip().str.upper()
    df['vendor_id'] = df['vendor_id'].str.strip()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    
    po_dict = {}
    for _, row in df.iterrows():
        po_dict[row['po_number']] = {
            'vendor_id': row['vendor_id'],
            'amount': float(row['amount'])
        }
    return po_dict
