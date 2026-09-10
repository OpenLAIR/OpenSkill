"""
Environment Setup, Unit Test Execution, and Result Saving Script

Handles:
1. Installing required Python packages for SimPO
2. Running the unit test to generate loss values
3. Saving results to /root/loss.npz
4. Logging Python version and package info
"""

import os
import subprocess
import sys


def setup_environment():
    """
    Install required packages for the SimPO project.
    
    Key dependencies:
    - torch: PyTorch for tensor operations and autograd
    - transformers: Hugging Face transformers for model loading
    - trl==0.8.6: Specific version needed (>=0.29 removed CPOTrainer)
    - accelerate: For distributed training utilities
    - datasets: For data loading
    - peft: For parameter-efficient fine-tuning
    - numpy: For saving results to npz format
    """
    packages = [
        'torch',
        'transformers',
        'trl==0.8.6',
        'datasets',
        'accelerate',
        'peft',
        'numpy',
    ]
    
    pip_cmd = [sys.executable, '-m', 'pip', 'install', '--break-system-packages'] + packages
    
    print(f"Installing packages: {' '.join(packages)}")
    result = subprocess.run(pip_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"WARNING: pip install returned non-zero exit code: {result.returncode}")
        print(f"stderr: {result.stderr[-500:]}")
        # Try without --break-system-packages (older pip versions)
        pip_cmd_alt = [sys.executable, '-m', 'pip', 'install'] + packages
        result2 = subprocess.run(pip_cmd_alt, capture_output=True, text=True)
        if result2.returncode != 0:
            print(f"ERROR: Package installation failed")
            print(f"stderr: {result2.stderr[-500:]}")
            return False
    
    print("Package installation completed")
    return True


def log_python_info(output_path='/root/python_info.txt'):
    """
    Log Python version and installed packages to a file.
    
    Args:
        output_path: Path to write the info file
    """
    try:
        # Get Python version (detailed)
        version_result = subprocess.run(
            [sys.executable, '-VV'],
            capture_output=True, text=True
        )
        
        # Get installed packages
        freeze_result = subprocess.run(
            [sys.executable, '-m', 'pip', 'freeze'],
            capture_output=True, text=True
        )
        
        with open(output_path, 'w') as f:
            f.write("=== Python Version ===\n")
            f.write(version_result.stdout or '')
            f.write(version_result.stderr or '')  # Python -VV outputs to stderr
            f.write("\n\n=== Installed Packages ===\n")
            f.write(freeze_result.stdout or '')
        
        print(f"Python info logged to {output_path}")
        return True
    except Exception as e:
        print(f"ERROR logging python info: {e}")
        return False


def run_unit_test(test_path='/root/SimPO/unit_test/unit_test_1.py', 
                  output_path='/root/loss.npz'):
    """
    Run the unit test script to generate loss values.
    
    The unit test creates fixed input tensors, passes them through simpo_loss,
    and saves the results. We run it as a subprocess to ensure clean imports.
    
    Args:
        test_path: Path to the unit test script
        output_path: Expected path where loss.npz will be saved
    
    Returns:
        bool: True if test ran successfully
    """
    if not os.path.exists(test_path):
        print(f"ERROR: Unit test not found at {test_path}")
        return False
    
    print(f"Running unit test: {test_path}")
    result = subprocess.run(
        [sys.executable, test_path],
        capture_output=True, text=True,
        cwd=os.path.dirname(test_path)
    )
    
    print(f"STDOUT: {result.stdout}")
    if result.stderr:
        print(f"STDERR: {result.stderr[-1000:]}")
    
    if result.returncode != 0:
        print(f"ERROR: Unit test failed with return code {result.returncode}")
        return False
    
    # Verify output file exists
    if os.path.exists(output_path):
        print(f"Loss file saved successfully at {output_path}")
        # Verify the file contents
        try:
            import numpy as np
            data = np.load(output_path)
            if 'losses' in data:
                print(f"Verified: 'losses' key found, shape={data['losses'].shape}, values={data['losses']}")
            else:
                print(f"WARNING: 'losses' key not found. Available keys: {list(data.keys())}")
        except Exception as e:
            print(f"WARNING: Could not verify npz file: {e}")
        return True
    else:
        print(f"WARNING: Expected output file {output_path} not found after test execution")
        return False


def save_loss_to_npz(losses_tensor, output_path='/root/loss.npz'):
    """
    Utility to save a PyTorch loss tensor to npz format.
    
    Handles:
    - Detaching from computation graph
    - Moving from GPU to CPU
    - Converting to numpy
    - Saving with correct key name
    
    Args:
        losses_tensor: PyTorch tensor of losses
        output_path: Path to save the npz file
    """
    import numpy as np
    
    # Ensure tensor is detached and on CPU
    if hasattr(losses_tensor, 'detach'):
        losses_np = losses_tensor.detach().cpu().numpy()
    elif hasattr(losses_tensor, 'cpu'):
        losses_np = losses_tensor.cpu().numpy()
    else:
        losses_np = np.array(losses_tensor)
    
    np.savez(output_path, losses=losses_np)
    print(f"Saved losses to {output_path}, shape={losses_np.shape}")


if __name__ == '__main__':
    # Full pipeline execution
    print("=" * 60)
    print("SimPO Code Reproduction Pipeline")
    print("=" * 60)
    
    # Step 1: Setup environment
    print("\n[Step 1] Setting up environment...")
    setup_environment()
    
    # Step 2: Implement simpo_loss
    print("\n[Step 2] Implementing simpo_loss...")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from simpo_loss_impl import implement_simpo_loss
    implement_simpo_loss('/root/SimPO/scripts/simpo_trainer.py')
    
    # Step 3: Run unit test
    print("\n[Step 3] Running unit test...")
    run_unit_test()
    
    # Step 4: Log python info
    print("\n[Step 4] Logging Python info...")
    log_python_info()
    
    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)