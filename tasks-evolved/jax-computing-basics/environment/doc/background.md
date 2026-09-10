# Comprehensive Guide to JAX 0.8.x Python Programming: Operations, Utilities, and Best Practices

**Key Points**
*   **Precision Management**: By default, JAX enforces 32-bit floating-point precision, a paradigm inherited from accelerator-optimized computing. Transitioning to 64-bit precision requires explicit global configuration via `jax.config.update("jax_enable_x64", True)`.
*   **Functional Control Flow**: Sequential computations, particularly recurrent neural networks (RNNs), must leverage `jax.lax.scan` rather than native Python loops to avoid catastrophic XLA unrolling and compilation overhead.
*   **Vectorization and Broadcasting**: Native operators (such as `x**2`) and built-in functions (like `jnp.square(x)`) implicitly parallelize element-wise operations, rendering explicit vectorization via `jax.vmap` redundant for simple scalar mappings.
*   **Deterministic Randomness**: JAX 0.8.x strictly enforces a stateless, explicitly managed pseudo-random number generator (PRNG) architecture, utilizing `jax.random.key` and `jax.random.split` rather than the globally mutable state found in standard NumPy.
*   **Serialization Best Practices**: While JAX arrays implement the Python buffer protocol, interacting with standard disk I/O (e.g., `numpy.save`) necessitates explicit conversion via `np.asarray()` to prevent implicit memory copies and avoid runtime tracer exceptions during Just-In-Time (JIT) compilation.

**Overview**
This comprehensive report systematically addresses the core computational patterns, numerical optimization techniques, and best practices for developing highly performant scientific computing and machine learning applications using JAX 0.8.x. It details data ingestion workflows, functional transformations (JIT, VMAP, GRAD), sequence scanning, and serialization, while strictly adhering to functional programming paradigms.

**Objectives**
The primary objective of this document is to provide robust, reusable, and academically rigorous utility functions and theoretical explanations for specific JAX operations. By strictly defining exact function signatures, default parameters, and shape transformations, this report acts as a definitive technical manual for migrating and optimizing workflows in the JAX 0.8.x ecosystem with `jaxlib` 0.8.2 on CPU environments.

**Limitations**
While this report strives for absolute comprehensiveness, the underlying Accelerated Linear Algebra (XLA) compiler behavior is subject to hardware-specific heuristics. Code execution times and minor floating-point non-associativities may vary slightly across different CPU architectures or when ported to GPU/TPU environments. The guidance is strictly tailored to JAX 0.8.x, and certain deprecated APIs (such as `jax.random.PRNGKey`) are treated according to their deprecation status in this specific release window.

---

## 1. Data Loading Patterns for JAX Workflows

