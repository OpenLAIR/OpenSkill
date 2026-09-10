# A Comprehensive Analysis of Python-Based PDDL Planning for the Travelling Purchase Problem Utilizing unified_planning and pyperplan

**Key Points:**
*   The `unified_planning` (UP) library offers a robust Python interface for parsing, manipulating, and solving PDDL problems [cite: 1, 2].
*   `pyperplan` is a lightweight, Python-native heuristic search planner focused on education and prototyping, supporting a strict STRIPS subset of PDDL [cite: 3].
*   Through the `up-pyperplan` integration, users can invoke `pyperplan` directly within the UP framework, configuring search algorithms (like A* or Greedy Best-First Search) and heuristics (like FF or LM-cut) [cite: 4, 5].
*   The Travelling Purchase Problem (TPP) is a complex logistics domain from the International Planning Competition (IPC). Its propositional PDDL version uses "levels" to encode quantities and capacities because pure STRIPS lacks numeric variables [cite: 6, 7].
*   While `pyperplan` is highly accessible, it may struggle with the combinatorial explosion inherent in large TPP instances, making fallbacks to C++ planners like Fast Downward a pragmatic alternative [cite: 3, 8].

**Overview**
The integration of automated planning into modern software engineering requires seamless interfaces between declarative domain definitions and programmatic execution. The Planning Domain Definition Language (PDDL) remains the *de facto* standard for specifying classical planning problems. Solving these problems using Python requires bridging the gap between formal logic representations and executable algorithms.

**The Travelling Purchase Problem**
The Travelling Purchase Problem (TPP) generalizes the classical Travelling Salesman Problem by introducing markets, depots, and goods. An agent must navigate a network to purchase required goods at varying quantities while respecting truck carrying capacities. Solving this using purely propositional logic (STRIPS) necessitates complex workarounds, such as encoding integer quantities as discrete, sequential objects known as "levels". 

**Tooling Selection**
The `unified_planning` framework acts as a meta-interface, allowing developers to write solver-agnostic code [cite: 2, 9]. `pyperplan` serves as the underlying engine. While `pyperplan` is an elegant tool for understanding planning algorithms, its pure-Python implementation presents performance ceilings [cite: 3]. This report details the API mechanics, theoretical underpinnings, formatting strategies, and practical implementations required to build a utility module for TPP tasks.

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

### SequentialPlanValidator API
Plan validation ensures that a generated sequence of actions correctly transitions the environment from the initial state to a state satisfying all goal conditions. In UP, this is handled by the `PlanValidator` or `SequentialPlanValidator` [cite: 15, 21, 22].

```python
from unified_planning.shortcuts import PlanValidator
from unified_planning.engines import ValidationResultStatus

with PlanValidator(problem_kind=problem.kind) as validator:
    validation_result = validator.validate(problem, result.plan)
    if validation_result.status == ValidationResultStatus.VALID:
        print("Plan is valid!")
```
The validator strictly checks preconditions and applies effects sequentially. If the final state entails the goal, it returns a `VALID` status [cite: 15].

### Serialization with Pickle
The UP object hierarchy (including `Problem`, `Fluent`, `ActionInstance`, and `FNode` syntax tree elements) is largely composed of pure Python objects designed immutably via a central `Environment` object. Consequently, standard Python `pickle` serialization generally works for `SequentialPlan` objects. However, because UP relies heavily on a singleton-like `Environment` to ensure uniqueness of `FNode` expressions (the abstract syntax tree nodes for logic), deserializing a plan in a completely fresh Python process requires ensuring that the target problem shares the exact same variable references, or you must rely on UP's native Protobuf/JSON exporters for cross-process communication.

### Compatibility
The `unified_planning` version 1.3.0 is highly stable, but when pairing it with external solvers like `pyperplan`, users depend on the wrapper package `up-pyperplan`. The version `up-pyperplan 1.1.0` supports classical symbolic state variables and hierarchical typing, strictly aligning with pyperplan's STRIPS capabilities [cite: 4]. Compatibility issues are rare in basic STRIPS tasks, provided the Python environment satisfies `pyperplan`'s requirement of Python \(\geq 3.6\) [cite: 3].

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

