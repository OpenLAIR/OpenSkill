"""Set up virtual environments and run fuzzers for Python libraries."""
import os
import subprocess
import shutil

def setup_venv_with_uv(lib_path):
    """Create a Python virtual environment using uv in lib_path/.venv."""
    venv_path = os.path.join(lib_path, '.venv')
    # Remove existing venv if present
    if os.path.exists(venv_path):
        shutil.rmtree(venv_path)
    result = subprocess.run(
        ['uv', 'venv', venv_path],
        capture_output=True, text=True, cwd=lib_path
    )
    if result.returncode != 0:
        print(f"Warning: venv creation issue for {lib_path}: {result.stderr}")
    return venv_path

def install_dependencies(lib_path, venv_path):
    """Install library dependencies and atheris into the venv."""
    lib_name = os.path.basename(lib_path)
    pip_cmd = ['uv', 'pip', 'install', '--python', os.path.join(venv_path, 'bin', 'python')]
    
    # Install atheris first
    subprocess.run(pip_cmd + ['atheris'], capture_output=True, text=True, cwd=lib_path)
    
    # Try to install the library in editable mode
    # For libraries with heavy deps (minisgl), install only what we need
    if lib_name == 'minisgl':
        # minisgl has heavy ML dependencies - install msgpack and json-related only
        subprocess.run(pip_cmd + ['msgpack'], capture_output=True, text=True, cwd=lib_path)
    elif lib_name == 'ujson':
        # ujson needs to be built from source (C extension)
        subprocess.run(pip_cmd + ['-e', '.'], capture_output=True, text=True, cwd=lib_path, timeout=120)
    elif lib_name == 'black':
        # black has hatchling build system
        subprocess.run(pip_cmd + ['hatchling', 'hatch-vcs', 'hatch-fancy-pypi-readme'],
                       capture_output=True, text=True, cwd=lib_path)
        subprocess.run(pip_cmd + ['-e', '.'], capture_output=True, text=True, cwd=lib_path, timeout=120)
    elif lib_name == 'ipython':
        # ipython needs setuptools
        subprocess.run(pip_cmd + ['setuptools'],
                       capture_output=True, text=True, cwd=lib_path)
        subprocess.run(pip_cmd + ['-e', '.'], capture_output=True, text=True, cwd=lib_path, timeout=120)
    else:
        # Generic: try editable install
        subprocess.run(pip_cmd + ['-e', '.'], capture_output=True, text=True, cwd=lib_path, timeout=120)
    
    return True

def run_fuzzer_with_timeout(lib_path, timeout_seconds=10):
    """Run the fuzzer for the specified duration and capture the log."""
    venv_path = os.path.join(lib_path, '.venv')
    python_bin = os.path.join(venv_path, 'bin', 'python')
    fuzz_script = os.path.join(lib_path, 'fuzz.py')
    log_path = os.path.join(lib_path, 'fuzz.log')
    
    if not os.path.isfile(fuzz_script):
        with open(log_path, 'w') as f:
            f.write(f"ERROR: fuzz.py not found at {fuzz_script}\n")
        return False
    
    try:
        result = subprocess.run(
            [python_bin, fuzz_script, f'-max_total_time={timeout_seconds}'],
            capture_output=True, text=True, cwd=lib_path,
            timeout=timeout_seconds + 30  # Extra buffer for startup/shutdown
        )
        # Write combined output to log
        with open(log_path, 'w') as f:
            f.write(result.stdout)
            f.write(result.stderr)
        return True
    except subprocess.TimeoutExpired as e:
        with open(log_path, 'w') as f:
            f.write(f"Fuzzer timed out after {timeout_seconds + 30} seconds\n")
            if e.stdout:
                f.write(e.stdout if isinstance(e.stdout, str) else e.stdout.decode('utf-8', errors='replace'))
            if e.stderr:
                f.write(e.stderr if isinstance(e.stderr, str) else e.stderr.decode('utf-8', errors='replace'))
        return False
    except Exception as e:
        with open(log_path, 'w') as f:
            f.write(f"ERROR running fuzzer: {str(e)}\n")
        return False

def capture_fuzz_log(lib_path):
    """Read and return the fuzz log contents."""
    log_path = os.path.join(lib_path, 'fuzz.log')
    if os.path.isfile(log_path):
        with open(log_path) as f:
            return f.read()
    return None
