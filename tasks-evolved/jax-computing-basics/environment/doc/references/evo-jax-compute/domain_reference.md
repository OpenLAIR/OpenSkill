# Domain Reference for evo-jax-compute

**Responsibility**: All JAX computation logic for the five problem tasks, dispatching by problem ID and returning JAX arrays as results.

**Key functions to implement**: compute_basic_reduce, compute_map_square, compute_grad_logistic, compute_scan_rnn, compute_jit_mlp, dispatch_task

---

## 2. Axis-wise Reductions: `jnp.mean`


The `jax.numpy.mean` function computes the arithmetic mean of array elements along specified dimensions.

### 2.2 Exact Behavior for 2D Arrays

When evaluating a 2D array \( X \) of shape `(M, N)`:
*   `axis=0` reduces across the rows (collapsing the row dimension `M`), producing a column-wise mean of shape `(N,)`.
*   `axis=1` reduces across the columns (collapsing the column dimension `N`), producing a per-row mean of shape `(M,)`.

For an input matrix of shape `(10, 5)`, computing `jnp.mean(x, axis=1)` explicitly iterates across the 5 columns for each of the 10 rows. The return shape is strictly `(10,)` [cite: 5].

## 3. Vectorized Element-wise Squaring: `jnp.square`


Squaring array elements is a ubiquitous operation. In JAX, there are three common paradigms to compute \( x_i^2 \): `jnp.square(x)`, `x**2`, and mapped applications like `jax.vmap(lambda xi: xi**2)(x)`.

### 3.1 `jnp.square` vs `x**2` vs `jax.vmap`

1.  **`jnp.square(x)`**: This is the canonical, JAX-native implementation of `numpy.square`. Under the hood, `jnp.square(x)` is implemented identically to `jnp.power(x, 2)` [cite: 6]. It is naturally vectorized over arbitrary dimensional arrays and lowers to an optimized XLA element-wise squaring kernel.
2.  **`x**2`**: This relies on Python's `__pow__` operator overload on JAX's `Array` class. Functionally and computationally, it translates into the exact same XLA instructions as `jnp.square(x)`. It is entirely valid and idiomatic.
3.  **`jax.vmap(lambda xi: xi**2)(x)`**: `jax.vmap` is an automatic vectorization transformation that maps a function along array axes [cite: 7]. Because `**2` is *already* natively vectorized by the JAX core array processing layer, wrapping an explicitly mapped lambda inside `vmap` is redundant. While the XLA compiler is generally sophisticated enough to optimize out the unnecessary map overhead and produce the same efficient binary, writing `vmap` for inherently element-wise functions adds unnecessary cognitive load and tracing overhead during compilation.

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

## 6. Just-In-Time Compilation with `jax.jit`: 2-Layer MLP


The `jax.jit` decorator leverages XLA to compile pure Python functions into highly optimized accelerator code [cite: 18].

### 6.1 Implementing ReLU and MLP Math

A Multi-Layer Perceptron (MLP) forward pass requires linear combinations interspersed with non-linear activations. The canonical function for a Rectified Linear Unit (ReLU) in JAX is `jax.nn.relu` [cite: 19]. 

While mathematically equivalent to `jnp.maximum(0, x)`, `jax.nn.relu` provides a specialized primitive custom-differentiated to handle the origin singularity (`x=0`). Specifically, `jax.nn.relu` defines its derivative at exactly zero to be 0 (`∇relu(0) = 0`) [cite: 19]. Using `jnp.maximum(0, x)` works in practice but lacks this explicitly documented algorithmic safety.

### 6.2 Does `jax.jit` Affect Numerical Results?

In theory, JIT compilation transforms the abstract syntax tree into mathematically equivalent linear algebra primitives. It affects **performance** rather than numeric semantics. However, in practice, XLA aggressively applies algebraic simplifications, loop fusions, and operator reordering (like transforming independent matrix multiplications into batched operations or leveraging hardware fused-multiply-add instructions) [cite: 3]. 
Because floating-point arithmetic is inherently non-associative, these compiler-level reorderings can cause minor discrepancies (on the order of $10^{-7}$ for float32) between the eager execution of JAX arrays and their compiled counterparts [cite: 20].

## 8. Common Pitfalls and Migration Notes in JAX 0.8.x


JAX iterates rapidly. The 0.8.x version branch introduces structural changes aiming at robust multi-device environments and stricter typing constraints.

### 8.3 `jnp.logaddexp` with Scalar Zero

As established in Section 4.2, `jnp.logaddexp(0, x)` performs flawlessly. JAX's promotion semantics automatically cast standard Python integers and floats into dimensionless scalars that successfully broadcast across the spatial dimensions of array `x` [cite: 12]. You do **not** need to wrap it in `jnp.float32(0)` unless strict typing policies in external validation logic demand it.

### 8.4 `jax.lax.scan` Signature Integrity

The fundamental signature of `jax.lax.scan` has not experienced breaking changes in JAX 0.8.x. However, developers must strictly ensure that the type and shape of the `carry` are mathematically identical between the input and output of the body function `f` [cite: 15]. In earlier JAX versions, implicit type casting inside the loop might occasionally survive the tracing process; in 0.8.x, a divergence between the `init` variable shape/dtype and the returned `carry` shape/dtype will yield a strict XLA compiler error [cite: 15].