### PDDL Feature Support
`pyperplan` supports a highly restricted fragment of PDDL: **STRIPS without action costs** [cite: 3, 23].
*   **Supported Requirements:** `:typing` (hierarchical types), `:strips`.
*   **Unsupported Features:** `:numeric-fluents` (math operations, metrics), `:action-costs`, `:equality`, conditional effects (`:conditional-effects`), universal/existential quantification, and durative actions [cite: 3, 26]. 
If a TPP domain relies on `:action-costs` to evaluate the cheapest route, `pyperplan` will ignore or fail to parse these optimization metrics. Therefore, you must use a purely propositional (satisficing) encoding of TPP for `pyperplan`.

## 3. Travelling Purchase Problem (TPP) in PDDL

The TPP is a logistics routing problem introduced in IPC-5 [cite: 6, 27, 28]. It is an NP-hard generalization of the Travelling Salesman Problem [cite: 6, 7]. The agent must travel a graph of connected markets to purchase specific quantities of goods and transport them to a depot, minimizing travel and purchase costs.

### The Standard Propositional Encoding
Because classical planners historically lacked numeric fluents, IPC domains often relied on a "level" encoding to simulate numbers. This is known as the propositional or STRIPS encoding of TPP [cite: 7].

**Levels:**
Instead of variables like `(amount_goods_in_truck = 3)`, the domain defines abstract objects representing integers: `level0`, `level1`, `level2`, etc. [cite: 7]. A static predicate defines their sequence:
`(next level0 level1)`, `(next level1 level2)`.
If a truck loads a good, a precondition checks its current capacity `(capacity ?truck level2)`, and the effect updates it to the next lower level `(capacity ?truck level1)` by traversing the `next` relation backwards.

### Typical Actions
A typical `domain.pddl` for TPP declares the following actions [cite: 7, 29]:

1.  **`drive`**: Moves a truck between locations.
    *   *Parameters*: `?t - truck`, `?from - place`, `?to - place`
    *   *Preconditions*: `(at ?t ?from)`, `(connected ?from ?to)`
    *   *Effects*: `(not (at ?t ?from))`, `(at ?t ?to)`

2.  **`buy`**: Purchases goods at a market, altering the market's inventory levels.
    *   *Parameters*: `?t - truck`, `?g - goods`, `?m - market`, `?l_current - level`, `?l_next - level`
    *   *Preconditions*: `(at ?t ?m)`, `(on-sale ?g ?m ?l_current)`, `(next ?l_next ?l_current)`
    *   *Effects*: `(not (on-sale ?g ?m ?l_current))`, `(on-sale ?g ?m ?l_next)`

3.  **`load`**: Transfers purchased goods into the truck, consuming truck capacity.
    *   *Parameters*: `?g - goods`, `?t - truck`, `?m - market`, `?cap_current - level`, `?cap_next - level`, `?amount_current - level`, `?amount_next - level`

4.  **`unload`**: Drops goods at a depot to satisfy the goal.
    *   *Parameters*: `?g - goods`, `?t - truck`, `?d - depot`, `... levels ...`

### Problem Structure
A standard `problem.pddl` defines:
*   **Objects**: `truck1 - truck`, `market1 market2 - market`, `goods1 goods2 - goods`, `level0 level1 level2 - level`.
*   **Init State**: The graph connectivity `(connected market1 depot1)`, the sequence of levels `(next level0 level1)`, initial truck capacities `(capacity truck1 level2)`, and starting locations.
*   **Goal**: The requirement that certain goods reach specific levels at the depot `(stored goods1 level2)`.

## 4. Plan Output Format

A crucial aspect of utility modules is converting internal plan representations to required output strings.

### The unified_planning ActionInstance Format
As previously noted, `str(action)` in the UP library yields `action_name(arg1, arg2)` [cite: 13]. However, classical PDDL evaluators (like VAL) often expect a parenthesized, space-separated format: `(action_name arg1 arg2)` [cite: 12].

