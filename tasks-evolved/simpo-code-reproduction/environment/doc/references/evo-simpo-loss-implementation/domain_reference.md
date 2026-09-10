# Domain Reference for evo-simpo-loss-implementation

**Responsibility**: Provide the correct SimPO loss function implementation including: pi_logratios computation, gamma/beta margin factoring, F.logsigmoid-based loss with label smoothing, hinge loss variant, and detached reward returns. Handles sigmoid and hinge loss types.

**Key functions to implement**: simpo_loss

---

## 2. Mathematical Formulation of SimPO


To rigorously understand SimPO, we must contrast its mathematical formulation directly with DPO.

### 3.3 The Core `simpo_loss` PyTorch Implementation


Because the log probabilities passed into `simpo_loss` are **already averaged** by `get_batch_logps` [cite: 14, 15], the `simpo_loss` formula simplifies algebraically. 

The mathematical term inside the sigmoid is:
$ \beta (\text{chosen\_logps\_avg}) - \beta (\text{rejected\_logps\_avg}) - \gamma $

Which can be factored as:
$ \beta \left( \text{chosen\_logps\_avg} - \text{rejected\_logps\_avg} - \frac{\gamma}{\beta} \right) $

This factorization is exactly how it is implemented in the official repository [cite: 13]:

```python
import torch
import torch.nn.functional as F
from typing import Tuple

def simpo_loss(
    self, 
    policy_chosen_logps: torch.FloatTensor, 
    policy_rejected_logps: torch.FloatTensor,
) -> Tuple[torch.FloatTensor, torch.FloatTensor, torch.FloatTensor]:
    """
    Compute the SimPO loss for a batch of policy model log probabilities.
    
    Args:
        policy_chosen_logps: Averaged log probabilities for chosen responses. Shape: (batch_size,)
        policy_rejected_logps: Averaged log probabilities for rejected responses. Shape: (batch_size,)
        
    Returns:
        losses: The SimPO loss for each example. Shape: (batch_size,)
        chosen_rewards: Extracted rewards for logging. Shape: (batch_size,)
        rejected_rewards: Extracted rewards for logging. Shape: (batch_size,)
    """
    # Calculate the difference in average log probabilities
    pi_logratios = policy_chosen_logps - policy_rejected_logps
    
    # Scale the margin by beta
    gamma_logratios = self.gamma / self.beta
    
    # Ensure correct device
    pi_logratios = pi_logratios.to(self.accelerator.device)
    
    # Compute the core logits argument for the sigmoid function
    # logits = (chosen_logps - rejected_logps) - (gamma / beta)
    logits = pi_logratios - gamma_logratios
    
    # Calculate the loss using the numerically stable F.logsigmoid
    if self.loss_type == "sigmoid":
        # SimPO loss with label smoothing support
        losses = (
            -F.logsigmoid(self.beta * logits) * (1 - self.label_smoothing)
            - F.logsigmoid(-self.beta * logits) * self.label_smoothing
        )
    elif self.loss_type == "hinge":
        losses = torch.relu(1 - self.beta * logits)
    else:
        raise ValueError(f"Unknown loss type: {self.loss_type}")

    # Calculate implicit rewards for logging purposes.
    # Note the use of .detach() - rewards do not require gradients!
    chosen_rewards = self.beta * policy_chosen_logps.to(self.accelerator.device).detach()
    rejected_rewards = self.beta * policy_rejected_logps.to(self.accelerator.device).detach()
    
    return losses, chosen_rewards, rejected_rewards
```
*(Source code cross-referenced from Princeton NLP [cite: 13] and Hugging Face TRL [cite: 14])*

### 3.4 Key Breakdown of the Implementation


1.  **Inputs are pre-normalized:** `policy_chosen_logps` and `policy_rejected_logps` are 1D tensors of shape `(batch_size,)`. They already represent $\frac{1}{|y|} \sum \log \pi_\theta$.
2.  **Margin subtraction:** The term `gamma_logratios = self.gamma / self.beta` is subtracted from `pi_logratios`. When later multiplied by `self.beta` inside `F.logsigmoid`, the math works out to `beta * pi_logratios - gamma`, satisfying the paper's formula exactly [cite: 13].
3.  **`F.logsigmoid` utilization:** The code explicitly relies on `torch.nn.functional.logsigmoid` instead of manually computing `-torch.log(torch.sigmoid(...))` because the former provides superior numerical stability, avoiding underflow issues for extreme logit values [cite: 13, 14].
4.  **Label Smoothing Integration:** The parameter `label_smoothing` (default 0.0) mixes the standard objective with an inverted objective. When `label_smoothing = 0`, the second term disappears, leaving the pure SimPO loss.
5.  **Return Data Structure:** The method returns unreduced, per-example losses (shape `(batch_size,)`). The reduction (usually `.mean()`) happens later in the training loop [cite: 12, 13]. It also returns the detached rewards for tracking metrics [cite: 7, 13].
6.  **No Reference Model:** Nowhere in `simpo_loss` do we observe variables like `reference_chosen_logps`. This drastically cuts memory footprints [cite: 5, 8].

---

## 5. Critical Implementation Details and Common Pitfalls


Implementing SimPO from scratch or porting it requires vigilance. A minor algebraic error will critically break the alignment math.