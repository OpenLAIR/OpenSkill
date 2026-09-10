import re

def check_balanced_braces(formula):
    """Check if braces {} are balanced. Returns (is_balanced, open_count, close_count)"""
    open_count = formula.count('{')
    close_count = formula.count('}')
    return (open_count == close_count, open_count, close_count)

def check_balanced_brackets(formula):
    """Check if brackets [] are balanced. Returns (is_balanced, open_count, close_count)"""
    open_count = formula.count('[')
    close_count = formula.count(']')
    return (open_count == close_count, open_count, close_count)

def fix_balanced_braces(formula):
    """Fix unbalanced braces by adding missing ones."""
    diff = formula.count('{') - formula.count('}')
    if diff > 0:
        formula += '}' * diff
    elif diff < 0:
        formula = '{' * (-diff) + formula
    return formula

def fix_balanced_brackets(formula):
    """Fix unbalanced brackets by adding missing ones."""
    diff = formula.count('[') - formula.count(']')
    if diff > 0:
        formula += ']' * diff
    elif diff < 0:
        formula = '[' * (-diff) + formula
    return formula

def fix_left_right_delimiters(formula):
    """Fix \\left/\\right delimiter mismatches using nesting analysis.
    Pairs \\left and \\right by stack depth and fixes mismatched delimiter types."""
    lefts = [(m.start(), m.group()) for m in re.finditer(r'\\left[\\[\\(\\{\\|.]', formula)]
    rights = [(m.start(), m.group()) for m in re.finditer(r'\\right[\\]\\)\\}\\|.]', formula)]
    
    if len(lefts) != len(rights):
        # Count-based fallback
        left_count = len(re.findall(r'\\left\b', formula))
        right_count = len(re.findall(r'\\right\b', formula))
        if left_count > right_count:
            formula += ' \\right.' * (left_count - right_count)
        elif right_count > left_count:
            formula = '\\left. ' * (right_count - left_count) + formula
        return formula
    
    # Match by nesting using stack
    events = []
    for pos, s in lefts:
        events.append((pos, 'L', s))
    for pos, s in rights:
        events.append((pos, 'R', s))
    events.sort(key=lambda x: x[0])
    
    stack = []
    replacements = []
    
    for pos, typ, s in events:
        if typ == 'L':
            stack.append((pos, s))
        elif typ == 'R' and stack:
            lpos, ls = stack.pop()
            l_delim = ls[-1]
            r_delim = s[-1]
            matching = {'(': ')', '[': ']', '{': '}', '|': '|', '.': '.'}
            expected_r = matching.get(l_delim, l_delim)
            if r_delim != expected_r:
                rev_matching = {')': '(', ']': '[', '}': '{', '|': '|', '.': '.'}
                new_l = rev_matching.get(r_delim, l_delim)
                new_ls = '\\left' + new_l
                replacements.append((lpos, ls, new_ls))
    
    for pos, old, new in sorted(replacements, key=lambda x: x[0], reverse=True):
        formula = formula[:pos] + new + formula[pos+len(old):]
    
    return formula

def fix_broken_commands(formula):
    """Fix common OCR-broken LaTeX commands."""
    fixes = [
        (r'\\fiac', r'\\frac'),
        (r'\\sqit', r'\\sqrt'),
    ]
    for pattern, replacement in fixes:
        formula = re.sub(pattern, replacement, formula)
    return formula

def validate_latex_formula(formula):
    """Validate a LaTeX formula. Returns (is_valid, list_of_issues)"""
    issues = []
    braces_ok, o, c = check_balanced_braces(formula)
    if not braces_ok:
        issues.append(f'Unbalanced braces: {o} open, {c} close')
    brackets_ok, o, c = check_balanced_brackets(formula)
    if not brackets_ok:
        issues.append(f'Unbalanced brackets: {o} open, {c} close')
    left_count = len(re.findall(r'\\left\b', formula))
    right_count = len(re.findall(r'\\right\b', formula))
    if left_count != right_count:
        issues.append(f'Unbalanced left/right: {left_count} left, {right_count} right')
    return (len(issues) == 0, issues)

def detect_and_fix_all(formula):
    """Detect and fix all syntax issues. Returns (fixed, was_changed, issues).
    Order: fix delimiter mismatches first, then braces, then brackets."""
    original = formula
    formula = fix_broken_commands(formula)
    formula = fix_left_right_delimiters(formula)
    formula = fix_balanced_braces(formula)
    formula = fix_balanced_brackets(formula)
    was_changed = (formula != original)
    issues = []
    if was_changed:
        _, issues = validate_latex_formula(original)
    return (formula, was_changed, issues)
