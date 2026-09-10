---
name: evo-pddl-plan-formatter
description: Handles plan output formatting and end-to-end task orchestration. Reads problem.json, calls the solver for each task, formats plans in action_name(param1, param2, ...) syntax, and writes output files.
---

# evo-pddl-plan-formatter

Orchestrates solving of all PDDL tasks from problem.json and writes
correctly formatted plan output files.

## Key Functions

- `run_all_tasks(problem_json_path, base_dir=None)` - Main orchestrator
- `write_plan_custom_format(plan_actions, filename)` - Write action_name(p1, p2) format
- `write_plan_pddl_format(plan_actions, filename)` - Write (action_name p1 p2) format
- `format_action_instance(action_name, params)` - Format single action

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-pddl-plan-formatter/scripts')
from utils import run_all_tasks

results = run_all_tasks('/app/problem.json', base_dir='/app')
```

## Output Format

The verifier expects plans in `action_name(param1, param2, ...)` format,
one action per line. Example:
```
move_seg_ppdoor_0_40_seg_tww1_0_200_north_south_medium(airplane_cfbeg)
startup_seg_tww1_0_200_north_medium(airplane_cfbeg)
```

## Dependencies

- evo-pddl-solver (for solve_pddl_task function)

## Notes

- unified_planning lowercases all names during parsing
- Plan output paths are relative to base_dir (default: directory of problem.json)
- Empty files are written for failed tasks to avoid file-not-found errors
