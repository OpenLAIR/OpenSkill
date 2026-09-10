# Domain Reference for evo-thermal-pid-control

**Responsibility**: SIMC/IMC gain calculation (Kp, Ki, Kd), discrete-time PID controller with trapezoidal integration and anti-windup clamping, closed-loop simulation loop management, performance metrics calculation (rise_time, overshoot, settling_time, steady_state_error, max_temp), and JSON serialization of tuned_gains.json, control_log.json, and metrics.json.

**Key functions to implement**: calculate_simc_gains, DiscretePID, run_closed_loop_control, calculate_control_metrics, save_control_results

---

## 2. PID Controller Tuning from Identified First-Order Model Parameters


Once \( K \) and \( \tau \) are known, we must determine the proportional (\( K_p \)), integral (\( K_i \)), and derivative (\( K_d \)) gains. Trial and error (or empirical methods like Ziegler-Nichols, which often cause 20-30% overshoot) are unsuitable for HVAC comfort [cite: 3]. Instead, we use analytical tuning methods based on Internal Model Control (IMC).

### 2.1 IMC (Internal Model Control) and Lambda Tuning


Lambda (\( \lambda \)) tuning is a specific formulation of IMC that designs the closed-loop system to respond as a first-order system with a user-specified closed-loop time constant, \( \lambda \) (often denoted \( \tau_c \)) [cite: 3]. 

For a First-Order system (without dead time, or where dead time \( \theta = 0 \)), the standard IMC PI controller parameters are derived as [cite: 3]:
\[ K_p = \frac{\tau}{K \cdot \lambda} \]
\[ T_i = \tau \]
Where \( T_i \) is the integral time constant. In the parallel PID formulation where \( K_i = K_p / T_i \):
\[ K_i = \frac{K_p}{\tau} = \frac{1}{K \cdot \lambda} \]

**Choosing \( \lambda \)**: 
*   \( \lambda \) dictates the speed of the response. A smaller \( \lambda \) yields aggressive, fast control; a larger \( \lambda \) yields slow, robust control [cite: 19, 20].
*   For a settling time \( T_{settle} \) (defined as reaching 98% of the final value, which takes approximately 4 closed-loop time constants), we want \( 4\lambda < 120 \) seconds. Thus, \( \lambda < 30 \) seconds.
*   To ensure overshoot < 10% and handle model mismatch, choosing \( \lambda = \tau \) is a standard cautious approach. If \( \tau \approx 40s \), choosing \( \lambda = 30s \) gives a faster-than-open-loop response.

### 2.2 SIMC (Skogestad IMC) Tuning Rules


Developed by Sigurd Skogestad, the SIMC method is a highly regarded modification to standard IMC that improves disturbance rejection for integrating and slow processes [cite: 3, 21]. Standard IMC sets \( T_i = \tau \), which effectively cancels the slow process pole but results in sluggish recovery from load disturbances [cite: 21]. 

SIMC modifies the integral time. For a First-Order system without dead time (\( \theta = 0 \)), the SIMC rules are [cite: 22, 23, 24]:
\[ K_p = \frac{\tau}{K (\tau_c + \theta)} = \frac{\tau}{K \cdot \tau_c} \quad \text{(since } \theta \approx 0) \]
\[ T_i = \min(\tau, 4(\tau_c + \theta)) = \min(\tau, 4\tau_c) \]

Because a pure first-order model lacks dead-time and second-order lags, SIMC mathematically simplifies to a PI controller (\( K_d = 0 \)) [cite: 23, 25]. Derivative action is generally only required to stabilize double-integrating systems or to counteract significant phase lag from second-order dynamics [cite: 21, 26]. For a noisy HVAC system, \( K_d = 0 \) is highly preferable to avoid amplifying sensor noise [cite: 3, 13, 25].

