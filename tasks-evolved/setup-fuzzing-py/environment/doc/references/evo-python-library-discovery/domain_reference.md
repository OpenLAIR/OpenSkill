# Domain Reference for evo-python-library-discovery

**Responsibility**: Identify Python library directories, list them to a file, and analyze each library's public API and important functions to produce notes_for_testing.txt files.

**Key functions to implement**: find_python_libraries, analyze_library_api, write_libraries_txt, write_testing_notes

---

## 6. Fuzz Driver Architectural Patterns for Specific Library Typologies


Writing effective fuzz drivers requires tailoring the harness to the specific semantics of the target library [cite: 9, 33]. Below are deep-dive strategies for various software typologies.

## 8. Heuristics for Identifying Python Libraries within Repositories


In automated security contexts, detecting whether a subdirectory constitutes a buildable Python library is necessary for generating dynamic build scripts.

A Python directory is definitively a package/library if it matches the following heuristics [cite: 32, 39, 40]:
1.  **Metadata Files:** The presence of a `pyproject.toml` (the modern PEP 517/621 standard) [cite: 39, 40].
2.  **Legacy Configuration:** The presence of `setup.py` or `setup.cfg` (legacy setuptools format) [cite: 32, 41].
3.  **Source Layout:** The existence of a `src/` directory containing Python files [cite: 32, 41], or a subdirectory containing an `__init__.py` file denoting an import package [cite: 32].
4.  **Dependencies:** `requirements.txt` or `Pipfile`.

**Shell Pattern Detection:**
```bash
if [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "setup.cfg" ]; then
    echo "Python library detected."
fi
```
Modern OSS-Fuzz deployments highly prefer `pyproject.toml`-based structures due to deterministic build-backend specifications [cite: 39, 40].

***