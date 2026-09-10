# evo-python-build-fixer

## Description
Diagnoses and fixes Python repository build failures. Analyzes source code for
import errors, syntax errors, missing dependencies, and configuration issues.
Generates standard unified diff patches and applies them.

## When to Use
- When a Python project fails to build or pass tests
- When you need to diagnose import errors, missing optional dependencies
- When you need to create and apply git-compatible patches

## Common Patterns

### Pattern 1: Optional Dependency Import Guard
When a module imports from an optional dependency unconditionally, wrap it in try/except:
```python
try:
    from .optional_module import OptionalClass
except ImportError:
    OptionalClass = None
```

### Pattern 2: Conditional Export in __init__.py
When __init__.py exports symbols from optional modules:
```python
try:
    from .langchain_handler import Handler
except ImportError:
    pass  # langchain not installed
```

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-python-build-fixer/scripts')
from utils import (
    diagnose_repo,
    find_import_errors,
    generate_unified_diff,
    write_patch_file,
    apply_patches,
    write_failed_reasons
)

# Step 1: Diagnose
repo_path = '/path/to/repo'
errors = diagnose_repo(repo_path)

# Step 2: Write analysis
write_failed_reasons('/path/to/failed_reasons.txt', errors)

# Step 3: Generate patches
patch_content = generate_unified_diff(original_lines, modified_lines, filepath)
write_patch_file(patch_content, '/path/to/repo/patch_1.diff')

# Step 4: Apply patches
apply_patches(repo_path, ['/path/to/repo/patch_1.diff'])
```
