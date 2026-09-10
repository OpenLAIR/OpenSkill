"""
PDDL Airport Planning Solver

Solves airport ground traffic control PDDL planning problems using
unified-planning with pyperplan backend.

Key domain insights (from IPC-4 Airport domain research):
- Airport domain is PSPACE-hard; largest instances encode Munich Airport (MUC)
- GBFS + hFF is the best agile satisficing strategy for pyperplan
- pyperplan is STRIPS-only: no ADL, negative preconditions, or conditional effects
- unified-planning PDDLReader forces all names to lower-case
- ADL-to-STRIPS compilation causes explosion in ground actions (memory risk)
- Plan output format must match what the validator expects
"""
import json
import os
import sys
import signal
import traceback
import unified_planning as up
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines import PlanGenerationResultStatus

# Suppress credits output
up.shortcuts.get_environment().credits_stream = None

# Default timeout for planning (seconds) - standard IPC evaluation limit
DEFAULT_TIMEOUT = 600


def parse_problem(domain_path, problem_path):
    """
    Parse a PDDL domain and problem file into a unified-planning Problem.
    
    Note: unified-planning PDDLReader forces all entity names to lower-case.
    This is by design (PDDL is case-insensitive) but downstream validators
    must account for this.
    
    Args:
        domain_path: Path to the PDDL domain file
        problem_path: Path to the PDDL problem file
    
    Returns:
        unified_planning Problem object
    
    Raises:
        FileNotFoundError: If domain or problem file doesn't exist
        Exception: If PDDL parsing fails (e.g., unsupported features)
    """
    if not os.path.exists(domain_path):
        raise FileNotFoundError(f"Domain file not found: {domain_path}")
    if not os.path.exists(problem_path):
        raise FileNotFoundError(f"Problem file not found: {problem_path}")
    
    reader = PDDLReader()
    return reader.parse_problem(domain_path, problem_path)


def solve_problem(problem, timeout=DEFAULT_TIMEOUT):
    """
    Solve a unified-planning Problem using pyperplan with optimal configuration.
    
    Strategy hierarchy (from DR findings):
    1. pyperplan with GBFS + hFF (best agile satisficing config)
    2. pyperplan with default settings (wastar + hadd) as fallback
    3. Returns None if all strategies fail
    
    Args:
        problem: unified-planning Problem object
        timeout: Maximum solving time in seconds (default: 600)
    
    Returns:
        Plan object or None if solving fails
    """
    # Strategy 1: GBFS + hFF - optimal for agile satisficing planning
    # Research shows this is conclusively the best pyperplan combination
    # for large navigation-heavy domains like Airport
    try:
        with OneshotPlanner(
            name='pyperplan',
            params={'search': 'gbf', 'heuristic': 'hff'}
        ) as planner:
            result = planner.solve(problem, timeout=timeout)
            
            if result.plan is not None:
                status_name = result.status.name if result.status else "UNKNOWN"
                print(f"  [GBFS+hFF] Plan found (status: {status_name}, "
                      f"{len(result.plan.actions)} actions)")
                return result.plan
            
            # Log specific failure modes for diagnostics
            if result.status == PlanGenerationResultStatus.TIMEOUT:
                print(f"  [GBFS+hFF] Timed out after {timeout}s")
            elif result.status == PlanGenerationResultStatus.MEMOUT:
                print(f"  [GBFS+hFF] Memory exhaustion (common for large MUC instances)")
            else:
                status_name = result.status.name if result.status else "UNKNOWN"
                print(f"  [GBFS+hFF] Failed with status: {status_name}")
    except Exception as e:
        print(f"  [GBFS+hFF] Exception: {e}")

    # Strategy 2: pyperplan with default settings (wastar + hadd)
    # This is the UP default for pyperplan - sometimes works when GBFS doesn't
    try:
        with OneshotPlanner(name='pyperplan') as planner:
            result = planner.solve(problem, timeout=timeout)
            
            if result.plan is not None:
                status_name = result.status.name if result.status else "UNKNOWN"
                print(f"  [pyperplan-default] Plan found (status: {status_name}, "
                      f"{len(result.plan.actions)} actions)")
                return result.plan
            
            if result.status == PlanGenerationResultStatus.TIMEOUT:
                print(f"  [pyperplan-default] Timed out after {timeout}s")
            elif result.status == PlanGenerationResultStatus.MEMOUT:
                print(f"  [pyperplan-default] Memory exhaustion")
            else:
                status_name = result.status.name if result.status else "UNKNOWN"
                print(f"  [pyperplan-default] Failed with status: {status_name}")
    except Exception as e:
        print(f"  [pyperplan-default] Exception: {e}")

    # Strategy 3: Try fast-downward if available (C++ based, much more scalable)
    # Fast Downward uses SAS+ translation to aggressively prune memory overhead
    try:
        with OneshotPlanner(name='fast-downward') as planner:
            result = planner.solve(problem, timeout=timeout)
            if result.plan is not None:
                status_name = result.status.name if result.status else "UNKNOWN"
                print(f"  [fast-downward] Plan found (status: {status_name}, "
                      f"{len(result.plan.actions)} actions)")
                return result.plan
            status_name = result.status.name if result.status else "UNKNOWN"
            print(f"  [fast-downward] Failed with status: {status_name}")
    except Exception as e:
        # fast-downward may not be installed - this is expected
        print(f"  [fast-downward] Not available: {e}")

    # Strategy 4: Try any available planner via automatic engine selection
    try:
        with OneshotPlanner(problem_kind=problem.kind) as planner:
            result = planner.solve(problem, timeout=timeout)
            if result.plan is not None:
                status_name = result.status.name if result.status else "UNKNOWN"
                print(f"  [auto-select] Plan found (status: {status_name}, "
                      f"{len(result.plan.actions)} actions)")
                return result.plan
            status_name = result.status.name if result.status else "UNKNOWN"
            print(f"  [auto-select] Failed with status: {status_name}")
    except Exception as e:
        print(f"  [auto-select] Exception: {e}")

    return None


