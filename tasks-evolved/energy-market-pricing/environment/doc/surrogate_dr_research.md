To verify the correctness of the market-clearing and impact analysis, you can implement a `pytest` suite that enforces physical and economic invariants derived from DC-OPF theory.

### 1. Dataset-Level Statistical Invariants
These assertions verify the integrity of the optimization output based on fundamental power system properties.

*   **Cost Monotonicity:** Relaxing a transmission constraint (increasing thermal capacity) expands the feasible region of the optimization problem. Therefore, the total system cost in the counterfactual scenario must be less than or equal to the base case cost.
    *   `assert cf_total_cost <= base_total_cost`
*   **LMP Convergence:** Congestion is the primary driver of price separation (LMP differences) in DC-OPF. Relieving congestion on a line should generally reduce the price spread between the buses connected by that line.
    *   `assert abs(cf_lmp_bus_i - cf_lmp_bus_j) <= abs(base_lmp_bus_i - base_lmp_bus_j)` (for the buses connected by the relaxed line).
*   **Binding Line Definition:** A line is considered "binding" if its loading level is $\ge 99\%$.
    *   `assert loading_pct >= 99.0` for any line included in the `binding_lines` list.
*   **Congestion Relief Flag:** If the line connecting bus 64 and 1501 was binding in the base case, and the capacity was increased, the `congestion_relieved` flag must be `true` if the new loading is $< 99\%$.

### 2. Independently Computable Reference Values
While exact LMPs depend on the specific network topology, you can verify the **Shadow Price relationship** using the KKT conditions of the DC-OPF:

*   **Shadow Price Interpretation:** The LMP at any bus $i$ is defined as $\lambda_i = \lambda_{ref} + \sum_{k \in \text{lines}} SF_{i,k} \cdot \mu_k$, where $\lambda_{ref}$ is the system marginal price (often the slack bus LMP), $SF_{i,k}$ is the shift factor of bus $i$ on line $k$, and $\mu_k$ is the shadow price (congestion rent) of line $k$.
*   **Verification:** If you identify a line $k$ that is binding in the base case but not in the counterfactual, the change in LMP at any bus $i$ should be proportional to the shadow price of that line:
    *   $\Delta LMP_i \approx -SF_{i,k} \cdot \mu_k^{base}$
    *   You can hard-code a check that the `delta` in `buses_with_largest_lmp_drop` is negative for buses that were "downstream" of the congestion.

### 3. Cross-Validation Approaches
To independently verify the optimization results without relying on the skill's internal logic:

*   **Alternative Solver Check:** Use `cvxpy` to solve the DC-OPF independently.
    ```python
    import cvxpy as cp
    # Define variables: theta (angles), p_gen (generation)
    # Constraints: 
    # 1. B * theta = p_gen - p_load
    # 2. -limit <= B_line * (theta_from - theta_to) <= limit
    # 3. p_min <= p_gen <= p_max
    # Objective: min sum(cost_i * p_gen_i)
    ```
*   **Dual Variable Extraction:** Ensure the solver is configured to return dual variables (shadow prices). In `cvxpy`, this is accessed via `constraint.dual_value`. These dual values are the authoritative source for LMPs and MCPs.

### 4. Benchmarks and Reference Implementations
*   **MATPOWER Case Files:** Use standard IEEE test cases (e.g., IEEE 14, 30, or 118 bus systems) available in the [MATPOWER repository](https://matpower.org/). These provide known optimal dispatch values for standard constraints.
*   **Test Oracle:** Run the `network.json` through a known-good DC-OPF solver (like `PyPSA` or `MATPOWER` itself) to generate a "golden" `report.json`. Assert that your skill's output matches these values within a tolerance (e.g., `pytest.approx(value, abs=1e-2)`).