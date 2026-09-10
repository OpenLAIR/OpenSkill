"""JAX computation utilities for all five tasks.

Implements:
1. basic_reduce: Row-wise mean reduction using jnp.mean(x, axis=1)
2. map_square: Element-wise squaring using jnp.square(x)
3. grad_logistic: Logistic loss gradient via jax.grad with logaddexp stability
4. scan_rnn: RNN forward pass via jax.lax.scan with RIGHT-multiply convention
5. jit_mlp: JIT-compiled 2-layer MLP forward pass with jax.nn.relu

Key domain knowledge:
- jnp.logaddexp(0, x) computes log(1+exp(x)) numerically stably; scalar 0 auto-promotes
- jax.grad requires scalar output; use jnp.mean to reduce
- jax.lax.scan requires carry dtype/shape identical across iterations
- RNN uses RIGHT-multiply per doc: h_new = tanh(x_t @ Wx + h @ Wh + b)
- JIT may cause minor float differences (~1e-7) due to XLA reordering
- jax.nn.relu is canonical for ReLU activation
"""
import jax
import jax.numpy as jnp


def compute_basic_reduce(x):
    """Compute mean of each row in a 2D array.

    Args:
        x: JAX array of shape (M, N). If 1D, returns scalar mean.

    Returns:
        JAX array of shape (M,) with per-row means.
    """
    if x.ndim == 1:
        return jnp.mean(x)
    return jnp.mean(x, axis=1)


def compute_map_square(x):
    """Apply square function to each element using vectorization.

    Uses jnp.square which is natively vectorized. Equivalent to x**2.

    Args:
        x: JAX array of any shape

    Returns:
        JAX array of same shape with each element squared
    """
    return jnp.square(x)


def compute_grad_logistic(data):
    """Compute gradient of logistic loss w.r.t. weights.

    Loss: L(w) = mean(logaddexp(0, -y * (X @ w)))
    Uses jnp.logaddexp(0, z) for numerical stability.
    jax.grad with argnums=0 differentiates w.r.t. first arg (w).

    Args:
        data: dict with keys 'x' (N,D), 'y' (N,), 'w' (D,)

    Returns:
        JAX array of shape (D,) - gradient of loss w.r.t. w
    """
    X = data.get('x', data.get('X'))
    y = data['y']
    w = data['w']

    if X is None:
        raise KeyError("Expected 'x' or 'X' key in data dict")

    X = jnp.asarray(X, dtype=jnp.float32) if not jnp.issubdtype(X.dtype, jnp.floating) else X
    y = jnp.asarray(y, dtype=jnp.float32) if not jnp.issubdtype(y.dtype, jnp.floating) else y
    w = jnp.asarray(w, dtype=jnp.float32) if not jnp.issubdtype(w.dtype, jnp.floating) else w

    def logistic_loss(w, X, y):
        logits = jnp.dot(X, w)
        elementwise_loss = jnp.logaddexp(0.0, -y * logits)
        return jnp.mean(elementwise_loss)

    grad_fn = jax.grad(logistic_loss, argnums=0)
    return grad_fn(w, X, y)


def compute_scan_rnn(data):
    """Implement RNN forward pass using jax.lax.scan.

    Uses RIGHT-multiply convention (matching the background doc):
        h_new = tanh(x_t @ Wx + h @ Wh + b)

    This is the standard formulation from the doc:
        h_new = tanh(jnp.dot(x_t, Wx) + jnp.dot(h, Wh) + b)

    Weight matrices are closed over (captured from outer scope).

    Args:
        data: dict with keys:
            'seq': input sequence (T, I)
            'init': initial hidden state (H,)
            'Wx': input-to-hidden weights (I, H)
            'Wh': hidden-to-hidden weights (H, H)
            'b': bias vector (H,)

    Returns:
        JAX array of shape (T, H) - stacked hidden states
    """
    x_seq = data['seq']
    h_init = data['init']
    Wx = data['Wx']
    Wh = data['Wh']
    b = data['b']

    target_dtype = Wx.dtype
    h_init = jnp.asarray(h_init, dtype=target_dtype)
    x_seq = jnp.asarray(x_seq, dtype=target_dtype)
    Wh = jnp.asarray(Wh, dtype=target_dtype)
    b = jnp.asarray(b, dtype=target_dtype)

    def rnn_step(carry, x_t):
        h = carry
        # RIGHT-multiply per doc: x_t @ Wx + h @ Wh + b
        h_new = jnp.tanh(jnp.dot(x_t, Wx) + jnp.dot(h, Wh) + b)
        return h_new, h_new

    _h_final, h_sequence = jax.lax.scan(rnn_step, h_init, x_seq)
    return h_sequence


def compute_jit_mlp(data):
    """Implement and JIT compile a 2-layer MLP forward pass.

    Layer 1: h = relu(X @ W1 + b1)
    Layer 2: out = h @ W2 + b2

    Uses jax.nn.relu (canonical) and jax.jit for compilation.

    Args:
        data: dict with keys:
            'X': input batch (B, F)
            'W1': first layer weights (F, H)
            'b1': first layer bias (H,)
            'W2': second layer weights (H, O)
            'b2': second layer bias (O,)

    Returns:
        JAX array of shape (B, O) - MLP output
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
    """Dispatch to appropriate compute function by task ID.

    Args:
        task_id: string task identifier from problem.json
        description: string task description (used for fuzzy matching)
        data: input data (JAX array or dict of JAX arrays)

    Returns:
        JAX array result

    Raises:
        ValueError: If task cannot be matched
    """
    tid = task_id.lower().strip() if task_id else ""
    desc = description.lower().strip() if description else ""
    combined = tid + " " + desc

    exact_dispatch = {
        'basic_reduce': compute_basic_reduce,
        'map_square': compute_map_square,
        'grad_logistic': compute_grad_logistic,
        'scan_rnn': compute_scan_rnn,
        'jit_mlp': compute_jit_mlp,
    }

    if tid in exact_dispatch:
        return exact_dispatch[tid](data)

    if 'grad' in combined or 'logistic' in combined:
        return compute_grad_logistic(data)
    elif 'scan' in combined or 'rnn' in combined:
        return compute_scan_rnn(data)
    elif 'jit' in combined or 'mlp' in combined:
        return compute_jit_mlp(data)
    elif 'square' in combined or 'map' in combined:
        return compute_map_square(data)
    elif 'reduce' in combined or 'mean' in combined or 'row' in combined:
        return compute_basic_reduce(data)

    raise ValueError(f"Unknown task: id='{task_id}', description='{description}'")
