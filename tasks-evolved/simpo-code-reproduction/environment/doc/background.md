# Comprehensive Analysis of the SimPO (Simple Preference Optimization) Loss Function: Mathematical Formulation and PyTorch Implementation

**Key Points:**
*   **SimPO (Simple Preference Optimization)** eliminates the need for a reference model during alignment training, substantially reducing memory and computational overhead compared to Direct Preference Optimization (DPO).
*   The method introduces a **length-normalized implicit reward** (average log probability) that directly aligns training objectives with inference-time generation metrics, effectively mitigating the verbosity bias common in standard RLHF approaches.
*   A **target reward margin ($\gamma$)** is embedded into the Bradley-Terry ranking objective, forcing a minimum separation between chosen and rejected responses to enhance generalization.
*   In reference PyTorch implementations, log probabilities must be **length-averaged before** being passed to the `simpo_loss` function, which then applies $\beta$ scaling, margin subtraction, and the `F.logsigmoid` reduction.
*   Hyperparameter tuning differs significantly from DPO: SimPO favors larger $\beta$ values (e.g., 2.0–10.0) and requires tuning the $\gamma/\beta$ ratio (often around 0.5).

**Overview of SimPO**
SimPO represents a significant paradigm shift in preference optimization. While traditional Reinforcement Learning from Human Feedback (RLHF) and DPO rely on complex pipelines involving reward models or static reference models, SimPO simplifies the process by extracting the reward directly from the policy model's own generation probabilities. It appears likely that the removal of the reference model not only democratizes alignment training by lowering hardware requirements but also improves stability. 

**Mathematical Innovations**
The theoretical foundation of SimPO hinges on replacing the summed log-probability ratio of DPO with an averaged log-probability. Research suggests that this length-normalization acts as an intrinsic penalty against long-winded outputs, a well-documented artifact of DPO. By incorporating a margin parameter ($\gamma$), the algorithm dynamically scales the penalty landscape, enforcing robust decision boundaries between high-quality and low-quality data. 

**Implementation Dynamics**
Integrating SimPO into existing frameworks like Hugging Face's TRL (Transformer Reinforcement Learning) requires careful attention to mathematical order-of-operations. The evidence leans toward calculating the per-token mean log-probabilities prior to loss computation. Developers transitioning from DPO must actively unlearn the standard summation approach to avoid critical degradation in model performance.

---

## 1. Introduction to Preference Optimization and the Genesis of SimPO

Learning from human feedback is an indispensable phase in aligning Large Language Models (LLMs) with human values, ensuring they are helpful, honest, and harmless [cite: 1]. The standard approach, Reinforcement Learning from Human Feedback (RLHF), utilizes a multi-stage procedure involving Supervised Fine-Tuning (SFT), training a distinct reward model, and optimizing a policy model using Proximal Policy Optimization (PPO) [cite: 1, 2]. 

Direct Preference Optimization (DPO) revolutionized this space by mathematically demonstrating that the language model itself can implicitly act as the reward model, effectively bypassing the need for a distinct reward model and the unstable PPO optimization loop [cite: 3, 4]. DPO optimizes a policy model $\pi_\theta$ against a frozen reference model $\pi_{\text{ref}}$ using a binary cross-entropy loss over preference pairs $(x, y_w, y_l)$, where $y_w$ is the winning (chosen) response and $y_l$ is the losing (rejected) response.

However, standard DPO suffers from two fundamental limitations:
1.  **Reference Model Overhead:** DPO requires maintaining a frozen copy of the reference model in GPU memory to compute KL-divergence penalties. This doubles the memory requirements during the forward pass [cite: 5].
2.  **Length Exploitation (Verbosity Bias):** DPO models implicitly favor longer responses because standard log-probability sums naturally aggregate to higher absolute deviations for longer sequences, leading to models that game the reward by generating verbose but hollow text [cite: 1, 6].

**Simple Preference Optimization (SimPO)**, introduced by Yu Meng, Mengzhou Xia, and Danqi Chen (2024), addresses these issues by proposing a reference-free, length-normalized objective [cite: 3, 4]. The effectiveness of SimPO is attributed to two key designs: using the average log probability of a sequence as the implicit reward and incorporating a target reward margin into the Bradley-Terry objective [cite: 4, 7].

