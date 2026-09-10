# Domain Reference for evo-text-normalize

**Responsibility**: All text preprocessing: NFKC normalization, full-width/half-width conversion, Chinese punctuation mapping, whitespace normalization, case folding, abbreviation expansion, and mixed-language token splitting. Does NOT perform matching or scoring.

**Key functions to implement**: normalize_width, preprocess_text, expand_abbreviations, split_mixed_text, split_compound_reasons

---

## 2. Native Chinese Text Processing Strategies


Processing mixed Chinese-English texts without heavy external NLP libraries (e.g., `jieba`, `spaCy`) requires leveraging Python's Unicode capabilities and regular expressions [cite: 14].

### 2.1 Character-Level Tokenization and Regex Approaches


In Chinese, meaning is conveyed through discrete characters (ideographs) where spaces are not historically used as word boundaries. Without a dictionary-based tokenizer like `jieba`, the most robust fallback strategy for similarity matching is **character-level tokenization** (unigrams or bigrams).

CJK Unified Ideographs occupy specific Unicode blocks. The primary block for everyday Chinese text is `\u4e00-\u9fff` [cite: 3]. Using the `re` module, we can systematically isolate Chinese text from ASCII English text, digits, and punctuation.

```python
import re

### 2.2 Full-width to Half-width Normalization


A prevalent source of noise in East Asian text input is the accidental use of "full-width" (全角) Latin characters, digits, and punctuation instead of "half-width" (半角) ASCII characters [cite: 15, 16]. A full-width `Ａ` (U+FF21) is visually similar to a standard `A` (U+0041) but possesses a different code point, completely failing exact string matching algorithms and distorting byte-level evaluations [cite: 17, 18].

Python’s `unicodedata` module provides an elegant, natively optimized solution via Normalization Form KC (NFKC) [cite: 14, 15, 19]. "NFKC" applies Compatibility Decomposition followed by Canonical Composition, efficiently mapping full-width variants back to their ASCII equivalents [cite: 15].

```python
import unicodedata

def normalize_width(text: str) -> str:
    """
    Converts full-width English/numeric/punctuation characters to half-width.
    """
    # NFKC normalizes U+FF01–FF5E (full-width) into U+0021-007E (ASCII)
    normalized = unicodedata.normalize('NFKC', text)
    
    # Custom mapping for lingering Chinese punctuation to English equivalents
    punctuation_map = {
        '。': '.', '，': ',', '；': ';', '：': ':', 
        '？': '?', '！': '!', '（': '(', '）': ')',
        '、': ','  # Chinese enumeration comma
    }
    for full_punc, half_punc in punctuation_map.items():
        normalized = normalized.replace(full_punc, half_punc)
        
    return normalized
```
This step is structurally critical; matching "ＰＣＢ Ｆａｉｌ" against "PCB Fail" using `SequenceMatcher` without NFKC normalization yields a ratio of 0.0 [cite: 17].

### 2.3 Manufacturing and QA Abbreviation Expansion


Industrial defect logs are notorious for shorthand [cite: 20]. Abbreviations must be expanded prior to scoring. In manufacturing QA, common abbreviations include "AQL" (Acceptable Quality Limit), "QC" (Quality Control), "OOC" (Out of Control), and shorthand like "SCR" (Scratch) [cite: 21, 22, 23].

A static dictionary mapping applied via regular expressions ensures reliable preprocessing:
```python
def expand_abbreviations(text: str) -> str:
    # Use word boundaries (\b) for English to prevent partial matching
    abbreviations = {
        r'\bscr\b': 'scratch',
        r'\bpcb\b': 'printed circuit board',
        r'\bbtn\b': 'button',
        r'不良': 'defect',
        r'NG': 'defect',
        r'OK': 'pass'
    }
    
    text_lower = text.lower()
    for pattern, expansion in abbreviations.items():
        text_lower = re.sub(pattern, expansion, text_lower, flags=re.IGNORECASE)
        
    return text_lower
```

---

## 3. Text Normalization Pipeline for Noisy Descriptions


Building an industrial-grade string matcher requires assembling isolated normalizations into a deterministic pipeline.

### 3.1 Preprocessing and Noise Removal

Engineers frequently inject whitespace noise (tabs, multiple spaces, invisible characters) into text fields. A robust preprocessing function sanitizes the input stream.

```python
def preprocess_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    
    # 1. Width normalization
    text = normalize_width(text)
    # 2. Lowercase all Latin text
    text = text.lower()
    # 3. Strip non-essential control characters and excess whitespace
    text = re.sub(r'\s+', ' ', text)
    # 4. Expand domain abbreviations
    text = expand_abbreviations(text)
    # 5. Trim leading/trailing whitespace
    return text.strip()
```

### 3.2 Splitting Compound Defect Reasons (Span Tracking)

A major challenge occurs when an operator reports multiple defects in a single cell: `"scratch on panel, button stuck; 屏幕坏了"`. The system must split this compound text into individual reasons while preserving the original character spans so that downstream interfaces can highlight exactly which substring mapped to which code.

```python
from typing import Dict, List, Tuple

def split_compound_reasons(raw_text: str) -> List[Dict]:
    """
    Splits compound text by delimiters, preserving original spans.
    """
    normalized_text = normalize_width(raw_text)
    # Delimiters: comma, semicolon, slash, and Chinese enumeration comma
    pattern = re.compile(r'[,;/\n]+')
    
    segments = []
    start = 0
    for match in pattern.finditer(normalized_text):
        end = match.start()
        span_text = raw_text[start:end].strip() # Use raw_text to preserve original characters
        if span_text:
            segments.append({
                "span_text": span_text,
                "start_idx": start,
                "end_idx": end
            })
        start = match.end()
        
    # Capture the final segment
    final_text = raw_text[start:].strip()
    if final_text:
        segments.append({
            "span_text": final_text,
            "start_idx": start,
            "end_idx": len(raw_text)
        })
        
    return segments
```

---