def solve_with_pyperplan_direct(domain_path, problem_path, timeout=DEFAULT_TIMEOUT):
    """
    Direct pyperplan invocation as ultimate fallback.
    Bypasses unified-planning entirely for maximum control.
    
    Uses GBFS + hFF which is the optimal agile configuration.
    
    Note: pyperplan is STRIPS-only. If the domain uses ADL features
    (negative preconditions, conditional effects, disjunctive preconditions),
    this will fail with a parsing exception.
    
    Args:
        domain_path: Path to PDDL domain file
        problem_path: Path to PDDL problem file
        timeout: Maximum time in seconds
    
    Returns:
        List of action strings in PDDL format, or None if solving fails
    """
    try:
        from pyperplan.pddl.parser import Parser
        from pyperplan.grounding import ground
        from pyperplan.heuristics.relaxation import hFFHeuristic as hFF
        from pyperplan.search.gbfs import greedy_best_first_search
    except ImportError:
        try:
            from pyperplan.pddl.parser import Parser
            from pyperplan.grounding import ground
            from pyperplan.heuristics.relaxation import hFF
            from pyperplan.search.gbfs import greedy_best_first_search
        except ImportError as e:
            print(f"  [direct-pyperplan] Import failed: {e}")
            return None

    try:
        # Set alarm for timeout (Unix only)
        old_handler = None
        if hasattr(signal, 'SIGALRM'):
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Direct pyperplan timed out after {timeout}s")
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))

        # Parse
        parser = Parser(domain_path, problem_path)
        domain = parser.parse_domain()
        problem = parser.parse_problem(domain)

        # Ground - this is where memory explosion happens for large Airport instances
        task = ground(problem)

        # Initialize heuristic and search
        heuristic = hFF(task)
        solution = greedy_best_first_search(task, heuristic)

        # Cancel alarm
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)

        if solution is not None:
            # Extract plan - pyperplan returns list of operators
            # Operator names are typically in format "(action_name param1 param2)"
            plan_lines = []
            for op in solution:
                op_name = op.name if hasattr(op, 'name') else str(op)
                plan_lines.append(op_name)
            print(f"  [direct-pyperplan] Plan found ({len(plan_lines)} actions)")
            return plan_lines
        else:
            print(f"  [direct-pyperplan] No solution found")
            return None

    except TimeoutError as e:
        print(f"  [direct-pyperplan] {e}")
        return None
    except MemoryError:
        print(f"  [direct-pyperplan] Memory exhaustion during grounding/search")
        return None
    except Exception as e:
        print(f"  [direct-pyperplan] Exception: {e}")
        traceback.print_exc()
        return None
    finally:
        # Ensure alarm is cancelled
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)


def format_plan_action(action):
    """
    Convert a unified-planning ActionInstance to the required output format.
    
    The task specification shows the expected format as:
        action_name(param1, param2, ...)
    
    Note: unified-planning's str(action) already produces this format:
        action_name(param1, param2, ...)
    But we handle edge cases explicitly.
    
    unified-planning forces all names to lower-case during parsing.
    This is consistent with PDDL case-insensitivity.
    
    Args:
        action: unified-planning ActionInstance
    
    Returns:
        Formatted action string
    """
    action_str = str(action)
    
    # The str() representation from unified-planning is already in
    # function-call format: action_name(param1, param2, ...)
    # Verify it has the expected format
    if '(' in action_str and action_str.endswith(')'):
        return action_str
    
    # Fallback: construct manually from action components
    try:
        action_name = action.action.name
        params = [str(p) for p in action.actual_parameters]
        if params:
            return f"{action_name}({', '.join(params)})"
        else:
            return f"{action_name}()"
    except Exception:
        # Ultimate fallback - return whatever string representation we have
        return action_str


def format_direct_pyperplan_action(action_str):
    """
    Convert a direct pyperplan action string to the required output format.
    
    pyperplan operator names are typically: "(action_name param1 param2)"
    Required output format: "action_name(param1, param2)"
    
    Args:
        action_str: Raw action string from pyperplan
    
    Returns:
        Formatted action string
    """
    # Strip outer parentheses if present
    s = action_str.strip()
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1].strip()
    
    parts = s.split()
    if not parts:
        return action_str
    
    action_name = parts[0]
    params = parts[1:]
    
    if params:
        return f"{action_name}({', '.join(params)})"
    else:
        return f"{action_name}()"


