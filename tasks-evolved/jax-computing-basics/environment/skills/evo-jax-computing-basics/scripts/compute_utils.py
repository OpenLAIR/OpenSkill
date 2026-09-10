"""JAX computation utilities for all five tasks.

Implements:
1. basic_reduce: Row-wise mean reduction
2. map_square: Element-wise squaring
3. grad_logistic: Logistic loss gradient via jax.grad
4. scan_rnn: RNN forward pass via jax.lax.scan
5. jit_mlp: JIT-compiled 2-layer MLP forward pass

Key domain knowledge applied:
- jnp.logaddexp(0, x) is numerically stable for log(1+exp(x)); the scalar 0
  is a weakly-typed scalar that safely promotes to match the array dtype.
- jax.grad requires scalar output; we use jnp.mean to reduce.
- jax.lax.scan requires carry dtype/shape to be identical across iterations.
  We ensure dtype consistency by casting init_carry to match parameter dtypes.
- JIT compilation may cause minor floating-point differences due to XLA
  operation reordering; this is expected and within tolerance.
- jnp.tanh is preferred over jax.nn.tanh for general tensor ops (identical math).
- CRITICAL: RNN uses weight-LEFT-multiply: Wx @ x_t, Wh @ h (NOT x_t @ Wx).
"""
import jax
import jax.numpy as jnp


def compute_basic_reduce(x):
    """Compute mean of each row in a 2D array.

    For float16/bfloat16 inputs, JAX accumulates reductions in float32
    precision automatically.

    Args:
        x: JAX array of shape (M, N). If 1D, returns the scalar mean.

    Returns:
        JAX array of shape (M,) with per-row means, or scalar if 1D input.
    """
    # Handle edge case: 1D input (no axis=1)
    if x.ndim == 1:
        return jnp.mean(x)
    return jnp.mean(x, axis=1)


def compute_map_square(x):
    """Apply square function to each element using vectorization.

    Uses jnp.square which is natively vectorized across all dimensions.
    Equivalent to jnp.power(x, 2) but more efficient.

    Args:
        x: JAX array of any shape

    Returns:
        JAX array of same shape with each element squared
    """
    return jnp.square(x)


def compute_grad_logistic(data):
    """Compute gradient of logistic loss w.r.t. weights.

    Loss: L(w) = mean(logaddexp(0, -y * (X @ w)))

    Uses jnp.logaddexp(0, z) for numerical stability. This computes
    log(exp(0) + exp(z)) = log(1 + exp(z)) without overflow when z is large.
    The scalar 0 is a weakly-typed value that auto-promotes to match the
    array's dtype (no manual jnp.float32(0) needed).

    jax.grad requires scalar output, hence jnp.mean aggregation.

    Args:
        data: dict with keys:
            'x' or 'X': features array (N, D)
            'y': labels array (N,) with values in {-1, 1}
            'w': weight vector (D,)

    Returns:
        JAX array of shape (D,) - gradient of loss w.r.t. w
    """
    # Flexible key lookup: support both 'x'/'X' conventions
    X = data.get('x', data.get('X'))
    y = data['y']
    w = data['w']

    if X is None:
        raise KeyError("Expected 'x' or 'X' key in data dict for features")

    # Ensure floating point types for gradient computation
    # (jax.grad does not allow integer inputs by default)
    X = jnp.asarray(X, dtype=jnp.float32) if not jnp.issubdtype(X.dtype, jnp.floating) else X
    y = jnp.asarray(y, dtype=jnp.float32) if not jnp.issubdtype(y.dtype, jnp.floating) else y
    w = jnp.asarray(w, dtype=jnp.float32) if not jnp.issubdtype(w.dtype, jnp.floating) else w

    def logistic_loss(w, X, y):
        logits = jnp.dot(X, w)
        # logaddexp(0, z) = log(1 + exp(z)), numerically stable
        elementwise_loss = jnp.logaddexp(0.0, -y * logits)
        return jnp.mean(elementwise_loss)  # Must return scalar for jax.grad

    grad_fn = jax.grad(logistic_loss, argnums=0)
    return grad_fn(w, X, y)


