To verify the correctness of your PDDL planning solution for the Travelling Purchase Problem (TPP) without relying on the solver's output, you can implement a surrogate test suite using the following anchors and invariants.

### 1. Dataset-Level Statistical Invariants
These invariants must hold for any valid plan in the TPP domain. You can use these to perform "sanity checks" on the generated plan file before or after validation.

*   **Action Sequence Completeness:** Every plan must contain at least one `buy` action for every required good specified in the problem's goal state.
*   **Capacity Constraint (If applicable):** If the domain uses "levels" to represent capacity, the sum of loaded goods (tracked via `load` actions) must never exceed the truck's maximum capacity level at any point in the sequence.
*   **Connectivity Constraint:** The truck must be at `market_i` to perform a `buy` or `load` action at `market_i`. A `drive` action must precede any action requiring a location change.
*   **Goal Satisfaction:** The final state of the plan must satisfy all predicates listed in the `(:goal ...)` section of the problem file (e.g., `(at-depot truck1 depot1)` and `(stored goods1 depot1)`).

### 2. Cross-Validation Approaches
Since you are using `unified_planning`, you should not rely solely on the planner's internal success flag. Use the `SequentialPlanValidator` as an independent verification step.

*   **Independent Validation Code:**
    ```python
    from unified_planning.io import PDDLReader
    from unified_planning.engines import SequentialPlanValidator
    from unified_planning.plans import SequentialPlan

    def verify_plan(domain_path, problem_path, plan_actions):
        reader = PDDLReader()
        problem = reader.parse_problem(domain_path, problem_path)
        validator = SequentialPlanValidator()
        
        # Convert your plan text to a list of ActionInstance objects
        # This ensures the plan is checked against the PDDL semantics
        plan = SequentialPlan(plan_actions)
        
        result = validator.validate(problem, plan)
        assert result.status.name == "VALID", f"Plan invalid: {result.log_messages}"
    ```

### 3. Benchmarks and Reference Implementations
The Travelling Purchase Problem is a standard IPC (International Planning Competition) domain. You can use these resources to find small, verifiable instances:

*   **IPC-5 Benchmarks:** The TPP domain was featured in the 5th International Planning Competition (IPC-5). You can find the original domain and problem files in the [IPC-5 repository](https://github.com/potassco/pddl-instances).
*   **Small Instance Testing:** Use the smallest instances (e.g., `task01.pddl`) to manually trace the plan. For a tiny TPP instance:
    *   **Input:** 1 truck, 1 depot, 1 market, 1 good.
    *   **Expected Plan:** `drive(truck, depot, market)` → `buy(truck, good, market, ...)` → `load(good, truck, market, ...)` → `drive(truck, market, depot)` → `unload(good, truck, depot, ...)`.
    *   **Assertion:** Assert that the sequence of locations visited by the truck follows a valid path in the graph defined in the problem file.

### 4. Pytest Assertion Strategy
Hard-code these assertions into your `pytest` suite to ensure the output adheres to the domain logic:

```python
import pytest

def test_plan_structure(plan_file):
    with open(plan_file, 'r') as f:
        actions = f.readlines()
    
    # Invariant: Plan must not be empty
    assert len(actions) > 0, "Plan is empty"
    
    # Invariant: Every plan must end with an unload or similar goal-achieving action
    assert "unload" in actions[-1].lower(), "Plan does not end with an unload action"

def test_no_illegal_jumps(plan_file):
    # Logic: If the plan contains 'drive(truck, A, B)' and then 'buy(truck, G, C)',
    # verify that C == B.
    # This can be implemented by parsing the actions and tracking the truck's state.
    pass
```