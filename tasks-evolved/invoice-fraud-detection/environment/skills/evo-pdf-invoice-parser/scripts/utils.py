import pdfplumber
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def extract_vendor_name(text):
    match = re.search(r'(?i)From:\s*(.+)', text)
    if match:
        return match.group(1).strip()
    return None

def extract_iban(text):
    match = re.search(r'(?i)(?:Payment\s+)?IBAN:\s*(\S+)', text)
    if match:
        return re.sub(r'\s+', '', match.group(1))
    return None

def extract_invoice_amount(text):
    pattern = r'(?i)Total\s*[\$\xe2\x82\xac\xc2\xa3]?\s*([\d,]+\.\d+)'
    match = re.search(pattern, text)
    if match:
        raw = match.group(1).replace(',', '')
        try:
            return float(raw)
        except ValueError:
            return None
    return None

def extract_po_number(text):
    match = re.search(r'(?i)PO\s*Number[\s:]*(PO-[A-Z0-9]+)', text)
    if match:
        return match.group(1).strip().upper()
    match = re.search(r'(?i)Purchase\s+Order[\s:]*(PO-[A-Z0-9]+)', text)
    if match:
        return match.group(1).strip().upper()
    match = re.search(r'\bPO-[A-Z0-9]+\b', text)
    if match:
        return match.group(0).upper()
    return None

def extract_invoice_fields_from_text(text):
    return {
        'vendor_name': extract_vendor_name(text),
        'iban': extract_iban(text),
        'invoice_amount': extract_invoice_amount(text),
        'po_number': extract_po_number(text),
    }

def extract_all_invoices(pdf_path):
    invoices = []
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            page_number = idx + 1
            text = page.extract_text(layout=False)
            if text:
                text = text.strip()
                fields = extract_invoice_fields_from_text(text)
                fields['invoice_page_number'] = page_number
                fields['raw_text'] = text
                invoices.append(fields)
    return invoices