def plan_to_lines(plan):
    """
    Convert a unified-planning plan to a list of formatted action strings.
    
    Output format per line: action_name(param1, param2, ...)
    
    Args:
        plan: unified-planning SequentialPlan object
    
    Returns:
        List of formatted action strings
    """
    return [format_plan_action(action) for action in plan.actions]


def write_plan(lines, output_path):
    """
    Write plan lines to a file, creating directories as needed.
    
    Args:
        lines: List of action strings
        output_path: Path to write the plan file
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
        if lines:
            f.write('\n')


def solve_task(domain_path, problem_path, output_path, timeout=DEFAULT_TIMEOUT):
    """
    End-to-end: parse, solve, format, and write a PDDL planning task.
    
    Attempts multiple solving strategies in order of preference:
    1. unified-planning with pyperplan (GBFS+hFF, then default)
    2. unified-planning with fast-downward (if available)
    3. unified-planning with auto-selected engine
    4. Direct pyperplan invocation (bypasses UP entirely)
    
    Args:
        domain_path: Path to PDDL domain file
        problem_path: Path to PDDL problem file
        output_path: Path to write the solution plan
        timeout: Maximum solving time in seconds
    
    Returns:
        True if solved successfully, False otherwise
    """
    print(f"Solving: {os.path.basename(problem_path)}")
    
    # Step 1: Parse PDDL files
    try:
        problem = parse_problem(domain_path, problem_path)
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return False
    except Exception as e:
        print(f"  ERROR parsing PDDL: {e}")
        traceback.print_exc()
        # If UP parsing fails, try direct pyperplan as last resort
        print(f"  Attempting direct pyperplan fallback...")
        direct_plan = solve_with_pyperplan_direct(domain_path, problem_path, timeout)
        if direct_plan is not None:
            formatted = [format_direct_pyperplan_action(a) for a in direct_plan]
            write_plan(formatted, output_path)
            print(f"  SUCCESS (direct fallback): {output_path} ({len(formatted)} actions)")
            return True
        return False

    # Step 2: Solve using unified-planning strategies
    plan = solve_problem(problem, timeout=timeout)
    
    if plan is not None:
        # Step 3: Format and write
        lines = plan_to_lines(plan)
        write_plan(lines, output_path)
        print(f"  SUCCESS: {output_path} ({len(lines)} actions)")
        return True
    
    # Step 4: Direct pyperplan fallback if UP strategies all failed
    print(f"  All UP strategies failed. Trying direct pyperplan...")
    direct_plan = solve_with_pyperplan_direct(domain_path, problem_path, timeout)
    if direct_plan is not None:
        formatted = [format_direct_pyperplan_action(a) for a in direct_plan]
        write_plan(formatted, output_path)
        print(f"  SUCCESS (direct fallback): {output_path} ({len(formatted)} actions)")
        return True
    
    # Write empty plan file so downstream doesn't crash on missing file
    write_plan([], output_path)
    print(f"  FAILED to solve: {problem_path}")
    return False


def solve_all_from_json(problem_json_path, base_dir=None):
    """
    Load problem.json and solve all tasks.
    
    Handles both absolute and relative paths in the JSON.
    Creates output directories as needed.
    
    Args:
        problem_json_path: Path to the problem.json file
        base_dir: Base directory for resolving relative paths.
                  If None, uses the directory containing problem.json.
    
    Returns:
        Dictionary mapping task IDs to success booleans
    """
    if not os.path.exists(problem_json_path):
        print(f"ERROR: problem.json not found at {problem_json_path}")
        return {}
    
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(problem_json_path))
    
    with open(problem_json_path) as f:
        tasks = json.load(f)
    
    results = {}
    total = len(tasks)
    solved = 0
    
    print(f"Processing {total} tasks from {problem_json_path}")
    print(f"Base directory: {base_dir}")
    print("=" * 60)
    
    for i, task in enumerate(tasks, 1):
        task_id = task.get('id', f'task_{i}')
        print(f"\n[{i}/{total}] Task: {task_id}")
        
        # Resolve paths - handle both absolute and relative
        domain_path = task['domain']
        problem_path = task['problem']
        output_path = task['plan_output']
        
        if not os.path.isabs(domain_path):
            domain_path = os.path.join(base_dir, domain_path)
        if not os.path.isabs(problem_path):
            problem_path = os.path.join(base_dir, problem_path)
        if not os.path.isabs(output_path):
            output_path = os.path.join(base_dir, output_path)
        
        success = solve_task(domain_path, problem_path, output_path)
        results[task_id] = success
        if success:
            solved += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {solved}/{total} tasks solved successfully")
    
    return results


if __name__ == '__main__':
    # Support command-line argument for problem.json path
    json_path = sys.argv[1] if len(sys.argv) > 1 else '/app/problem.json'
    solve_all_from_json(json_path)