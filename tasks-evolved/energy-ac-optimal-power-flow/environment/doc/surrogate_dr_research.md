To verify the correctness of an AC Optimal Power Flow (ACOPF) solution without relying on the skill's own output, you must implement a **"Validator-as-a-Test"** pattern. Since ACOPF is a constrained optimization problem, the most robust verification is to check if the solution satisfies the physical laws (KCL/KVL) and operational limits defined in `math-model.md`.

### 1. Independently Computable Reference Values (The "Small-Case" Oracle)
For a small subset of the `network.json` (e.g., a 3-bus system), you can manually verify the nodal power balance.
*   **Computation Chain**:
    1.  **Input**: Extract $V_i = |V_i|\angle\theta_i$ and $S^g_k$ from `report.json`.
    2.  **Intermediate**: Calculate branch complex power flows $S_{ij}$ using the $\Pi$-model:
        $S_{ij} = V_i (Y_{ij}^* V_i^* - Y_{ij}^* V_j^*)$ (simplified for nominal tap).
    3.  **Final**: Verify Nodal Balance: $\sum S^g_i - \sum S^d_i - \sum S^s_i = \sum_{j \in \text{adj}(i)} S_{ij}$.
*   **Assertion**: `assert abs(sum_gen - sum_load - sum_losses) < 1e-3` (in MW/MVAr).

### 2. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the solver's internal logic. Hard-code these into your `pytest` suite:

*   **Global Energy Balance**:
    $$\text{Total Generation (MW)} - \text{Total Load (MW)} = \text{Total Losses (MW)}$$
    *   *Assertion*: `assert abs(report['summary']['total_generation_MW'] - report['summary']['total_load_MW'] - report['summary']['total_losses_MW']) < 1.0`
*   **Voltage Magnitude Bounds**:
    For every bus $i$, $v^l_i \leq |V_i| \leq v^u_i$.
    *   *Assertion*: `assert all(b['vmin_pu'] <= b['vm_pu'] <= b['vmax_pu'] for b in report['buses'])`
*   **Branch Thermal Limits**:
    The `flow_from_MVA` must not exceed `limit_MVA`.
    *   *Assertion*: `assert all(b['flow_from_MVA'] <= b['limit_MVA'] * 1.0001 for b in report['most_loaded_branches'])`

### 3. Cross-Validation Approaches
To verify the solver's output, perform a **"Power Flow Verification"** using a different, simpler method (e.g., a standard Newton-Raphson power flow).

*   **Method**: Take the `pg_MW`, `qg_MVAr`, and `vm_pu` (for PV buses) from the `report.json` and treat them as fixed inputs. Run a standard Power Flow (using `pandapower.runpp`) to see if the resulting voltages and angles match the report.
*   **Code Snippet for Test**:
    ```python
    import pandapower as pp
    def test_ac_feasibility_via_pandapower(report, network_json):
        net = pp.from_json(network_json)
        # Apply the dispatch from report.json to the net
        # ... (update net.gen and net.load)
        pp.runpp(net)
        # Check if the resulting voltages match the report within tolerance
        assert np.allclose(net.res_bus.vm_pu, report_vm_pu, atol=1e-3)
    ```

### 4. Benchmarks and Reference Implementations
Use the **MATPOWER Case Library** as your gold-standard oracle.
*   **Source**: [MATPOWER Case Library](https://matpower.org/docs/ref/matpower5.0/case9.html)
*   **Verification Strategy**:
    1.  Download `case9.m` (a standard 9-bus test system).
    2.  Run the skill on this specific input.
    3.  Compare the `total_cost_per_hour` against the known optimal value for `case9` (typically found in the MATPOWER documentation or by running the case in the official MATPOWER/PowerModels.jl environment).
    4.  **Assertion**: `assert report['summary']['total_cost_per_hour'] == pytest.approx(5296.69, rel=1e-3)` (Value specific to standard IEEE 9-bus).