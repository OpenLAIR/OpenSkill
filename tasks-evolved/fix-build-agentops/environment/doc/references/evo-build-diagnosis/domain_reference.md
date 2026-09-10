# Domain Reference for evo-build-diagnosis

**Responsibility**: Scan repository files for syntax errors (via ast.parse/compile), parse pytest output and CI logs, check build configuration files (pyproject.toml, setup.py, setup.cfg), identify missing dependencies, and produce a structured diagnosis report in failed_reasons.txt.

**Key functions to implement**: find_repo_path, parse_syntax_errors, run_build_and_capture_errors, run_tests_and_capture_failures, analyze_build_config, check_import_availability, write_diagnosis_report

---

## 1. Analyzing Python Build Failures


When an AI agent interacts with a failing GitHub repository, it must first classify the nature of the failure. Python build failures are not monolithic; they span a spectrum of error categories, from static syntax violations to dynamic runtime exceptions during test execution. A robust AI skill must deploy a pipeline of programmatic parsers to extract actionable intelligence from these disparate error sources.

### 1.1 Python Syntax Errors and Import Errors


Syntax errors occur during the parsing phase before the Python interpreter attempts to execute the code. Programmatic detection of these errors involves intercepting the `SyntaxError` exception. In Python, `SyntaxError` provides detailed attributes that pinpoint the exact location of the failure [cite: 1]. 

When the parser encounters a syntax error, it exposes the following attributes:
*   `filename`: The name of the file where the error occurred [cite: 1].
*   `lineno`: The 1-indexed line number [cite: 1].
*   `offset`: The 1-indexed column where the error began [cite: 1].
*   `end_lineno` and `end_offset`: Introduced in Python 3.10, these attributes delineate the exact span of the syntactic violation [cite: 1].

Import errors (`ImportError` and `ModuleNotFoundError`) typically arise during the execution phase when the interpreter cannot resolve a module dependency. An AI agent can use the `importlib` standard library to dynamically check for the presence of a module without executing the entire script.

```python
import importlib.util
import sys
import traceback

def check_module_exists(module_name: str) -> bool:
    """
    Programmatically verifies if a module can be resolved in the current environment.
    """
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ModuleNotFoundError:
        return False

def parse_syntax_error(file_path: str):
    """
    Attempts to compile a Python file and captures exact SyntaxError details.
    """
    try:
        with open(file_path, 'rb') as f:
            source = f.read()
        compile(source, file_path, 'exec')
    except SyntaxError as e:
        return {
            "type": "SyntaxError",
            "file": e.filename,
            "line": e.lineno,
            "offset": e.offset,
            "end_line": getattr(e, 'end_lineno', None),
            "end_offset": getattr(e, 'end_offset', None),
            "text": e.text.strip() if e.text else ""
        }
```

### 1.2 Parsing Pytest Test Failures


For unit testing, `pytest` is the de facto standard in the Python ecosystem. However, parsing `pytest` standard output via regex is brittle due to varying verbosity levels and terminal color codes. Research suggests that relying on `pytest` exit codes and machine-readable output formats (like JUnit XML or JSON) is a far more resilient strategy [cite: 2].

Pytest exit codes are standardized: an exit code of `0` indicates all tests passed, `1` indicates tests were collected and run but some failed, `2` indicates test execution was interrupted, `3` indicates an internal error, `4` indicates a command-line usage error, and `5` indicates no tests were collected [cite: 3].

To capture detailed tracebacks programmatically, an AI agent should invoke `pytest` with the `--junitxml` flag. The resulting XML file provides a highly structured schema that can be parsed using the `xmltodict` or built-in `xml.etree.ElementTree` modules [cite: 2]. Alternatively, tools like `pytest-json` were historically used, though they often struggled with parsing configuration files like `setup.cfg` [cite: 2].

```python
import subprocess
import xml.etree.ElementTree as ET
from typing import List, Dict

def run_and_parse_pytest(target_dir: str, xml_report_path: str = "report.xml") -> List[Dict]:
    """
    Runs pytest and parses the resulting JUnit XML to extract failure tracebacks.
    """
    # Execute pytest as a subprocess to isolate execution and capture exit codes
    cmd = [
        "python", "-m", "pytest", target_dir,
        f"--junitxml={xml_report_path}",
        "--tb=long", # Ensure exhaustive traceback formatting [cite: 4]
        "-q" # Quiet mode to reduce stdout noise [cite: 4]
    ]
    
    process = subprocess.run(cmd, capture_output=True, text=True)
    exit_code = process.returncode
    
    failures = []
    if exit_code in (1, 2): # Tests failed or execution was interrupted
        try:
            tree = ET.parse(xml_report_path)
            root = tree.getroot()
            for testcase in root.iter('testcase'):
                failure_node = testcase.find('failure')
                if failure_node is not None:
                    failures.append({
                        "test_name": testcase.attrib.get('name'),
                        "file": testcase.attrib.get('file'),
                        "line": testcase.attrib.get('line'),
                        "message": failure_node.attrib.get('message'),
                        "traceback": failure_node.text
                    })
        except Exception as e:
            pass # Handle XML parsing errors
            
    return failures
```

