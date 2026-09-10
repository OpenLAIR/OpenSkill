import ast
import os
import subprocess
import difflib
from typing import List, Dict, Tuple, Optional


def find_python_files(repo_path: str, exclude_dirs: List[str] = None) -> List[str]:
    """Find all Python files in a repository, excluding specified directories."""
    if exclude_dirs is None:
        exclude_dirs = ['.git', 'env', 'venv', '.venv', '__pycache__', 'node_modules']
    py_files = []
    for dp, dn, fns in os.walk(repo_path):
        dn[:] = [d for d in dn if d not in exclude_dirs]
        for fn in fns:
            if fn.endswith('.py'):
                py_files.append(os.path.join(dp, fn))
    return py_files


def check_syntax_errors(py_files: List[str]) -> List[Dict]:
    """Check Python files for syntax errors using ast.parse."""
    errors = []
    for fp in py_files:
        try:
            with open(fp) as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append({
                'file': fp,
                'type': 'syntax_error',
                'line': e.lineno,
                'message': str(e)
            })
    return errors


def check_import_errors(repo_path: str) -> List[Dict]:
    """Try importing the main package and capture import errors."""
    errors = []
    result = subprocess.run(
        ['python', '-c', f'import sys; sys.path.insert(0, "{repo_path}"); import agentops'],
        capture_output=True, text=True, cwd=repo_path
    )
    if result.returncode != 0:
        errors.append({
            'type': 'import_error',
            'message': result.stderr.strip()
        })
    return errors


def run_pytest(repo_path: str) -> Tuple[int, str, str]:
    """Run pytest and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short'],
        capture_output=True, text=True, cwd=repo_path,
        timeout=120
    )
    return result.returncode, result.stdout, result.stderr


def diagnose_repo(repo_path: str) -> List[Dict]:
    """Full diagnosis of a Python repository."""
    all_errors = []
    py_files = find_python_files(repo_path)
    
    # Check syntax
    syntax_errors = check_syntax_errors(py_files)
    all_errors.extend(syntax_errors)
    
    # Check imports
    import_errors = check_import_errors(repo_path)
    all_errors.extend(import_errors)
    
    return all_errors


def find_unconditional_optional_imports(init_file: str, optional_modules: List[str]) -> List[Dict]:
    """Find imports in __init__.py that import from optional dependency modules unconditionally."""
    issues = []
    with open(init_file) as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for mod in optional_modules:
            if stripped.startswith(('from .', 'import ')) and mod in stripped:
                # Check if this import is inside a try block
                # Simple heuristic: check indentation
                if not line.startswith(' ') and not line.startswith('\t'):
                    issues.append({
                        'file': init_file,
                        'line': i,
                        'type': 'unconditional_optional_import',
                        'content': stripped,
                        'module': mod
                    })
    return issues


def generate_unified_diff(original_content: str, modified_content: str, 
                          filepath: str, n_context: int = 3) -> str:
    """Generate a unified diff between original and modified content."""
    original_lines = original_content.splitlines(keepends=True)
    modified_lines = modified_content.splitlines(keepends=True)
    
    # Ensure files end with newline
    if original_lines and not original_lines[-1].endswith('\n'):
        original_lines[-1] += '\n'
    if modified_lines and not modified_lines[-1].endswith('\n'):
        modified_lines[-1] += '\n'
    
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f'a/{filepath}',
        tofile=f'b/{filepath}',
        n=n_context
    )
    return ''.join(diff)


def write_patch_file(patch_content: str, patch_path: str):
    """Write a patch to a file."""
    with open(patch_path, 'w') as f:
        f.write(patch_content)


def apply_patches(repo_path: str, patch_files: List[str]) -> List[Dict]:
    """Apply patch files to the repository using git apply or patch command."""
    results = []
    for pf in patch_files:
        # Try git apply first
        result = subprocess.run(
            ['git', 'apply', '--verbose', pf],
            capture_output=True, text=True, cwd=repo_path
        )
        if result.returncode == 0:
            results.append({'file': pf, 'status': 'applied', 'method': 'git apply'})
        else:
            # Fallback to patch command
            result2 = subprocess.run(
                ['patch', '-p1', '-i', pf],
                capture_output=True, text=True, cwd=repo_path
            )
            if result2.returncode == 0:
                results.append({'file': pf, 'status': 'applied', 'method': 'patch'})
            else:
                results.append({
                    'file': pf, 
                    'status': 'failed',
                    'git_error': result.stderr,
                    'patch_error': result2.stderr
                })
    return results


def write_failed_reasons(output_path: str, errors: List[Dict], analysis_text: str = ''):
    """Write the failed reasons analysis to a file."""
    with open(output_path, 'w') as f:
        f.write('# Build Failure Analysis\n\n')
        if analysis_text:
            f.write(analysis_text + '\n\n')
        f.write('## Errors Found\n\n')
        for err in errors:
            f.write(f"- Type: {err.get('type', 'unknown')}\n")
            f.write(f"  File: {err.get('file', 'N/A')}\n")
            f.write(f"  Message: {err.get('message', 'N/A')}\n")
            if 'line' in err:
                f.write(f"  Line: {err['line']}\n")
            f.write('\n')


def make_import_conditional(file_content: str, import_line: str, 
                            fallback: str = 'pass') -> str:
    """Wrap an import line in a try/except ImportError block."""
    lines = file_content.split('\n')
    new_lines = []
    for line in lines:
        if line.strip() == import_line.strip():
            new_lines.append('try:')
            new_lines.append('    ' + line)
            new_lines.append('except ImportError:')
            new_lines.append('    ' + fallback)
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)