**Ensuring Design Constraints:**
To meet: Overshoot < 10%, Settling Time < 120s, Steady-State Error < 0.5°C:
1.  **Overshoot < 10%**: SIMC tuning inherently provides well-damped responses with minimal overshoot for first-order systems because it targets a first-order closed-loop trajectory. Setting \( \tau_c \) appropriately ensures no overshoot assuming a perfect model [cite: 20].
2.  **Settling Time < 120s**: The closed-loop time constant will be \( \tau_c \). Setting \( \tau_c = 25 \) seconds results in an approximate settling time of \( 4 \times 25 = 100 \) seconds.
3.  **Steady-State Error < 0.5°C**: The presence of the Integral term (\( K_i > 0 \)) guarantees zero steady-state error to step disturbances and setpoint changes, easily satisfying the 0.5°C requirement [cite: 25, 26].

```python
def calculate_simc_gains(K, tau, tau_c):
    """
    Calculates SIMC PI gains for a first-order system.
    tau_c is the desired closed-loop time constant.
    """
    # Prevent division by zero [cite: 27]
    if K == 0 or tau_c == 0:
        raise ValueError("Process gain K and tau_c must be non-zero.")
        
    Kp = tau / (K * tau_c)
    Ti = min(tau, 4 * tau_c)
    Ki = Kp / Ti
    Kd = 0.0 # Derivative action not recommended for pure 1st order SIMC [cite: 21]
    
    return Kp, Ki, Kd
```

### 2.3 Safeguards: Anti-Windup and Derivative Filtering


**Integral Windup** occurs when the actuator saturates (e.g., heater is at 100%), but the temperature is still below the setpoint. The integral accumulator continues to grow massively. When the setpoint is finally reached, the integral term is so large that the heater remains at 100%, causing massive overshoot [cite: 13, 28, 29]. We implement **conditional integration (clamping)**: stop integrating if the output is saturated and the error has the same sign as the output [cite: 28, 30].

**Derivative Filtering**: Although SIMC for first order yields \( K_d = 0 \), if a user manually adds derivative action, the high-frequency sensor noise will cause massive spikes (Derivative Kick) [cite: 13, 25]. We implement a low-pass filter on the derivative term:
\[ D(s) = \frac{K_d \cdot s}{1 + \frac{K_d}{N \cdot K_p} s} \]
Where \( N \) is the filter coefficient (typically 10 to 20) [cite: 31, 32].

---

## 3. Discrete-Time PID Implementation in Python


A mathematical \( C(s) \) controller must be converted to discrete time \( C(z) \) to run in a software loop.

### 3.1 Discretization Mathematics

For a digital implementation with sample time \( \Delta t \):
*   **Proportional**: \( P[k] = K_p \cdot e[k] \)
*   **Integral (Trapezoidal)**: \( I[k] = I[k-1] + K_i \frac{\Delta t}{2} (e[k] + e[k-1]) \)
    *   Trapezoidal (Tustin) integration provides better numerical stability and accuracy than Euler rectangular integration, avoiding frequency warping [cite: 33, 34].
*   **Derivative on Measurement**: To prevent a massive spike in output when the user suddenly changes the setpoint (Derivative Kick), we take the derivative of the *Process Variable* (PV) rather than the error [cite: 25, 28]. 
    \( \frac{de}{dt} = \frac{d(SP - PV)}{dt} = - \frac{dPV}{dt} \) (assuming constant SP).

### 3.2 Complete Python PID Class


Below is a highly robust, production-ready PID implementation [cite: 25, 29, 30, 31, 32].

