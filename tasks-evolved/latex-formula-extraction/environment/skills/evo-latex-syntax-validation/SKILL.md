---
name: evo-latex-syntax-validation
description: Validates extracted LaTeX formulas for syntax correctness and produces fixed versions of problematic formulas. Focuses on typos/syntax errors only.
---

# evo-latex-syntax-validation

Validates and fixes LaTeX formula syntax issues.

## Key Functions

- `validate_latex_formula(formula)` - Check for syntax issues
- `check_balanced_braces(formula)` - Check {} balance
- `check_balanced_brackets(formula)` - Check [] balance  
- `fix_left_right_delimiters(formula)` - Balance \left/\right
- `fix_broken_commands(formula)` - Fix OCR typos in commands
- `detect_and_fix_all(formula)` - Full validation and fix pipeline

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-latex-syntax-validation/scripts')
from utils import detect_and_fix_all, validate_latex_formula

fixed, was_changed, issues = detect_and_fix_all(formula)
if was_changed:
    print(f"Fixed: {issues}")
```