### Extracting and Formatting Actions
To custom-format a plan, you must interrogate the properties of the `ActionInstance` object.
The available properties are [cite: 18, 30]:
*   `action.action.name`: The string name of the lifted action operator (e.g., `"drive"`).
*   `action.actual_parameters`: A tuple of the parameters applied to the action. These are typically `FNode` objects representing the domain constants/objects [cite: 18, 30]. 

To build the `action_name(arg1, arg2, ...)` format explicitly:
```python
def format_action_up_style(action_instance):
    name = action_instance.action.name
    params = [str(p) for p in action_instance.actual_parameters]
    return f"{name}({', '.join(params)})"
```

To build the standard PDDL validator format `(action_name arg1 arg2)`:
```python
def format_action_pddl_style(action_instance):
    name = action_instance.action.name
    params = [str(p) for p in action_instance.actual_parameters]
    return f"({name} {' '.join(params)})"
```

## 5. Common Pitfalls and Edge Cases

### Case Sensitivity Issues
The PDDL standard designates all identifiers as case-insensitive. The `PDDLReader` enforces this by downcasing all parsed symbols [cite: 10, 12]. Consequently, an action defined as `(DRIVE TRUCK1 MARKET1)` in the PDDL file will yield an `ActionInstance` whose name is `"drive"` and parameters are `"truck1"`, `"market1"`. If a post-processing validation script compares output using exact string matching against the original uppercase file, it will fail unless normalized [cite: 10].

### Validation Strictness and Exact String Matching
If your automated validator script checks `plan_actions_str == pred_plan_actions_str`, you face a brittle pipeline. Planning is a highly degenerate problem space—meaning multiple completely valid, optimal plans can exist for a single problem [cite: 31]. 
*   **Determinism:** `pyperplan` is largely deterministic if the Python environment dictionary ordering is stable (Python 3.7+ ensures insertion-order dicts). If you supply the exact same problem with the exact same heuristic and search (e.g., A* with `hadd`), you will receive the exact same plan.
*   **Slight Variants:** Altering the heuristic (e.g., using `hff` instead of `hadd`) or changing the order of declarations in the PDDL file will drastically alter the action sequence output [cite: 8, 32]. An exact string match is an anti-pattern in planning evaluation; a robust pipeline must use a semantic validator like UP's `PlanValidator` or the C++ `VAL` tool [cite: 15, 24].

### TPP Level Encodings and Memory
The "level" encoding of the TPP is notorious for state-space explosion [cite: 7]. A truck navigating multiple markets managing permutations of level transitions creates massive branching factors. Because `pyperplan` evaluates states in Python, attempting to solve a TPP problem with more than a dozen levels and a handful of trucks will reliably trigger `MemoryError` or extreme timeouts [cite: 3, 25].

## 6. Alternative Approaches if pyperplan Fails

When `pyperplan` times out or exhausts memory, a resilient utility module must gracefully degrade to alternative solvers.

### Built-In Alternative Planners
`unified_planning` supports several high-performance C++ engines out-of-the-box, assuming they are installed [cite: 9, 21, 33]:
*   **Fast Downward (`fast-downward`)**: The gold standard of classical planning. Written in C++, it easily handles massive state spaces and complex IPC domains [cite: 2, 14, 21].
*   **Tamer (`tamer`)**: Handles classical and temporal problems [cite: 1, 13].
*   **ENHSP (`enhsp`)**: Excellent for problems that require numeric PDDL capabilities, bypassing the need for clunky "level" encodings [cite: 9, 14].

You can implement fallback logic using UP's dynamic resolution:
```python
planners = ["pyperplan", "fast-downward", "tamer"]
for planner_name in planners:
    with OneshotPlanner(name=planner_name) as planner:
        result = planner.solve(problem)
        if result.plan:
            break
```

