"""
SimPO Loss Implementation Script

Implements the simpo_loss function in the SimPOTrainer class.
Based on the SimPO paper (Meng et al., 2024):

L_SimPO = -log(sigmoid(beta * avg_logp_chosen - beta * avg_logp_rejected - gamma))

Where:
- avg_logp = (1/|y|) * sum(log pi(y_t|x, y_{<t}))  [computed upstream]
- gamma = gamma_beta_ratio * beta  [target reward margin]
- beta scales the log-probability differences

The function receives already-averaged log probabilities and computes:
  pi_logratios = chosen_logps - rejected_logps
  logits = pi_logratios - gamma/beta
  losses = -F.logsigmoid(beta * logits)  [for sigmoid loss type]

This is algebraically equivalent to:
  losses = -F.logsigmoid(beta * (chosen - rejected) - gamma)
"""

import re
import os


def get_simpo_loss_code():
    """
    Returns the SimPO loss function body code.
    
    This code implements the exact SimPO loss from the paper:
    L = -log(sigma(beta * (avg_logp_w - avg_logp_l) - gamma))
    
    With label smoothing support:
    L = -(1-eps)*log(sigma(logits)) - eps*log(sigma(-logits))
    
    And hinge loss variant:
    L = max(0, 1 - beta * (avg_logp_w - avg_logp_l - gamma/beta))
    
    Key: policy_chosen_logps and policy_rejected_logps are ALREADY
    length-normalized (averaged) by get_batch_logps upstream.
    """
    return '''        # Compute difference in average log probabilities (already length-normalized upstream)
        pi_logratios = policy_chosen_logps - policy_rejected_logps

        # Compute gamma (target reward margin) from gamma_beta_ratio
        # gamma = gamma_beta_ratio * beta, so gamma/beta = gamma_beta_ratio
        # We factor out beta: logits = pi_logratios - gamma/beta
        # Then beta * logits = beta * pi_logratios - gamma (matches paper formula exactly)
        gamma_logratios = self.gamma_beta_ratio
        logits = pi_logratios - gamma_logratios

        if self.loss_type == "sigmoid":
            # SimPO sigmoid loss: -log(sigma(beta * logits))
            # With label smoothing: -(1-eps)*logsigmoid(beta*logits) - eps*logsigmoid(-beta*logits)
            losses = (
                -F.logsigmoid(self.beta * logits) * (1 - self.label_smoothing)
                - F.logsigmoid(-self.beta * logits) * self.label_smoothing
            )
        elif self.loss_type == "hinge":
            # Hinge loss variant: max(0, 1 - beta * logits)
            losses = torch.relu(1 - self.beta * logits)
        else:
            raise ValueError(f"Unknown loss type: {self.loss_type}. Expected 'sigmoid' or 'hinge'.")

        # Compute implicit rewards for logging (detached from computation graph)
        # Reward = beta * avg_log_prob (the SimPO reward formulation)
        chosen_rewards = self.beta * policy_chosen_logps.detach()
        rejected_rewards = self.beta * policy_rejected_logps.detach()

        return losses, chosen_rewards, rejected_rewards'''


def get_simpo_loss_code_alt():
    """
    Alternative implementation that computes gamma directly (not via gamma_beta_ratio).
    Used as fallback if the trainer uses self.gamma instead of self.gamma_beta_ratio.
    
    This version computes: logits = beta * pi_logratios - gamma
    directly without the factoring trick.
    """
    return '''        # Compute difference in average log probabilities (already length-normalized upstream)
        pi_logratios = policy_chosen_logps - policy_rejected_logps

        # Compute the logits for the sigmoid: beta * (chosen - rejected) - gamma
        # gamma is self.gamma_beta_ratio * self.beta (the target reward margin)
        gamma = self.gamma_beta_ratio * self.beta
        logits = self.beta * pi_logratios - gamma

        if self.loss_type == "sigmoid":
            # SimPO sigmoid loss with label smoothing support
            losses = (
                -F.logsigmoid(logits) * (1 - self.label_smoothing)
                - F.logsigmoid(-logits) * self.label_smoothing
            )
        elif self.loss_type == "hinge":
            # Hinge loss variant
            losses = torch.relu(1 - logits)
        else:
            raise ValueError(f"Unknown loss type: {self.loss_type}. Expected 'sigmoid' or 'hinge'.")

        # Compute implicit rewards for logging (detached from computation graph)
        chosen_rewards = self.beta * policy_chosen_logps.detach()
        rejected_rewards = self.beta * policy_rejected_logps.detach()

        return losses, chosen_rewards, rejected_rewards'''


