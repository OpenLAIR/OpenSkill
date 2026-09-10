import re
from datetime import datetime
from openpyxl import Workbook


TOTAL_KEYWORD_GROUPS = [
    ['GRAND TOTAL'],
    ['TOTAL RM', 'TOTAL: RM', 'TOTAL:RM'],
    ['TOTAL AMOUNT'],
    ['TOTAL DUE', 'AMOUNT DUE', 'BALANCE DUE', 'NETT TOTAL', 'NET TOTAL'],
    ['TOTAL'],
]

EXCLUSION_PATTERNS = [
    r'\bSUB\s*TOTAL\b',
    r'\bSUBTOTAL\b',
    r'\bCHANGE\b',
    r'\bCASH\s+TENDERED\b',
]

SKIP_IF_ONLY_THESE = ['TAX', 'GST', 'SST', 'DISCOUNT']


def _should_exclude_line(line_upper):
    for pat in EXCLUSION_PATTERNS:
        if re.search(pat, line_upper):
            return True
    has_total_kw = bool(re.search(r'\bTOTAL\b|\bAMOUNT\b|\bBALANCE\b|\bNETT?\b|\bGRAND\b|\bDUE\b', line_upper))
    if not has_total_kw:
        for kw in SKIP_IF_ONLY_THESE:
            if kw in line_upper:
                return True
    return False


def _extract_amount_from_text(text):
    pattern = r'(\d{1,3}(?:,\d{3})*\.\d{1,2})'
    matches = re.findall(pattern, text)
    if matches:
        raw = matches[-1].replace(',', '')
        try:
            return f"{float(raw):.2f}"
        except ValueError:
            return None
    return None


def _extract_amount_loose(text):
    result = _extract_amount_from_text(text)
    if result:
        return result
    nums = re.findall(r'(?:RM|\$)?\s*(\d+)', text)
    if nums:
        raw = nums[-1]
        try:
            val = float(raw)
            if val > 0:
                return f"{val:.2f}"
        except ValueError:
            pass
    return None


def extract_total_amount(ocr_text):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    for keyword_group in TOTAL_KEYWORD_GROUPS:
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if _should_exclude_line(line_upper):
                continue
            for keyword in keyword_group:
                if keyword in line_upper:
                    amount = _extract_amount_from_text(line)
                    if amount:
                        return amount
                    amount = _extract_amount_loose(line)
                    if amount:
                        return amount
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if not _should_exclude_line(next_line.upper()):
                            amount = _extract_amount_from_text(next_line)
                            if amount:
                                return amount
                            amount = _extract_amount_loose(next_line)
                            if amount:
                                return amount
                    break
    return None


def extract_date(ocr_text):
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'june': 6, 'july': 7, 'august': 8, 'september': 9,
        'october': 10, 'november': 11, 'december': 12
    }
    text = ocr_text
    # Pattern 1: DD/MM/YYYY (4-digit year)
    for m in re.finditer(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})', text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= y <= 2099:
            if 1 <= mo <= 12 and 1 <= d <= 31:
                try:
                    return datetime(y, mo, d).strftime('%Y-%m-%d')
                except ValueError:
                    pass
            if 1 <= d <= 12 and 1 <= mo <= 31:
                try:
                    return datetime(y, d, mo).strftime('%Y-%m-%d')
                except ValueError:
                    pass
    # Pattern 2: DD/MM/YY (2-digit year)
    for m in re.finditer(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})(?!\d)', text):
        d, mo, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = 2000 + y2 if y2 < 50 else 1900 + y2
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return datetime(y, mo, d).strftime('%Y-%m-%d')
            except ValueError:
                pass
        if 1 <= d <= 12 and 1 <= mo <= 31:
            try:
                return datetime(y, d, mo).strftime('%Y-%m-%d')
            except ValueError:
                pass
    # Pattern 3: DD Mon YYYY
    for m in re.finditer(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', text):
        d = int(m.group(1))
        ms = m.group(2).lower()
        y = int(m.group(3))
        mo = month_map.get(ms) or month_map.get(ms[:3])
        if mo and 1900 <= y <= 2099 and 1 <= d <= 31:
            try:
                return datetime(y, mo, d).strftime('%Y-%m-%d')
            except ValueError:
                pass
    # Pattern 4: Mon DD, YYYY
    for m in re.finditer(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', text):
        ms = m.group(1).lower()
        d = int(m.group(2))
        y = int(m.group(3))
        mo = month_map.get(ms) or month_map.get(ms[:3])
        if mo and 1900 <= y <= 2099 and 1 <= d <= 31:
            try:
                return datetime(y, mo, d).strftime('%Y-%m-%d')
            except ValueError:
                pass
    return None


def parse_receipt_text(ocr_text):
    return {
        'date': extract_date(ocr_text),
        'total_amount': extract_total_amount(ocr_text)
    }


def write_results_to_excel(results, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])
    sorted_results = sorted(results, key=lambda r: r['filename'])
    for row in sorted_results:
        ws.append([row['filename'], row.get('date'), row.get('total_amount')])
    wb.save(output_path)
