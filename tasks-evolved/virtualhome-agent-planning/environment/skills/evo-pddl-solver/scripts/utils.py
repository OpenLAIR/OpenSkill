import sys
import os
import signal

def solve_pddl_task(domain_path, problem_path, timeout=300):
    """
    Main entry point: tries unified_planning first, then direct pyperplan.
    Returns a list of action strings in the format expected by the formatter.
    Each action string is like: "action_name(param1, param2, ...)"
    """
    plan = solve_with_unified_planning(domain_path, problem_path, timeout=timeout)
    if plan is not None:
        return plan
    
    print("Unified planning failed, trying direct pyperplan...")
    plan = solve_with_pyperplan_direct(domain_path, problem_path, timeout=timeout)
    if plan is not None:
        return plan
    
    print("All solving strategies failed.")
    return None


def solve_with_unified_planning(domain_path, problem_path, timeout=300):
    """
    Solve using unified_planning with pyperplan backend.
    Uses GBFS + hFF for fast satisficing planning.
    Returns list of action strings in format: "action_name(param1, param2, ...)"
    """
    try:
        from unified_planning.io import PDDLReader
        from unified_planning.shortcuts import OneshotPlanner
        from unified_planning.engines import PlanGenerationResultStatus
        
        reader = PDDLReader()
        problem = reader.parse_problem(domain_path, problem_path)
        
        # Try with GBFS + hFF first (fastest for satisficing)
        try:
            with OneshotPlanner(name='pyperplan', params={'search': 'gbf', 'heuristic': 'hff'}) as planner:
                result = planner.solve(problem, timeout=timeout)
                if result.status in (PlanGenerationResultStatus.SOLVED_SATISFICING,
                                     PlanGenerationResultStatus.SOLVED_OPTIMALLY):
                    return _extract_plan_from_up(result.plan)
                else:
                    print(f"UP pyperplan GBFS+hFF status: {result.status}")
        except Exception as e:
            print(f"UP pyperplan GBFS+hFF failed: {e}")
        
        # Fallback: try default pyperplan config
        try:
            with OneshotPlanner(name='pyperplan') as planner:
                result = planner.solve(problem, timeout=timeout)
                if result.status in (PlanGenerationResultStatus.SOLVED_SATISFICING,
                                     PlanGenerationResultStatus.SOLVED_OPTIMALLY):
                    return _extract_plan_from_up(result.plan)
                else:
                    print(f"UP pyperplan default status: {result.status}")
        except Exception as e:
            print(f"UP pyperplan default failed: {e}")
        
        return None
    except Exception as e:
        print(f"Unified planning failed: {e}")
        return None


def _extract_plan_from_up(plan):
    """
    Extract plan actions from a unified_planning SequentialPlan.
    Returns list of strings in format: "action_name(param1, param2, ...)"
    """
    if plan is None:
        return None
    
    actions = []
    for action_instance in plan.actions:
        action_name = action_instance.action.name
        params = [str(p) for p in action_instance.actual_parameters]
        param_string = ", ".join(params)
        formatted = f"{action_name}({param_string})"
        actions.append(formatted)
    
    return actions


def solve_with_pyperplan_direct(domain_path, problem_path, timeout=300):
    """
    Solve using pyperplan directly (bypassing unified_planning).
    Uses GBFS + hFF heuristic.
    Returns list of action strings.
    """
    try:
        from pyperplan.pddl.parser import Parser
        from pyperplan.grounding import ground
        from pyperplan.heuristics.relaxation import hFFHeuristic as hFF
        from pyperplan.search.gbfs import greedy_best_first_search
        
        # Parse
        parser = Parser(domain_path, problem_path)
        domain = parser.parse_domain()
        problem = parser.parse_problem(domain)
        
        # Ground
        task = ground(problem)
        
        # Initialize heuristic
        heuristic = hFF(task)
        
        # Search
        solution = greedy_best_first_search(task, heuristic)
        
        if solution is not None:
            # Extract operator names - pyperplan returns list of search nodes
            plan = []
            for node in solution:
                # node is a SearchNode with .operator attribute
                op_name = node.name if hasattr(node, 'name') else str(node)
                plan.append(_format_pyperplan_action(op_name))
            return plan
        
        return None
    except Exception as e:
        print(f"Direct pyperplan failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def _format_pyperplan_action(op_string):
    """
    Convert pyperplan operator name format to action_name(param1, param2, ...) format.
    Pyperplan format is like: "(move-car loc1 loc2)" or "move-car loc1 loc2"
    Target format: "move-car(loc1, loc2)"
    """
    # Remove parentheses if present
    s = op_string.strip()
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1].strip()
    
    parts = s.split()
    if len(parts) == 0:
        return op_string
    
    action_name = parts[0]
    params = parts[1:]
    param_string = ", ".join(params)
    return f"{action_name}({param_string})"


def solve_with_fallback_strategies(domain_path, problem_path, timeout=300):
    """
    Try multiple strategies in order of likelihood of success.
    """
    # Strategy 1: UP with pyperplan GBFS+hFF
    plan = solve_with_unified_planning(domain_path, problem_path, timeout=timeout)
    if plan:
        return plan
    
    # Strategy 2: Direct pyperplan
    plan = solve_with_pyperplan_direct(domain_path, problem_path, timeout=timeout)
    if plan:
        return plan
    
    return None
