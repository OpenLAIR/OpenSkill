import re
import unicodedata
from typing import Dict, List

def normalize_width(text: str) -> str:
    """Converts full-width chars to half-width via NFKC, maps Chinese punctuation."""
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize('NFKC', text)
    punctuation_map = {
        '\u3002': '.', '\uff0c': ',', '\uff1b': ';', '\uff1a': ':',
        '\uff1f': '?', '\uff01': '!', '\uff08': '(', '\uff09': ')',
        '\u3001': ','  # Chinese enumeration comma
    }
    for full_punc, half_punc in punctuation_map.items():
        normalized = normalized.replace(full_punc, half_punc)
    return normalized

def expand_abbreviations(text: str) -> str:
    """Expand common manufacturing abbreviations."""
    abbreviations = {
        r'\bscr\b': 'scratch',
        r'\bpcb\b': 'printed circuit board',
        r'\bbtn\b': 'button',
    }
    for pattern, expansion in abbreviations.items():
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
    return text

def preprocess_text(text: str) -> str:
    """Full preprocessing pipeline: width norm, lowercase, whitespace, abbreviations."""
    if not isinstance(text, str):
        return ""
    text = normalize_width(text)
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = expand_abbreviations(text)
    return text.strip()

def split_mixed_text(text: str) -> List[str]:
    """Splits mixed Chinese-English text into contiguous blocks."""
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9_]+', text)
    return tokens

def split_compound_reasons(raw_text: str) -> List[Dict]:
    """Splits compound text by delimiters, preserving original span_text from raw.
    
    Only splits on commas and semicolons (not slashes, which are ambiguous
    in manufacturing context - used both as delimiters and within descriptions).
    Chinese commas/semicolons are first normalized to ASCII equivalents.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return []
    
    # Normalize width first to convert Chinese commas/semicolons
    normalized_text = normalize_width(raw_text)
    
    # Only split on commas and semicolons (NOT slashes)
    pattern = re.compile(r'[,;\n]+')
    
    segments = []
    start = 0
    for match in pattern.finditer(normalized_text):
        end = match.start()
        span_text = raw_text[start:end].strip()
        if span_text:
            segments.append({
                "span_text": span_text,
                "start_idx": start,
                "end_idx": end
            })
        start = match.end()
    
    # Final segment
    final_text = raw_text[start:].strip()
    if final_text:
        segments.append({
            "span_text": final_text,
            "start_idx": start,
            "end_idx": len(raw_text)
        })
    
    return segments