### Direct pyperplan Execution
If UP encapsulation proves problematic, `pyperplan` can be executed directly.
**CLI Invocation:**
```bash
pyperplan -H hff -s gbf domain.pddl problem.pddl
```
This generates a file named `problem.soln` [cite: 3, 20].

**Native Python API:**
```python
from pyperplan import _parse, _ground, _search
from pyperplan.pddl.parser import Parser

parser = Parser("domain.pddl", "problem.pddl")
domain, problem = parser.parse_domain_and_problem()
task = _ground(problem)
# Initialize heuristic and search manually...
```
Native `pyperplan` plan files (`.soln`) contain LISP-like strings: `(drive truck1 depot1 market1)` [cite: 20]. Reading this format simply requires stripping the parentheses and splitting by spaces to convert to the desired output.

## 7. Working Code Examples

The following is a production-ready, highly defensive Python utility module designed to parse a JSON configuration file, solve TPP tasks via `unified_planning` and `pyperplan`, format the output, validate the plan, and provide graceful fallbacks.

```python
import json
import logging
from pathlib import Path
from typing import List, Optional

# unified_planning imports
import unified_planning as up
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner, PlanValidator
from unified_planning.engines import PlanGenerationResultStatus, ValidationResultStatus

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def format_action_to_function_call(action_instance: up.plans.ActionInstance) -> str:
    """
    Converts a UP ActionInstance into the format: action_name(arg1, arg2, ...)
    """
    name = action_instance.action.name.lower() # Ensure lowercase per UP standard
    params = [str(p).lower() for p in action_instance.actual_parameters]
    return f"{name}({', '.join(params)})"

def solve_tpp_task(domain_path: str, problem_path: str, planner_name: str = "pyperplan") -> Optional[List[str]]:
    """
    Reads PDDL files, solves the task using the specified planner,
    validates the output, and returns a list of formatted action strings.
    """
    logger.info(f"Parsing domain: {domain_path} | problem: {problem_path}")
    reader = PDDLReader()
    
    try:
        # PDDLReader parses into the UP Problem object model
        problem = reader.parse_problem(domain_path, problem_path)
    except Exception as e:
        logger.error(f"Failed to parse PDDL files: {e}")
        return None

    # Configure pyperplan with Greedy Best-First Search and FF heuristic for faster solving
    planner_params = {}
    if planner_name == "pyperplan":
        planner_params = {"search": "gbf", "heuristic": "hff"}

    logger.info(f"Invoking planner: {planner_name}")
    try:
        with OneshotPlanner(name=planner_name, params=planner_params) as planner:
            result = planner.solve(problem)
            
            if result.status in (PlanGenerationResultStatus.SOLVED_SATISFICING, 
                                 PlanGenerationResultStatus.SOLVED_OPTIMALLY):
                plan = result.plan
                logger.info("Plan successfully generated.")
                
                # Validate the plan semantically
                with PlanValidator(problem_kind=problem.kind) as validator:
                    val_result = validator.validate(problem, plan)
                    if val_result.status == ValidationResultStatus.VALID:
                        logger.info("Plan is logically VALID.")
                    else:
                        logger.warning("Plan generated but flagged as INVALID by validator.")
                
                # Format the actions
                formatted_actions = [format_action_to_function_call(a) for a in plan.actions]
                return formatted_actions
            
            elif result.status == PlanGenerationResultStatus.TIMEOUT:
                logger.error("Planner timed out. The TPP state space may be too large.")
            else:
                logger.error(f"No plan found. Planner status: {result.status.name}")
                
    except Exception as e:
        logger.error(f"Planner engine encountered an exception: {e}")
        
    return None

def process_tasks_from_json(config_path: str):
    """
    Reads a JSON configuration containing multiple planning tasks,
    attempts to solve them, and writes the output to specified files.
    
    Expected JSON format:
    [
        {
            "domain": "tpp_domain.pddl",
            "problem": "tpp_problem_1.pddl",
            "output": "solution_1.txt"
        }, ...
    ]
    """
    try:
        with open(config_path, 'r') as f:
            tasks = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read JSON config: {e}")
        return

    for task in tasks:
        domain_file = task.get("domain")
        problem_file = task.get("problem")
        output_file = task.get("output")
        
        if not all([domain_file, problem_file, output_file]):
            logger.warning("Skipping invalid task entry in JSON.")
            continue
            
        formatted_plan = solve_tpp_task(domain_file, problem_file, planner_name="pyperplan")
        
        # Fallback mechanism if pyperplan fails
        if formatted_plan is None:
            logger.info("Attempting fallback to Fast Downward planner...")
            formatted_plan = solve_tpp_task(domain_file, problem_file, planner_name="fast-downward")
            
        if formatted_plan:
            try:
                with open(output_file, 'w') as out_f:
                    for action_str in formatted_plan:
                        out_f.write(f"{action_str}\n")
                logger.info(f"Successfully wrote plan to {output_file}\n")
            except Exception as e:
                logger.error(f"Failed to write output file {output_file}: {e}")
        else:
            logger.error(f"Failed to generate any plan for {problem_file}. Writing empty file.")
            with open(output_file, 'w') as out_f:
                out_f.write(";; NO PLAN FOUND\n")

if __name__ == "__main__":
    # Example execution trigger
    config_file = "tasks_config.json"
    if Path(config_file).exists():
        process_tasks_from_json(config_file)
    else:
        logger.error(f"Configuration file {config_file} not found.")
```