---

## 2. Mathematical Formulation of SimPO

To rigorously understand SimPO, we must contrast its mathematical formulation directly with DPO. 

### 2.1 The DPO Objective

In DPO, the implicit reward $r(x,y)$ is defined as the scaled log-ratio between the policy model and the reference model:
\[ r_{\text{DPO}}(x,y) = \beta \log \frac{\pi_\theta(y|x)}{\pi_{\text{ref}}(y|x)} \]
Where $\beta$ is a scaling hyperparameter controlling the strength of the KL-divergence penalty. 
The loss function minimizes the negative log-sigmoid of the reward difference:
\[ \mathcal{L}_{\text{DPO}} = -\mathbb{E}_{(x, y_w, y_l) \sim D} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi_{\text{ref}}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi_{\text{ref}}(y_l|x)} \right) \right] \]

### 2.2 The SimPO Reward Formulation

SimPO asserts that the reward formulation should align with the actual metric used during generation (inference). At inference, models use length-normalized log probabilities to select the best sequence. Therefore, SimPO defines the reward directly as the **length-normalized log probability of the policy model** [cite: 8, 9]:

\[ r_{\text{SimPO}}(x, y) = \frac{\beta}{|y|} \log \pi_\theta(y|x) \]

Here:
*   $\pi_\theta(y|x)$ is the sequence probability.
*   $|y|$ is the number of tokens in the response.
*   $\log \pi_\theta(y|x)$ is mathematically equivalent to the sum of log probabilities of individual tokens: $\sum_{t=1}^{|y|} \log \pi_\theta(y_t | x, y_{<t})$.
*   Dividing by $|y|$ computes the **average log probability per token**.

This formulation eliminates the reference model entirely. As proven in recent theoretical analyses, SimPO can be interpreted as a special case of DPO where the reference model $\pi_{\text{ref}}$ is substituted with a uniform distribution $U$ over the vocabulary [cite: 10, 11]. 

### 2.3 The Target Reward Margin ($\gamma$)

Because SimPO removes the KL-divergence anchor (the reference model), the absolute scale of the probabilities might drift. To prevent the model from assigning trivially similar probabilities to both $y_w$ and $y_l$, SimPO introduces a **target reward margin**, denoted as $\gamma$ [cite: 4, 9].

The margin ensures that the reward for the winning response must exceed the reward for the losing response by at least $\gamma$ to minimize the loss effectively. This modifies the Bradley-Terry ranking objective to push the winning and losing representations further apart [cite: 4, 7].

### 2.4 The Exact SimPO Loss Formula

Combining the length-normalized reward and the margin, the exact mathematical formulation for the SimPO loss over a dataset $D$ is:

\[ \mathcal{L}_{\text{SimPO}}(\pi_\theta) = -\mathbb{E}_{(x,y_w,y_l)\sim D} \left[ \log \sigma \left( \frac{\beta}{|y_w|} \log \pi_\theta(y_w|x) - \frac{\beta}{|y_l|} \log \pi_\theta(y_l|x) - \gamma \right) \right] \]
*(Citation: Meng et al., 2024; also confirmed in [cite: 9, 10, 11])*

Expanding the sequence log probability to its per-token summation formulation, we obtain the expression requested in the query:
\[ L_{\text{SimPO}} = -\log\left(\text{sigmoid}\left(\frac{\beta}{|y_w|} \sum_{i} \log \pi_\theta(y_{w,i}|x) - \frac{\beta}{|y_l|} \sum_{j} \log \pi_\theta(y_{l,j}|x) - \gamma \right)\right) \]

---

## 3. Hugging Face TRL and GitHub Reference Implementations

The integration of SimPO into real-world pipelines requires mapping the continuous mathematical formulas into discrete tensor operations. We will analyze the official implementation from the `princeton-nlp/SimPO` GitHub repository [cite: 12, 13] and the Hugging Face `trl` library [cite: 14].

### 3.1 Data Preparation: Length Normalization in `get_batch_logps`