```python
class DiscretePID:
    def __init__(self, Kp, Ki, Kd, dt, output_min=0.0, output_max=100.0, N=10.0):
        """
        Discrete-time PID Controller with anti-windup, output saturation, 
        derivative on measurement, and low-pass derivative filtering.
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.dt = dt                 # Sample time in seconds
        self.output_min = output_min # e.g., 0% heater
        self.output_max = output_max # e.g., 100% heater
        self.N = N                   # Derivative filter coefficient [cite: 32]

        # State variables
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_measurement = None
        self.prev_derivative = 0.0
        
        # Check for small dt numerical issues [cite: 29, 34]
        if self.dt <= 1e-3:
            raise ValueError("Time step dt is too small, risking division by zero or precision loss.")

    def update(self, setpoint, measurement):
        """
        Computes the PID control action for the current timestep.
        """
        error = setpoint - measurement

        # Handle first timestep: assume previous measurement was the same as current
        # to prevent a massive derivative spike [cite: 29]
        if self.prev_measurement is None:
            self.prev_measurement = measurement
            self.prev_error = error

        # 1. Proportional Term
        P = self.Kp * error

        # 2. Integral Term (Trapezoidal integration) [cite: 33]
        # Tentative integral assuming no saturation
        tentative_integral = self.integral + self.Ki * (self.dt / 2.0) * (error + self.prev_error)

        # 3. Derivative Term (Derivative on measurement, with Low-Pass Filter) [cite: 13, 28]
        # Equation: D[k] = (2*Kd / (2*tau_f + dt)) * (PV[k-1] - PV[k]) 
        #                  + (2*tau_f - dt) / (2*tau_f + dt) * D[k-1]
        # where tau_f = Kd / (Kp * N)
        if self.Kd > 0 and self.Kp > 0:
            tau_f = self.Kd / (self.Kp * self.N)
            # Filter calculation
            alpha = (2.0 * tau_f - self.dt) / (2.0 * tau_f + self.dt)
            beta = (2.0 * self.Kd) / (2.0 * tau_f + self.dt)
            
            D = beta * (self.prev_measurement - measurement) + alpha * self.prev_derivative
        else:
            D = 0.0

        # Sum terms for tentative output
        v = P + tentative_integral + D

        # 4. Output Saturation and Anti-Windup (Clamping) [cite: 28, 29, 30]
        output = v
        
        # Determine if actuator is saturated
        is_saturated = False
        if output > self.output_max:
            output = self.output_max
            is_saturated = True
        elif output < self.output_min:
            output = self.output_min
            is_saturated = True

        # Clamping Anti-Windup Logic:
        # Only accumulate integral if we are NOT saturated, OR if the integration 
        # is helping to UN-saturate the output (error and output have opposite signs)
        if not is_saturated or np.sign(error) != np.sign(output):
            self.integral = tentative_integral

        # Save states for next timestep
        self.prev_error = error
        self.prev_measurement = measurement
        self.prev_derivative = D

        return output

    def reset(self):
        """Clears controller state (bumpless transfer setup)."""
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_measurement = None
        self.prev_derivative = 0.0
```

---

## 4. Simulation Loop Pattern


Software integration requires a specific architectural pattern to handle the state transition between the Calibration (Open-Loop) phase and the Control (Closed-Loop) phase. Data is typically serialized into JSON for subsequent offline analysis and tuning validation.

## 5. Control Performance Metrics Calculation


To scientifically evaluate if the SIMC controller met our constraints, we analyze the closed-loop JSON data to extract the standard metrics: Rise Time, Settling Time, Overshoot, and Steady-State Error (SSE) [cite: 2, 9, 35, 36, 37, 38].

### 5.1 Metric Definitions and Edge Cases

*   **Rise Time ($t_r$)**: Time taken to go from 10% to 90% of the final steady-state value [cite: 9, 36].
*   **Overshoot ($OS$)**: Percentage by which the peak exceeds the steady-state value [cite: 9, 36]. *Edge case*: If the peak is lower than the setpoint (overdamped), overshoot is 0.
*   **Settling Time ($t_s$)**: Time after which the signal stays permanently within a threshold ($\pm 2\%$ or $\pm 0.5$°C) of the steady-state value. The most robust way to calculate this programmatically is to trace backward from the end of the array [cite: 9, 37]. *Edge case*: If it never enters the band, settling time is infinite.
*   **Steady-State Error (SSE)**: The difference between the setpoint and the average temperature over the final \( N \) seconds. *Edge case*: If the signal is highly oscillatory, averaging over an exact number of periods is required; for SIMC first-order, oscillations are minimal [cite: 2, 39].

### 5.2 Python Implementation


