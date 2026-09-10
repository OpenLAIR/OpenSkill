import subprocess
import os

def read_lean_template(filepath, num_prefix_lines=14):
    """Read a Lean template file and return the prefix (first num_prefix_lines lines)."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    prefix = ''.join(lines[:num_prefix_lines])
    return prefix

def generate_proof_body():
    """Generate the Lean 4 proof body for S n <= 2.
    
    Strategy: Prove closed form S m = 2 - 1/2^m by induction, then derive inequality.
    
    Key techniques:
    - Use `suffices` to introduce the stronger closed-form statement
    - Use standard `induction m with` (NOT simple_induction which causes push_cast issues)
    - Base case: `show (1:Q) = 2 - 1/2^0` then `norm_num`
    - Inductive step: `show S k + 1/2^(k+1) = 2 - 1/2^(k+1)` then:
      1. rw [IH] to substitute closed form for S k
      2. Rewrite 2^(k+1) = 2 * 2^k using `ring`
      3. Prove 1/2^k = 2/(2*2^k) using `div_eq_div_iff` + `ring`
      4. `rw [hkey]` to substitute, then `ring` closes the goal
    - Final: positivity for 0 <= 1/2^n, linarith to conclude
    
    Returns the proof body as a string (to be appended after line 14).
    """
    proof = """  suffices h : \u2200 m : \u2115, S m = 2 - 1 / 2 ^ m by
    have := h n
    have hpos : (0:\u211a) \u2264 1 / 2 ^ n := by positivity
    linarith
  intro m
  induction m with
  | zero =>
    show (1:\u211a) = 2 - 1 / 2 ^ 0
    norm_num
  | succ k IH =>
    show S k + 1 / 2 ^ (k + 1) = 2 - 1 / 2 ^ (k + 1)
    rw [IH]
    have h2k : (0:\u211a) < 2 ^ k := by positivity
    rw [show (2:\u211a) ^ (k + 1) = 2 * 2 ^ k from by ring]
    have hne : (2:\u211a) * 2 ^ k \u2260 0 := ne_of_gt (by linarith)
    have hkey : (1:\u211a) / (2 ^ k) = 2 / (2 * 2 ^ k) := by
      rw [div_eq_div_iff (ne_of_gt h2k) hne]
      ring
    rw [hkey]
    ring
"""
    return proof

def write_proof_to_file(filepath, prefix, proof_body):
    """Write the complete solution file with the given prefix and proof body."""
    content = prefix + proof_body
    with open(filepath, 'w') as f:
        f.write(content)
    return content

def validate_lean_build(workspace_dir, timeout=300):
    """Validate that the Lean file type-checks by running lake env lean.
    
    Returns (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            ['lake', 'env', 'lean', 'solution.lean'],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        # Check for warnings (treat as errors per task constraint)
        has_warnings = 'warning' in output.lower()
        has_errors = 'error' in output.lower()
        return (success and not has_warnings and not has_errors), output
    except subprocess.TimeoutExpired:
        return False, "Build timed out"
    except Exception as e:
        return False, str(e)