A critical implementation detail in SimPO is that the length normalization (averaging the log probabilities) happens **before** the arrays are passed to the actual `simpo_loss` function [cite: 12, 15]. 

In the official `simpo_trainer.py`, this is managed by a function `get_batch_logps` which takes an argument `average_log_prob=True` [cite: 12].

```python
import torch
import torch.nn.functional as F

def get_batch_logps(
    logits: torch.FloatTensor,
    labels: torch.LongTensor,
    average_log_prob: bool = True,
    label_pad_token_id: int = -100,
) -> torch.FloatTensor:
    """
    Compute the log probabilities of the given labels under the given logits.
    """
    # Shift logits and labels for autoregressive training
    shift_logits = logits[..., :-1, :].contiguous()
    shift_labels = labels[..., 1:].contiguous()
    
    # Create a mask to ignore padding tokens
    loss_mask = (shift_labels != label_pad_token_id)
    
    # Compute per-token log probabilities
    per_token_log_probs = F.log_softmax(shift_logits, dim=-1)
    
    # Gather the log probabilities of the actual target labels
    selected_log_probs = per_token_log_probs.gather(
        dim=-1, index=shift_labels.unsqueeze(-1)
    ).squeeze(-1)
    
    # Mask out padding tokens
    selected_log_probs = selected_log_probs * loss_mask
    
    # Sum the log probabilities for each sequence in the batch
    sum_log_probs = selected_log_probs.sum(dim=-1)
    
    if average_log_prob:
        # SIMPO SPECIFIC: Length Normalization
        # Calculate the actual sequence lengths (number of non-padding tokens)
        lengths = loss_mask.sum(dim=-1).float()
        # Return the mean log probability per sequence
        return sum_log_probs / lengths
    else:
        # DPO standard behavior
        return sum_log_probs
```
*(Based on the official Princeton NLP implementation [cite: 12, 15])*

### 3.2 The `concatenated_forward` Method

Trainers extending `DPOTrainer` or `CPOTrainer` often use a `concatenated_forward` method to perform a single forward pass containing both the chosen and rejected responses (for FSDP efficiency) [cite: 2, 16].

```python
def concatenated_forward(
    self, model: torch.nn.Module, batch: dict
) -> tuple:
    # Perform forward pass
    all_logits = model(**batch, return_dict=True, use_cache=False).logits.to(torch.float32)
    
    # Extract averaged log probabilities
    all_logps = self.get_batch_logps(
        logits=all_logits, 
        labels=batch["labels"], 
        average_log_prob=True, # Critical for SimPO!
        label_pad_token_id=self.label_pad_token_id
    )
    
    # Split back into chosen and rejected
    batch_size = batch["input_ids"].size(0) // 2
    chosen_logps = all_logps[:batch_size]
    rejected_logps = all_logps[batch_size:]
    
    return chosen_logps, rejected_logps
```
*(Reference: Hugging Face TRL codebase [cite: 14, 17])*

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

## 4. Hugging Face TRL Class Structure and Configuration

In the Hugging Face `trl` library ecosystem, SimPO is not isolated as a standalone trainer but is primarily implemented as a `loss_type` strategy inside the `CPOTrainer` (Contrastive Preference Optimization) and the `DPOTrainer` [cite: 2, 7].

### 4.1 `CPOConfig` and `DPOConfig` 

To utilize SimPO in TRL, you configure `loss_type="simpo"` within the configuration object [cite: 2, 7].

```python
from trl import CPOConfig, CPOTrainer

training_args = CPOConfig(
    output_dir="./simpo_results",
    loss_type="simpo",
    cpo_alpha=0.0,            # Must be 0 to disable CPO's BC regularizer
    beta=2.0,                 # SimPO beta scaling factor
    simpo_gamma=1.0,          # SimPO target reward margin
    label_smoothing=0.0,
    max_length=1024
)
```