```python
def calculate_control_metrics(time_arr, temp_arr, setpoint, threshold_val=0.5, sse_window=20):
    """
    Calculates control performance metrics.
    time_arr: array of time values (starting at t=0 when step was applied)
    temp_arr: array of temperature values
    setpoint: the target temperature
    threshold_val: absolute error threshold for settling time (e.g., 0.5C)
    sse_window: number of points at the end of the array to average for SSE
    """
    t = np.array(time_arr)
    y = np.array(temp_arr)
    
    # 1. Steady State Error
    # Average the last 'sse_window' points
    steady_state_val = np.mean(y[-sse_window:])
    sse = np.abs(setpoint - steady_state_val)
    
    # 2. Overshoot
    peak_val = np.max(y)
    if peak_val > setpoint:
        overshoot_pct = ((peak_val - setpoint) / np.abs(setpoint)) * 100.0
    else:
        overshoot_pct = 0.0

    # 3. Rise Time (10% to 90% of setpoint delta)
    start_val = y
    delta = setpoint - start_val
    target_10 = start_val + 0.10 * delta
    target_90 = start_val + 0.90 * delta
    
    try:
        t_10_idx = np.where(y >= target_10)
        t_90_idx = np.where(y >= target_90)
        rise_time = t[t_90_idx] - t[t_10_idx]
    except IndexError:
        # Edge case: temperature never reached 90%
        rise_time = float('inf')

    # 4. Settling Time (Trace backward method) [cite: 9, 37]
    upper_bound = setpoint + threshold_val
    lower_bound = setpoint - threshold_val
    
    # Find all indices where the signal is OUTSIDE the threshold bounds
    outside_bounds_indices = np.where((y > upper_bound) | (y < lower_bound))
    
    if len(outside_bounds_indices) == 0:
        # Signal was always inside bounds
        settling_time = 0.0
    else:
        # The last time the signal was outside the bounds
        last_outside_idx = outside_bounds_indices[-1]
        
        if last_outside_idx == len(y) - 1:
            # Signal NEVER settled
            settling_time = float('inf')
        else:
            # Settling time is the timestep immediately after the last violation
            settled_idx = last_outside_idx + 1
            settling_time = t[settled_idx] - t

    return {
        "Rise_Time_s": rise_time,
        "Overshoot_pct": overshoot_pct,
        "Settling_Time_s": settling_time,
        "Steady_State_Error_C": sse
    }
```

---

### 7.1 Integral Windup Causing Massive Overshoot

*   **Problem**: If the setpoint is moved from 20°C to 40°C, the error is large and positive. The proportional term immediately drives the heater to 100%. Over the 10 minutes it takes the room to heat up, the discrete integration sum $\sum e \cdot dt$ accumulates a massive value [cite: 28, 29]. By the time the room hits 40°C, $P = 0$, but $I = 5000$. The heater stays at 100%, causing a massive temperature overshoot.
*   **Mitigation**: As shown in the `DiscretePID` class, conditional integration (Dynamic Clamping) solves this. We literally stop executing `self.integral += ...` if the output is at 100% and the error is still positive [cite: 29, 30].

### 7.2 Numerical Issues with Very Small $dt$

*   **Problem**: In software systems, people sometimes sample at very high rates, e.g., $dt = 0.001$ seconds, or they use `time.time()` leading to jitter where $dt \approx 0$ randomly.
*   **Mitigation**: 
    1. The integral term multiplies by $dt$, resulting in values so small they suffer from floating-point truncation (loss of precision) if $K_i$ is small.
    2. The derivative term *divides* by $dt$. If $dt$ is jittery or near zero, the derivative spikes to infinity [cite: 34]. 
    Use a strict, fixed $dt$ execution loop, and ensure $dt > 0.01$s. The provided class explicitly raises a `ValueError` for dangerously small $dt$.

### 7.4 Off-by-One Errors in Settling Time Calculation

*   **Problem**: Attempting to find the settling time by looping forward and breaking when `abs(error) < threshold`. If the signal oscillates, it will cross the threshold early, yield a falsely short settling time, and then bounce back out [cite: 9, 37].
*   **Mitigation**: As implemented in `calculate_control_metrics()`, use NumPy vectorization to identify *all* instances where the threshold is violated, select the final index `[-1]`, and take the timestep immediately following it [cite: 9].

### 7.5 Division by Zero

*   **Problem**: If the step test fails (e.g., heater was broken, $T$ didn't change), then estimated $K \approx 0$. When calculating SIMC gains, $K_p = \tau / (K \cdot \tau_c)$, causing a `ZeroDivisionError`.
*   **Mitigation**: Implement bounds checking and raise explicit domain-specific exceptions. In `calculate_simc_gains`, we explicitly check `if K == 0` and raise an error rather than allowing the program to crash unpredictably.

---