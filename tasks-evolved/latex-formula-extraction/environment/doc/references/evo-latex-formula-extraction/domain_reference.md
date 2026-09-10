# Domain Reference for evo-latex-formula-extraction

**Responsibility**: Regex-based extraction of $$...$$ blocks, stripping of equation numbering/tags/trailing punctuation, normalization of LaTeX environments to clean display math format

**Key functions to implement**: extract_display_formulas, strip_equation_numbering, strip_trailing_punctuation, normalize_formula

---

## 3. Distinguishing Display Math from Inline Math


Once the `marker-pdf` pipeline yields a Markdown string, the next critical step is extracting the standalone formulas.

### 3.1 Patterns and Heuristics for Extraction


In `marker-pdf` output, display math is fenced by `$$` on either side [cite: 1, 2]. However, a naive regex like `\$\$(.*?)\$\$` is insufficient because:
1.  Formulas often contain internal line breaks (`\n`).
2.  Adjacent inline math formulas (e.g., `$x$` and `$y$`) might accidentally trigger false positive matches if regex greediness is not controlled.
3.  Some block formulas are mistakenly formatted by OCR with single dollars but reside on their own isolated lines.

**The Optimal Regex for Marker-PDF Block Math:**

```python
import re

def extract_display_math(markdown_text: str) -> list[str]:
    """
    Extracts standalone block math from marker-pdf markdown output.
    """
    # Pattern explanation:
    # \$\$          : Match opening $$
    # ([\s\S]*?)    : Match any character (including newlines) non-greedily
    # \$\$          : Match closing $$
    # (?:\s*$)      : Ensure it is essentially standalone by looking for line ends/whitespace
    
    pattern = re.compile(r'\$\$([\s\S]*?)\$\$', re.MULTILINE)
    
    raw_formulas = pattern.findall(markdown_text)
    
    # Clean up whitespace
    return [formula.strip() for formula in raw_formulas]
```

### 3.2 Standard Environments and Delimiters in Source LaTeX


In traditional LaTeX source code, displayed equations can be invoked using numerous environments. If you are parsing raw LaTeX or if `marker-pdf` occasionally leaks native environments without the `$$` wrapper, you must account for all of them [cite: 11].

The standard display math delimiters and environments include:
*   **Delimiters:** `$$ ... $$`, `\[ ... \]` [cite: 11, 12].
*   **Base Environments:** `\begin{equation} ... \end{equation}`, `\begin{displaymath} ... \end{displaymath}` [cite: 11].
*   **AMS-Math Environments:** `\begin{align}`, `\begin{gather}`, `\begin{multline}`, `\begin{flalign}`, `\begin{eqnarray}` (and their starred versions like `\begin{align*}`) [cite: 11].

### 4.1 Common OCR Artifacts in Mathematical LaTeX


1.  **Misrecognized Symbols:** Confusion between `l`, `1`, `I`, and `|`. Confusion between `\times` and `x`.
2.  **Broken Commands:** `\fiac` instead of `\frac`, `\sqit` instead of `\sqrt`.
3.  **Unmatched Brackets:** e.g., `\frac{a}{b` or `\left( x + y \right.` [cite: 22, 23].
4.  **Trailing Equation Numbers:** Extraction of visual numbering as part of the equation, e.g., `a^2 + b^2 = c^2 \quad (1.4)` [cite: 11, 12].