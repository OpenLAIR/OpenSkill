# Domain Reference for evo-pddl-solver

**Responsibility**: Parse PDDL files, configure and invoke planning engines (pyperplan via unified_planning or directly), handle timeout/memout errors, return solution plans

**Key functions to implement**: solve_pddl_task, solve_with_unified_planning, solve_with_pyperplan_direct, solve_with_fallback_strategies

---

## 2. `unified_planning` API for PDDL Parsing and Solving


The `unified_planning` library (version 1.3.0) streamlines the lifecycle of a planning problem. Below is a detailed breakdown of the exact import paths, parsing mechanics, and solver invocation strategies required to build a functional utility module.

### 2.1 Exact Import Paths and Instantiation


The fundamental classes required for file I/O operations and planner interactions reside within the `unified_planning.io` and `unified_planning.shortcuts` modules. 

```python

### 2.2 Understanding `PDDLReader`


The `PDDLReader` class provides the capability to parse standard PDDL files and translate them into a semantically equivalent `unified_planning.model.Problem` instance [cite: 13, 14]. 

**Execution:**
```python
reader = PDDLReader()
problem = reader.parse_problem("domain.pddl", "problem.pddl")
```

**Internal Mechanics:**
When `parse_problem` is invoked, the library attempts to utilize an underlying AI-PDDL parser (`unified_planning.interop.from_pddl.from_ai_pddl`). If the domain requirements exceed the capabilities of the primary parser, it gracefully falls back to the `UPPDDLReader` [cite: 8]. 

**Properties of the Returned `Problem` Object:**
The resulting `problem` is a comprehensive data structure containing:
*   `problem.kind`: Returns a `ProblemKind` object detailing the expressivity requirements (e.g., whether it requires STRIPS, numeric fluents, temporal features, or negative preconditions) [cite: 15, 16].
*   `problem.actions`: A list of abstract transition functions (`InstantaneousAction` or `DurativeAction`) [cite: 17, 18].
*   `problem.all_objects`: A list of all domain entities mapped to their respective `UserType` [cite: 14, 17].
*   `problem.initial_values`: A dictionary mapping state variables (fluents) to their initial boolean or numeric values [cite: 16, 17].
*   `problem.goals`: A list of boolean expressions representing the target state [cite: 17, 19].

*Important Caveat:* Due to the case-insensitivity of PDDL, the `PDDLReader` explicitly forces all entity names (actions, fluents, objects) to **lower-case** during parsing [cite: 8].

### 2.3 `OneshotPlanner` and Engine Selection


The `OneshotPlanner` is an "Operation Mode" (OM) within the UP library. Its semantic purpose is straightforward: given a problem, return a single valid solution plan [cite: 20].

**Automatic Selection:**
If invoked without specifying an engine name, the UP factory evaluates `problem.kind` and cross-references it with the `supported_kind()` methods of all installed engines. It then selects the highest-priority compatible engine from its preference list [cite: 15, 21].
```python
with OneshotPlanner(problem_kind=problem.kind) as planner:
    result = planner.solve(problem)
```

**Explicit Engine Specification (`pyperplan` vs `up-pyperplan`):**
To force the selection of `pyperplan`, you must use the internal engine registration name. The integration package is installed via `pip install up-pyperplan` (or `pip install unified-planning[pyperplan]`), but the engine itself registers its identity as `'pyperplan'` [cite: 22]. Therefore, you must specify `name='pyperplan'`. The engine name `'pyperplan-opt'` can also be used to enforce optimal planning [cite: 22].

```python
with OneshotPlanner(name='pyperplan') as planner:
    result = planner.solve(problem, timeout=600)
```

## 3. Direct Usage of `pyperplan` as a Fallback


While `unified_planning` abstracts the backend, encountering obscure integration errors or seeking absolute control over search node expansion might necessitate using `pyperplan` directly as a Python module [cite: 27, 28].

### 3.1 Architecture and Grounding


`pyperplan` operates through a distinct multi-stage pipeline: parsing, grounding, and searching [cite: 29]. 

1.  **Parsing:** The `pyperplan.pddl.parser.Parser` reads text files and converts them into abstract syntax trees representing the `Domain` and `Problem`.
2.  **Grounding:** PDDL tasks are abstract (lifted). They must be "grounded"—meaning variables are replaced with all possible concrete objects. The `pyperplan.grounding.ground()` function processes the problem and returns a `Task` instance [cite: 29]. This `Task` acts as a container for all concrete `Operator` instances [cite: 29].

### 3.2 Programmatic Search Invocation


To run a search directly without the CLI, one must instantiate the search algorithm and heuristic dynamically.

```python
from pyperplan.pddl.parser import Parser
from pyperplan.grounding import ground
from pyperplan.search.searchspace import SearchNode
from pyperplan.heuristics.relaxation import hFF
from pyperplan.search.gbfs import greedy_best_first_search

