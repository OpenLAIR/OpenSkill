# Domain Reference for evo-latex-syntax-validation

**Responsibility**: Syntax validation of LaTeX strings, detection of unmatched braces/delimiters/broken commands, and automated heuristic fixing of syntax errors

**Key functions to implement**: validate_latex_formula, check_balanced_braces, fix_left_right_delimiters, fix_broken_commands, detect_and_fix_all

---

## 4. LaTeX Formula Cleaning and Validation


Due to the stochastic nature of machine learning, OCR-extracted LaTeX is riddled with structural artifacts. Attempting to feed these directly into a downstream analytical engine or RAG pipeline will lead to catastrophic failures.

### 4.3 Detecting and Fixing Common Syntax Errors


While `LatexWalker` detects errors [cite: 26], automatically fixing them requires heuristic interventions. 

**Fixing Unmatched `\left` and `\right`:**
LaTeX requires every `\left<delim>` to have a corresponding `\right<delim>` (or `\right.`). OCR often drops one.

```python
def fix_left_right_delimiters(formula: str) -> str:
    """
    Heuristically balances \left and \right operators.
    """
    left_count = len(re.findall(r'\\left\b', formula))
    right_count = len(re.findall(r'\\right\b', formula))
    
    if left_count > right_count:
        # Append invisible right delimiters to close the groups
        formula += " \\right." * (left_count - right_count)
    elif right_count > left_count:
        # Prepend invisible left delimiters
        formula = ("\\left. " * (right_count - left_count)) + formula
        
    return formula
```

**Stripping Trailing Equation Numbers:**
Academic equations extracted by `texify` frequently include the numbering string [cite: 11, 12]. This regex safely removes trailing identifiers like `(1)`, `(2.3a)`, `[cite: 2]`, or explicit `\tag{...}` commands [cite: 12].

```python
def strip_equation_numbering(formula: str) -> str:
    """
    Removes visual equation numbering and \tag{} macros.
    """
    # Remove standard LaTeX tagging macros
    formula = re.sub(r'\\tag\{.*?\}', '', formula)
    formula = re.sub(r'\\label\{.*?\}', '', formula)
    formula = re.sub(r'\\nonumber\b', '', formula)
    formula = re.sub(r'\\notag\b', '', formula)
    
    # Remove right-aligned numbering like (1), (A.1), [3.4] at the end of the string
    # E.g., Matches: " \quad (1.2) $$" -> " $$"
    pattern = r'(?:\s*|\\quad\s*|\\qquad\s*)[(\[]?[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*[)\]]?\s*$'
    formula = re.sub(pattern, '', formula).strip()
    
    # Clean up trailing punctuation accidentally included in the math block
    formula = re.sub(r'[,.;:]\s*$', '', formula)
    
    return formula
```

---

## 5. Rendering Verification with Playwright


Even if a formula passes AST validation via `pylatexenc` [cite: 26], the ultimate test of its accuracy is whether an engine like MathJax can successfully render it into a DOM tree without throwing an internal rendering error [cite: 27].

By utilizing Playwright (version 1.57.0) in a headless Chromium instance, we can inject the extracted LaTeX into a minimal HTML document, allow MathJax to process it, and dynamically poll the DOM for error classes such as `.MathJax_ERROR` or `<mjx-merror>` [cite: 27].

### 5.1 Playwright Implementation for MathJax Verification


This script utilizes `sync_playwright` to orchestrate the headless browser, injecting a local HTML template equipped with the MathJax CDN [cite: 27, 28].

```python
import time
from playwright.sync_api import sync_playwright

class MathJaxVerifier:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True) # Ensure headless execution
        self.page = self.browser.new_page()
        
    def close(self):
        """Cleanly terminate the browser context."""
        self.browser.close()
        self.playwright.stop()

    def verify_formula(self, latex_string: str) -> dict:
        """
        Injects a LaTeX formula into a DOM with MathJax and checks for rendering errors.
        """
        # Minimal HTML template loading MathJax 3 via CDN
        # Using double braces {{ }} to escape Python's f-string formatting
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <script>
                window.MathJax = {{
                    tex: {{
                        inlineMath: [['$', '$']],
                        displayMath: [['$$', '$$']]
                    }},
                    startup: {{
                        pageReady: () => {{
                            return MathJax.startup.defaultPageReady().then(() => {{
                                window.renderingComplete = true;
                            }});
                        }}
                    }}
                }};
            </script>
            <script id="MathJax-script" async 
                src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js">
            </script>
        </head>
        <body>
            <!-- Inject the raw LaTeX block -->
            <div id="formula-container">$$ {latex_string} $$</div>
        </body>
        </html>
        """
        
        # Load the HTML content directly into the page
        self.page.set_content(html_content)
        
        # Wait for the MathJax promise to resolve indicating processing is done
        try:
            self.page.wait_for_function("window.renderingComplete === true", timeout=5000)
        except Exception as e:
            return {"valid": False, "error": "MathJax rendering timed out."}
            
        # Execute JavaScript in the browser to query for MathJax error nodes
        # mjx-merror is used in MathJax v3, .MathJax_ERROR in legacy versions
        verification_result = self.page.evaluate("""
            () => {
                const container = document.querySelector('#formula-container');
                
                // MathJax v3 error element
                const merror = container.querySelector('mjx-merror');
                if (merror) {
                    return { valid: false, error: merror.textContent || "Unknown mjx-merror" };
                }
                
                // Fallback for older MathJax versions
                const legacyError = container.querySelector('.MathJax_Error');
                if (legacyError) {
                    return { valid: false, error: legacyError.textContent };
                }
                
                return { valid: true, error: null };
            }
        """)
        
        return verification_result

### 5.2 Handling Encoding Issues and Raw Strings


When passing LaTeX strings in Python, the backslash `\` is an escape character. If you read the output from `marker-pdf` from a file, Python handles the raw characters correctly. However, if you are defining strings manually in code or manipulating them via Regex substitutions, you must use Python raw strings (`r"\frac"`) or double-escape them (`"\\frac"`) [cite: 29]. Failure to do so will result in `\f` being interpreted as a form-feed character, which immediately breaks both `pylatexenc` and MathJax [cite: 29, 30].

---