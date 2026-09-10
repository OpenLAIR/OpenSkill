# Domain Reference for evo-pddl-plan-formatter

**Responsibility**: Read problem.json, orchestrate solving of all tasks, format plan actions correctly (handling case-sensitivity and syntax requirements), write plan files to specified output paths

**Key functions to implement**: run_all_tasks, write_plan_pddl_format, write_plan_custom_format, format_action_instance

---

### 2.4 Plan Export with `PDDLWriter`


Once a plan is generated, it is stored within the `PlanGenerationResult` as a `unified_planning.plans.SequentialPlan` object [cite: 15, 23]. To export this plan to a file in a compliant format, the `PDDLWriter` is used [cite: 24, 25].

```python
writer = PDDLWriter(problem)
writer.write_plan(result.plan, "solution.plan")
```

**Format Syntax:**
The `PDDLWriter.write_plan()` method inherently generates strings formatted according to standard PDDL plan conventions: `(action-name param1 param2 ... paramN)` [cite: 8]. Each action is printed on a new line. It does *not* utilize the `action_name(param1, param2)` format, which is exclusively used by the `SequentialPlan` class's internal Python `__str__` representation [cite: 16, 26].

### 2.5 Parsing Plans with `PDDLReader.parse_plan()`


For subsequent verification or execution, the `PDDLReader` offers the `parse_plan` method. 
```python
plan = reader.parse_plan(problem, "solution.plan")
```
This method explicitly expects the file to be formatted with standard PDDL parentheses: `(action-name param1 param2 ... paramN)` on each line [cite: 8]. Parentheses-less or function-call style strings will cause parsing errors.

### 2.6 Full Pipeline Code Example


Below is a complete, working Python pipeline integrating all required steps.

```python
from unified_planning.io import PDDLReader, PDDLWriter
from unified_planning.shortcuts import OneshotPlanner, PlanValidator
from unified_planning.engines import PlanGenerationResultStatus, ValidationResultStatus

def solve_airport_problem(domain_path: str, problem_path: str, plan_output_path: str):
    reader = PDDLReader()
    
    # 1. Parse PDDL
    print("Parsing PDDL files...")
    problem = reader.parse_problem(domain_path, problem_path)
    
    # 2. Solve using Pyperplan with a 600s timeout
    print("Initializing pyperplan search...")
    with OneshotPlanner(name='pyperplan') as planner:
        result = planner.solve(problem, timeout=600)
        
        if result.status == PlanGenerationResultStatus.SOLVED_SATISFICING:
            print("Plan found!")
            
            # 3. Write plan to file in (action p1 p2) format
            writer = PDDLWriter(problem)
            writer.write_plan(result.plan, plan_output_path)
            
            # 4. Validate plan
            with PlanValidator(name='tamer') as validator: # Tamer is standard for validation
                val_result = validator.validate(problem, result.plan)
                if val_result.status == ValidationResultStatus.VALID:
                    print("Plan successfully validated.")
                else:
                    print("Plan is invalid!")
                    
        elif result.status == PlanGenerationResultStatus.TIMEOUT:
            print("Planner timed out after 600 seconds.")
        elif result.status == PlanGenerationResultStatus.MEMOUT:
            print("Planner ran out of memory.")
        else:
            print(f"Planning failed with status: {result.status}")

## 5. Plan Output Format Requirements


A frequent stumbling block in planning pipelines involves the syntactic formatting of the output plan. Verification scripts often expect highly specific string formats.

### 5.1 Syntax Conflicts: Standard vs UP Representation


1.  **PDDL Standard Format:** According to PDDL specifications, a plan is a sequence of actions enveloped in parentheses: `(move_aircraft plane1 loc1 loc2)` [cite: 8, 25]. The `PDDLWriter.write_plan()` method inherently produces this exact string syntax [cite: 8].
2.  **UP Internal String Format:** If one calls Python's native `print(result.plan)`, the `unified_planning` library utilizes its internal `__str__` method. This prints the action in a functional programming style: `move_aircraft(plane1, loc1, loc2)` [cite: 16, 26].
3.  **PDDLReader Requirements:** The `PDDLReader.parse_plan()` utility strictly enforces the parenthesized PDDL format. It will crash or return an empty sequence if fed the functional `action(param)` style [cite: 8].

### 5.2 Manual Custom Formatting


If a downstream application or a specific validation script rigidly demands the `action_name(param1, param2, ...)` format—one action per line—and `PDDLWriter` does not suffice, the string must be constructed manually.

The `SequentialPlan` object in UP contains an `actions` property, which is an iterable of `ActionInstance` objects [cite: 15, 25].

```python
def write_custom_plan_format(plan, filename):
    with open(filename, 'w') as f:
        for action_instance in plan.actions:
            action_name = action_instance.action.name
            # Extract arguments
            params = [param.name for param in action_instance.actual_parameters]
            param_string = ", ".join(params)
            
            # Format: action_name(param1, param2)
            formatted_action = f"{action_name}({param_string})"
            f.write(formatted_action + "\n")
```

If a mismatch occurs and you need to parse this custom format back into UP, you cannot use `PDDLReader.parse_plan()`. You would be required to write a custom regex parser to extract the strings and map them back to the `Problem`'s action space using the `problem.action(name)` method.

---

### 7.2 Case-Sensitivity Discrepancies

A highly obscure but common pitfall involves string case-sensitivity. The PDDL language specification dictates that variable and action names are case-insensitive. To standardize this, the `unified_planning` `PDDLReader` aggressively forces all parsed text into **lower-case** [cite: 8].
*   *Consequence:* If your source PDDL defines an action `(PushBack_Plane1)`, it will be internally modeled as `pushback_plane1`. When `PDDLWriter.write_plan()` dumps the plan, the string will be completely lower-cased. If an external validation tool utilizes case-sensitive string matching against the original PDDL file, validation will falsely fail.
*   *Solution:* Downstream validators must convert all strings to lower-case prior to evaluation.