def run_pyperplan_direct(domain_file, problem_file):
    # 1. Parse
    parser = Parser(domain_file, problem_file)
    domain = parser.parse_domain()
    problem = parser.parse_problem(domain)
    
    # 2. Ground
    task = ground(problem)
    
    # 3. Initialize Heuristic (Fast-Forward)
    heuristic = hFF(task)
    
    # 4. Run Search
    solution_nodes = greedy_best_first_search(task, heuristic)
    
    # 5. Extract Plan
    if solution_nodes is not None:
        plan = [node.operator.name for node in solution_nodes]
        return plan
    return None
```

### 3.3 Available Search Algorithms and Heuristics


`pyperplan` provides several classical search algorithms and heuristics.

**Search Algorithms (`pyperplan.search`):** [cite: 22]
*   `bfs`: Breadth-First Search (Blind, guaranteed optimal but scales poorly).
*   `astar`: A* Search (Optimal if paired with an admissible heuristic).
*   `wastar`: Weighted A* Search.
*   `gbf`: Greedy Best-First Search (Non-optimal but exceptionally fast for satisficing planning).
*   `ehs`: Enforced Hill-Climbing.
*   `ids`: Iterative Deepening Search.

**Heuristics (`pyperplan.heuristics`):** [cite: 22, 30]
*   `blind`: Returns 0 for goals, 1 for non-goals.
*   `hmax`: Admissible delete-relaxation heuristic. Calculates the maximum cost of achieving subgoals [cite: 30].
*   `hadd` (\(h_{add}\)): Inadmissible delete-relaxation heuristic. Sums the cost of achieving subgoals [cite: 30].
*   `hff` (\(h_{FF}\)): The Fast-Forward heuristic. Inadmissible, but highly informative. It calculates the length of a relaxed plan [cite: 6, 7].
*   `lmcut`: Landmark-Cut heuristic. Admissible and dominant for optimal classical planning [cite: 7, 30].

### 3.4 Selecting the Optimal Strategy


For large PDDL instances such as the Airport domain, obtaining optimal solutions is often computationally infeasible due to exponential state-space growth [cite: 4]. 

*   If the goal is **Satisficing (Agile)** planning (finding any valid plan quickly), **GBFS paired with \(h_{FF}\)** is conclusively the best combination available in `pyperplan` [cite: 6, 7, 11].
*   If the goal is **Optimal** planning, **A* paired with `lmcut`** is the premier choice, though it will severely struggle with large airport groundings within a 600-second limit [cite: 7, 30].

The `pyperplan` search functions return a sequence of `SearchNode` objects. Each node contains an `.operator` attribute representing the specific grounded action taken to reach that state. Calling `.name` on this operator returns the action as a string (e.g., `"(move l1 l2)"`).

---

## 4. The IPC Airport Domain Specifics


The deterministic track of the fourth International Planning Competition (IPC-4) in 2004 introduced several real-world application domains designed to push automated planners to their limits [cite: 5, 31]. Among the most notoriously difficult was the **Airport Ground Traffic Control** domain, engineered by Jörg Hoffmann and Sebastian Trüg [cite: 32].

### 4.3 Expressivity Requirements: STRIPS vs. ADL


The most critical aspect of the Airport domain for `pyperplan` users is its expressivity format.

**Action Description Language (ADL)**
The natural formulation of the Airport domain relies heavily on **ADL** (Action Description Language) [cite: 5, 9]. ADL expands classical STRIPS by allowing:
*   **Negative Preconditions**: E.g., `(not (occupied ?segment))` [cite: 9, 38].
*   **Disjunctive Preconditions**: E.g., `(or (facing-north ?plane) (facing-south ?plane))` [cite: 9, 38].
*   **Conditional Effects**: Effects that only occur if a specific condition holds true upon action execution [cite: 9, 38].

**The Compilation to STRIPS**
`pyperplan` is explicitly a **STRIPS-only** planner [cite: 3, 11]. It completely lacks the capacity to parse or process negative preconditions and conditional effects natively [cite: 2, 39]. Attempting to feed the raw ADL version of the Airport domain to `pyperplan` will result in an immediate parsing exception.

To remedy this for planners with limited expressivity, the IPC-4 organizers utilized a preprocessor based on the Fast-Forward (FF) compilation method devised by Gazen and Knoblock (1997) [cite: 9, 35]. This compiler structurally converts ADL constructs into pure STRIPS by compiling away negative conditions (creating explicit `not-P` predicates) and multiplying out conditional effects [cite: 9, 35].

**Crucial Directive:** To solve Airport problems with `pyperplan` or `up-pyperplan`, you **must** use the pre-compiled STRIPS versions of the domain and problem files provided by the IPC-4 benchmark repositories [cite: 32, 35, 40]. Be warned that this compilation causes an explosion in the number of ground actions, drastically increasing memory overhead [cite: 5, 9].

In addition, the IPC-4 Airport domain occasionally utilizes **Timed Initial Literals (TILs)** to simulate temporary runway blocks from landing aircraft [cite: 32]. TILs represent a temporal feature (PDDL 2.2) [cite: 35, 40]. Since `pyperplan` does not support time, these instances must either be avoided or stripped of their temporal components using static simplifications [cite: 35, 37].

---

## 6. Performance, Scaling, and Timeout Considerations


Applying a purely Pythonic STRIPS planner to PSPACE-hard Munich Airport tasks subject to tight hardware limits introduces immense computational bottlenecks.

### 6.1 Timeout Handling in `unified_planning`


The UP framework allows execution constraints to be dynamically injected into the `OneshotPlanner.solve()` method via the `timeout` parameter [cite: 20].

```python
result = planner.solve(problem, timeout=600)
```

**What happens at timeout?**
If `pyperplan` fails to locate a goal state within 600 seconds, it does **not** crash or raise a Python exception. Instead, the process is safely terminated, and the OM returns a `PlanGenerationResult` object with its `status` attribute explicitly set to `PlanGenerationResultStatus.TIMEOUT` [cite: 20]. The developer must check this enum to handle the failure gracefully.

### 6.2 Best Search Configurations for Agile Limits


For a 600-second deadline, optimality is impossible for large Airport instances. An Agile search paradigm must be adopted. 
*   **Configuration:** The internal solver must use **Greedy Best-First Search (GBFS)** combined with the **Fast-Forward heuristic (\(h_{FF}\))** [cite: 6, 7, 11]. GBFS foregoes the strict cost accumulation of A*, diving purely toward the lowest heuristic estimation [cite: 6, 7]. \(h_{FF}\) estimates the goal distance by computing a relaxed planning graph (ignoring delete effects), which provides exceptionally strong guidance in navigation-heavy domains like Airport [cite: 6, 7]. 
*   In UP, `up-pyperplan` sets Weighted A* with \(h_{add}\) as its absolute default [cite: 22]. To change this, you must pass parameters to the engine:
    ```python
    with OneshotPlanner(name='pyperplan', params={'search': 'gbf', 'heuristic': 'hff'}) as planner:
        planner.solve(problem)
    ```

### 6.3 Memory Exhaustion (MEMOUT)


The biggest threat to `pyperplan` is not the 600s time limit, but RAM exhaustion. `pyperplan` instantiates every grounded action as a distinct Python object. The ADL-to-STRIPS compiled Munich Airport files possess massive operator branches. Consequently, the memory required to simply parse and ground the task can easily exceed standard limits (e.g., 8 GB), resulting in a `PlanGenerationResultStatus.MEMOUT` prior to the search even beginning [cite: 20, 39]. 

To mitigate this, one might run `pyperplan` on `PyPy` instead of `CPython`, which drastically improves execution speed and memory efficiency in recursive search operations [cite: 39, 41].

## 7. Common Pitfalls and Edge Cases


When developing automated evaluation modules for academic benchmarks, slight technical discrepancies can cascade into silent pipeline failures.

### 7.1 PDDL Expressivity Conflicts

As reiterated, **`pyperplan` does not support ADL, negative preconditions, conditional effects, or disjunctive preconditions** [cite: 2, 3, 39].
*   *Bug Manifestation:* If you feed a domain with `:negative-preconditions` into `pyperplan`, the parsing phase will throw a fatal syntax exception [cite: 39]. 
*   *Solution:* The developer must ensure the datasets provided are the `STRIPS` reformulations from IPC-4, not the raw ADL variants [cite: 5, 9, 35]. While UP 1.3.0 correctly parses negative preconditions into its internal `Problem` model, `pyperplan` will reject the task at the engine capability verification step.