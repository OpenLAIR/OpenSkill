---
name: evo-text-normalize
description: Preprocesses and normalizes noisy multilingual (Chinese-English mixed) industrial text. Handles full-width to half-width conversion, Unicode NFKC normalization, lowercasing, whitespace cleanup, punctuation normalization, abbreviation expansion, and splitting compound reasons.
---

# evo-text-normalize

Text preprocessing for noisy manufacturing defect logs with mixed Chinese-English content.

## Key Functions

- `normalize_width(text)` - NFKC normalization + Chinese punctuation mapping
- `preprocess_text(text)` - Full pipeline: width norm, lowercase, whitespace, abbreviations
- `expand_abbreviations(text)` - Expand common manufacturing abbreviations
- `split_mixed_text(text)` - Split mixed Chinese/English into contiguous blocks
- `split_compound_reasons(raw_text)` - Split compound reasons by delimiters, preserving spans

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-text-normalize/scripts')
from utils import preprocess_text, split_compound_reasons, normalize_width

clean = preprocess_text("ＰＣＢ Ｆａｉｌ")
segments = split_compound_reasons("scratch on panel, button stuck; 屏幕坏了")
```
