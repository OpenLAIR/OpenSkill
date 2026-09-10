---
name: evo-simpo-code-reproduction
description: Implements the SimPO (Simple Preference Optimization) loss function and handles environment setup, execution, and result saving for code reproduction tasks.
---

# evo-simpo-code-reproduction

## Overview
Complete skill for reproducing the SimPO (Simple Preference Optimization) loss function from the paper by Meng et al. (2024). Handles implementation of the `simpo_loss` method, environment setup, unit test execution, and saving results.

## Key Concepts (from the paper)

### SimPO Loss Formula
```
L_SimPO = -log(sigmoid(beta/|y_w| * sum(log π(y_w|x)) - beta/|y_l| * sum(log π(y_l|x)) - gamma))
```

### Critical Implementation Details
1. **Inputs are pre-normalized**: `policy_chosen_logps` and `policy_rejected_logps` are already length-averaged (mean log probs per token) before entering `simpo_loss`. The averaging happens in `get_batch_logps` with `average_log_prob=True`.

2. **Margin factoring**: The code computes `logits = pi_logratios - gamma/beta`, then applies `beta * logits` inside logsigmoid. This is algebraically equivalent to `beta * pi_logratios - gamma`.

3. **gamma computation**: In the SimPO trainer, `gamma = self.gamma_beta_ratio * self.beta` (where `gamma_beta_ratio` defaults to ~0.25, giving gamma≈0.5 for beta=2.0). The paper recommends gamma/beta ≈ 0.5.

4. **Loss types**:
   - Sigmoid (default): `losses = -F.logsigmoid(beta * logits) * (1 - label_smoothing) - F.logsigmoid(-beta * logits) * label_smoothing`
   - Hinge: `losses = torch.relu(1 - beta * logits)`

5. **Rewards are detached**: `chosen_rewards = beta * chosen_logps.detach()`, `rejected_rewards = beta * rejected_logps.detach()`

6. **Return shape**: Per-example losses of shape `(batch_size,)` — reduction happens upstream.

### Sigmoid Loss with Label Smoothing (label_smoothing=0 by default)
When `label_smoothing=0`, the second term vanishes, leaving pure SimPO loss:
```python
losses = -F.logsigmoid(self.beta * logits)
```

When `label_smoothing > 0`:
```python
losses = (
    -F.logsigmoid(self.beta * logits) * (1 - self.label_smoothing)
    - F.logsigmoid(-self.beta * logits) * self.label_smoothing
)
```

## Environment Setup
- Python 3.10+
- `pip install torch transformers 'trl==0.8.6' datasets accelerate peft numpy`
- trl>=0.29 removed CPOTrainer; use trl==0.8.6 for compatibility with the SimPO codebase

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-simpo-code-reproduction/scripts')
from simpo_loss_impl import implement_simpo_loss
from run_and_save import setup_environment, run_unit_test, log_python_info

# Step 1: Setup environment
setup_environment()

# Step 2: Implement the loss function
implement_simpo_loss('/root/SimPO/scripts/simpo_trainer.py')

# Step 3: Run unit test and save results
run_unit_test()

# Step 4: Log python info
log_python_info()
```

## Common Pitfalls
1. **Sum vs Mean**: SimPO uses MEAN log probs (already done upstream), not sum. Don't re-normalize.
2. **gamma/beta factoring**: The margin is `gamma/beta` subtracted from logratios, then multiplied by beta. Don't subtract gamma directly before beta scaling.
3. **Detach rewards**: Always `.detach()` rewards to prevent memory leaks.
4. **Hinge loss formula**: Uses `torch.relu(1 - beta * logits)`, not `torch.relu(-logits)`.
5. **Device handling**: Some implementations move tensors to accelerator device; in unit tests without accelerator, this may need to be handled gracefully.