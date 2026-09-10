# Domain Reference for evo-jax-io

**Responsibility**: All file I/O: parsing problem.json, loading numpy/npz data files and converting to JAX arrays, and safely serializing JAX arrays to .npy output files using np.asarray().

**Key functions to implement**: load_problem_json, load_input_data, save_jax_array

---

## 1. Data Loading Patterns for JAX Workflows


A fundamental requirement in any numerical pipeline is the efficient ingestion of serialized multi-dimensional arrays. In the JAX ecosystem, data loading must bridge the gap between host memory (typically managed by NumPy) and device memory (managed by JAX's XLA backends).

### 1.1 Loading `.npy` and `.npz` Files

The standard protocol for loading binary array data utilizes `numpy.load()`. Because JAX does not provide native disk I/O primitives—a design choice reflecting its pure functional and side-effect-free philosophy—users must load data using NumPy and subsequently transfer it to JAX arrays.

When loading an `.npz` archive, `numpy.load()` returns an `NpzFile` object, which acts as a dictionary. To extract named arrays (e.g., `data['x']`, `data['y']`) and cast them to JAX device arrays, the `jax.numpy.array()` or `jax.numpy.asarray()` function is utilized.

### 1.2 Dtype Conversion Pitfalls and Default Precision

A significant pitfall in JAX involves implicit type casting and default precision settings. Unlike NumPy, which defaults to 64-bit precision (e.g., `float64`, `int64`) for scientific computing accuracy, JAX defaults to 32-bit precision (`float32`, `int32`) [cite: 1, 2]. This design favors machine learning workflows where 32-bit math provides significant speedups on accelerators (GPUs/TPUs) with negligible loss in predictive performance [cite: 3].

If you load a NumPy array of `dtype=np.float64` and pass it to `jnp.array(arr)`, JAX will implicitly downcast the data to `float32` under standard configuration. This truncation of the mantissa can cause insidious numerical instability in sensitive operations like eigenvalue decompositions, Hessian calculations, or log-space probability accumulations [cite: 1, 2].

**Enabling 64-bit Precision:**
To force JAX to respect 64-bit types, you must update the global configuration at the very beginning of your script, prior to any JAX array instantiation or compilation [cite: 1, 2]:

```python
import jax

## 7. Data Serialization: Saving JAX Arrays to NumPy Files


Because JAX and NumPy both support the Python buffer protocol, JAX arrays share fundamental memory structures with NumPy arrays.

### 7.1 Direct Application of `np.save`

If you attempt to execute `np.save("file.npy", jax_array)` directly, two things can happen depending on the execution context:
1.  **In Eager Mode**: NumPy detects the JAX array via duck-typing and the buffer protocol, pulling the device array implicitly to host memory and saving it. While functional, it relies on implicit dispatch logic that is sometimes fragile.
2.  **Inside `jax.jit` (Tracing)**: If `np.save` is invoked within a compiled function, the input variable is not an actual array but an abstract `Tracer` representing the computational graph [cite: 21]. `np.save` will attempt to serialize the `Tracer` object itself, leading to a catastrophic `ConcretizationTypeError` or silently corrupting execution memory [cite: 21]. JAX 0.8.x strictly enforces that `Tracer` objects no longer inherit from `jax.Array` specifically to prevent these silent leaks [cite: 22].

### 7.2 The Correct Serialization Pattern

To safely and explicitly serialize a JAX array, users must ensure the tensor is firmly resolved to a concrete host memory array outside of JIT boundaries. The most efficient approach utilizes `np.asarray()` [cite: 23]. Using `np.array(jax_array)` works but enforces a deep memory copy. `np.asarray()` avoids unnecessary copies when memory is already safely addressable.