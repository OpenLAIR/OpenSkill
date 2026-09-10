To create a robust surrogate test for the LaTeX formula extraction task, we must define invariants that are independent of the specific `marker-pdf` implementation. Since we are extracting mathematical content, we can leverage the formal properties of LaTeX syntax and document structure.

### 1. Independently Computable Reference Values
For a given formula, we can define a "Sanity Check" oracle based on LaTeX syntax rules.

*   **Input:** A string extracted from the PDF (e.g., `\frac{a}{b}`).
*   **Intermediate:** A check for balanced delimiters (braces `{}` and brackets `[]`).
*   **Computation Chain:**
    1.  **Delimiter Balance:** A valid LaTeX formula must have an equal number of opening and closing braces.
    2.  **Example:** If the extracted string is `\frac{a}{b`, the count of `{` is 1 and `}` is 0.
    3.  **Assertion:** `formula.count('{') == formula.count('}')` and `formula.count('[') == formula.count(']')`.
*   **Verification:** This can be computed via a simple Python function `is_balanced(s)` and used as a test oracle for any extracted line.

### 2. Dataset-Level Statistical Invariants
These properties must hold true for the final `/root/latex_formula_extraction.md` file regardless of the extraction method:

*   **Format Constraint:** Every line must start with `$$` and end with `$$`.
    *   *Assertion:* `all(line.startswith("$$") and line.endswith("$$") for line in lines if line.strip())`
*   **Non-Empty Constraint:** No extracted formula should be empty or contain only whitespace.
    *   *Assertion:* `all(len(line.strip(" $")) > 0 for line in lines if line.strip())`
*   **Exclusion of Punctuation:** The task requires removing trailing commas or periods.
    *   *Assertion:* `all(not line.strip(" $").endswith(('.', ',')) for line in lines if line.strip())`
*   **Unique Formula Count:** If the PDF contains $N$ distinct visual blocks identified as equations, the output file should contain at least $N$ lines.

### 3. Cross-Validation Approaches
To verify the extraction without relying solely on `marker-pdf`, use an alternative structural extraction method:

*   **Alternative Tool:** `pdfplumber` (or `PyMuPDF` as mentioned in your domain knowledge) can extract text blocks.
*   **Cross-Check Logic:**
    1.  Use `PyMuPDF` (`import fitz`) to extract text blocks.
    2.  Filter blocks that contain high densities of non-alphanumeric characters (common in LaTeX).
    3.  Compare the count of "formula-like" blocks found by `PyMuPDF` against the count of `$$` blocks in your output file.
*   **Code Snippet for Verification:**
    ```python
    import fitz # PyMuPDF
    doc = fitz.open("latex_paper.pdf")
    # Count blocks that look like math (e.g., contain \frac, \sum, or ^)
    math_blocks = [b for page in doc for b in page.get_text("blocks") if "\\" in b[4]]
    assert len(extracted_formulas) >= len(math_blocks) * 0.5 # Heuristic threshold
    ```

### 4. Benchmarks and Reference Implementations
*   **Syntax Validation:** Use the `pylatexenc` library to programmatically validate the LaTeX strings.
    *   *Reference:* `pylatexenc.latexnodes.parsers.LatexParser` can parse the string. If it raises a `LatexWalkerParseError`, the formula is syntactically invalid.
    *   *Test Oracle:*
        ```python
        from pylatexenc.latexwalker import LatexWalker
        def test_latex_syntax(formula):
            try:
                LatexWalker(formula).get_latex_nodes()
            except Exception:
                pytest.fail(f"Invalid LaTeX syntax: {formula}")
        ```
*   **Standard Test Case:** Use a known LaTeX formula from the [LaTeX Project documentation](https://www.latex-project.org/help/documentation/) as a "Golden Sample" to verify your parser's ability to handle complex nesting:
    *   *Input:* `$$ \int_{0}^{\infty} e^{-x^2} dx = \frac{\sqrt{\pi}}{2} $$`
    *   *Expected:* The parser should return this string exactly, stripped of any trailing punctuation.