**Understanding the Hyperparameters:**
*   **`beta`**: In standard DPO, `beta` is typically small (e.g., 0.1) acting as a KL-penalty coefficient [cite: 18]. However, in SimPO, `beta` acts as a global scaling factor for the likelihoods. The SimPO paper specifies that **SimPO requires a much larger beta than DPO** [cite: 19]. The recommended starting values are **$\beta \in [2.0, 10.0]$**, with 2.0 or 2.5 used in the base paper models [cite: 15, 19, 20]. Note: TRL's default for `beta` remains `0.1` due to legacy DPO settings, so it **must be explicitly overridden** [cite: 21].
*   **`simpo_gamma`** (or `gamma`): This is the target reward margin. The paper suggests tuning the ratio of $\gamma / \beta$ to be approximately 0.5. Thus, if $\beta = 2.0$, $\gamma = 1.0$ is an optimal starting point [cite: 15, 19]. TRL's default `simpo_gamma` is 0.5 [cite: 2].
*   **`cpo_alpha`**: When using TRL's `CPOTrainer`, you must set `cpo_alpha = 0.0`. CPO includes a Behavioral Cloning (BC) regularizer by default; setting alpha to 0 disables it, resulting in the pure SimPO objective [cite: 7, 21].
*   **`label_smoothing`**: TRL supports label smoothing (default 0.0). If configured $> 0$, it penalizes overconfidence by blending the targeted loss with the inverse loss [cite: 2, 21].

### 4.2 The `CPOTrainer` Execution Flow

The `CPOTrainer` inherits from the standard Hugging Face `Trainer`. When `loss_type="simpo"` is triggered:
1.  **Forward Pass**: The trainer passes concatenated batches to the policy model.
2.  **Log Probability Extraction**: `get_batch_logps` is called. For SimPO, it internally computes the length-normalized mean (`average_log_prob=True`) [cite: 14].
3.  **Loss Calculation**: The execution routes to the `simpo_loss` method, which ingests the `policy_chosen_logps` and `policy_rejected_logps` and outputs the loss [cite: 14].
4.  **Metric Logging**: The detached rewards returned by `simpo_loss` are aggregated into metrics: `rewards/chosen`, `rewards/rejected`, `rewards/accuracies`, and `rewards/margins` [cite: 7, 22].

---

## 5. Critical Implementation Details and Common Pitfalls

Implementing SimPO from scratch or porting it requires vigilance. A minor algebraic error will critically break the alignment math.

### 5.1 Pitfall 1: Sum vs. Mean Log Probabilities (The Cardinal Rule)
The **most critical difference** between DPO and SimPO is the normalization of log probabilities [cite: 7]. 
*   **DPO** relies on the **sum** of the log probabilities: $\sum \log \pi_\theta(y_t|x)$.
*   **SimPO** relies on the **mean** of the log probabilities: $\frac{1}{|y|} \sum \log \pi_\theta(y_t|x)$.

**The Pitfall:** If you write a custom trainer and pass the raw sum of log probabilities directly to `simpo_loss`, you are effectively training DPO without a reference model. This causes massive instability because longer sequences will generate astronomically large (negative) log sums, violently shifting the logits out of the dynamic range of the sigmoid function [cite: 13]. 
*Correction:* You must explicitly compute `lengths = loss_mask.sum(dim=-1).float()` and perform `sum_log_probs / lengths` before feeding the tensors to the loss function [cite: 15].

### 5.2 Pitfall 2: The Margin ($\gamma$) Subtraction Logic
In the code `logits = pi_logratios - gamma_logratios`, recall that `gamma_logratios = gamma / beta` [cite: 13]. 
**The Pitfall:** A common mistake is subtracting $\gamma$ directly from the log probability difference before applying $\beta$: `beta * (pi_logratios - gamma)`.
*Correction:* The mathematical formula is $\beta(\text{ratio}) - \gamma$. If factoring $\beta$ out, it becomes $\beta(\text{ratio} - \gamma/\beta)$. Failing to divide by $\beta$ during the logit preparation will result in a margin that is effectively multiplied by $\beta$ twice.

### 5.3 Pitfall 3: Detaching Rewards for Logging
The `simpo_loss` function returns `chosen_rewards` and `rejected_rewards` [cite: 13].
**The Pitfall:** If you compute `chosen_rewards = self.beta * policy_chosen_logps` without calling `.detach()`, the computation graph remains attached. When the trainer aggregates these scalars for logging, it can cause severe memory leaks (OOM errors) as the GPU holds onto the gradient graphs of every forward pass [cite: 13, 17].
*Correction:* Always append `.detach()` or `.to(device).detach()` when extracting reward metrics for purely observational logging [cite: 13].