def detect_trainer_style(content):
    """
    Detect which style of SimPO trainer we're dealing with by examining
    the class attributes and existing code patterns.
    
    Returns:
        'gamma_beta_ratio' if the trainer uses self.gamma_beta_ratio
        'gamma' if the trainer uses self.gamma directly
        'unknown' if we can't determine
    """
    if 'self.gamma_beta_ratio' in content:
        return 'gamma_beta_ratio'
    elif 'self.gamma' in content and 'gamma_beta_ratio' not in content:
        return 'gamma'
    return 'gamma_beta_ratio'  # default assumption


def implement_simpo_loss(filepath):
    """
    Patch the simpo_loss function in the given trainer file.
    
    This function reads the trainer file, identifies the simpo_loss method,
    and replaces its body with the correct SimPO loss implementation.
    
    Handles multiple file formats:
    1. Empty function with just 'return losses, chosen_rewards, rejected_rewards'
    2. Function with placeholder/pass statements
    3. Function with TODO comments
    
    Args:
        filepath: Path to the simpo_trainer.py file
    
    Returns:
        bool: True if patching was successful, False otherwise
    """
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()

    # Check if already implemented (has the core computation logic)
    if 'pi_logratios' in content and 'F.logsigmoid' in content:
        print("simpo_loss already appears to be implemented, skipping patch")
        return True

    # Detect trainer style
    style = detect_trainer_style(content)
    print(f"Detected trainer style: {style}")

    # Strategy 1: Replace the placeholder return statement
    # Look for the simpo_loss function and replace its body
    old_body = '        return losses, chosen_rewards, rejected_rewards'
    
    if style == 'gamma_beta_ratio':
        new_body = get_simpo_loss_code()
    else:
        new_body = get_simpo_loss_code_alt()

    if old_body in content:
        # Find the simpo_loss function to make sure we're replacing the right return
        # Check if there's meaningful code before the return in simpo_loss
        simpo_func_pattern = r'def simpo_loss\(self.*?\).*?:'
        match = re.search(simpo_func_pattern, content)
        
        if match:
            func_start = match.end()
            return_pos = content.find(old_body, func_start)
            
            if return_pos != -1:
                # Check what's between function def and return
                between = content[func_start:return_pos].strip()
                # Remove docstrings and comments
                between_clean = re.sub(r'""".*?"""', '', between, flags=re.DOTALL)
                between_clean = re.sub(r"'''.*?'''", '', between_clean, flags=re.DOTALL)
                between_clean = re.sub(r'#.*', '', between_clean)
                between_clean = between_clean.strip()
                
                if not between_clean or between_clean == 'pass':
                    # Empty function body - safe to replace
                    content = content[:return_pos] + new_body + content[return_pos + len(old_body):]
                    with open(filepath, 'w') as f:
                        f.write(content)
                    print("Patched simpo_loss successfully (replaced empty body)")
                    return True
                else:
                    print(f"WARNING: Found existing code in simpo_loss body: {between_clean[:100]}...")
                    # Still try to replace - the existing code might be incomplete
                    # Replace everything from after docstring to the return
                    content = content[:return_pos] + new_body + content[return_pos + len(old_body):]
                    with open(filepath, 'w') as f:
                        f.write(content)
                    print("Patched simpo_loss (replaced body with existing code)")
                    return True
        
        # Fallback: simple replacement of the return statement
        content_new = content.replace(old_body, new_body, 1)
        if content_new != content:
            with open(filepath, 'w') as f:
                f.write(content_new)
            print("Patched simpo_loss successfully (simple replacement)")
            return True

    # Strategy 2: Try regex-based replacement of the entire function body
    # Match from 'def simpo_loss' to the next method or end of class
    pattern = r'(def simpo_loss\(self[^)]*\)[^:]*:)(.*?)((?=\n    def |\nclass |\Z))'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        func_signature = match.group(1)
        # Preserve any docstring
        body = match.group(2)
        docstring_match = re.match(r'(\s*(?:""".*?"""|\'\'\'.*?\'\'\'))', body, re.DOTALL)
        docstring = docstring_match.group(1) if docstring_match else ''
        
        new_func = func_signature + docstring + '\n' + new_body + '\n'
        content = content[:match.start()] + new_func + content[match.end():]
        
        with open(filepath, 'w') as f:
            f.write(content)
        print("Patched simpo_loss successfully (regex replacement)")
        return True

    print("ERROR: Could not find simpo_loss function to patch")
    return False


if __name__ == '__main__':
    # Default path for the SimPO trainer
    trainer_path = '/root/SimPO/scripts/simpo_trainer.py'
    implement_simpo_loss(trainer_path)