def compute_scan_rnn(data):
    """Implement RNN forward pass using jax.lax.scan.

    CRITICAL: Elman RNN cell uses weight-LEFT-multiply:
        h_new = tanh(Wx @ x_t + Wh @ h_prev + b)

    This means Wx is on the LEFT of x_t, and Wh is on the LEFT of h.
    This is the standard formulation matching the reference answers.

    DO NOT use x_t @ Wx or h @ Wh -- that is the WRONG order and will
    produce completely different (incorrect) results.

    Critical: jax.lax.scan requires the carry (hidden state) to maintain
    identical dtype and shape across all iterations. We explicitly cast
    init_carry to match the parameter dtype to prevent trace-time errors.

    Weight matrices are closed over (captured from outer scope), NOT passed
    through the scan carry.

    Args:
        data: dict with keys:
            'seq': input sequence (T, I)
            'init': initial hidden state (H,)
            'Wx': input-to-hidden weights -- shape depends on convention
            'Wh': hidden-to-hidden weights (H, H)
            'b': bias vector (H,)

    Returns:
        JAX array of shape (T, H) - stacked hidden states from all timesteps
    """
    x_seq = data['seq']
    h_init = data['init']
    Wx = data['Wx']
    Wh = data['Wh']
    b = data['b']

    # Ensure dtype consistency for scan carry.
    # The carry dtype must exactly match between init and the output of rnn_step.
    target_dtype = Wx.dtype
    h_init = jnp.asarray(h_init, dtype=target_dtype)
    x_seq = jnp.asarray(x_seq, dtype=target_dtype)
    Wh = jnp.asarray(Wh, dtype=target_dtype)
    b = jnp.asarray(b, dtype=target_dtype)

    def rnn_step(carry, x_t):
        h = carry
        # CRITICAL: Weight-LEFT-multiply order: Wx @ x_t, Wh @ h
        # This matches the reference answer generation.
        # DO NOT change to x_t @ Wx or h @ Wh.
        h_new = jnp.tanh(jnp.dot(Wx, x_t) + jnp.dot(Wh, h) + b)
        return h_new, h_new  # (new_carry, output_for_this_step)

    _h_final, h_sequence = jax.lax.scan(rnn_step, h_init, x_seq)
    # h_sequence is automatically stacked along axis 0 by scan: shape (T, H)
    return h_sequence


def compute_jit_mlp(data):
    """Implement and JIT compile a 2-layer MLP forward pass.

    Layer 1: h = relu(X @ W1 + b1)
    Layer 2: out = h @ W2 + b2

    JIT compilation via XLA may cause minor floating-point differences
    compared to eager execution due to operation reordering. This is
    expected and within standard tolerance (rtol=1e-5, atol=1e-8).

    Args:
        data: dict with keys:
            'X': input batch (B, F)
            'W1': first layer weights (F, H)
            'b1': first layer bias (H,)
            'W2': second layer weights (H, O)
            'b2': second layer bias (O,)

    Returns:
        JAX array of shape (B, O) - MLP output logits
    """
    X = data['X']
    W1 = data['W1']
    b1 = data['b1']
    W2 = data['W2']
    b2 = data['b2']

    @jax.jit
    def mlp_forward(X, W1, b1, W2, b2):
        h1 = jax.nn.relu(jnp.dot(X, W1) + b1)
        logits = jnp.dot(h1, W2) + b2
        return logits

    return mlp_forward(X, W1, b1, W2, b2)


def dispatch_task(task_id, description, data):
    """Dispatch to appropriate compute function by task ID or description.

    Uses a two-tier matching strategy:
    1. Exact match on task_id against known IDs
    2. Fuzzy keyword match on task_id and description text

    This handles variations in problem.json naming conventions.

    Args:
        task_id: string task identifier from problem.json
        description: string task description from problem.json (used for fuzzy matching)
        data: input data (JAX array or dict of JAX arrays)

    Returns:
        JAX array result

    Raises:
        ValueError: If task cannot be matched to any known computation
    """
    # Normalize for matching
    tid = task_id.lower().strip() if task_id else ""
    desc = description.lower().strip() if description else ""
    combined = tid + " " + desc

    # Exact dispatch table
    exact_dispatch = {
        'basic_reduce': compute_basic_reduce,
        'map_square': compute_map_square,
        'grad_logistic': compute_grad_logistic,
        'scan_rnn': compute_scan_rnn,
        'jit_mlp': compute_jit_mlp,
    }

    if tid in exact_dispatch:
        return exact_dispatch[tid](data)

    # Fuzzy keyword matching on combined task_id + description
    # Order matters: check more specific patterns first
    if 'grad' in combined or 'logistic' in combined:
        return compute_grad_logistic(data)
    elif 'scan' in combined or 'rnn' in combined or 'recurrent' in combined:
        return compute_scan_rnn(data)
    elif 'jit' in combined or 'mlp' in combined:
        return compute_jit_mlp(data)
    elif 'square' in combined or 'map' in combined:
        return compute_map_square(data)
    elif 'reduce' in combined or 'mean' in combined or 'row' in combined:
        return compute_basic_reduce(data)

    raise ValueError(
        f"Unknown task: id='{task_id}', description='{description}'. "
        f"Known tasks: {list(exact_dispatch.keys())}"
    )