By leveraging `pytest.main(args)` internally, one can run an in-process test run [cite: 3, 5]. However, running `pytest.main()` directly within the AI agent's process namespace can lead to state pollution; thus, subprocess isolation is highly recommended.

### 1.3 Build Configuration Errors: setup.py, pyproject.toml, and setup.cfg


Modern Python packaging has largely shifted from imperative `setup.py` scripts to declarative `pyproject.toml` files, compliant with PEP 517 and PEP 518. A common build failure pattern occurs when invoking `python -m build`. If the `build` module is not installed, the environment will throw an error stating: `No module named build.__main__; 'build' is a package and cannot be directly executed` [cite: 6, 7]. This signifies that the user must `python -m pip install build` prior to building the package [cite: 7].

Furthermore, missing system-level dependencies declared in the `pyproject.toml` (e.g., `cmake` or `ninja` for C++ extensions via `scikit-build`) will abort the build process [cite: 8]. An AI agent must parse the `pyproject.toml` to verify that all constraints within the `[build-system] requires` array are satisfied [cite: 8].

### 1.4 CI/CD Configuration Issues


Build failures in CI/CD platforms like GitHub Actions or Travis CI often stem from environmental mismatches rather than source code defects. These include incorrect Python version matrices, missing OS-level packages (e.g., `apt-get install libssl-dev`), or misconfigured `tox.ini` files. An AI agent should read the `.github/workflows/*.yml` files to replicate the exact sequence of shell commands executed by the runner.

### 1.5 Type Checking and Linting Errors


Static analysis tools like `mypy` or `pyright` enforce type hints, while linters like `flake8`, `ruff`, `pylint`, and `black` enforce stylistic conventions. An AI agent can invoke these tools programmatically and parse their standard output. For instance, `flake8` outputs errors in a highly parsable `path:line:column: error_code message` format. 

However, formatters like `black` introduce edge cases. When running `black --diff`, the output relies on unified diff formatting. Historically, `black` struggled with the `\ No newline at end of file` marker, resulting in diffs that could not be successfully applied via `git apply` [cite: 9]. An agent attempting to autofix formatting must be acutely aware of these diff toolchain idiosyncrasies.

## 3. Python AST and Code Analysis for Error Detection


While string manipulation and regex are adequate for basic log parsing, they fall drastically short when an AI agent needs to semantically alter Python code. The `ast` (Abstract Syntax Tree) module provides a structural representation of the source code, allowing the agent to pinpoint errors with exact coordinates.

### 3.1 Syntax Validation via `ast.parse()`


The `ast.parse()` function attempts to convert Python source code into an `ast.Module` tree [cite: 24, 25]. If the source code contains invalid syntax, it raises a `SyntaxError` [cite: 1]. For an AI agent, invoking `ast.parse()` is faster and safer than using `eval()` or `exec()`, as it performs pure static analysis without executing arbitrary logic [cite: 24, 26].

```python
import ast
from typing import Optional, Tuple

def validate_syntax_via_ast(source_code: str) -> Tuple[bool, Optional[str]]:
    """
    Uses the AST module to statically verify Python syntax.
    Returns a tuple of (is_valid, error_message).
    """
    try:
        # ast.PyCF_ONLY_AST ensures we only get the tree, bypassing byte-code compilation [cite: 24, 26]
        ast.parse(source_code, filename='<unknown>', mode='exec')
        return True, None
    except SyntaxError as e:
        error_msg = f"SyntaxError at line {e.lineno}, column {e.offset}: {e.msg}"
        return False, error_msg
```

### 3.2 Navigating AST Coordinate Systems: Byte Offsets vs. Characters


A significant pitfall for AI agents manipulating code based on AST coordinates is the distinction between character offsets and byte offsets. Instances of `ast.expr` and `ast.stmt` possess `lineno` and `col_offset` attributes [cite: 24, 25]. Since Python 3.8, they also feature `end_lineno` and `end_col_offset` [cite: 25].

Crucially, the `col_offset` is the **UTF-8 byte offset** of the token, not the Unicode character index [cite: 24, 25, 26]. This occurs because the internal Python C parser operates on UTF-8 bytes [cite: 25, 26]. If a line of code contains multi-byte characters (such as emojis or accented characters like `café`), a byte offset of 5 might correspond to a character index of 4 [cite: 27]. 

If an AI agent blindly uses string slicing (`source_line[node.col_offset : node.end_col_offset]`) on a native Python string (which operates on characters), it will slice at the wrong location [cite: 25, 28]. To reliably extract the text segment, the agent must encode the string to bytes, slice it, and decode it back:

