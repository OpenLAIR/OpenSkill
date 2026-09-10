import re

def extract_display_formulas(markdown_text):
    """
    Extracts standalone block math from marker-pdf markdown output.
    Uses $$ delimiters to find display math blocks.
    
    Args:
        markdown_text (str): Markdown text from marker-pdf
    
    Returns:
        list[str]: List of formula strings (without $$ delimiters)
    """
    pattern = re.compile(r'\$\$([\s\S]*?)\$\$', re.MULTILINE)
    raw_formulas = pattern.findall(markdown_text)
    # Clean up whitespace and filter empty
    formulas = [formula.strip() for formula in raw_formulas]
    formulas = [f for f in formulas if f]  # Remove empty strings
    return formulas

def strip_equation_numbering(formula):
    """
    Removes visual equation numbering and \tag{} macros from a formula.
    
    Args:
        formula (str): Raw LaTeX formula string
    
    Returns:
        str: Formula with equation numbers removed
    """
    # Remove standard LaTeX tagging macros
    formula = re.sub(r'\\tag\{.*?\}', '', formula)
    formula = re.sub(r'\\label\{.*?\}', '', formula)
    formula = re.sub(r'\\nonumber\b', '', formula)
    formula = re.sub(r'\\notag\b', '', formula)
    return formula.strip()

def strip_trailing_punctuation(formula):
    """
    Removes trailing commas, periods, semicolons, colons from formula.
    
    Args:
        formula (str): LaTeX formula string
    
    Returns:
        str: Formula with trailing punctuation removed
    """
    formula = re.sub(r'[,.;:]\s*$', '', formula)
    return formula.strip()

def normalize_formula(formula):
    """
    Normalizes a LaTeX formula by:
    - Stripping equation numbering
    - Stripping trailing punctuation
    - Cleaning up whitespace
    
    Args:
        formula (str): Raw LaTeX formula
    
    Returns:
        str: Cleaned formula
    """
    formula = strip_equation_numbering(formula)
    formula = strip_trailing_punctuation(formula)
    # Collapse multiple spaces/newlines into single space
    formula = re.sub(r'\s+', ' ', formula).strip()
    return formula

def format_output(formulas, fixed_formulas=None):
    """
    Formats formulas into the required markdown output format.
    Each formula on its own line wrapped in $$.
    
    Args:
        formulas (list[str]): Original cleaned formulas
        fixed_formulas (list[str]): Fixed versions of problematic formulas
    
    Returns:
        str: Formatted markdown string
    """
    lines = []
    for f in formulas:
        lines.append(f'$${f}$$')
    
    if fixed_formulas:
        lines.append('')  # blank line separator
        for f in fixed_formulas:
            lines.append(f'$${f}$$')
    
    return '\n'.join(lines) + '\n'
