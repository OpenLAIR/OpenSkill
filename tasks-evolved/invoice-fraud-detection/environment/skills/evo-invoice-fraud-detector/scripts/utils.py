import json
import logging
from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process, utils as rfutils

logger = logging.getLogger(__name__)

def find_vendor_match(vendor_name: str, vendor_dict: Dict) -> Optional[str]:
    """
    Fuzzy match vendor name against vendor database.
    vendor_dict: {vendor_id: {"name": name, "iban": iban}}
    Returns vendor_id if match found with score >= 85, else None.
    """
    if not vendor_name:
        return None
    
    # Build choices: {name: vendor_id}
    choices = {v_data['name']: v_id for v_id, v_data in vendor_dict.items()}
    
    result = process.extractOne(
        query=vendor_name,
        choices=choices.keys(),
        scorer=fuzz.token_set_ratio,
        score_cutoff=85,
        processor=rfutils.default_process
    )
    
    if result is not None:
        matched_name, score, _ = result
        return choices[matched_name]
    
    return None

def check_invoice_fraud(invoice: Dict, vendor_dict: Dict, po_dict: Dict) -> Optional[Dict]:
    """
    Check a single invoice for fraud using priority-ordered rules.
    Returns a fraud record dict if fraudulent, or None if clean.
    
    Priority order:
    1. Unknown Vendor - vendor name not in vendors database
    2. IBAN Mismatch - vendor exists but IBAN doesn't match
    3. Invalid PO - PO number doesn't exist in PO database
    4. Amount Mismatch - PO exists but amount differs by > 0.01
    5. Vendor Mismatch - PO valid but linked to different vendor
    """
    vendor_name = invoice.get('vendor_name')
    iban = invoice.get('iban')
    po_number = invoice.get('po_number')
    amount = invoice.get('invoice_amount')
    page = invoice.get('invoice_page_number')
    
    # Rule 1: Unknown Vendor
    vendor_id = find_vendor_match(vendor_name, vendor_dict)
    if vendor_id is None:
        return {
            'invoice_page_number': page,
            'vendor_name': vendor_name,
            'invoice_amount': amount,
            'iban': iban,
            'po_number': po_number if po_number else None,
            'reason': 'Unknown Vendor'
        }
    
    # Rule 2: IBAN Mismatch
    db_iban = vendor_dict[vendor_id]['iban'].replace(' ', '')
    invoice_iban = (iban or '').replace(' ', '')
    if invoice_iban and db_iban and invoice_iban != db_iban:
        return {
            'invoice_page_number': page,
            'vendor_name': vendor_name,
            'invoice_amount': amount,
            'iban': iban,
            'po_number': po_number if po_number else None,
            'reason': 'IBAN Mismatch'
        }
    
    # Rule 3: Invalid PO
    if po_number is None:
        # No PO found - set to null in output
        # According to task: "If the PO is missing, set it to null"
        # But we still need to check if this is fraud - missing PO itself
        # isn't listed as a fraud reason, so only if other rules trigger
        pass
    elif po_number not in po_dict:
        return {
            'invoice_page_number': page,
            'vendor_name': vendor_name,
            'invoice_amount': amount,
            'iban': iban,
            'po_number': po_number,
            'reason': 'Invalid PO'
        }
    else:
        # PO exists - check rules 4 and 5
        po_record = po_dict[po_number]
        
        # Rule 4: Amount Mismatch
        if amount is not None and abs(amount - po_record['amount']) > 0.01:
            return {
                'invoice_page_number': page,
                'vendor_name': vendor_name,
                'invoice_amount': amount,
                'iban': iban,
                'po_number': po_number,
                'reason': 'Amount Mismatch'
            }
        
        # Rule 5: Vendor Mismatch
        if po_record['vendor_id'] != vendor_id:
            return {
                'invoice_page_number': page,
                'vendor_name': vendor_name,
                'invoice_amount': amount,
                'iban': iban,
                'po_number': po_number,
                'reason': 'Vendor Mismatch'
            }
    
    # No fraud detected
    return None

def run_fraud_detection_pipeline(invoices: List[Dict], vendor_dict: Dict, po_dict: Dict) -> List[Dict]:
    """Run fraud detection on all invoices. Returns list of flagged invoices."""
    flagged = []
    for invoice in invoices:
        result = check_invoice_fraud(invoice, vendor_dict, po_dict)
        if result is not None:
            flagged.append(result)
    return flagged

def save_fraud_report(flagged: List[Dict], output_path: str):
    """Save fraud report as JSON."""
    with open(output_path, 'w') as f:
        json.dump(flagged, f, indent=2, ensure_ascii=False)
