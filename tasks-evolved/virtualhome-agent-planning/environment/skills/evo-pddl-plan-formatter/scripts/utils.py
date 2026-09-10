import json
import os
import sys
import importlib.util


def _get_solver():
    """Import solve_pddl_task from the solver skill using importlib to avoid naming conflicts."""
    solver_file = '/app/environment/skills/evo-pddl-solver/scripts/utils.py'
    spec = importlib.util.spec_from_file_location('solver_utils', solver_file)
    solver_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solver_module)
    return solver_module.solve_pddl_task


def run_all_tasks(problem_json_path, base_dir=None):
    """
    Read problem.json, solve each task, format and write plans.
    """
    solve_pddl_task = _get_solver()
    
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(problem_json_path))
    
    with open(problem_json_path, 'r') as f:
        tasks = json.load(f)
    
    results = {}
    for task in tasks:
        task_id = task['id']
        domain_path = os.path.join(base_dir, task['domain'])
        problem_path = os.path.join(base_dir, task['problem'])
        plan_output = os.path.join(base_dir, task['plan_output'])
        
        print(f"\n{'='*60}")
        print(f"Solving task: {task_id}")
        print(f"  Domain: {domain_path}")
        print(f"  Problem: {problem_path}")
        print(f"  Output: {plan_output}")
        print(f"{'='*60}")
        
        try:
            plan = solve_pddl_task(domain_path, problem_path, timeout=300)
            
            if plan is not None:
                output_dir = os.path.dirname(plan_output)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                
                write_plan_custom_format(plan, plan_output)
                results[task_id] = 'SUCCESS'
                print(f"Task {task_id}: Plan written successfully ({len(plan)} actions)")
            else:
                results[task_id] = 'FAILED - No plan found'
                print(f"Task {task_id}: FAILED - No plan found")
                with open(plan_output, 'w') as f:
                    f.write('')
        except Exception as e:
            results[task_id] = f'ERROR - {str(e)}'
            print(f"Task {task_id}: ERROR - {e}")
            import traceback
            traceback.print_exc()
            with open(plan_output, 'w') as f:
                f.write('')
    
    return results


def write_plan_custom_format(plan_actions, filename):
    """Write plan in action_name(param1, param2, ...) format, one per line."""
    with open(filename, 'w') as f:
        for action in plan_actions:
            f.write(action + '\n')


def write_plan_pddl_format(plan_actions, filename):
    """Write plan in standard PDDL format: (action-name param1 param2)"""
    with open(filename, 'w') as f:
        for action in plan_actions:
            pddl_action = _custom_to_pddl_format(action)
            f.write(pddl_action + '\n')


def _custom_to_pddl_format(action_str):
    """Convert action_name(p1, p2, ...) to (action_name p1 p2 ...)"""
    if '(' not in action_str:
        return action_str
    name_part = action_str[:action_str.index('(')]
    params_part = action_str[action_str.index('(')+1:action_str.rindex(')')]
    params = [p.strip() for p in params_part.split(',') if p.strip()]
    if params:
        return f"({name_part} {' '.join(params)})"
    else:
        return f"({name_part})"


def format_action_instance(action_name, params):
    """Format an action instance as action_name(param1, param2, ...)"""
    param_string = ", ".join(params)
    return f"{action_name}({param_string})"
