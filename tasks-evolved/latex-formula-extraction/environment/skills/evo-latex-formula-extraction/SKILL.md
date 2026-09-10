---
name: evo-latex-formula-extraction
description: Extracts display math formulas from marker-pdf Markdown output, strips equation numbers/tags/trailing punctuation, and organizes them for output.
---

# evo-latex-formula-extraction

Extracts display math formulas from marker-pdf Markdown output and cleans them.

## Key Functions

- `extract_display_formulas(markdown_text)` - Extract all $$...$$ blocks
- `strip_equation_numbering(formula)` - Remove \tag{}, \label{}, etc.
- `strip_trailing_punctuation(formula)` - Remove trailing commas, periods, etc.
- `normalize_formula(formula)` - Full cleanup pipeline
- `format_output(formulas, fixed_formulas)` - Format for markdown output

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-latex-formula-extraction/scripts')
from utils import extract_display_formulas, normalize_formula, format_output

formulas = extract_display_formulas(markdown_text)
cleaned = [normalize_formula(f) for f in formulas]
output = format_output(cleaned)
```
