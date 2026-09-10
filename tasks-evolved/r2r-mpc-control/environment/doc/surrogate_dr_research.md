To verify the implementation of your Model Predictive Control (MPC) for the 6-section Roll-to-Roll (R2R) system, you can use the following independent verification anchors and statistical invariants. These are derived from the physical dynamics provided and standard control engineering principles.

### 1. Independently Computable Reference Values
The system dynamics are defined by the coupled equations for tension ($T_i$) and velocity ($v_i$). At the steady-state operating point, the derivatives $\frac{dT_i}{dt}$ and $\frac{dv_i}{dt}$ must be zero.

*   **Steady-State Velocity Constraint:**
    From the tension dynamics $\frac{dT_i}{dt} = \frac{EA}{L_i}(v_i - v_{i-1}) + \frac{1}{L_i}(v_{i-1}T_{i-1} - v_i T_i) = 0$, at steady state:
    $$v_i (EA + T_i) = v_{i-1} (EA + T_{i-1})$$
    Given $v_0 = 0.01$ m/s, $EA = 2400$ N, and initial tensions $T_{ref\_initial}$, you can compute the required steady-state velocities $v_i$ for any tension setpoint.
    *   **Verification:** For a tension change in section 3 from 20N to 44N, the steady-state velocity $v_3$ must adjust to satisfy $v_3 = v_2 \frac{EA + T_2}{EA + T_3}$. Since $v_0$ is fixed, all $v_i$ are deterministic functions of $T_i$. Use this to verify that your controller's steady-state velocities match these calculated values.

### 2. Dataset-Level Statistical Invariants
Your `control_log.json` must satisfy the following physical and operational constraints:

*   **Tension Bounds:** For all $t > 0.5s$, the tension $T_3$ should converge toward 44N. The controller must ensure $T_i \in [5.0, 50.0]$ N for all $i$ at all times.
*   **Settling Time Invariant:** The settling time is defined as the time required for the tension to remain within a $\pm 2\%$ error band of the new setpoint (44N for section 3).
    *   *Assertion:* `abs(tensions[2] - 44.0) <= 0.88` for all $t > (0.5 + \text{settling\_time})$.
*   **Steady-State Error:** The mean error $\frac{1}{N} \sum |T_{i, actual} - T_{i, ref}|$ for the final 1 second of the simulation must be $< 2.0$ N.

### 3. Cross-Validation Approaches
You can verify your linearized $A$ and $B$ matrices independently using `scipy`:

*   **Jacobian Verification:** Use `scipy.optimize.approx_fprime` to numerically compute the Jacobian of the nonlinear dynamics equations at the operating point $(T_{ref\_initial}, v_{ref\_initial})$.
*   **Comparison:** The resulting numerical Jacobian should be nearly identical to your hard-coded `A_matrix` and `B_matrix`.
    ```python
    # Example snippet for pytest
    import numpy as np
    from scipy.optimize import approx_fprime
    
    def dynamics(state_input):
        # Implement the nonlinear dT/dt and dv/dt equations here
        ...
        return np.array([dT1, ..., dv6])
        
    # Compare with your A and B matrices
    numerical_jacobian = approx_fprime(x0, dynamics, epsilon=1e-6)
    assert np.allclose(my_A_matrix, numerical_jacobian[:, :12], atol=1e-3)
    ```

### 4. Benchmarks and Reference Implementations
*   **Standard R2R Dynamics:** The equations provided in the simulator are standard for R2R web handling (see *Branca et al., 2013* and *Yan & Du, 2020*).
*   **Performance Targets:** The targets (steady-state error < 2.0N, settling time < 4.0s) are consistent with high-precision R2R control literature, where tracking errors are typically maintained within 1-2% of the setpoint.
*   **Pytest Assertion Strategy:**
    ```python
    def test_performance_metrics(metrics):
        assert metrics["steady_state_error"] < 2.0
        assert metrics["settling_time"] < 4.0
        assert metrics["max_tension"] < 50.0
        assert metrics["min_tension"] > 5.0
    ```