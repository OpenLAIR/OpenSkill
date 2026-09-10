To verify the temperature controller's performance without relying on the implementation itself, you can use the following engineering invariants and verification anchors derived from control theory.

### 1. Independently Computable Reference Values
For a first-order thermal system defined by $\frac{dT}{dt} = \frac{1}{\tau} (K \cdot u(t) + T_{ambient} - T(t))$, the step response is analytically defined.

*   **Step Response Formula**: Given a step input $u(t) = U_{step}$ starting at $t=0$ from initial temperature $T_0 = T_{ambient}$, the temperature at time $t$ is:
    $$T(t) = T_{ambient} + K \cdot U_{step} \cdot (1 - e^{-t/\tau})$$
*   **Verification Anchor (Calibration)**: If you apply a constant heater power $U_{step} = 50.0\%$ and the system starts at $T_{ambient} = 18.0^\circ\text{C}$, with $K=0.12$ and $\tau=40.0$ (from `verification_params.json`), the temperature at $t=40.0\text{s}$ (one time constant) must be:
    $$T(40) = 18.0 + 0.12 \cdot 50.0 \cdot (1 - e^{-40/40}) = 18.0 + 6.0 \cdot (1 - 0.3679) \approx 21.79^\circ\text{C}$$
    *   **Assertion**: `assert abs(data_at_40s - 21.79) < 0.5` (allowing for noise).

### 2. Dataset-Level Statistical Invariants
The output logs must satisfy these physical and control-theoretic constraints:
*   **Monotonicity (Calibration Phase)**: During the calibration step (constant power input), the temperature must be monotonically non-decreasing (ignoring noise).
    *   *Invariant*: `all(data[i+1].temp >= data[i].temp - noise_std for i in range(len(data)-1))`
*   **Steady-State Error**: The final temperature $T_{final}$ must satisfy $|T_{final} - 22.0| < 0.5^\circ\text{C}$.
*   **Safety Bound**: $T(t)$ must never exceed $30.0^\circ\text{C}$ at any time $t$.
    *   *Invariant*: `assert max(d['temperature'] for d in control_log['data']) < 30.0`
*   **Settling Time**: Based on the 2% criterion for a first-order system, the settling time $T_s \approx 4\tau$. Given $\tau=40.0$, $T_s$ should be approximately $160\text{s}$. The requirement is $< 120\text{s}$, which implies the controller must be tuned more aggressively than the open-loop system.

### 3. Cross-Validation Approaches
*   **Numerical Verification**: Use `scipy.optimize.curve_fit` in your test suite to independently fit the `calibration_log.json` data to the model $T(t) = A + B(1 - e^{-t/C})$.
    *   Compare the resulting $B$ (which corresponds to $K \cdot U_{step}$) and $C$ (which corresponds to $\tau$) against the values in `estimated_params.json`.
    *   *Code Snippet*:
        ```python
        def model(t, K, tau, T_amb, U):
            return T_amb + K * U * (1 - np.exp(-t/tau))
        # Use scipy.optimize.curve_fit to verify estimated_params.json
        ```
*   **Integral Check**: The integral of the error over time (IAE) can be computed from `control_log.json` to verify that the controller is actually minimizing error over the 150s duration.

### 4. Benchmarks and Reference Implementations
*   **SIMC Tuning Rules**: For a first-order system $G(s) = \frac{K}{\tau s + 1}$, the SIMC PI controller gains are:
    *   $K_p = \frac{1}{K} \frac{\tau}{\tau_c}$
    *   $\tau_I = \min(\tau, 4\tau_c)$
    *   Where $\tau_c$ is the desired closed-loop time constant (tuning parameter). To meet the settling time $<120\text{s}$, you can set $\tau_c \approx 30\text{s}$.
*   **Reference Oracle**: Use the analytical step response formula provided in Section 1 to generate a "golden" dataset in your test suite. If the simulator's output deviates from this curve by more than the expected noise floor ($3 \times \text{noise\_std}$), the simulator or the controller logic is flawed.