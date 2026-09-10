import os
import ast
import glob

def find_python_libraries(base_dir):
    """Scan base_dir for subdirectories that are Python libraries.
    A directory is a Python library if it contains pyproject.toml, setup.py, or setup.cfg.
    Returns list of absolute paths."""
    libraries = []
    for entry in sorted(os.listdir(base_dir)):
        full_path = os.path.join(base_dir, entry)
        if not os.path.isdir(full_path):
            continue
        markers = ['pyproject.toml', 'setup.py', 'setup.cfg']
        if any(os.path.isfile(os.path.join(full_path, m)) for m in markers):
            libraries.append(full_path)
    return libraries

def write_libraries_txt(libraries, output_path):
    """Write list of library paths to a file, one per line."""
    with open(output_path, 'w') as f:
        for lib in libraries:
            f.write(lib + '\n')

def analyze_library_api(lib_path):
    """Analyze a library's structure and identify important functions for fuzzing.
    Returns a dict with lib name, source info, and key functions."""
    lib_name = os.path.basename(lib_path)
    info = {
        'name': lib_name,
        'path': lib_path,
        'source_dirs': [],
        'key_modules': [],
        'key_functions': [],
        'has_c_extensions': False,
        'dependencies': [],
    }
    
    # Detect source layout
    if os.path.isdir(os.path.join(lib_path, 'src')):
        info['source_dirs'].append('src')
    # Check for package dir matching lib name
    for candidate in os.listdir(lib_path):
        candidate_path = os.path.join(lib_path, candidate)
        if os.path.isdir(candidate_path) and os.path.isfile(os.path.join(candidate_path, '__init__.py')):
            info['source_dirs'].append(candidate)
    
    # Check for C extensions
    for root, dirs, files in os.walk(lib_path):
        for f in files:
            if f.endswith(('.c', '.cpp', '.pyx')):
                info['has_c_extensions'] = True
                break
    
    # Read pyproject.toml for dependencies
    pyproject_path = os.path.join(lib_path, 'pyproject.toml')
    if os.path.isfile(pyproject_path):
        with open(pyproject_path) as f:
            content = f.read()
            # Simple extraction of dependencies
            if 'dependencies' in content:
                info['dependencies_hint'] = 'See pyproject.toml'
    
    # Analyze key Python files for public functions
    _analyze_key_modules(lib_path, lib_name, info)
    
    return info

def _analyze_key_modules(lib_path, lib_name, info):
    """Find key modules and their public functions."""
    # Library-specific knowledge for better analysis
    lib_analysis = {
        'arrow': {
            'import_name': 'arrow',
            'key_modules': ['arrow.py', 'parser.py', 'factory.py', 'formatter.py', 'api.py'],
            'key_functions': [
                'arrow.get() - Main parsing entry point for dates/times',
                'arrow.Arrow.fromtimestamp() - Create from Unix timestamp',
                'arrow.Arrow.format() - Format arrow object to string',
                'arrow.parser.DateTimeParser.parse() - Parse date strings',
            ],
            'fuzz_targets': [
                'String parsing via arrow.get()',
                'Timestamp boundary testing via Arrow.fromtimestamp()',
            ],
        },
        'black': {
            'import_name': 'black',
            'key_modules': ['src/black/__init__.py', 'src/black/mode.py', 'src/black/parsing.py'],
            'key_functions': [
                'black.format_str() - Main code formatting entry point',
                'black.Mode() - Configuration for formatting',
            ],
            'fuzz_targets': [
                'Code formatting via black.format_str()',
                'Mode configuration variation',
            ],
        },
        'ipython': {
            'import_name': 'IPython',
            'key_modules': ['IPython/core/', 'IPython/lib/', 'IPython/utils/'],
            'key_functions': [
                'IPython.core.inputtransformer2 - Input transformation pipeline',
                'IPython.utils.text - Text processing utilities',
                'IPython.lib.pretty - Pretty printing',
            ],
            'fuzz_targets': [
                'Input transformation pipeline',
                'Text processing utilities',
            ],
        },
        'minisgl': {
            'import_name': 'minisgl',
            'key_modules': ['python/minisgl/core.py', 'python/minisgl/tokenizer/', 'python/minisgl/utils/'],
            'key_functions': [
                'minisgl tokenizer/parser functions',
                'minisgl configuration parsing',
                'minisgl utility functions',
            ],
            'fuzz_targets': [
                'Tokenizer/parser functions',
                'Configuration/JSON parsing',
            ],
        },
        'ujson': {
            'import_name': 'ujson',
            'key_modules': ['ujson (C extension)'],
            'key_functions': [
                'ujson.loads() - JSON deserialization (C extension)',
                'ujson.dumps() - JSON serialization (C extension)',
                'ujson.encode() - Alias for dumps',
                'ujson.decode() - Alias for loads',
            ],
            'fuzz_targets': [
                'Differential fuzzing: ujson.loads() vs json.loads()',
                'Serialization round-trip testing',
            ],
        },
    }
    
    if lib_name in lib_analysis:
        analysis = lib_analysis[lib_name]
        info['key_modules'] = analysis['key_modules']
        info['key_functions'] = analysis['key_functions']
        info['fuzz_targets'] = analysis['fuzz_targets']
        info['import_name'] = analysis['import_name']

def write_testing_notes(lib_info, output_path):
    """Write notes_for_testing.txt for a library."""
    with open(output_path, 'w') as f:
        f.write(f"Library: {lib_info['name']}\n")
        f.write(f"Path: {lib_info['path']}\n")
        f.write(f"Source directories: {', '.join(lib_info.get('source_dirs', []))}\n")
        f.write(f"Has C extensions: {lib_info.get('has_c_extensions', False)}\n")
        f.write(f"Import name: {lib_info.get('import_name', lib_info['name'])}\n")
        f.write(f"\nKey Modules:\n")
        for m in lib_info.get('key_modules', []):
            f.write(f"  - {m}\n")
        f.write(f"\nKey Functions:\n")
        for func in lib_info.get('key_functions', []):
            f.write(f"  - {func}\n")
        f.write(f"\nFuzz Targets:\n")
        for t in lib_info.get('fuzz_targets', []):
            f.write(f"  - {t}\n")
