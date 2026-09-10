"""I/O utilities for JAX computation tasks.

Handles loading problem.json, reading .npy/.npz input files into JAX arrays,
and saving JAX array results back to .npy files with proper numpy conversion.

Key considerations from DR:
- JAX arrays are immutable; saving requires explicit np.asarray() conversion.
- For JAX 0.8.x + NumPy 2.4.x, implicit conversion is deprecated; always convert explicitly.
- Use allow_pickle=False for security and portability.
- jnp.load handles .npy natively but .npz returns numpy arrays needing jnp.asarray().
"""
import json
import os
import numpy as np
import jax.numpy as jnp


def load_problem_json(path: str) -> list:
    """Load and parse problem.json.

    Args:
        path: Path to problem.json file

    Returns:
        List of task dictionaries with keys: id, description, input, output

    Raises:
        FileNotFoundError: If problem.json doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"problem.json not found at: {path}")

    with open(path, 'r') as f:
        tasks = json.load(f)

    if not isinstance(tasks, list):
        raise ValueError(f"Expected a JSON array in problem.json, got {type(tasks).__name__}")

    return tasks


def load_input_data(file_path: str):
    """Load .npy or .npz file and convert to JAX arrays.

    For .npy files: returns a single JAX array.
    For .npz files: returns a dict mapping key names to JAX arrays.

    Uses allow_pickle=False for security (prevents arbitrary code execution).
    Converts via jnp.asarray() to ensure proper JAX DeviceArray types.

    Args:
        file_path: Path to .npy or .npz file

    Returns:
        For .npy: a single JAX array
        For .npz: a dict mapping key names to JAX arrays

    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If file extension is not .npy or .npz
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input data file not found: {file_path}")

    if file_path.endswith('.npz'):
        with np.load(file_path, allow_pickle=False) as data:
            # .npz returns numpy arrays; convert each to JAX array
            result = {}
            for key in data.keys():
                arr = data[key]
                result[key] = jnp.asarray(arr)
        return result
    elif file_path.endswith('.npy'):
        arr = np.load(file_path, allow_pickle=False)
        return jnp.asarray(arr)
    else:
        # Fallback: try loading as .npy anyway (numpy can handle headerless binary)
        try:
            arr = np.load(file_path, allow_pickle=False)
            return jnp.asarray(arr)
        except Exception:
            raise ValueError(f"Unsupported file format: {file_path}. Expected .npy or .npz")


def save_jax_array(path: str, jax_array) -> None:
    """Safely save a JAX array to .npy file.

    Uses np.asarray() to explicitly convert JAX DeviceArray to numpy array
    before saving. This is critical for JAX 0.8.x + NumPy 2.4.x compatibility
    where implicit conversion via array protocols is deprecated.

    Creates parent directories if they don't exist.

    Args:
        path: Destination file path (should end in .npy)
        jax_array: JAX array to save
    """
    # Ensure parent directory exists
    parent_dir = os.path.dirname(path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    # Explicit conversion: JAX DeviceArray -> numpy ndarray
    # This avoids DeprecationWarning/ValueError in NumPy 2.4.x
    host_array = np.asarray(jax_array)
    np.save(path, host_array, allow_pickle=False)