### 5.4 Pitfall 4: Tensor Dimensionality and Reduction
The `simpo_loss` function outputs a vector of losses of shape `(batch_size,)` [cite: 12, 13].
**The Pitfall:** Using `.mean()` inside the `simpo_loss` function. 
*Correction:* Hugging Face Trainers expect per-example losses in some internal routing scenarios (like tracking per-sample metrics). The reduction `loss = losses.mean()` should happen in the parent `compute_loss` method of the trainer, not inside the mathematical `simpo_loss` primitive itself [cite: 12].

### 5.5 Pitfall 5: Sign Errors in the Log-Sigmoid
The loss minimizes the negative log-sigmoid. 
**The Pitfall:** Writing `F.logsigmoid(-self.beta * logits)`.
*Correction:* The objective is to maximize the margin by which the chosen response beats the rejected response. Therefore, we want the `logits` (which is `chosen - rejected`) to be positive and large. To maximize the sigmoid of this positive value, we minimize its negative log: `-F.logsigmoid(self.beta * logits)` [cite: 13]. The only time a negative sign is inside the sigmoid is during the inverted label-smoothing branch.

---

## 6. Saving PyTorch Tensor Results to NumPy (.npz)

During research and debugging of SimPO, it is often necessary to export the intermediate tensors (losses, log-probabilities, and rewards) to disk for statistical analysis. PyTorch tensors tracked by the autograd engine cannot be directly saved to NumPy without proper offboarding.

To save the results of `simpo_loss` to an `.npz` file, you must systematically detach the tensors from the computational graph, move them from GPU to system memory (CPU), and convert them to NumPy arrays.

```python
import torch
import numpy as np

# Assuming you just ran a batch through simpo_loss
losses, chosen_rewards, rejected_rewards = trainer.simpo_loss(
    policy_chosen_logps, 
    policy_rejected_logps
)

# 1. Detach from the autograd graph (losses requires this, rewards are already detached)
# 2. Move to CPU (numpy cannot read GPU memory)
# 3. Convert to numpy array
losses_np = losses.detach().cpu().numpy()

# Rewards are already detached in the simpo_loss implementation, 
# but calling detach() again is safe and standard practice.
chosen_rewards_np = chosen_rewards.cpu().numpy()
rejected_rewards_np = rejected_rewards.cpu().numpy()

# Save to an uncompressed .npz dictionary format
np.savez(
    "simpo_batch_results.npz",
    losses=losses_np,
    chosen_rewards=chosen_rewards_np,
    rejected_rewards=rejected_rewards_np
)

# To load later:
# data = np.load("simpo_batch_results.npz")
# print(data['losses'])
```

This serialization preserves the exact floating-point arrays, permitting downstream analysis on margin distributions and length-normalization impacts without keeping the heavy PyTorch framework engaged.

---

## 7. Conclusion

Simple Preference Optimization (SimPO) effectively streamlines alignment tuning by removing the dependence on a frozen reference model. Through the elegant utilization of the length-normalized average log-probability per token, it intrinsically combats the verbosity biases that plague classical DPO [cite: 1, 4, 6]. The addition of the target margin $\gamma$ ensures strict discriminative capability is maintained even as the absolute probabilities drift [cite: 9].

For engineers and researchers adopting SimPO, careful attention must be paid to the PyTorch implementation [cite: 13]. The transition from DPO entails altering the log-probability extraction to a mean-reduction schema (`average_log_prob=True`), fundamentally re-tuning hyperparameters (large $\beta \approx 2.5$, $\gamma \approx 1.0$), and ensuring computational stability through functions like `F.logsigmoid` [cite: 15, 19]. When correctly executed, SimPO offers an alignment methodology that is concurrently more memory-efficient and structurally robust.