```python
def extract_node_text(source_line: str, node: ast.AST) -> str:
    """
    Safely extracts the exact text of an AST node, accounting for UTF-8 byte offsets.
    """
    if not hasattr(node, 'col_offset') or not hasattr(node, 'end_col_offset'):
        return ""
        
    # Encode the line into UTF-8 bytes [cite: 27, 28]
    byte_line = source_line.encode('utf-8')
    
    # Slice using byte offsets [cite: 25]
    sliced_bytes = byte_line[node.col_offset : node.end_col_offset]
    
    # Decode back to a string
    return sliced_bytes.decode('utf-8')
```

### 3.3 Dynamic Extraction of Missing Imports


To resolve `NameError` or `ModuleNotFoundError` anomalies, the AI agent can walk the AST to find all `ast.Import` and `ast.ImportFrom` nodes. By comparing the imported modules against the names referenced in `ast.Name` nodes, the agent can heuristically determine if a variable is undeclared or if an import is missing.

## 4. Build System Specifics: The AgentOps Case Study


To deploy these tools effectively, an AI agent must understand the build system utilized by the repository. We analyze the `AgentOps-AI/agentops` package as a prime example of modern Python ecosystem dynamics.

### 4.2 Build Toolchains and Dependency Resolution


The `AgentOps` package is distributed via PyPI and is installable via modern package managers like `pip`, `poetry`, and particularly `uv` [cite: 33, 36]. The presence of `uv` (a blazing-fast rust-based package installer) suggests that the repository utilizes standard `pyproject.toml` configurations [cite: 36].

An AI agent investigating a build failure in `agentops` must begin by parsing the `pyproject.toml` file to ensure the environment matches the project's requirements.

### 4.3 Parsing `pyproject.toml` Programmatically


Since Python 3.11, the standard library includes `tomllib` for parsing TOML files natively. For environments running Python 3.7 through 3.10, the third-party `tomli` package is the canonical backport.

The agent can parse the `pyproject.toml` to deduce the build backend (e.g., `setuptools`, `hatchling`, `poetry-core`) and extract the required dependencies:

```python
import sys

## 5. The BugSwarm Reproduction Framework


If an AI agent discovers a build failure on GitHub, attempting to reproduce it locally can result in an "it works on my machine" scenario due to conflicting system libraries or mismatched Python minor versions. To guarantee reliable evaluation, researchers utilize frameworks like BugSwarm [cite: 37].

### 5.2 Directory Structures and Reproduction Scripts


Within a BugSwarm Docker container, the environment contains crucial structural blueprints:
*   **Failed Repository Path**: `/home/travis/build/failed` [cite: 39].
*   **Passed Repository Path**: `/home/travis/build/passed` [cite: 39].

The container provides shell scripts to automatically execute the CI commands exactly as they originally ran:
*   `/usr/local/bin/run_failed.sh`: Replicates the commands that resulted in the build failure [cite: 39].
*   `/usr/local/bin/run_passed.sh`: Replicates the commands from the successful build [cite: 39].

### 6.1 Encoding Issues and Unicode Escapes


When operating on cross-platform repositories (especially between Windows and Unix-like OSes), file paths and text strings frequently induce `SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes` [cite: 42]. This occurs when a raw backslash `\` is misinterpreted as an escape sequence delimiter (e.g., `\U` or `\x`) instead of a directory separator [cite: 42]. 

When the AI agent parses tracebacks or modifies source files, it must consistently enforce UTF-8 file encodings. Opening a `.py` file with the incorrect default encoding (like `cp1252` on Windows) will cause a `SyntaxError` or `UnicodeDecodeError` during the AST parsing phase [cite: 27]. The agent must supply `encoding='utf-8'` explicitly to all file I/O operations.

### 6.2 Python Version Compatibility Constraints


Python syntax evolves rapidly. Features introduced in newer versions will trigger immediate `SyntaxError` failures if executed on older runtimes.
*   **Python 3.8**: Introduced the Walrus Operator (`:=`) and positional-only parameters (`/`). It also added `end_lineno` to AST nodes [cite: 25].
*   **Python 3.9**: Enabled type hinting using standard collections (e.g., `list[int]` instead of `List[int]`).
*   **Python 3.10**: Introduced Structural Pattern Matching (`match/case`) and better `SyntaxError` localization [cite: 1].
*   **Python 3.11**: Added `tomllib` to the standard library and enhanced exception groups.
*   **Python 3.12**: Formalized syntactic f-string enhancements, allowing quotes inside f-string expressions.

If an AI agent generates a patch utilizing a walrus operator but the CI environment specified in `.github/workflows/python-app.yml` is running Python 3.7, the patched build will fail with a `SyntaxError`. The agent must deduce the target Python version from the repository metadata and constrain its generated code accordingly.