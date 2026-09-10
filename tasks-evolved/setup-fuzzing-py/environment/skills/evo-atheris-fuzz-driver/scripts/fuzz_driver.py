"""Generate Atheris fuzz drivers for Python libraries."""
import os

def get_driver_template(lib_name):
    """Return the fuzz driver code for a specific library."""
    templates = {
        'arrow': _arrow_driver(),
        'black': _black_driver(),
        'ipython': _ipython_driver(),
        'minisgl': _minisgl_driver(),
        'ujson': _ujson_driver(),
    }
    return templates.get(lib_name, _generic_driver(lib_name))

def _arrow_driver():
    return '''#!/usr/bin/env python3
import sys
import atheris

with atheris.instrument_imports():
    import arrow

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    
    # Target 1: Arbitrary string parsing
    time_str = fdp.ConsumeUnicodeNoSurrogates(50)
    try:
        arrow.get(time_str)
    except (arrow.parser.ParserError, ValueError, TypeError, OverflowError):
        pass
    
    # Target 2: Timestamp boundary testing
    if fdp.ConsumeBool():
        timestamp = fdp.ConsumeFloatInRange(-1e12, 1e12)
        try:
            arrow.Arrow.fromtimestamp(timestamp)
        except (ValueError, OverflowError, OSError):
            pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
'''

def _black_driver():
    return '''#!/usr/bin/env python3
import sys
import atheris

with atheris.instrument_imports():
    import black

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    code_str = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 4096))
    
    mode = black.Mode(
        line_length=fdp.ConsumeIntInRange(10, 150),
        string_normalization=fdp.ConsumeBool(),
        is_pyi=fdp.ConsumeBool(),
    )
    
    try:
        black.format_str(code_str, mode=mode)
    except (black.InvalidInput, SyntaxError, TypeError, ValueError):
        pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
'''

def _ipython_driver():
    return '''#!/usr/bin/env python3
import sys
import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    code_str = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 2048))
    
    try:
        manager = TransformerManager()
        manager.transform_cell(code_str)
    except (SyntaxError, ValueError, TypeError, IndexError):
        pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
'''

def _minisgl_driver():
    return '''#!/usr/bin/env python3
import sys
import atheris
import json

with atheris.instrument_imports():
    try:
        from minisgl.core import ChatTemplate, get_prompt_from_template
        HAS_CHAT = True
    except (ImportError, ModuleNotFoundError):
        HAS_CHAT = False
    try:
        import msgpack
        HAS_MSGPACK = True
    except ImportError:
        HAS_MSGPACK = False

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    
    # Target 1: JSON parsing (common in ML configs)
    json_str = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 1024))
    try:
        parsed = json.loads(json_str)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # Target 2: msgpack if available
    if HAS_MSGPACK:
        raw_bytes = fdp.ConsumeBytes(fdp.ConsumeIntInRange(0, 512))
        try:
            msgpack.unpackb(raw_bytes, raw=False)
        except (msgpack.exceptions.UnpackValueError, msgpack.exceptions.ExtraData,
                ValueError, TypeError):
            pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
'''

def _ujson_driver():
    return '''#!/usr/bin/env python3
import sys
import atheris

with atheris.instrument_imports():
    import json
    import ujson

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    test_string = fdp.ConsumeUnicodeNoSurrogates(sys.maxsize)
    
    stdlib_result = None
    ujson_result = None
    
    # Parse with standard library
    try:
        stdlib_result = json.loads(test_string)
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError):
        stdlib_result = "ERROR"
    
    # Parse with ujson
    try:
        ujson_result = ujson.loads(test_string)
    except (ValueError, RecursionError):
        ujson_result = "ERROR"
    
    # Compare semantic equality
    if stdlib_result != "ERROR" and ujson_result != "ERROR":
        if stdlib_result != ujson_result:
            raise RuntimeError(f"Mismatch: stdlib={stdlib_result} vs ujson={ujson_result}")

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
'''

def _generic_driver(lib_name):
    return f'''#!/usr/bin/env python3
import sys
import atheris

with atheris.instrument_imports():
    import {lib_name}

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    test_str = fdp.ConsumeUnicodeNoSurrogates(100)
    try:
        pass  # Add library-specific fuzzing logic
    except (ValueError, TypeError):
        pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
'''

def get_exception_handlers_for_lib(lib_name):
    """Return list of expected exceptions for a library."""
    handlers = {
        'arrow': ['arrow.parser.ParserError', 'ValueError', 'TypeError', 'OverflowError'],
        'black': ['black.InvalidInput', 'SyntaxError', 'TypeError', 'ValueError'],
        'ipython': ['SyntaxError', 'ValueError', 'TypeError', 'IndexError'],
        'minisgl': ['json.JSONDecodeError', 'ValueError', 'TypeError'],
        'ujson': ['ValueError', 'RecursionError', 'json.JSONDecodeError'],
    }
    return handlers.get(lib_name, ['ValueError', 'TypeError'])

def create_fuzz_driver_file(lib_path, lib_name=None):
    """Write fuzz.py to the library directory."""
    if lib_name is None:
        lib_name = os.path.basename(lib_path)
    driver_code = get_driver_template(lib_name)
    fuzz_path = os.path.join(lib_path, 'fuzz.py')
    with open(fuzz_path, 'w') as f:
        f.write(driver_code)
    return fuzz_path

def generate_fuzz_driver(lib_path):
    """High-level: generate fuzz driver for a library."""
    lib_name = os.path.basename(lib_path)
    return create_fuzz_driver_file(lib_path, lib_name)
