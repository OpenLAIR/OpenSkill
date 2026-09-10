# Domain Reference for evo-tpp-solver

**Responsibility**: Complete pipeline: JSON config parsing, PDDL parsing, plan generation with pyperplan (with fallback configurations like gbf/hff if default times out), action formatting as 'action_name(arg1, arg2, ...)' strings, writing plan output files, and pickle serialization for validator compatibility.

**Key functions to implement**: load_task_config, solve_task, format_action, write_plan, solve_all_tasks

---

## 1. The unified_planning Library (Version 1.3.0) API Details


The `unified_planning` (UP) library serves as an abstraction layer designed to decouple the formulation of a planning problem from the specific engine used to solve it [cite: 9]. Version 1.3.0 brings refined interoperability and stable interfaces for classical planning.

### PDDLReader and Problem Instantiation

The `PDDLReader` class is the primary entry point for converting text-based PDDL files into UP's internal object representation. 

The exact API usage for parsing a complete planning task involves instantiating the reader and calling `parse_problem` [cite: 10, 11]:
```python
from unified_planning.io import PDDLReader

reader = PDDLReader()
problem = reader.parse_problem("domain.pddl", "problem.pddl")
```
When `parse_problem` is executed, it parses the domain and problem files, generating an equivalent `unified_planning.model.Problem` object [cite: 10, 12]. 
*   **Case Sensitivity:** It is crucial to note that PDDL is case-insensitive. The `PDDLReader` enforces this by internally converting everything—action names, fluents, objects, and types—to lowercase [cite: 10, 12].
*   **The `Problem` Object:** The returned `Problem` object contains the full specification of the task. It includes lists of `UserType` definitions, `Fluent` declarations (predicates), `InstantaneousAction` definitions, `Object` instances, and expressions defining the initial state and the goal [cite: 13, 14].

### OneshotPlanner and Plan Generation

The `OneshotPlanner` is the UP Operation Mode (OM) dedicated to generating a single plan for a given problem [cite: 15, 16]. It acts as a factory that selects the appropriate engine based on the problem's characteristics or a user-specified name.

To invoke `pyperplan`:
```python
from unified_planning.shortcuts import OneshotPlanner
import unified_planning as up

with OneshotPlanner(name="pyperplan") as planner:
    result = planner.solve(problem)
    if result.status == up.engines.PlanGenerationResultStatus.SOLVED_SATISFICING:
        plan = result.plan
```
*   **Result Object:** The `result` returned by `solve()` is of type `PlanGenerationResult`. It contains a `status` flag (e.g., `SOLVED_SATISFICING`, `UNSOLVABLE_PROVEN`, `TIMEOUT`), the `engine_name`, and the `plan` itself [cite: 1, 16, 17].
*   **The Plan Object:** If a solution is found, `result.plan` is instantiated as a `SequentialPlan` (for classical STRIPS problems). 
*   **Actions:** The sequence of applied actions is accessed via `result.plan.actions`, which yields a list of `ActionInstance` objects [cite: 1, 18].

### ActionInstance Formatting

When you call `str(action)` on an `ActionInstance`, the UP library formats it using a function-call syntax by default. Specifically, it outputs a string in the format `action_name(arg1, arg2, ...)` [cite: 13, 19]. For example, a movement action would print as `drive(truck1, depot1, market1)`. It does *not* natively use the LISP-like parenthesized format `(action_name arg1 arg2)` typical of raw PDDL output [cite: 12, 20].

### Serialization with Pickle

The UP object hierarchy (including `Problem`, `Fluent`, `ActionInstance`, and `FNode` syntax tree elements) is largely composed of pure Python objects designed immutably via a central `Environment` object. Consequently, standard Python `pickle` serialization generally works for `SequentialPlan` objects. However, because UP relies heavily on a singleton-like `Environment` to ensure uniqueness of `FNode` expressions (the abstract syntax tree nodes for logic), deserializing a plan in a completely fresh Python process requires ensuring that the target problem shares the exact same variable references, or you must rely on UP's native Protobuf/JSON exporters for cross-process communication.