A fundamental requirement in any numerical pipeline is the efficient ingestion of serialized multi-dimensional arrays. In the JAX ecosystem, data loading must bridge the gap between host memory (typically managed by NumPy) and device memory (managed by JAX's XLA backends). 

### 1.1 Loading `.npy` and `.npz` Files
The standard protocol for loading binary array data utilizes `numpy.load()`. Because JAX does not provide native disk I/O primitives—a design choice reflecting its pure functional and side-effect-free philosophy—users must load data using NumPy and subsequently transfer it to JAX arrays.

When loading an `.npz` archive, `numpy.load()` returns an `NpzFile` object, which acts as a dictionary. To extract named arrays (e.g., `data['x']`, `data['y']`) and cast them to JAX device arrays, the `jax.numpy.array()` or `jax.numpy.asarray()` function is utilized.

#### Code Example: Safe Data Loading
```python
import numpy as np
import jax
import jax.numpy as jnp

def load_and_convert_data(file_path: str) -> dict:
    """
    Loads an .npz file and converts its named arrays to JAX arrays.
    
    Args:
        file_path: String path to the .npz archive.
        
    Returns:
        A dictionary mapping array names to jnp.ndarray objects.
    """
    # Load the archive (allow_pickle=False is recommended for security)
    with np.load(file_path, allow_pickle=False) as data:
        # Extract and convert. jnp.asarray avoids copying if already 
        # in memory, though transfer to device will occur.
        jax_data = {
            'x': jnp.asarray(data['x']),
            'y': jnp.asarray(data['y'])
        }
    return jax_data
```

### 1.2 Dtype Conversion Pitfalls and Default Precision
A significant pitfall in JAX involves implicit type casting and default precision settings. Unlike NumPy, which defaults to 64-bit precision (e.g., `float64`, `int64`) for scientific computing accuracy, JAX defaults to 32-bit precision (`float32`, `int32`) [cite: 1, 2]. This design favors machine learning workflows where 32-bit math provides significant speedups on accelerators (GPUs/TPUs) with negligible loss in predictive performance [cite: 3].

If you load a NumPy array of `dtype=np.float64` and pass it to `jnp.array(arr)`, JAX will implicitly downcast the data to `float32` under standard configuration. This truncation of the mantissa can cause insidious numerical instability in sensitive operations like eigenvalue decompositions, Hessian calculations, or log-space probability accumulations [cite: 1, 2].

**Enabling 64-bit Precision:**
To force JAX to respect 64-bit types, you must update the global configuration at the very beginning of your script, prior to any JAX array instantiation or compilation [cite: 1, 2]:

```python
import jax
# Must be called at startup/top of the main file
jax.config.update("jax_enable_x64", True)
import jax.numpy as jnp
```
Once `jax_enable_x64` is `True`, JAX will natively preserve `float64` arrays loaded from NumPy, and operations like `jnp.zeros` will default to `float64` rather than `float32` [cite: 1, 4].

## 2. Axis-wise Reductions: `jnp.mean`

The `jax.numpy.mean` function computes the arithmetic mean of array elements along specified dimensions.

### 2.1 Function Signature and Parameters
The exact signature for the function in JAX is [cite: 5]:
```python
jax.numpy.mean(a, axis=None, dtype=None, out=None, keepdims=False, *, where=None)
```

*   `a` (ArrayLike): The input array.
*   `axis` (int or sequence of ints, default=`None`): The axis or axes along which to compute the mean. If `None`, the array is flattened.
*   `dtype` (DTypeLike, default=`None`): The type of the output array. If `None`, floating-point inputs retain their dtype, while integer inputs are promoted to `float32` or `float64` (depending on the `x64` flag).
*   `out`: Unused by JAX (included strictly for NumPy API compatibility).
*   `keepdims` (bool, default=`False`): If `True`, reduced axes are retained in the output with a size of 1, allowing for proper broadcasting.
*   `where` (ArrayLike, default=`None`): A boolean array indicating elements to include in the mean.

### 2.2 Exact Behavior for 2D Arrays
When evaluating a 2D array \( X \) of shape `(M, N)`:
*   `axis=0` reduces across the rows (collapsing the row dimension `M`), producing a column-wise mean of shape `(N,)`.
*   `axis=1` reduces across the columns (collapsing the column dimension `N`), producing a per-row mean of shape `(M,)`.

For an input matrix of shape `(10, 5)`, computing `jnp.mean(x, axis=1)` explicitly iterates across the 5 columns for each of the 10 rows. The return shape is strictly `(10,)` [cite: 5].

#### Code Example: Row-wise Means
```python
import jax
import jax.numpy as jnp

def compute_row_means(x: jax.Array) -> jax.Array:
    """
    Computes the per-row arithmetic mean of a 2D array.
    
    Args:
        x: Input array of shape (M, N).
        
    Returns:
        Array of shape (M,) containing the mean of each row.
    """
    # x has shape (10, 5)
    # axis=1 reduces the dimension at index 1 (the 5 columns)
    row_means = jnp.mean(x, axis=1)
    return row_means

# Demonstration
key = jax.random.key(42)
X = jax.random.normal(key, (10, 5))
result = compute_row_means(X)
print(result.shape) # Output: (10,)
```

## 3. Vectorized Element-wise Squaring: `jnp.square`

Squaring array elements is a ubiquitous operation. In JAX, there are three common paradigms to compute \( x_i^2 \): `jnp.square(x)`, `x**2`, and mapped applications like `jax.vmap(lambda xi: xi**2)(x)`.

### 3.1 `jnp.square` vs `x**2` vs `jax.vmap`
1.  **`jnp.square(x)`**: This is the canonical, JAX-native implementation of `numpy.square`. Under the hood, `jnp.square(x)` is implemented identically to `jnp.power(x, 2)` [cite: 6]. It is naturally vectorized over arbitrary dimensional arrays and lowers to an optimized XLA element-wise squaring kernel.
2.  **`x**2`**: This relies on Python's `__pow__` operator overload on JAX's `Array` class. Functionally and computationally, it translates into the exact same XLA instructions as `jnp.square(x)`. It is entirely valid and idiomatic.
3.  **`jax.vmap(lambda xi: xi**2)(x)`**: `jax.vmap` is an automatic vectorization transformation that maps a function along array axes [cite: 7]. Because `**2` is *already* natively vectorized by the JAX core array processing layer, wrapping an explicitly mapped lambda inside `vmap` is redundant. While the XLA compiler is generally sophisticated enough to optimize out the unnecessary map overhead and produce the same efficient binary, writing `vmap` for inherently element-wise functions adds unnecessary cognitive load and tracing overhead during compilation.

#### Code Example: Correct Usage
```python
import jax.numpy as jnp

def square_elements(x: jnp.ndarray) -> jnp.ndarray:
    """
    Computes element-wise square natively.
    """
    # jnp.square(x) is identical to x**2 in performance and outcome.
    return jnp.square(x)
```

## 4. Automatic Differentiation with `jax.grad`: Scalar Loss

The core of JAX's machine learning utility lies in `jax.grad`, which performs reverse-mode automatic differentiation (backpropagation) to exact numerical precision [cite: 8].

### 4.1 Signature and Defaults of `jax.grad`
```python
jax.grad(fun, argnums=0, has_aux=False, holomorphic=False, allow_int=False, reduce_axes=())
```
*   `fun`: The Python function to be differentiated. A critical constraint is that `fun` **must return a scalar** [cite: 9]. If it returns an array with more than one element, `jax.grad` will throw a `TypeError`.
*   `argnums` (int | Sequence[int], default=`0`): Specifies which positional argument(s) to differentiate with respect to [cite: 9]. By default, it computes the gradient with respect to the first argument.

### 4.2 Differentiating Logistic Loss
The logistic loss function (binary cross-entropy) over a dataset is defined mathematically as:
\[ L(w) = \frac{1}{N} \sum_{i=1}^N \log(1 + \exp(-y_i (X_i \cdot w))) \]
where \( y_i \in \{-1, 1\} \). 

Calculating \( \log(1 + \exp(z)) \) is numerically unstable for large \( z \) due to floating-point overflow in the exponential. The numerically stable identity utilizes the log-sum-exp trick, natively implemented as `jnp.logaddexp(0, z)` [cite: 10, 11].

**Pitfall resolution:** Can `jnp.logaddexp` accept a Python scalar `0` as its first argument? Yes. JAX's lax-backend implementation automatically coerces standard Python scalars (like `0` or `1.0`) into JAX scalar arrays of the matching dtype without requiring explicit `jnp.float32(0)` wrappers [cite: 12, 13].

#### Code Example: Logistic Loss Gradient
To compute the gradient with respect to the weight vector `w`, `w` must be provided as an independent argument. If `w` is the first argument, `argnums=0` applies implicitly.

```python
import jax
import jax.numpy as jnp

def logistic_loss(w: jax.Array, X: jax.Array, y: jax.Array) -> jax.Array:
    """
    Computes the mean logistic loss.
    
    Args:
        w: Weight vector of shape (D,)
        X: Feature matrix of shape (N, D)
        y: Target vector of shape (N,) with labels in {-1, 1}
        
    Returns:
        A scalar JAX array representing the mean loss.
    """
    # X @ w yields logits of shape (N,)
    # jnp.logaddexp(0, z) is mathematically log(exp(0) + exp(z)) = log(1 + exp(z))
    # Scalar 0 is perfectly safe and natively broadcasted/promoted by JAX.
    logits = jnp.dot(X, w)
    elementwise_loss = jnp.logaddexp(0, -y * logits)
    
    # Must return a scalar for jax.grad to work
    return jnp.mean(elementwise_loss)

# Define the gradient function. 
# argnums=0 is default, differentiating with respect to 'w'.
grad_logistic_loss = jax.grad(logistic_loss, argnums=0)

# Demonstration
key = jax.random.key(123) # Using JAX 0.8.x preferred key gen
X_data = jax.random.normal(key, (100, 5))
y_data = jnp.where(jax.random.uniform(key, (100,)) > 0.5, 1.0, -1.0)
w_init = jnp.zeros(5)

# Calculate gradient: returns an array of shape (5,)
gradient_wrt_w = grad_logistic_loss(w_init, X_data, y_data)
```

## 5. Sequence Processing with `jax.lax.scan` for RNNs

Control flow (like `for` and `while` loops) behaves idiosyncratically in JAX. If you place a Python `for` loop inside a `@jax.jit` function, JAX traces the loop, completely unrolling it into a massive, static computational graph [cite: 14]. For an RNN processing 1000 timesteps, XLA generates 1000 sequential copies of the RNN cell, causing massive compile times and potential out-of-memory errors [cite: 14]. 

To circumvent this, JAX provides `jax.lax.scan`, a compiled looping primitive that allows the XLA compiler to generate a true, memory-efficient loop at the machine level [cite: 15].

### 5.1 Exact Signature of `jax.lax.scan`
```python
jax.lax.scan(f, init, xs=None, length=None, reverse=False, unroll=1)
```
*   `f`: A Python function representing the loop body. It must possess the signature `f(carry, x) -> (new_carry, output)` [cite: 15].
*   `init`: The initial state of the `carry`. Its shape and dtype **must remain completely invariant** across all loop iterations [cite: 15].
*   `xs`: A PyTree of arrays to iterate over along their leading (0th) axis.

### 5.2 Return Values and Array Stacking
The loop body `f(carry, x)` returns a two-tuple `(new_carry, output)`. 
`jax.lax.scan` takes these tuples over all $T$ timesteps, threads the `carry` recursively, and accumulates the `output` by stacking it along a newly created leading axis [cite: 15, 16]. 

Therefore, `scan` returns `(final_carry, stacked_outputs)`.
For an RNN with hidden state `H` and input sequence `T`:
*   `init` shape: `(H,)`
*   `xs` shape: `(T, I)`
*   `stacked_outputs` shape: `(T, H)` (if the output is the hidden state).
*   Total return of `scan`: `(Array(H,), Array(T, H))` [cite: 14].

Should the function return the final hidden state, all hidden states, or both? Standard practice dictates that `f` returns `(h_new, h_new)`. Thus, `scan` returns both the final hidden state (for downstream sequences) and the full sequence of hidden states (for loss calculations across time) [cite: 17].

#### Code Example: RNN Forward Pass
```python
import jax
import jax.numpy as jnp

def rnn_forward(params: dict, x_seq: jnp.ndarray, h_init: jnp.ndarray) -> tuple:
    """
    Computes the forward pass of a vanilla RNN using jax.lax.scan.
    
    Args:
        params: Dictionary containing 'Wx', 'Wh', and 'b'.
                Wx: (I, H), Wh: (H, H), b: (H,)
        x_seq: Input sequence of shape (T, I)
        h_init: Initial hidden state of shape (H,)
        
    Returns:
        A tuple (h_final, h_sequence)
        h_final: Final hidden state of shape (H,)
        h_sequence: Stacked hidden states of shape (T, H)
    """
    
    def rnn_step(carry: jnp.ndarray, x_t: jnp.ndarray) -> tuple:
        """
        The recurrence step. 
        Signature: (carry, x) -> (new_carry, output)
        """
        h = carry
        Wx, Wh, b = params['Wx'], params['Wh'], params['b']
        
        # RNN mathematics: h_new = tanh(x_t @ Wx + h @ Wh + b)
        h_new = jnp.tanh(jnp.dot(x_t, Wx) + jnp.dot(h, Wh) + b)
        
        # We output h_new as both the carry for the next step, 
        # and the output to be stacked into the historical sequence.
        return h_new, h_new

    # jax.lax.scan threads the carry and stacks the outputs automatically
    # over the leading dimension of x_seq (which is T)
    h_final, h_sequence = jax.lax.scan(rnn_step, h_init, x_seq)
    
    return h_final, h_sequence
```

## 6. Just-In-Time Compilation with `jax.jit`: 2-Layer MLP

The `jax.jit` decorator leverages XLA to compile pure Python functions into highly optimized accelerator code [cite: 18]. 

### 6.1 Implementing ReLU and MLP Math
A Multi-Layer Perceptron (MLP) forward pass requires linear combinations interspersed with non-linear activations. The canonical function for a Rectified Linear Unit (ReLU) in JAX is `jax.nn.relu` [cite: 19]. 

While mathematically equivalent to `jnp.maximum(0, x)`, `jax.nn.relu` provides a specialized primitive custom-differentiated to handle the origin singularity (`x=0`). Specifically, `jax.nn.relu` defines its derivative at exactly zero to be 0 (`∇relu(0) = 0`) [cite: 19]. Using `jnp.maximum(0, x)` works in practice but lacks this explicitly documented algorithmic safety.

### 6.2 Does `jax.jit` Affect Numerical Results?
In theory, JIT compilation transforms the abstract syntax tree into mathematically equivalent linear algebra primitives. It affects **performance** rather than numeric semantics. However, in practice, XLA aggressively applies algebraic simplifications, loop fusions, and operator reordering (like transforming independent matrix multiplications into batched operations or leveraging hardware fused-multiply-add instructions) [cite: 3]. 
Because floating-point arithmetic is inherently non-associative, these compiler-level reorderings can cause minor discrepancies (on the order of $10^{-7}$ for float32) between the eager execution of JAX arrays and their compiled counterparts [cite: 20].

#### Code Example: JIT-Compiled MLP
```python
import jax
import jax.numpy as jnp

def mlp_forward(params: dict, X: jnp.ndarray) -> jnp.ndarray:
    """
    Forward pass of a 2-layer MLP.
    
    Args:
        params: Dict with 'W1', 'b1', 'W2', 'b2'
        X: Input data of shape (Batch, Features)
        
    Returns:
        Outputs of shape (Batch, Output_Dim)
    """
    W1, b1 = params['W1'], params['b1']
    W2, b2 = params['W2'], params['b2']
    
    # Layer 1: Linear + ReLU
    # jax.nn.relu is the canonical method
    h1 = jax.nn.relu(jnp.dot(X, W1) + b1)
    
    # Layer 2: Linear output
    logits = jnp.dot(h1, W2) + b2
    return logits

# Compile the function using jax.jit
# The function will trace the first time it is invoked, and reuse the binary thereafter.
jit_mlp = jax.jit(mlp_forward)

# Demonstration parameters
key = jax.random.key(0)
k1, k2, k3, k4, kX = jax.random.split(key, 5)

params = {
    'W1': jax.random.normal(k1, (10, 32)),
    'b1': jnp.zeros(32),
    'W2': jax.random.normal(k2, (32, 2)),
    'b2': jnp.zeros(2)
}
X_batch = jax.random.normal(kX, (64, 10))

# Execute the compiled function
output = jit_mlp(params, X_batch)
```

## 7. Data Serialization: Saving JAX Arrays to NumPy Files

Because JAX and NumPy both support the Python buffer protocol, JAX arrays share fundamental memory structures with NumPy arrays. 

### 7.1 Direct Application of `np.save`
If you attempt to execute `np.save("file.npy", jax_array)` directly, two things can happen depending on the execution context:
1.  **In Eager Mode**: NumPy detects the JAX array via duck-typing and the buffer protocol, pulling the device array implicitly to host memory and saving it. While functional, it relies on implicit dispatch logic that is sometimes fragile.
2.  **Inside `jax.jit` (Tracing)**: If `np.save` is invoked within a compiled function, the input variable is not an actual array but an abstract `Tracer` representing the computational graph [cite: 21]. `np.save` will attempt to serialize the `Tracer` object itself, leading to a catastrophic `ConcretizationTypeError` or silently corrupting execution memory [cite: 21]. JAX 0.8.x strictly enforces that `Tracer` objects no longer inherit from `jax.Array` specifically to prevent these silent leaks [cite: 22].

### 7.2 The Correct Serialization Pattern
To safely and explicitly serialize a JAX array, users must ensure the tensor is firmly resolved to a concrete host memory array outside of JIT boundaries. The most efficient approach utilizes `np.asarray()` [cite: 23]. Using `np.array(jax_array)` works but enforces a deep memory copy. `np.asarray()` avoids unnecessary copies when memory is already safely addressable.

#### Code Example: Proper Array Saving
```python
import numpy as np
import jax.numpy as jnp

def save_jax_array(path: str, jax_array: jax.Array):
    """
    Safely serializes a JAX array to disk as a NumPy .npy file.
    
    Args:
        path: Destination file path.
        jax_array: The JAX device array to save.
    """
    # Explicitly cast to a NumPy array on the host. 
    # np.asarray prevents unnecessary copies if buffer sharing is viable.
    host_array = np.asarray(jax_array)
    
    # Save natively (allow_pickle=False for safety across environments)
    np.save(path, host_array, allow_pickle=False)
```

## 8. Common Pitfalls and Migration Notes in JAX 0.8.x

JAX iterates rapidly. The 0.8.x version branch introduces structural changes aiming at robust multi-device environments and stricter typing constraints.

### 8.1 Breaking Changes in JAX 0.8.x
The most profound shift in JAX 0.8.0 pertained to parallel mapping (`jax.pmap`). The default implementation of `pmap` was completely rewritten to be based on `jax.jit` combined with `jax.shard_map` [cite: 24, 25]. 

Crucially, **rank-reduction behavior** was altered. Historically, `pmap` might have reduced the dimensionality of mapped arrays improperly. In 0.8.x, the "no-rank-reduction" behavior is rigidly enforced: if `jax.pmap(f)` receives a shape `(8, 128)` distributed across 8 devices, the body function `f` sees an array of shape `(1, 128)`, not `(128,)` [cite: 22, 24]. Temporary mitigation flags (`jax_pmap_shmap_merge`) exist but are marked for deprecation by JAX 0.10.x [cite: 22, 25].

### 8.2 Import Paths
The module `jax.numpy` remains the canonical, fully supported interface for array manipulation. There have been no deprecations to the core import pattern: `import jax.numpy as jnp` remains perfectly standard [cite: 26]. However, internals (like specific elements within `jax.core`) have moved to `jax.extend.core` [cite: 22].

### 8.3 `jnp.logaddexp` with Scalar Zero
As established in Section 4.2, `jnp.logaddexp(0, x)` performs flawlessly. JAX's promotion semantics automatically cast standard Python integers and floats into dimensionless scalars that successfully broadcast across the spatial dimensions of array `x` [cite: 12]. You do **not** need to wrap it in `jnp.float32(0)` unless strict typing policies in external validation logic demand it.

### 8.4 `jax.lax.scan` Signature Integrity
The fundamental signature of `jax.lax.scan` has not experienced breaking changes in JAX 0.8.x. However, developers must strictly ensure that the type and shape of the `carry` are mathematically identical between the input and output of the body function `f` [cite: 15]. In earlier JAX versions, implicit type casting inside the loop might occasionally survive the tracing process; in 0.8.x, a divergence between the `init` variable shape/dtype and the returned `carry` shape/dtype will yield a strict XLA compiler error [cite: 15].

### 8.5 Random Seed Handling: The Death of `PRNGKey`
A monumental shift finalized in recent JAX updates is the migration from legacy unstructured integers for random generation to strictly typed key structures [cite: 27]. 

In JAX 0.4.x, `jax.random.PRNGKey(seed)` generated a standard `uint32` array. In JAX 0.8.x, `jax.random.PRNGKey` is heavily deprecated and internally dismantled [cite: 27, 28]. The modern, functionally accurate method to initialize a pseudorandom number generator is `jax.random.key(seed)` [cite: 29]. This produces a strictly typed scalar key array (`KeyArray`) that prevents users from erroneously performing arithmetic operations (like `key + 1`) directly on the internal seed representation [cite: 27].

#### Code Example: Proper 0.8.x RNG Handling
```python
import jax

# Initialize typed key - DO NOT USE jax.random.PRNGKey(0)
master_key = jax.random.key(0)

# Functional randomness strictly requires splitting the key explicitly
# before evaluating random parameters, preventing state aliasing.
key_model, key_data = jax.random.split(master_key)

# The new sub-keys can now be safely consumed
random_weights = jax.random.normal(key_model, (10, 10))
```

## Conclusion
Developing optimized algorithms in JAX 0.8.x necessitates an intimate understanding of the functional paradigm. By explicitly splitting random states via `jax.random.key`, orchestrating repetitive logic strictly through `jax.lax.scan`, resolving array concretization outside of `jax.jit` prior to NumPy serialization, and globally defining numeric precision constants, engineers can avoid JAX's ubiquitous sharp edges and harness the compiler's profound capacity for high-performance scale-out computation.

**Sources:**
1. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAe-mwYOEVrALR0zDpHC6rtG-U6sa7tPombHN-uMHo3F5iGJx5S5bLTu-Mx-cg27k-ksoRD700ZoZkCLvi18ifgRcrqoK02MWQoNbkc_e4o0gbB7MHoNhKvIv9Q2Dqgl3ifvnzihQG4Q==)
2. [quantecon.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhD3nKl3hWC34uAB_zIrLz2fS2MsMLv7KagQrc_BacX6lYMFGfW4fjNvqIEyUdiU9050yN3Sdc2vaHb-s-ZgvAaDMBUoZJBB4AV4FE1LDtiDZsdZwtf6HzCi20ySf8)
3. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGGTLfVTu9Xx8cCO4UKzkF3AKMCJ83fLbPOubMC-YQ9DHpzSEnaXgkPAwWfd5mCyCsYbaYI89XdQS9uPIYl29GGqJ5tCOy1e4IMHWlwFH3Eu4OZBejPVmuCEg==)
4. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGFAA5bV0HOS0EesvnDWLygBRR0MTvQ5kIoAt2QmazBzVlTYPQgaOcBPkYwcYxRqV7y2R4OnOk-AThM-ypt-X_iWTsAT9CTVmshyU1DguE5Fv-_A6eqPiBwCsvqdzjpDXa2)
5. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFAaVs5HiCb0VyJp3-E0qDgM2sZwBS8k6hDwz9IXTig6GkOH7w5vqFwqR13cVRm17_REVQ_mWXsxuFEXWYi1254S-kFykq_SijNsZzpxwDumqcxBhvIsNKk1YuPY3_eSXIVnuUMF6baka2MVJpvfFhFlQ6mp8=)
6. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGset_28ufOo_OivT4VKA7J1TwOTHJXmIUBZkv4jxNhpmUEKIC3ixVIvfSpQHMw8LVBLJFl3OEilyLrqgK2Z5Lyod61aSyE2c3swXIia4Ge76bnO1NrP7pHYq_85bGPGhemDLjgFuzFdhbYhlyhnbFCm8rgRSxhjA==)
7. [colinraffel.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF8f88zAVMclPv7N5OgmUsd0cXmtNASGAhtWb94L1ijtJByyIQuiQThhd0A3BEAeK5HBLWDO9o12PgzKV8gg8F7xo2FCOn8F7RioYHs8iaQ9enrWeOCyqAZMHChR7LM0DB04vInmVSdF3Au)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnuNf1wbkPHnoQLCUOYN0NEZ7y5gyS3HCGA8gFg2viDcVtPmvEGJP9PMiVIrtt7kJfWgZQRcku8bRUAVjC3n8AlgfNLAvPeKXMNqoD7CAN3U5AEw==)
9. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEoE1NrCtE-22wwj1evrviwBJFyeBo3iw-dqGp5Xx-GLRV2AxCk08UKCaSHqJzt3Xcx01r2HJ_kdRm8CP__uLmKSe3wSkj-8ZccnBVDHh7o3pwRYgAHA05fok_cBjBR80Ea2oiIPw8GHhjvsIY60mE=)
10. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEzqyLkIBGaA6p_q2Ig4sOHiUOlvssYko6ehdMaKU7G54fmOV0P_vO0stLn3ZD19KfMQu921g1Ju7c83kqlAj2khjIBxCY6fmKxQmqIpiin5YyR1SWAqjpDUiqSI-43puyGcb5fLRtYNMVStwnvxyfu1qfP8JpAnsJZCQ==)
11. [numpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE5pL7AB00aF8UpYU79Hi60WysgzmSzk6FN_-zQKE8tAOVTFR2ULHxa7m-KqftHBYJxlmwT3mGC6VSX6H4ds_pZrooN_rd5fz9NFgdph9lURVWjbv8X7z6MSY9MI0p8H2e2-NYqx_KiKGOwRnvYoQ3OE9H7etXzHjc=)
12. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH12D0wS5VCZzxtJVhpY92578RDvqcNocBJGozMb4jdIejoFqrzQ9_V3RLAByZ-HvsIwwKXQbtTq8R7skO73Oaef4AjhOjYWxzVTYmnYXXXssecgwH9aP93uQh-gKRdehxa_jx8OOBVOdbFLlqeOfoVTvIPAlSQ)
13. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtUUM6CppHsC8orvW4OVPpOGtju56f2knIBDwUz6QQXWi5PakgKngHihKfmPUmfkmpPGMNfMKxoa0aeQ0Z779c3wevX1X4LMLy6X29rcz6oySKLAtn4z2xda2eIxTGgNLGTvSESnr6XY_jKdf4BPrNy7VIdhB7tziRKN0=)
14. [apxml.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHDxzuDeNyDoblMu3Sh5LaSpqkbHqqHS07Lcxt2Xcqk-Zt9A1XrdTdKg8BFWu0fTlNwMs-iBD_iyuUl5IgsUNrD_hoivK4EMTdbe6OybpMWihwOrHNCezqD6KvWwDfD3jD-pRXJf_vakhz0uI64fP2aO5N05idHnsPHCTQuKS5mDIwn-aw0IGaK62mlShZIvhMeZrmtnjwbHJIAylJHZo_CvNgv)
15. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG2bS6oBKkBtZWMwz8N5RJzeTEp9BHII_-_2dBVXec2Fp0KS53HEfzQHQ9wmwZR7MEuWwNVplt9KtpTK80-jRGIgJHLxJko9-J8dGQKz7DE5uAc2NlQyJsxv2YrwH-acn_6WPTlLTkv8EJJaVMLpfM4rIZD)
16. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_EkjMasT_US7XgCWNE_oOXm3IJ2YCmqgT5AYaNsSeBpqALMoByVUQ0gUvP0rK2R6oPqEQ4OxX6Q7awK2gbhbfuNHmn5JWfOB0rSVSlox2JhFU5Cak1IJ-PPTpXr_gKq1gh0Z6Ry8hUq8EZxc1PDAaa1D4Rf2t3JV1SunG8cSDy0cxRzFS60jSaAxmVw==)
17. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlG1iVr0T9GQrxVPJkddxKm5wL_gQ-3knti2pATLBkKYGghiWvUDw_Cq_6rVn3EHeq1d5RLjtTmN712KXB4_UnGIOuCigz6axjecZPrfNnsc_wWfidQ0Wypmai4sJdmB4s)
18. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzQmBh89pr_TtQ8hAiRWYBiMnELDDNkwdnYPmyTQTj19C-cSHHPSA7CCf4dK3mwT3QHvsaT_BOjLcu6hTG5Q1nTZiFua4vXr0VR4DgOnioQnnaeA==)
19. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGozcW4d8FSWM8RUhh9BZmiy4sYmsl_vsgsKY4woBe3GcVDflwOkRRACS6_eD1EUMYF66t3HmRbgZdWaf7b0XmAoWHM_kTVO9XPIXlTmnq7AJzbGWTenk3WlruFjqjNtGvIZPKDbpjJ4tt-yHbxURofmhQ=)
20. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKOWbdYmGjQ9PQ1Ryfmh1ouTcR-H0seM2V9Gubg1pEFlcRjocYwXmsOSF5DpK92J167kEERb79QwafM0gfF80IXOdStIwx21iR6TgWXdgsg1k3kXJUm9zWqOwzN5NLrJ-vjpDjpemckWc_Ww==)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFIVAB0gQB0LGbIbh-6wby60hgj-4IXRDrXwABKRRIl6s5iLNlTLaExUFx4rJqBjG8ZHUEOqnpSg-vluBGHpJQSFfXr-3bqqw_Mdmoh_GrDpiBMRodHDePt0EOZDOqHZZvFpz7y)
22. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH8ILBcoHKpEZ3rFdRyffKJU9GFifzXa1zPO0-IFeGREnsM4GSSwPc3EFhrEuUSy1JRXBHnCgSKbAoUslKhqv7vC-AfYiaL_JOzunFehM6QqcgETeSwI6V3zWRRZ4cGY8ryOdw=)
23. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTKVQ0g1tIkJp-xKde22WSMtor38Lhqdmx9gSOmeQUBYkc4fmUswIMfczDjVd5O6seYEs0rX3HFbjKJouQoEsj1-62FVAueydwaaIE9d94lhhzR3UYBqKCiNqBx-EUDqRd-JJEqF5yp9YsSJt_zSL2iSdLiFY4BA==)
24. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEcbt28HOSIIR4O8WVcw0VUDAczFkMVed_WfMU8hAQv1ptOJp_2eoC63-AE6f5SyM_dIq6zPAxyS5KT7FVgCnzdPTiSkLgB7Dr2_-LRpBESHpBH0Plg_vdXb5lmKVaYEohavjF_89Q=)
25. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0f4pNe_TB6Cfv2bUtpmR76oew8uo2HumCaelT4oX1g7n_ps-Xdqxso5tcgnpbdjgL2ZvFAZBeNwPswxxeKGkp9tP9CJuumrjEb3AfNjfsTx2milvjKqKMOPFVtpQa7OXmQe5nIQ==)
26. [codesignal.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF67YigC57wY0wS-lxXmXr8VBjCQbzf0ONELYcB4-t6ynTURXzKeA3OoS7qJCkFOLn6WnRaqeone5E-Fiz8VhtB_SwBZyrwFuFDJeZ4y_8SDH9ONBTo2W1PQPHQERYZMB7E0M4hRuDpOSwHoplzY_cavuyVLw0PCFQLppKIgv_4iuCjIJjJC7vgbTqH6TuXUoAY9jj2WEtGLc82_NiSfdmYuNcWr0QuTXacJ7vUFSHAjHpd6MM=)
27. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHag8wT7YYT9vKj2JvXwENZIhjOheIQn362Y2K3rMvCenzkPqRn6KlZ8FvYGiI55NrorYzAhu4vXLkjfFJM3Ud5R_BgQYAx13Q5TbeFDCKqr71kNqaI1MO02DQxlo_g4_pSgU9TJ_3cQ0O-RKnk)
28. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQETxZ0lKIbPjOTTzYpVNaTX-FTyE2cbFv1u-kd5ODDvsm3czT8-Vv2PWzalg8DwmfWACVGT3-rGLMRa3uRZk7rYsf0su_JyI86RSRmk0v4gpseR9eMUb06jg4iiD8TQpS4=)
29. [jax.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGS9PzdwwSfSPpsncuxd60ONEvdkrfHDJurZ3FMysTVtbQzjo64P-d_HJPaey5P1VqyvDOlNwpsOLh6llCsaGWjqyGY_RK4fYEMbmbUW_VQMoRL8t4orVNEwyOg_SaSxyxETAw53gTcRVtSjOKs8g-T2gKmSSI=)