### Conclusion
Building a utility to solve the TPP using Python involves navigating the intricacies of state-space theory and API interoperability. While `pyperplan` offers a native, transparent heuristic search environment perfectly suited for academic and educational contexts [cite: 3, 23], the inherent memory restrictions of pure Python mean that complex propositional level encodings (like the IPC TPP domain) must be approached cautiously. Utilizing the `unified_planning` library effectively acts as a safety net, allowing developers to extract clean semantic abstractions from PDDL [cite: 1, 10], gracefully format `ActionInstance` outputs [cite: 18], programmatically validate state transitions [cite: 15, 21], and instantly swap engines when computational limits are breached [cite: 9].

**Sources:**
1. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYQhBPG6hgbQN339tG6ntBFPrbzHGaKkHkLQHlPW6ox-ZOtbZbVuOXzZXCUWv8XAEmkl59awsETNPP0FgMmH_fPnbTPhAVA1cp914nClq7u6FTqSzrtw9Yz1W5y1aAr9Ec4Sfss7Z69RXZnLCMawcA3wVt_NyFzWI45j2PM_OjQQdb5qTFxQ==)
2. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEEiHoMWZJix0jEICiRTDcgIZe4ZF9d-4JuRt3WGLE7h_dsaYRUYVP2enxSd9B36Ef8QQ8nYlZ3dxr7-n7p0I4_EQLrnVemTimiNRgdp11OvAtqROLAL3ZrTGb0qe8GxTRmn-Gq_4m6eW1eyK988rqrbl4Cixc0KvZY1dlTDFiXMb-469xdZYzpFIxPDKvggv091qv3csuG_RuSyX0_7yDXGfGd6_9f2uigsMU0s6R_T912uC-Td4vAPk0=)
3. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHoScfnY6Di8mplyLVEzqhnAZMOoi2Em-9XytFWpgn8qLu_-Fyt18Mlmv24agN8YaNWCKI7a9WDgPDR89KKGwaOFy-l_DbIi92a0gLD2ahKoSeLpFaquPWQ)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJxBZXQZJyFkmp4heYiG4vgTdVnRpY9-M7Rug3dwcE-hcV-rotp8F0eyy-6lQuXde60tNltLDQFwEFLTpmh7of4-XNjRkh87-Mri3UjXVbiuCxpVewmUOWDu0PwdGP)
5. [aiplan4eu-project.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGByojmOcsLM2v0rLtA136sdp1INCsWDUxtvhu1QAM9aqS7Tviiq31Eeu2Q6h3W9Hrx58ec5XxxJadBs4C8sIkeBacleCrFGHMlWq-eIQDazxiyXki_b5sOxLQFu7CABtDNeo_GR5HEUpPuN0KT-qJryeHelm_hpcgUr8-9DNxo01lQ-Fb62Im6LMiLmHyWsgrCAMhSwnYWsIccPXY=)
6. [icaps-conference.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhkfT01CDT7Sn_96A_sN1dztv1zh7dJexaM7_jfY86KeqAo88sCfjJ4AMQLawA8Xb7If2-44JQ3GierbeJK-dknC3Tagboi5kJq5sFbcSIga0JCFAR4yN0VQ9BT1qt4vIeEexCM2s2DedwWJ7JZWZxrk0fJ5-D9_QgVUShXRBd5k4=)
7. [hud.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESDCquG3Rq9nOnRt7zFZ51z8VWVU6yZXxBTArklCOFH5HMw1ojiDkrmEMbTaIVxr-dCiTSOoj2DMTQaT45VmYw1PztJ9JneDUPzGu91enkdFf9LdttLJNrXjxoDguh_GcqT1i_FIipPRbrL2GxmkUQMWQLk7x0ReU6D-EvtG8sPg==)
8. [ufrgs.br](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFj--B8a7jB-rgbt9ZqMZ6MIJiKx9bSOlgp7gnXtY10KyTEUcslr5s4Dt_Ygohm-F4Dn0DYdWzVLEd7JUGPueYYGR7mxVC0_dsLFkOIqQz3hoEK0JChd81_kj57CAQH_B-V6xFDwqNaAItKvps=)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGb5ot4VENSZPXLgsRXdn0gKR_9TDbfnTXSt910_04zfA4lutEk_wO6kqU_KpqtHhOAOaxLEK3IiYeEBZ8-itwHgx7sqW3MU8TpMDwCHuFuT5d3FYo04_bIX_MdW4KTVe78XLHEbfu3)
10. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEywX3ejZRNfwRm4DYi4tGpi6mvM1uQZluoAZKP-S3FToU5xeR8H4azoqf0lMBlNHkK1HjnimBVVsNZO8PMuXzYJfnRXR5-jYpDlIP3jciRYL_gcIpNcJtLBueTZUCHukVYX_9RfY3SWEMHyCtLpD093BThXbhLT02nYVatxQ==)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_-roAx6SXVPhYkIpGEkSYC2i57YLSakAScdketZ-Z3pgMUjaKe8-oApJtg_JjQyxSfWLmylWZpWHLMlMnAgPJyb1Rppe3W6j5MSI_sXNJ2XExkXuqzMfwf69VAhaV9YkUXIDvBpzB0yDEP_vwtVPi-V6hB1P0LuD6UtLggPXI3LgRcGrJ81oSEphIuJPE)
12. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHC-r8Lglq9xtPEGeE_k93LJo-brK92adEnzvSp0PEXnSQTXVlU4ZYLLisQOXh273rmzmXquE0Guq4mUbSscrDpd_ERmltNlfrIwbrzM9guBSwGYUEqds_QAK3TER4rhQI-WqQQ6oFAmAe1mvKESiarXKBmy1dSpYvdgo4TZw==)
13. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFepBvwQI_M5rETcGtjt2YYYlwrrbhYWzLCS6azUb0oGGVnD-_gghQ0CL0gx5HOTbDWeDAhRKTzoo2yyD6DuAzqusXIAVHG4Q-O8gP3JiNHGTOadK6jicIC6wfQ3vaao8BYq5lmfopq19I97ZdBjOfYQf5EXbe7k9_IFyTSzF1ZEqubqlCbyA==)
14. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYAYio9GojOu61lMzzQxkd1tYeCznIrToVfnRFoQDUvzV6QqZwmhcCEtEcsb6MyTYM8DA1NScLk5siYtHk-TUEjkFob4ycDigGaUVmbYL6Yh68B_oBlc4r9YLUA6vxijSXUtcpId03TnD0cpaiGMQ_E6pnDOOb3ul63V6-GJqHoTt9KJ-RvHw=)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE89Cjdfm3ZKGohes00aT9AS6XOFvVbkW_iuIYulv2u521zxwJrRdtmHesfhzKqGXxMqHRLiCDFK6EF99AYN7RJqiQ2qlIP6LVPnrHislmKjSZeR3Q_KjJeh5Ssi6aF2OHsRTGK75GUkPOtlLay5hMUBioqbQMN8E_OpQk=)
16. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHfkn_s7Q0NnBYZkE2jh0TXMqDTgqDmCgDDNpwqTY-l64WkLWLunkKTOfRcPI3qpdlRCpz7Mhv5kShOr2ufxrwKZ6j3TrL4bDfsxczdJQENZTkL2BuPQOqnXE-Y5kdHpozlpr1oDRFBJRCrbImGRIqmdORMyJwYDyp5Pypa5AvplzxdzQlUpO4_jYcQGc6tYBQybw==)
17. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHw1Nhx3BoW_kXJ6IQDpdGz6R4nKUBpWHvMLbwVU8BsS4mMw5M0vg9dFaB52U4-JW1-pw62gzBzYqH8xDb_XuZ6MRtIxZS55qhLrKxtqYc1X3V6lDBz6_Re4tXTv-7H8Sc2IBrvLdyobQQLKeGq9WI6TIhiR73pkPfFhCE=)
18. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoiM9TSOqiKarU4_9DVfzvuturudolx6aokK8Z1QN1xN9GbgJ0eS8HJoxVvEpnfMJAFCASqgHgo3R4IGfSkDsKLFxnw4XS9900YPj3GdLEz-tqedaStqvnPqUASKOXob4A-GlaMFmWJXl659Z3Cia8EFSmfyiMdHAfdxQlV73xzASRLAY=)
19. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH44kUtSjlP-EEX3u1ZZ_C42_N249_07NLZvfb0WxXy1WiC9QFse4LPLZxZXQzvzVf-8nxJG55jTI5lNfYn85W0Vk6qr_VnR_yS2hpB4Sa-bDW0IToAaspohpU-XheIqEqSUAv0kFKpgfDYZ13tq1Uw49ul26N1stKVN-zSYUo=)
20. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMFJFEEYfNAifCoBHQfvncivZEhmlHGhXYXKdjJu2N3uLgIEWWv7SgFWGPO8ZFQQ_QvQ10HMs0aU6zo8DxPmgAPxM2QjYGl_MLLN719Jyr4eYdJqtERUPCKe48jX9vwc1tmJ0yF70lou_noShWfhGzRFBCrWAj-q0=)
21. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJdZUoKWzxtB_d9-CimKtgddTKOVnaLIgNlDYypahow3tg-aEcHPcK858U0OPzmzTu1a3-g6HTJc_P46kLrcagpCRP4Dc-7Ash0Ol_tVLB1dcdg3Ahjs9mkr1ebx7BT83AOm3-ifKZrfQStceMRIPYt9JqNN87CT6MbKnCm_iAZQ8Qz4zONRzJzdnlan0D7JK9bkZdC0068UuCtLffo7SBqQ==)
22. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8FPe_TCY_fxXE3_2EjFr-J9kGgfdZ0JEi_k4rym9U5KEw_sg0MDmcOZCxVjN1OpARoOfgZXCrYRsjsIcf1nn_j3xBgm1XWgYwfy-2H5f0vvzKtB7LkBjTI1ARCCyIJsM4Kf2_tQvPSCg81Tsz-a5TDJlzVaa5KlfqPK4ABRnRBVZWLK72DxEutIdiLz6AmUu2bDVmlLABTYj3WaveK_NHJUYlKj_E1DdxeQ==)
23. [zenodo.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJvvzU1LXTKolji8erNgdPtUO7jniPSfSmdyNDjTF1IiAH-X92-6Q0dFY2TiCuaWXKuCAtMOsH3JuxI5TtPfhsso9adlNG_Tl1aTI-bbS0vmgwmQWP7OQ=)
24. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1HzTYIobwIQISCSOsPXzQ7Ei3uEPzLYlrPDvW-_XnzD5EUsfuiizqRPbZaB24os6B6bxVxu-tNP-wTaOQ-ZNr-LIKFJTjz8VIia8fAXgH_lnTIV3eQBZHlc1AIsl0hNLF0EA-bjcFaNpooXc=)
25. [shen.nz](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFznq8LeNZT55sSeQESBIPZB0DUWLEF1t7ondGPSbDdh9KomWeNX-qU5PTa8ZZ_tKeIqeUG_diihFUv-lbHskRYf2q-e9QNgSMxqLQnqPsojyB-szPTw7LRLlAr_MZMNw==)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHsTfkbb-ZvKTYwtHgFZzwO3inQrc3M-D5Ild0FnHTq_Em_2eJYE_hgcqKfIB6ouKDS3WsZJFXGrIFs8IjPr3jP_X7_FL39HGWUBfyAyogrG35naEkrM3NTqOKBvZbZOLmNYRM5TtvPIUQvQH5lv5PlF3cWuxN54A0mSl3nq8-G9hS3Mi0-_Rgh4AmFvQ5ryyx9zJDoSVgd710p2w==)
27. [planning.wiki](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDEG5uM2lz0-rgv-u-0pVuKqIoUkvlUtkqgewIoKdY3bMcnIxMKcMuaK1tmi35lEZZRf91M_yNfF0Pka1byoQuZILSNTDupC_FJ55N2JeMDmyJzauL58qRvWQ-_VXi5AHkUkkkWmJxRcIsfaY=)
28. [uct.ac.za](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE6V6hi0x_fh0Uaxq7p7PywKMS3zR1_-_P_o17Eogef_L2YQmwQZ2-GU4YFBs6J6Ij1dM2b_jIN2Y9neuXQtRMinrifchUJEScje-tAvEaQ64Soxu-ori5U-ktF-b1y0GaZIt8G3qJLX0E4c0mx1rvYUt_SniX9zIHRRZ33Sn-L)
29. [asu.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2Rh4wxjyLTbCwcavng0ZSGqVAspjgJuvnF-1Koy21kqeviXgmkXt-MP8mVQE4j_qC0i7hGBaB5Efv_f4ZpxhxJIQpv8eJP-vWU1ZTCROVB_jnbPMqbXAc646ud0xV0OScBTB3WNgTZea-)
30. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGRjylr0CUg1dT7DL8slPIMNATnYhR_uHJA2OUSfx2T2ic_nLn6cDOuCuHfRvlKUKyFZcCFOU1zFhp0qAcvO-ZIq389RYg0IwUoqlIDeb8ZW4Al0tThVr3VJRyC7uDpmsG9maZtOXCZu_586LenO4GesXU9JukxQcMKyi8yiErmSyhXQoec64urSpYQ8kJ-E-KhjfqnQ-cEXV3L2Q==)
31. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFTVyeJLFFHYZv0ClM1P9vNlGZSf1N388jf00yHj8oRF9n_ZuIdrPOXmN_4W8ZCU39lt32ecN0TJJ-77txUC_lVvN5TQA3ws5PTYlmAYlIukZ4cdd0qXu4=)
32. [mrlab.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH90sU6kUDhTt-RWrbfGKUcbZ9WqxiM43tsTFrXJhcFDhV1AaiPZbAHT4K7ZSO28tM7yI_7U1buHPc1056n6OwHzrdN6kpWbf1WM05u4Q5DM0OLKTLPjXXExyFC9LJ7fNxQDP4mQ1JXpTg=)
33. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMrq-alk3hEH3r2Sztrn7G52OZilPeJSnxFe1TJzoqveI3TMTTq8_IfDcb6500oNwRHCq5bzt9FGM7Ej8D8luDnSj6epnl2RIx0u7WD6g87KELsNTHr7no77OBHZI3p90NS6BVri065m1nvhtpp0KfB2c=)