## 2. pyperplan (Version 2.1) as a Planning Engine


`pyperplan` is a lightweight, academic planning engine written entirely in Python. It was developed at the University of Freiburg as a teaching tool [cite: 3, 20, 23].

### Search Algorithms and Defaults

`pyperplan` implements a variety of standard forward-chaining state-space search algorithms [cite: 24, 25].
Supported algorithms include:
1.  **Breadth-First Search (bfs)**: Expands the shallowest nodes first.
2.  **A* Search (astar)**: Uses the evaluation function \(f(n) = g(n) + h(n)\) to find optimal paths.
3.  **Weighted A* Search (wastar)**: Scales the heuristic by a weight \(W > 1\) to speed up search at the cost of optimality.
4.  **Greedy Best-First Search (gbf)**: Expands the node with the lowest \(h(n)\), ignoring path cost. It is purely satisficing.
5.  **Enforced Hill-Climbing (ehs)**
6.  **Iterative Deepening Search (ids)**

**Defaults:**
When invoked from the command line without arguments, native `pyperplan` defaults to a blind Breadth-First Search [cite: 3]. However, when invoked through the `unified_planning` integration (`up-pyperplan`), the default configuration is intentionally overridden to be **Weighted A* Search (wastar)** paired with the **Additive Heuristic (hadd)** [cite: 4].

### Configuring Heuristics and Search via UP

The `up-pyperplan` wrapper exposes configuration parameters directly through the `OneshotPlanner` constructor via the `params` argument [cite: 4, 13].

Available parameters:
*   `search`: String values including `'wastar'`, `'astar'`, `'gbf'`, `'bfs'`, `'ehs'`, `'ids'`, `'sat'`.
*   `heuristic`: String values including `'hadd'`, `'hmax'`, `'hsa'`, `'hff'` (Fast-Forward), `'blind'`, `'lmcut'` (Landmark-cut), and `'landmark'` [cite: 4].

Example configuration for a fast, satisficing search using Greedy Best-First and the FF heuristic:
```python
with OneshotPlanner(
    name='pyperplan', 
    params={'search': 'gbf', 'heuristic': 'hff'}
) as planner:
    result = planner.solve(problem)
```

### Performance Characteristics

Because `pyperplan` "deliberately prefers clean code over fast code" [cite: 3], its performance is orders of magnitude slower than state-of-the-art C++ planners like Fast Downward. 
*   **Small problems:** Handles spaces with a few thousand states in seconds.
*   **Medium problems:** Might take several minutes.
*   **Large problems:** Susceptible to memory exhaustion and timeouts. In IPC benchmarks, Python's overhead in generating successors and evaluating delete-relaxation heuristics (like `hff` or `lmcut`) often results in timeouts for moderately sized instances [cite: 8, 25].

## 3. Travelling Purchase Problem (TPP) in PDDL


The TPP is a logistics routing problem introduced in IPC-5 [cite: 6, 27, 28]. It is an NP-hard generalization of the Travelling Salesman Problem [cite: 6, 7]. The agent must travel a graph of connected markets to purchase specific quantities of goods and transport them to a depot, minimizing travel and purchase costs.

## 4. Plan Output Format


A crucial aspect of utility modules is converting internal plan representations to required output strings.

## 5. Common Pitfalls and Edge Cases



## 6. Alternative Approaches if pyperplan Fails


When `pyperplan` times out or exhausts memory, a resilient utility module must gracefully degrade to alternative solvers.

## 7. Working Code Examples


The following is a production-ready, highly defensive Python utility module designed to parse a JSON configuration file, solve TPP tasks via `unified_planning` and `pyperplan`, format the output, validate the plan, and provide graceful fallbacks.

```python
import json
import logging
from pathlib import Path
from typing import List, Optional