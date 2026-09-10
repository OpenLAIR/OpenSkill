#!/usr/bin/env python3
"""TPP PDDL Solver - Solves Travelling Purchase Problem tasks using pyperplan via unified_planning.

Complete pipeline: JSON config parsing, PDDL parsing, plan generation with
pyperplan (with fallback configurations), action formatting, plan file writing,
and pickle serialization for validation compatibility.
"""

import json
import logging
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import unified_planning as up
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines import PlanGenerationResultStatus

# Suppress UP credits banner
up.shortcuts.get_environment().credits_stream = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Solver configurations to try in order (search, heuristic)
SOLVER_CONFIGS = [
    {"search": "gbf", "heuristic": "hff"},     # Fast satisficing
    {"search": "wastar", "heuristic": "hadd"},  # UP default
    {"search": "gbf", "heuristic": "hadd"},     # Alternative fast
    {"search": "astar", "heuristic": "hff"},    # Optimal but slower
]


def load_task_config(config_path: Path) -> List[Dict[str, str]]:
    """Parse problem.json and return list of task configurations.
    
    Each task dict has keys: id, domain, problem, plan_output
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, "r") as f:
        tasks = json.load(f)
    
    if not isinstance(tasks, list):
        raise ValueError("problem.json must contain a JSON array of task objects")
    
    logger.info(f"Loaded {len(tasks)} tasks from {config_path}")
    return tasks


def format_action(action_instance) -> str:
    """Format a unified_planning ActionInstance as 'action_name(arg1, arg2, ...)'.
    
    The str() representation of UP ActionInstance already produces this format,
    but we use it explicitly for clarity and to ensure lowercase.
    """
    return str(action_instance)


def solve_task(
    domain_path: Path,
    problem_path: Path,
    configs: Optional[List[Dict[str, str]]] = None,
) -> Optional[Tuple[List[str], Any]]:
    """Parse PDDL files and solve using pyperplan with fallback configurations.
    
    Args:
        domain_path: Path to the PDDL domain file
        problem_path: Path to the PDDL problem file
        configs: List of solver config dicts with 'search' and 'heuristic' keys.
                 Defaults to SOLVER_CONFIGS.
    
    Returns:
        Tuple of (formatted_actions_list, plan_object) or None if no plan found.
    """
    if configs is None:
        configs = SOLVER_CONFIGS
    
    domain_path = Path(domain_path)
    problem_path = Path(problem_path)
    
    if not domain_path.exists():
        logger.error(f"Domain file not found: {domain_path}")
        return None
    if not problem_path.exists():
        logger.error(f"Problem file not found: {problem_path}")
        return None
    
    # Parse PDDL files
    reader = PDDLReader()
    try:
        problem = reader.parse_problem(str(domain_path), str(problem_path))
    except Exception as e:
        logger.error(f"Failed to parse PDDL files: {e}")
        return None
    
    # Try each solver configuration
    for config in configs:
        search = config.get("search", "gbf")
        heuristic = config.get("heuristic", "hff")
        logger.info(f"Trying pyperplan with search={search}, heuristic={heuristic}")
        
        try:
            with OneshotPlanner(
                name="pyperplan",
                params={"search": search, "heuristic": heuristic}
            ) as planner:
                result = planner.solve(problem)
                
                if result.status in (
                    PlanGenerationResultStatus.SOLVED_SATISFICING,
                    PlanGenerationResultStatus.SOLVED_OPTIMALLY,
                ):
                    plan = result.plan
                    formatted_actions = [format_action(a) for a in plan.actions]
                    logger.info(
                        f"Plan found with {len(formatted_actions)} actions "
                        f"using {search}/{heuristic}"
                    )
                    return formatted_actions, plan
                else:
                    logger.warning(
                        f"No plan with {search}/{heuristic}: {result.status.name}"
                    )
        except Exception as e:
            logger.warning(f"Solver failed with {search}/{heuristic}: {e}")
            continue
    
    logger.error(f"All solver configurations failed for {problem_path}")
    return None


def write_plan(
    formatted_actions: List[str],
    output_path: Path,
    plan_object: Any = None,
) -> None:
    """Write formatted plan to text file and optionally pickle the plan.
    
    Args:
        formatted_actions: List of action strings like 'drive(truck1, depot1, market1)'
        output_path: Path for the output text file
        plan_object: Optional UP plan object to pickle for validation
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write text plan file
    with open(output_path, "w") as f:
        for action_str in formatted_actions:
            f.write(f"{action_str}\n")
    logger.info(f"Plan written to {output_path} ({len(formatted_actions)} actions)")
    
    # Write pickle file for validation compatibility
    pickle_path = output_path.with_suffix(".pkl")
    plan_data = {
        "actions": formatted_actions,
        "plan": plan_object,
    }
    with open(pickle_path, "wb") as f:
        pickle.dump(plan_data, f)
    logger.info(f"Pickle written to {pickle_path}")


def solve_all_tasks(
    config_path: Path,
    base_dir: Optional[Path] = None,
) -> Dict[str, bool]:
    """End-to-end solver: load config, solve all tasks, write all outputs.
    
    Args:
        config_path: Path to problem.json
        base_dir: Base directory for resolving relative paths.
                  Defaults to config_path's parent directory.
    
    Returns:
        Dict mapping task IDs to success/failure booleans.
    """
    config_path = Path(config_path)
    if base_dir is None:
        base_dir = config_path.parent
    base_dir = Path(base_dir)
    
    tasks = load_task_config(config_path)
    results = {}
    
    for task in tasks:
        task_id = task.get("id", "unknown")
        domain_rel = task.get("domain", "")
        problem_rel = task.get("problem", "")
        output_rel = task.get("plan_output", "")
        
        if not all([domain_rel, problem_rel, output_rel]):
            logger.warning(f"Skipping task {task_id}: missing required fields")
            results[task_id] = False
            continue
        
        domain_path = base_dir / domain_rel
        problem_path = base_dir / problem_rel
        output_path = base_dir / output_rel
        
        logger.info(f"=== Solving task {task_id} ===")
        
        result = solve_task(domain_path, problem_path)
        
        if result is not None:
            formatted_actions, plan_obj = result
            write_plan(formatted_actions, output_path, plan_obj)
            results[task_id] = True
        else:
            logger.error(f"Failed to solve task {task_id}")
            # Write empty plan file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write("")  # Empty file for failed tasks
            results[task_id] = False
    
    # Summary
    solved = sum(1 for v in results.values() if v)
    total = len(results)
    logger.info(f"\n=== Summary: {solved}/{total} tasks solved ===")
    
    return results


if __name__ == "__main__":
    # Default: solve from /app/problem.json
    config = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/problem.json")
    base = Path(sys.argv[2]) if len(sys.argv) > 2 else config.parent
    
    results = solve_all_tasks(config, base)
    
    # Exit with error code if any task failed
    if not all(results.values()):
        sys.exit(1)