**Sources:**
1. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMwJ4hB1ntQ7wi9P7e-J_Iuc_OjD0pAoJ4REdcxfRBpM0Oo18Z5qu4UQOI9ai297jtzkjIZsXf9LysN_s5q-ue7ZXIKt7Y0FBflbeI3p8q2D_4QKwbE3KxIw==)
2. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGr7MxqEdNDwjOZEmRJlPdG5rk_wXW8kNOuqZwPSuLN-sac3Tdfxcb_yYgpB95nCvZybPCmpmkArnBmmpSmThek_zqRW5ecB-VFxosQ9b-kTKugGRL9MrK2qY2FevQmUAaSpA==)
3. [semanticscholar.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFgHW0KPja1eYDELAfbPL_3ouPKGQdUO1__gZwclJrKXFI20HciDRmtRx4R53sJ0D5Jdf_nsQJQ4sg1_aOIC-jgBACxtRq-OGiUTeGtNWx8kvwGAHZQbnF6LbYx1BvahI3pdz-JJRVUNwuNQIy4UWXXP58ceFvNjeIg-r21lK_i-ZoxoNJBWPSuD9YJhshl41SdpXJMxNw_vbsaWx6ccfqZDR29kA9eI2KKywF8ATjnjEL3jc0t_x16QIpyyggLXaNUEOny)
4. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG06IS-_m6v_gxTCXy45NekMHs6aQzrWsDfIeDsodYrNdYYVwIok3FFnrSMO59PQL7pxhdKmerl1qJ3LzOHoV49mM3_el4Ef0GxU6pEYF9Sv8LX7EAFp6u0pMHZik0E)
5. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXp48L3hI9aTjfqcS4t4C-lhuYMm78bcmlxrLNgAZEFdHDer9Db8zNKCMl81SVe3kReZeTImcQ0_0G1T__xcvTMWR02LV_pLlob3F5HC9jFt5pqFcbINlH6XgIHa9KF4HwHmP4Om2j6ZGwany7d3YiduEe-00X7h7748Hho6HB7E6u1hnhl2-t5MT0iUnNCIFRBjzsWK8LDZ2WsZHJ8ok=)
6. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjTmFy2z9XrJHB2gwlhs-SARjNunsB8IXFKgQ2fzefo2EMUl4lHIcm5i_XXL4q50rCuaa6nAgMahkm2k8UE6f8SR5Wq-DUGHloMMMx14aSko7QrtpyAuoa2beUmV-OcJU-)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFDQSesjnTm0EAw-55QG2QlmYgnYpP5YUQX6WQb5Q-LfTJHrSVJjblxIaEXmILob0T6NqIbWY3vpEMEdZ_MRuznWjhJKY1MgoXgYCdLXj8yIsWZZtCIzAzdduQ5gHVJcmFUt7Ouqtrw81k_CBJixNWMq5tVzrZkJUBKMw9jA==)
8. [emergentmind.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgczNxR5ZQGA5iYZPXVYKsYONorILfmIA8JBy_CXBGHmMJLMCoQxLpRoL4kYt-GRGTOJt8vbVPZgokDwXtqmQsBZXhsZIY6DKpG2TU9VGEsZ5E-02DUelKgiJOoyDN0h86CyQwrjAjh3zi5N3Y4m49eRkBw4hRzg9qs73-tbk=)
9. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMl7KLaPNMP0RSv125E83b4nk26u8_DJHaA7YEDLrgtjQJtTNX3tOz9SGNjz-RVoJju1580YJE7jqIX44-E0hPPeVTJjnJiBAqLa8pyjWjTsBTXkeDintuGg==)
10. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGWwRKLnZ7bKqSJXePcjTMm6Rr8d8tnJ6Ytl5D_9G_FekPoji_ddxkTOyxZtveVv4yP2ae-Q2T1YQb6Hv5iNt2utFV5hWa-8DWCA3cDtKdLrABPhYlFhtBpQQ==)
11. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9tiO1kA16mvXiYRJjnrqzGP088v2t5VcSO5KyuURrbLHeazaSvczb7_WyhUyl7BlECUXOC-eh4e34BiiuT32HCY9n5577QVAOapzLBvbYWfTv-Dp_vCynPQ==)
12. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTL_O_6Z_iXiod59HtEbFstR6et_jORU7nX1hOFfH_55wLGbYpQmPFuhVo0ulqqhxCQVCj8SXqVegQpgLeonXoC5_kqWnHfJvdFSn47kxwbS7-b-QZAks9DgfbAxAR2Azx-oXRGfeEP5kCK417VBKJsbQys1eI_LyKB_HOHv-x)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOpuUpeGO5p1zY6EvSPdSC-FdW6kkjA7h-GeWIgYeQHsZFiqtcG4LFNCQSj9Me776dNkTE5_wn65yztKtVgodFe_o1pT4Gn2a9Snuqdb1zRN3vaPkxkWTdVTKdDDYsInEX4vN_Ng==)
14. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEu8CwzXFVeosFhbVtWzNTiwX9BLhr4TwxqI1jBCkVrSDjqw4z2YE-mrM-t0bH7vZ1DyJ9XDGSuDZ38069PABjwOHUAqyzpx2iocKDD2aOZwLgpvtqkc5HrHD6KDkehdVWHY-H8CUZ0K9I4-sCOLJUaRNUaGoelK6qDBiGQtWjsNR287X82JDNtESx9pcyk)
15. [csdn.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG41IzCU5PgV2nULx2BZYozWa9en2x21m79QlWby2JJfVOk5VHuoI7tGkJEJFwUm4S1XHpO7eBCBS1gvhcaYFUXfaZWovoR_bUi4HRVcgaH1cLFwfPbO_yI28hLgfRa9LkacxFe9sQ5XZgPUbPESiQ=)
16. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHDRnjqA5dA8qW0qedRdT5kHltOyiucOvSjX8Mu3V5ULj9Tx2hPcZhxxnVePrO4ZUvqdPdy6Kookqjiex-G8ujggvLgRO6Sykb6jeGRAA5xhjQskwElDLMMUoFBlrgv6vqdxxK2LA==)
17. [csdn.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQW-MytNLmbE6L4lNuGORxtllMHP_v9tbynpnDmSVS6sXUMI5Jgd5pcx6F-zkdAsZxA1lQ8UdJr2yxf0Co2R4T1SggV5LjcV-S01cfijMACtpi6Ee4yBC3El7mvXEP73bg0l0V1g0LPyusVSI3sLciJw==)
18. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE37cRfBh_e_lF9KPvaT7NXQYhE-j1vJjNHqLzYydL6MW45u2eUVIZWeWC2RbPZdYAMU1CZbNlK8WB6LeKnT5xL65OoRIHnNrhF2QDdQToTm2BO1VaIPPoDgQ15odIAfEO8g1RRHfrY9vPiyTzPWkAI)
19. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHIKaeWn4Yt6BSTCRD543ohyM9G6T3pWzYYuTpTrIGYOdQlELJf07Q8DgBa82ZiN4865HWNzMtRrxZ6fHLiy9BnNXpure6VSpeWzzQ0t-or5SJKdJTjKiL9-DwAjA==)
20. [substack.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXX6AT3YTP8biacY4aDxCg4mZa0Ekb2NaRmd1iGe5Bf8d5ziVLGg_7ZzpJ397vECmDEjCuS1aR5mlDO565yfxGxVBTqPaacr_9V0il7z34Em7Jj2q15tjC0MaHh_AKxXbeNTSXDB_e2Rmvrv596Itm7kDCx0Y6)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaztSkGx9domP6NoPnXt9mvf_tc8ll5I5dC28XxgOXOZekwvq-YS0hPXsoAV9yJIjw7OPyaTy_w1JBHILKtdmzwvTDI_rvHZrvwit8TdaVAtaqOedalp_6jX_OlAHBMGJ2j6KUpelk_QNrZPeO9sEBhKkRC7aLZr8jT2Wha6jqeq42hFi-)
22. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQrJizL6YN_Q1MDdSemI5oiANnOI_UWsaoI42V4HuG2CH23EQi7i2RXrNwngcB6sCGt0N_kieElk2ls77fQAsjg9btYxqO5UVglscmWAGDXoszWtL-TeYGBNO9D2XnqFUV)
