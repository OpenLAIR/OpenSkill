---
name: evo-virtualhome-agent-planning
description: Solves PDDL airport ground traffic control planning problems from the IPC Airport domain. Uses unified-planning with pyperplan backend (GBFS + hFF for agile solving), with direct pyperplan fallback, robust timeout/memout handling, and correct plan output formatting.
---

# evo-virtualhome-agent-planning

## Description
Solves PDDL airport ground traffic control planning problems from the IPC Airport domain.
Uses unified-planning with pyperplan backend to automatically find valid plans, with multiple
fallback strategies and robust error handling for large-scale instances (up to Munich Airport scale).

## Key Domain Knowledge
- Airport domain models ground traffic: airplanes taxi between segments (taxiways, runways, parking)
- Actions: move, startup (pushing->moving), park (terminal), takeoff (terminal), pushback
- Dual-predicate pattern: occupied/not_occupied, blocked/not_blocked must be maintained
- Blocking is per-airplane (safety buffers)
- IPC-4 Airport domain is PSPACE-hard; largest instances encode full Munich Airport (MUC)
- STRIPS-compiled versions required for pyperplan (no ADL/negative preconditions support)
- For agile satisficing planning: GBFS + hFF is the optimal pyperplan configuration
- unified-planning PDDLReader forces all names to lower-case during parsing
- Plan format: `action_name(param1, param2, ...)` - function-call style, one per line
- Timeout of 600s is standard for IPC-style evaluation

## Dependencies
- unified_planning >= 1.3.0
- up-pyperplan >= 1.1.0
- pyperplan >= 2.1

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-virtualhome-agent-planning/scripts')
from solver import solve_all_from_json, solve_task

# Solve all tasks from problem.json
results = solve_all_from_json('/app/problem.json')

# Or solve a single task
solve_task('/app/airport/domain01.pddl', '/app/airport/task01.pddl', '/app/task01.txt')
```

## Functions
- `parse_problem(domain_path, problem_path)` - Parse PDDL files with error handling
- `solve_problem(problem, timeout)` - Solve using pyperplan with GBFS+hFF, fallback strategies
- `solve_with_pyperplan_direct(domain_path, problem_path, timeout)` - Direct pyperplan fallback
- `format_plan_action(action)` - Convert action to `action_name(p1, p2, ...)` format
- `plan_to_lines(plan)` - Convert full plan to list of formatted strings
- `write_plan(lines, output_path)` - Write plan to file with directory creation
- `solve_task(domain, problem, output)` - End-to-end single task with fallbacks
- `solve_all_from_json(json_path, base_dir)` - Solve all tasks from problem.json