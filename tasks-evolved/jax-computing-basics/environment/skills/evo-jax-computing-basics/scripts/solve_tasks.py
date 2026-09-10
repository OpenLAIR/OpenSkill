"""Main orchestration script for solving all JAX computation tasks.

Reads problem.json, loads input data, dispatches each task to the
appropriate JAX computation, and saves results.

Usage:
    python solve_tasks.py [path_to_problem.json]

Or import and call:
    from solve_tasks import solve_all_tasks
    solve_all_tasks('/app/problem.json')
"""
import os
import sys
import traceback

# Ensure this skill's scripts directory is on the path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from io_utils import load_problem_json, load_input_data, save_jax_array
from compute_utils import dispatch_task


def solve_all_tasks(problem_path: str = 'problem.json'):
    """Load problem.json, solve all tasks, and save results.

    For each task in problem.json:
    1. Load input data from the specified path
    2. Dispatch to the correct JAX computation based on task ID and description
    3. Save the result to the specified output path

    Handles relative paths by resolving them against the problem.json directory.

    Args:
        problem_path: Path to problem.json file
    """
    # Resolve base directory for relative paths
    problem_path = os.path.abspath(problem_path)
    base_dir = os.path.dirname(problem_path)

    tasks = load_problem_json(problem_path)
    print(f"Loaded {len(tasks)} tasks from {problem_path}")

    for i, task in enumerate(tasks):
        task_id = task.get('id', f'task_{i}')
        description = task.get('description', '')
        input_path = task.get('input', '')
        output_path = task.get('output', '')

        print(f"\n--- Task {i+1}/{len(tasks)}: {task_id} ---")
        print(f"  Description: {description}")
        print(f"  Input: {input_path}")
        print(f"  Output: {output_path}")

        try:
            # Resolve paths relative to problem.json location
            abs_input = input_path if os.path.isabs(input_path) else os.path.join(base_dir, input_path)
            abs_output = output_path if os.path.isabs(output_path) else os.path.join(base_dir, output_path)

            # Load input data
            data = load_input_data(abs_input)
            print(f"  Loaded input data from {abs_input}")

            # Dispatch and compute
            result = dispatch_task(task_id, description, data)
            print(f"  Computed result: shape={getattr(result, 'shape', 'N/A')}, dtype={getattr(result, 'dtype', 'N/A')}")

            # Save output
            save_jax_array(abs_output, result)
            print(f"  Saved result to {abs_output}")

        except Exception as e:
            print(f"  ERROR processing task '{task_id}': {e}")
            traceback.print_exc()
            # Continue with remaining tasks rather than failing entirely
            continue

    print(f"\nAll {len(tasks)} tasks processed.")


if __name__ == '__main__':
    # Allow passing problem.json path as command line argument
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        # Default: look in current directory, then /app/
        if os.path.exists('problem.json'):
            path = 'problem.json'
        elif os.path.exists('/app/problem.json'):
            path = '/app/problem.json'
        else:
            print("ERROR: problem.json not found. Provide path as argument.")
            sys.exit(1)

    solve_all_tasks(path)