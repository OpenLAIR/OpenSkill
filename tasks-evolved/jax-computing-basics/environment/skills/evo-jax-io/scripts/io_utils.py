"""JAX I/O utilities for loading problem.json, input data, and saving results.

Handles:
- Parsing problem.json task definitions
- Loading .npy and .npz files into JAX arrays
- Saving JAX arrays to .npy files with proper numpy conversion

Key domain knowledge:
- JAX has no native disk I/O; use numpy.load() then convert with jnp.asarray()
- JAX defaults to float32; use jax.config.update('jax_enable_x64', True) for float64
- For saving, use np.asarray(jax_array) to safely convert to numpy before np.save()
- np.asarray() avoids unnecessary copies vs np.array()
- Never call np.save() inside jax.jit (Tracer objects will cause errors)
"""
import json
import os
import numpy as np
import jax.numpy as jnp


def load_problem_json(path: str) -> list:
    """Load and parse problem.json file.

    Args:
        path: Path to problem.json file

    Returns:
        List of task dictionaries with keys: id, description, input, output
    """
    with open(path, 'r') as f:
        tasks = json.load(f)
    return tasks


def load_input_data(file_path: str):
    """Load .npy or .npz file and convert arrays to JAX arrays.

    For .npy files: returns a single JAX array
    For .npz files: returns a dict mapping array names to JAX arrays

    Args:
        file_path: Path to .npy or .npz file

    Returns:
        JAX array (for .npy) or dict of JAX arrays (for .npz)
    """
    file_path = os.path.abspath(file_path)
    
    if file_path.endswith('.npz'):
        with np.load(file_path, allow_pickle=False) as data:
            result = {key: jnp.asarray(data[key]) for key in data.files}
        return result
    else:
        # .npy file
        arr = np.load(file_path, allow_pickle=False)
        return jnp.asarray(arr)


def save_jax_array(path: str, jax_array) -> None:
    """Safely save a JAX array to a .npy file.

    Converts JAX array to numpy using np.asarray() (zero-copy when possible)
    then saves with np.save(). Must be called outside jax.jit boundaries.

    Args:
        path: Destination file path (should end in .npy)
        jax_array: JAX device array to save
    """
    # Ensure output directory exists
    out_dir = os.path.dirname(path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    # Convert to numpy safely (np.asarray avoids unnecessary copies)
    host_array = np.asarray(jax_array)
    np.save(path, host_array, allow_pickle=False)
