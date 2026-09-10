# Comprehensive Design and Implementation of a PID Temperature Controller for First-Order Thermal Systems in Python

**Key Points**
*   **System identification** is foundational; extracting accurate process gain and time constants from noisy step-response data ensures control algorithms operate on physical realities rather than theoretical assumptions.
*   The evidence leans toward **Skogestad Internal Model Control (SIMC)** as the most robust analytical tuning method for first-order systems, offering a reliable trade-off between aggressive tracking and robust stability.
*   **Integral windup** and **derivative kick** are the most common causes of instability in software-based controllers; implementing output clamping and calculating the derivative on the measurement (rather than the error) mitigates these risks.
*   While `scipy.optimize.curve_fit` is standard for parameter estimation, the underlying **Levenberg-Marquardt** or **Trust-Region Reflective** algorithms require carefully bounded initial guesses to avoid divergence, especially in noisy HVAC environments.

**Introduction to the Engineering Challenge**
Designing a reusable software module for HVAC temperature control bridges theoretical continuous-time control and practical discrete-time software engineering. A pure first-order thermal system can be modeled mathematically, but translating this into a reliable Python skill module requires handling sensor noise, asynchronous time steps, actuator limits, and numerical edge cases. 

**Bridging Theory and Implementation**
The development process is divided into distinct phases: calibrating the system to find its mathematical model, mathematically deriving the optimal controller gains, constructing a discrete-time controller with anti-windup safeguards, and managing the simulation loop. 

**Evaluating Performance**
Finally, control theory requires rigorous validation. We cannot simply state that a system "works well." We must calculate exact metrics—rise time, overshoot, settling time, and steady-state error—to ensure the controller meets strict environmental constraints.

---

## 1. First-Order Thermal System Identification from Step Response Data

The foundation of analytical controller design is an accurate mathematical model of the process dynamics. For a simple HVAC zone, the system is typically modeled as a first-order ordinary differential equation (ODE) describing the rate of change of temperature.

### 1.1 The First-Order Thermal Model

The heat balance equation for a single-zone thermal system can be approximated as a first-order system:
\[ \frac{dT}{dt} = \frac{1}{\tau} (K \cdot u(t) + T_{ambient} - T(t)) \]
Where:
*   \( T(t) \) is the measured temperature at time \( t \).
*   \( T_{ambient} \) is the ambient (surrounding) temperature.
*   \( u(t) \) is the control input (heater power, usually 0-100%).
*   \( K \) is the **steady-state process gain** (in °C / % power), representing how much the temperature will eventually rise for a 1% increase in heater power.
*   \( \tau \) is the **thermal time constant** (in seconds), representing the time required for the system to reach approximately 63.2% of its final steady-state temperature change.

If we apply a step input \( u(t) = U_{step} \) starting at \( t = 0 \) from an initial steady-state temperature \( T_0 = T_{ambient} \), the analytical solution to this ODE is the standard exponential step response [cite: 1, 2]:
\[ T(t) = T_{ambient} + K \cdot U_{step} \cdot \left(1 - e^{-t/\tau}\right) \]

### 1.2 Estimating Parameters using `scipy.optimize.curve_fit`

To design our controller, we must determine \( K \) and \( \tau \) experimentally. This is achieved by placing the HVAC system in manual mode, applying a constant step input to the heater, recording the temperature over time, and fitting the data to our theoretical exponential equation [cite: 3, 4].

The `scipy.optimize.curve_fit` function uses non-linear least squares to fit a function to data [cite: 5, 6]. It is a wrapper around `scipy.optimize.least_squares` [cite: 7, 8].

#### 1.2.1 Data Requirements
For reliable identification of a system with \( \tau \approx 40 \) seconds:
*   **Duration**: The test must run long enough to approach steady state. A rule of thumb is to collect data for at least \( 3\tau \) to \( 5\tau \) (120s to 200s for \( \tau=40s \)) [cite: 9, 10].
*   **Data Points**: You should have at least 10-20 points per time constant. With \( \tau=40s \), a sampling rate of 1 Hz or 2 Hz (40 to 80 points per \( \tau \)) is excellent [cite: 3].
*   **Excitation**: The step input \( U_{step} \) must be large enough so that the resulting temperature change is clearly distinguishable from the sensor noise (std ~0.1°C) [cite: 3].

#### 1.2.2 Implementation of `curve_fit`
When using `curve_fit`, you must provide the objective function, the independent variable data, the dependent variable data, and, crucially, an initial guess (`p0`) and parameter bounds [cite: 1, 6]. The Levenberg-Marquardt algorithm is the default, but supplying bounds automatically switches the solver to the Trust Region Reflective (`trf`) algorithm, which is highly recommended to prevent unphysical negative values for \( K \) and \( \tau \) [cite: 11, 12].

```python
import numpy as np
from scipy.optimize import curve_fit

def first_order_step_response(t, K, tau, T_amb, U_step):
    """
    Theoretical first-order step response function.
    t: Array of time points
    K: Process gain
    tau: Time constant
    T_amb: Ambient initial temperature
    U_step: Magnitude of the control step input
    """
    return T_amb + K * U_step * (1 - np.exp(-t / tau))

def identify_system_curve_fit(time_data, temp_data, U_step):
    """
    Identifies K and tau using scipy.optimize.curve_fit.
    """
    # Shift time to start at 0
    t = np.array(time_data) - time_data
    T = np.array(temp_data)
    
    # Estimate initial guesses
    T_amb_guess = T
    T_final_guess = np.mean(T[-10:]) # Average of last few points
    K_guess = (T_final_guess - T_amb_guess) / U_step if U_step != 0 else 0.1
    
    # Estimate tau: time it takes to reach 63.2% of the change
    target_temp = T_amb_guess + 0.632 * (T_final_guess - T_amb_guess)
    try:
        # Find first index where temperature exceeds the 63.2% target
        tau_idx = np.where(T >= target_temp)
        tau_guess = t[tau_idx]
    except IndexError:
        tau_guess = 40.0 # Fallback
        
    # Since curve_fit expects the function signature f(x, *params), 
    # we create a wrapper to pass U_step and T_amb as fixed or allow them to float.
    # It is safer to fix T_amb and U_step and only fit K and tau.
    def wrapper_func(t_val, K_val, tau_val):
        return first_order_step_response(t_val, K_val, tau_val, T_amb_guess, U_step)
        
    p0 = [K_guess, tau_guess]
    # Bounds: K > 0, tau > 0 (prevents solver from exploring non-physical negative values)
    bounds = ([0.0, 0.0], [np.inf, np.inf])
    
    try:
        # maxfev handles convergence failures by allowing more iterations [cite: 11]
        popt, pcov = curve_fit(wrapper_func, t, T, p0=p0, bounds=bounds, maxfev=10000)
        K_est, tau_est = popt
        return K_est, tau_est, T_amb_guess, pcov
    except RuntimeError as e:
        print(f"Curve fitting failed to converge: {e}")
        return None, None, None, None
```

### 1.3 Alternative: Using `scipy.optimize.least_squares`

While `curve_fit` is a convenient wrapper, calling `scipy.optimize.least_squares` directly provides more control over the loss function, which is useful for handling outliers. By using a loss function like `soft_l1` or `huber`, you can reduce the influence of massive sensor anomalies [cite: 8, 11].

```python
from scipy.optimize import least_squares

def identify_system_least_squares(time_data, temp_data, U_step):
    t = np.array(time_data) - time_data
    T = np.array(temp_data)
    T_amb = T
    
    # Residuals function
    def residuals(params):
        K_val, tau_val = params
        T_pred = first_order_step_response(t, K_val, tau_val, T_amb, U_step)
        return T - T_pred
        
    # Guesses
    K_guess = (T[-1] - T) / U_step if U_step > 0 else 0.1
    p0 = [K_guess, 40.0]
    
    # trf method supports bounds and robust loss functions [cite: 11]
    res = least_squares(residuals, x0=p0, bounds=(, [np.inf, np.inf]), loss='soft_l1')
    
    if res.success:
        return res.x, res.x[cite: 13]
    else:
        raise ValueError("Least squares optimization failed.")
```

### 1.4 Handling Sensor Noise and Filtering Data

If the sensor has Gaussian noise with a standard deviation of ~0.1°C, fitting directly might be acceptable since least squares estimators are maximum likelihood estimators for Gaussian noise. However, to ensure numerical stability and a cleaner fit, preprocessing the data is highly recommended.

The **Savitzky-Golay filter** (`scipy.signal.savgol_filter`) is ideal here. Unlike a simple moving average which flattens the curve and distorts the time constant, the Savitzky-Golay filter fits a low-degree polynomial over a sliding window, effectively smoothing the data while preserving the steepness of the initial exponential rise [cite: 14, 15, 16].

```python
from scipy.signal import savgol_filter

def filter_temperature_data(temp_data, window_length=15, polyorder=2):
    """
    Applies Savitzky-Golay filter to smooth noisy temperature data.
    window_length must be odd.
    """
    # Ensure window_length is odd and less than data length
    if window_length % 2 == 0:
        window_length += 1
    if window_length > len(temp_data):
        window_length = len(temp_data) - 1 if len(temp_data) % 2 == 0 else len(temp_data)
        
    # mode 'interp' prevents boundary artifacts at the start/end of the array [cite: 17]
    return savgol_filter(temp_data, window_length, polyorder, mode='interp')
```

### 1.5 Evaluating Fit Quality: R-Squared and Errors

To determine if the calibration data successfully modeled a first-order system, we calculate the coefficient of determination (\( R^2 \)) and the Root Mean Square Error (RMSE) [cite: 6, 18].

```python
def calculate_fit_metrics(T_actual, T_predicted):
    # Sum of Squares of Residuals
    ss_res = np.sum((T_actual - T_predicted) ** 2)
    # Total Sum of Squares
    ss_tot = np.sum((T_actual - np.mean(T_actual)) ** 2)
    
    # Division by zero safeguard
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    rmse = np.sqrt(ss_res / len(T_actual))
    
    return r_squared, rmse
```
An \( R^2 \) value close to 1.0 (e.g., >0.95) indicates that a first-order model accurately captures the HVAC thermal dynamics. A lower value might indicate unaccounted higher-order dynamics (like sensor lag) or unmeasured disturbances (like a door opening).

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

### 4.1 Interactions with a Simulator
We assume the existence of an object `sim` representing the HVAC hardware interface or software simulator, containing the methods: `get_temperature()`, `set_heater(power)`, `step()`, and `get_time()`.

### 4.2 Pattern Implementation

```python
import json

def run_simulation_pattern(sim, dt, sim_duration_calib, sim_duration_control, target_sp):
    # Data storage
    log_data = []

    # ==========================================
    # Phase 1: Calibration (Open-Loop Step Test)
    # ==========================================
    print("Starting calibration phase...")
    calibration_power = 50.0 # Apply 50% power
    sim.set_heater(calibration_power)
    
    calib_time = []
    calib_temp = []

    while sim.get_time() < sim_duration_calib:
        t = sim.get_time()
        temp = sim.get_temperature()
        
        calib_time.append(t)
        calib_temp.append(temp)
        
        log_data.append({
            "phase": "calibration",
            "time": t,
            "temperature": temp,
            "heater_power": calibration_power,
            "setpoint": None
        })
        
        sim.step()

    # Perform System Identification
    # Ensure window is odd for Savitzky-Golay
    smoothed_temp = filter_temperature_data(calib_temp, window_length=11, polyorder=2)
    K, tau, T_amb, pcov = identify_system_curve_fit(calib_time, smoothed_temp, calibration_power)
    print(f"Identified Parameters: K = {K:.4f}, tau = {tau:.2f}s")

    # ==========================================
    # Phase 2: Closed-Loop Control
    # ==========================================
    print("Starting closed-loop control phase...")
    
    # Calculate SIMC Tuning Parameters
    # Let's choose lambda (tau_c) to be half of the process time constant for fast tracking
    tau_c = tau * 0.5 
    Kp, Ki, Kd = calculate_simc_gains(K, tau, tau_c)
    print(f"Controller Gains: Kp={Kp:.3f}, Ki={Ki:.3f}, Kd={Kd:.3f}")
    
    # Initialize Controller
    pid = DiscretePID(Kp, Ki, Kd, dt, output_min=0.0, output_max=100.0)
    
    control_start_time = sim.get_time()
    
    while sim.get_time() < (sim_duration_calib + sim_duration_control):
        t = sim.get_time()
        temp = sim.get_temperature()
        
        # Calculate controller output
        heater_power = pid.update(target_sp, temp)
        sim.set_heater(heater_power)
        
        log_data.append({
            "phase": "control",
            "time": t,
            "temperature": temp,
            "heater_power": heater_power,
            "setpoint": target_sp
        })
        
        sim.step()

    # ==========================================
    # Data Logging
    # ==========================================
    with open("hvac_simulation_log.json", "w") as f:
        json.dump(log_data, f, indent=4)
        
    print("Simulation complete. Data logged to hvac_simulation_log.json")
    return log_data
```

---

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

## 6. Specific APIs: NumPy 1.26.4 & SciPy 1.13.0

Working with modern iterations of the SciPy stack requires awareness of changing interfaces.

### 6.1 `numpy.polyfit` vs `numpy.polynomial.Polynomial.fit`
In NumPy 1.26.4, while `np.polyfit` is highly functional, using it to fit higher-order systems can generate a `RankWarning` due to numerical instability in badly conditioned Vandermonde matrices [cite: 40]. The official NumPy documentation explicitly deprecates old polynomial API structures and highly recommends using `np.polynomial.Polynomial.fit()` for new code due to better numerical stability [cite: 40].

If you were to fit a simple linear baseline trend before step analysis:
```python
# Old, discouraged way [cite: 40]
coefficients = np.polyfit(t, y, deg=1) 

# Modern, recommended way in 1.26.4 [cite: 40]
from numpy.polynomial import Polynomial
p = Polynomial.fit(t, y, deg=1)
linear_trend = p(t)
```

### 6.2 `scipy.optimize.curve_fit` Best Practices
In SciPy 1.13.0, `curve_fit` relies on `least_squares` [cite: 7]. 
*   **Signature**: `curve_fit(f, xdata, ydata, p0=None, sigma=None, absolute_sigma=False, check_finite=True, bounds=(-np.inf, np.inf), method=None, jac=None, *, full_output=False, **kwargs)` [cite: 11, 12].
*   **`maxfev`**: If your initial guesses are poor, the algorithm hits the maximum function evaluation limit and throws a `RuntimeError`. Pass `maxfev=10000` via `**kwargs` to prevent this [cite: 11].
*   **Covariance (`pcov`)**: `curve_fit` returns the optimal parameters and a 2D covariance matrix. The diagonal of `pcov` gives the variance of the parameter estimate. The standard error for parameter `i` is `np.sqrt(pcov[i, i])`. Checking these errors helps identify if the model parameters are reliable [cite: 5, 12, 41].

### 6.3 SciPy 1.13.0 Deprecations
If adapting older codebases to SciPy 1.13.0, ensure that you avoid the following recently removed or deprecated items [cite: 42, 43]:
*   Do not use `scipy.signal.step2` or `scipy.signal.lsim2`; they have been removed. Use `scipy.signal.step` and `scipy.signal.lsim` instead [cite: 42].
*   Window functions can no longer be imported directly from the `scipy.signal` namespace. You must access them through `scipy.signal.windows` [cite: 42].

---

## 7. Common Pitfalls and Mitigation Strategies

Bridging control theory and software implementation entails navigating several subtle pitfalls.

### 7.1 Integral Windup Causing Massive Overshoot
*   **Problem**: If the setpoint is moved from 20°C to 40°C, the error is large and positive. The proportional term immediately drives the heater to 100%. Over the 10 minutes it takes the room to heat up, the discrete integration sum $\sum e \cdot dt$ accumulates a massive value [cite: 28, 29]. By the time the room hits 40°C, $P = 0$, but $I = 5000$. The heater stays at 100%, causing a massive temperature overshoot.
*   **Mitigation**: As shown in the `DiscretePID` class, conditional integration (Dynamic Clamping) solves this. We literally stop executing `self.integral += ...` if the output is at 100% and the error is still positive [cite: 29, 30].

### 7.2 Numerical Issues with Very Small $dt$
*   **Problem**: In software systems, people sometimes sample at very high rates, e.g., $dt = 0.001$ seconds, or they use `time.time()` leading to jitter where $dt \approx 0$ randomly.
*   **Mitigation**: 
    1. The integral term multiplies by $dt$, resulting in values so small they suffer from floating-point truncation (loss of precision) if $K_i$ is small.
    2. The derivative term *divides* by $dt$. If $dt$ is jittery or near zero, the derivative spikes to infinity [cite: 34]. 
    Use a strict, fixed $dt$ execution loop, and ensure $dt > 0.01$s. The provided class explicitly raises a `ValueError` for dangerously small $dt$.

### 7.3 Curve Fitting Convergence Failures
*   **Problem**: `scipy.optimize.curve_fit` returning `RuntimeError: Optimal parameters not found`.
*   **Mitigation**: Non-linear optimization requires walking down a gradient. If you initialize $\tau = 1$ when the true $\tau = 1000$, the gradient space is flat, and the algorithm gets lost [cite: 11, 44]. Providing `p0` via analytical estimates (finding the 63.2% point of the step response in the array) guarantees the solver starts in the correct localized valley of the cost function.

### 7.4 Off-by-One Errors in Settling Time Calculation
*   **Problem**: Attempting to find the settling time by looping forward and breaking when `abs(error) < threshold`. If the signal oscillates, it will cross the threshold early, yield a falsely short settling time, and then bounce back out [cite: 9, 37].
*   **Mitigation**: As implemented in `calculate_control_metrics()`, use NumPy vectorization to identify *all* instances where the threshold is violated, select the final index `[-1]`, and take the timestep immediately following it [cite: 9].

### 7.5 Division by Zero 
*   **Problem**: If the step test fails (e.g., heater was broken, $T$ didn't change), then estimated $K \approx 0$. When calculating SIMC gains, $K_p = \tau / (K \cdot \tau_c)$, causing a `ZeroDivisionError`.
*   **Mitigation**: Implement bounds checking and raise explicit domain-specific exceptions. In `calculate_simc_gains`, we explicitly check `if K == 0` and raise an error rather than allowing the program to crash unpredictably.

---

## Conclusion
The design of a reusable Python PID skill module for HVAC first-order systems represents a synthesis of classical control theory, modern numerical optimization, and defensive software architecture. By meticulously handling system identification through bounded Levenberg-Marquardt or Trust Region algorithms, utilizing Skogestad's IMC rules to mathematically guarantee the satisfaction of time-domain constraints, and safeguarding the discrete-time execution loop against integral windup and numerical jitter, engineers can deploy temperature controllers that are both highly responsive and inherently stable.

**Sources:**
1. [allaboutcircuits.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPANuiLgZ21xu2Z9z0Q-T8n64chZeF7VBz67Tjlcn5NphIuzSacNF2no9yrqb6DeEzcDS97KvL_ppSEetc-fNkVxGanW1cP_wyB5dQzjKWCG9Slv-PwpU1i7_EStKwT82036LyAZTj7dCuwJLUxwNjZjO9lT5cy2mtU5x8nN8NRr0B7ZT69NvnbZ0NGE-Yi0W1Yv5jUFBdat2QMc9w_YX8XgNq87eW2UC2RucH3Zt4)
2. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUuZpgm0c0By9ef8sOFjuvS_b-fbICGFLEygBGbPpROR1BNU0DCjKOWG8VmRLKJ3sjrmfl4JA0L72DXTZ0gqQ3yoIPe80AyLqQOl_76W97YDXHZxpQho5kRq6JB8O5dzTSZlyGhQ5tEoCJWQFUIOh3mBkeebMUktszHVdJ2POLvFXJ3m3tMeLahC2gAQyHCDzKYXNSw5PuajEvu2xMMjKzzBd9s3mv6bjZ_x0jGqM3b2GWdT7DmtQW6K2BzIf_)
3. [industrialmonitordirect.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2QaJRHtEt1Kf7UVYHbLSw7AiRXOnleICGkvE-ufI4IxUgPsIrqSSO8-oZaRxO24kkXW5BrMhrklJ4080e2Jmu4PUl__ci6IWMren99_lWWyxmpjIk_zsWb2EtchZbEIuzM10uHPLhiF61Bsgy_RPELBFlXGQxP1tGXmstAZlvX3t32uRtT1_zLo_dn3QwcpfrW4APHbpwLukT6JBlD-16eSCIOBDlC_UOsC19EFiqG4OMxdTe6bkNNIpUoItgsw==)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEK89gDcpekDRue9POeKWMEYeSm-KU1y3lYnU3gwjIWAv3fF1MDHvIwR5zQMxiS-yjRSV7rpkJ0ThH6m1EHIxLnarLYSAq9xGR3YrafePiWY2CX8WOyJD7o-44Pq2Wr5eYhqwKhhbYYaWAKQvWcvrzArKHw6__Hv9xQbMFye2WU2xJ972PRRkWpJ7BXfN63Lh7TAbOkHPwzltA0ix4RqJwOSaDkgoeBwAggf3ExwQZ6U6_oTZRufRUkryXo5tM=)
5. [molssi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGblUd1NRenqPmOwzSqoURlWR3NxDMNDmgDCCkzGOixxvHNULaFTqjAcPqJ9_TSw4Ayw6a4hTGcX-x3dwwXcg1WEEe4kBM7tMFgYhihUDJRaRMy4BwwLuKRWSZnFIrC00DfEIE_FAZrJRTsfKrnUumsf1fSf4LpWPw3MjR7HQbQSVZc)
6. [machinelearningmastery.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZqorPZ1BPi0CNzjZoYMRFdT_Nsiz51KZ7bwu-845pQsCT5GBUc5Jc43aHlNs6t3cEz6fvwijkF577yNrRGq5P_7Cs-UPoD3Z1ZIeMVEGb5qiedmW-6X2gjQCc9FRZwyBWJezKE1UNRoBiMSExPnSlXD_I)
7. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhrhtj3Sn1KrqrJbzK40WWz5RDIhyAecGJPrZ_aKItcoMPyyZHMNjfzOrGDM3wcjAevcBBmtd53Yu7wfbO2JeVjpdGJMF0MqwOtzo3SRgtc5RXhnf9v2R4GIOe85nwWiXz)
8. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFfydpYbgZ8cYG5yiBIKESmZxGPsbARaucBR5CI464V6_jK5W_2BJS1EPoC6BoGhBf6XPYLdvHNzNgGlXYQHrT1-CkCk2ip9aIJHUCFKTpGadg3RSQN5Agpl2hqe2bcfXeJ2jk=)
9. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHVai9lFKFyFUScRhoJW3oFv2HBI67Tf5FdWBLxBSG8WXgsLBnrFxduX0VryQnJRTkaho_9Z5O-UkwxmW-x10qWA2i3jN27SSndupMYaBt-kz2Li_e34eMTUHzgd2irMY4hgnqIOBFQJM00Dw2npiGhMFidYaa-JoHXXzP5sYbQ5lMr_KaacYeChDSFjySq-Qla3ZmmuYi59U-h8ZcHVCPC-u4312NiMpgfIjOo7EHdxuY=)
10. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE43lThpz3MfLCiMg_vehPm5-yfTmueRYLXWvjNgiVoXQFxZRlNO0Nggq6BTk38vlfI4sdv0EZiYlfPlDFFyaBnwnzQzLrYCBfb9RaAx1vJ-bbfG7FFQWKwJRXapOqAmbVTaSTQ-6jNowag1rY486fwkLYk53GAAYoOt1Zvmwpoam5g6xV6FyfgMGg=)
11. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxfCYCyF_-DHejEp3UsGy-7QWEKuOaeVQRxkc0Gme00_SNoGJRnOmhz_t9gkVSMIpL1naRocIycRNQ7xoqodRRO6XWUcFPKfid_7WCcM889h9HQnqMjVGKcRJzredUodM80JWLyHhag2l06yvQ3TSkj0vP27ByxoggQaClrEopakA68CRV0tR6IIVpOg==)
12. [nedcharles.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFfmY3qb9hDnJ3fK5R82SLDatQM6bKPA5Hlpy70QXS5FlIevwYuin0oDGJrwNTVCRj-Pdzyi1P7uMLIYDN1iYurvpVGyVVGyz5WHBdyWsEjbViEDkpulLuw77aCsM5Jxz-LT6ccV2fIR8IQYJhcbCRSvOhK-6-8IYb5nZzv7jqAjL6WZT-DQlr3n59WbaJC)
13. [wevolver.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdE-pQdHR2JdniLqcps3WTLsz9mmsFXJwv8r9dIhtFfszfc1q0Z4OcN0clr3syyF2mIXi34OremOXbCEkpe2SR98e_Zdo5l1QiZVxHNJMCKGYIBqGPyg8OmbZ4Wi9lALZ-QxqitWS-d3krVuPmVDUpkNKjdDdAn9x8grUTQroPwgllwHAnoGCf5ICoK47LN_NT30yNxA4pmQ==)
14. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZUHYvkOKX98LFLKW7uufVwB8j_Elh2quZzQH_Ro-NOO3LmEAE_rKS4LjK_LQZiz6QEBS7m-Ggrt7WDHCKGqY-XPtbSQ9Bn6czqlY5AjU0jKCDWxBebSXYBFVaIJMIP-X6O-tuUGFQk_95KFUNsD4xL1xGtAwBUowdGYOZN7Fra27LjWoNQgFplEsbZ7-JNMWCm1FifVzlBhyA3yeEH_zOeuT7jx00v1smjSNKoJAojEHy8_vL)
15. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFP1whNy604j2SGNf2xwRY-rz16SI5hJSJco3cR66kN9IJdLFV3nN5hXRy-9_Yfc-o-U0zqRo6cwdP9mXC-BBwd5YriwgMp8Qnos8Cqg0Ou9rbeozfXDiMMAGtqlrIiKYuVTea_t0phCqnh-4FnvTRhZzyr7yvsrYh6TRwCXC_GDImSubJsYHCfv6tohNr---9xznxOFZ3g4qyNaGYP8rnPz44QogLoVGDojj9_IA==)
16. [nixtla.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEy-zRFGNbn2eS_nY6JRy4nhFFG6vB5iSAnWUriDoXEX0BuZIJX-ldhKe-bnpWfI_S-sWPdvMQKSEDKwm-kzDwhjAPRqKxZKbFUnsu4cRGJAn34JYoxG4hcsp_E2bj3hY4L25VS6Q==)
17. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFphptgmJTEA_4BfwlZ9KIb1RyiNthta-XhtZn8ANgcnnquFOclyr-8GvGDV8bx3nAt0bXj5iHKQGSpNSlMDTTzI_5FY-F_jfFqXuNfWllwBe7wyHPiMM-AkdQFZCYqsPQm315ph2mK85esjPFB3bDysIS5COTMetUOYfkASovhzmaTPFqsYY5Qt8=)
18. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZHfZGcMjCM9bYcf9r3Lwjy7MM1r1HQumIfkBUvUs7DgC8BbFXlsX-rEw6FX8YYbeN23MXSKO5GXWO7AQHPeH2qrLdutnxqBAu_0TuIVkTiFAww3GqoCTCOqV0-f1yUeNf52kWNCXazjYU4sAgxa-Js0isz3F0Evi0QLzg7GzICRAqygk8FvzmSp9eZKU=)
19. [apmonitor.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHkVSBJiLq5taBe-Mc5YSDRyP_4T3i6bT-e9274v9zftrnsXWJ-VhXQ-2kvCaMhLY5CQcGdTjLlwIHPxRbMiO_pYO8TjHL2giPUzIO7yVuWhAlhIfdgHOoO83AOcS2Z_2TsXd6wdyYSjFfYoWVXDDYUKhxhMD9yThXUQg==)
20. [slideserve.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlTJhGnL3NOPbrEbcJt1TenAlq38AsGxs5es85gtJEVKjeB-hTqto_OgOvT3xuTHfEnIIDdXIawcOAnbuOvz4UknOGF9OvhK2aPrfycW5HnUACQ8aRYVIBQ42ld6a0xHLHxGr5JXfNR5YnVtalK5ZEe-GbIdvC7t42U1MGT3d68VULyyYn3R__tCySClE3aEnZLR77nsD72nEiZrADMnTAVr2xLsvykbvveb4IJeG6-P3vV9U-yJIf-NiK)
21. [ntnu.no](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFj36sNwBzJ0Z0LPcJ_qdjCSkXQ6185WY0n7Pl4kydOpHRx44vWZQDNny-SiHxOZt64qweJYvgc3s8SMnJ1XAaGpS_RKIvlJcDtzVXerEtm18lbvEz-tqrRbumh-L4AkZEj_bWAbrHq1_xaRM59QgoL10sAzTQQxiaXvrOKkIqvASo_WrD7RYLVlWqItdONow==)
22. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOGJyCJPz8JxK4Iy4ZPlCXaM6hopuKd938W-jeHj-zdqPv0Kt5goKmAmtLfr7_PEo_N1FSROvCa_t6_ce99n9tPjWvd80mlfDx78cwQhMtA9YtDvyWSpjyF-K8VQ==)
23. [ntnu.no](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFP9nfkmVdcZ5TuSRyJTTa8nIH0SEP7NQpIMVzqJhK61sCGmXBEQ87E5aIQ9VkqG51Jh34Iem4yzSa9MJIN1J-6R3lgNSdqzbVcy1lJSI1gjSc6UsRAj3Dl4wVus8Va2wvTqAIBse8kv_mahAWfeXR2MSz0uEfpsPDYpcwvs2bNUMvjZXJoV3SBC5rVQNR2icYui1V_bDffJw==)
24. [acs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFm82n-K7aBTp33EAFKUetAF7P5XSENh7uOiJcQhd-dIYzyxQ9Dk-UFiZ-1CLbYeUW_vVfSfHMNdrFPrdx98Txxs6gMFEY00caVI08nsZsY2l1Yv6rOy4AC2dfcT4586mQ=)
25. [techietory.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEDLEG0ZMBG4rHd0iHAYmZxuxzMZFqvm6738A1g0xd_YN7CvzFw1kPLVTKOSg_kkBnnW-uRHZdjFjogX7430FBMev58b9atybY88EMPfs3aL2Ck7bkfMspaA6FmF3JXbu8U4_CFagzOfhiSDfBJyFkdJwQm0JqJ)
26. [lth.se](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHrkbDBU8QiGW-pBbTOpfKJV3IUpzTAmSkac8tMmFOiZxLcgcxT2LwOTYDZjVyHtR50UTOya9P4MP2Y4Vb7RTTgPPX7t-I614YLT3pVjdOSUMpNiYhhWUCbg4kc0SVQwECVNQ3RPcAvv7xrEMwGgJSOlSqfMm5snAxkAjS6_ehKkn9U4mXuVM-_Choa0njdThd4y2hHAFSoMj2FKrnde9AdqDwecSuq-c1r)
27. [htwg-konstanz.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGL4NnkV6PuCNmo-PIQKLi6k6jwpOSaBGmX_x38S0k4LjG5cUxQYYpzPidajgJMYjTJGA28HBU7xHy0sULUUytrcUgYLtK3y7d9AeTp10uNgkj6ZCeEW3vC_dQlmJZmfDZRe0PPZxR3vuW6_ETnWZ_aG_WRi9VyZ9GGYWo=)
28. [makeitworklab.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEGU5WWbkn7coY0jqgjl3jyfW_wCs1HMlvii1mH0k-sas2cOo5h0bnWH9OoZ3DHFdRP1wsJP-qACPYWauQjaktfTcazPrvt9DYVdjG2kGP3DGBtfRPzxKGf_PyuH-dgTLwg8rg=)
29. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGxnG4qMWWE_FWJM3P05XRayWIsdblAF26TYqWTTz5URF4uCnwr7wRdtkfYDPtlObA8kLUSfiA-FM3BifiZ5PCjNVIZy8HvT5jmAyZsTIjm5QyLG8MN6GG6yxqBgHWcGtCXaDbtoVUytiAb2so3nCB-pa-sC8bA8a0gPxJMDWTDBjl2WXUAeyLSVC7y8Lzeobvr_1LWSnIDEOw=)
30. [ntnu.no](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElh1QY3PMOB6boNOG-_SmmJ-rA01qm3Si5ehCTxuZswax5eEOaF7v1iF-7zlP1ASYMbEWPL-2tas7O97NPc8_oHrzquW2RAVCNEw7rjcaTKpK3M74bHkXg-SzFkc2cJrPzCcCtBsxYv4no231pD_Shq3j0ZA==)
31. [simonebertonilab.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgBEFczKPbOgcIVcWOUMjD0D-OKuWlpeGky8aQQxKNLUYA1Z_OQnBp47pQs18lHgAQVBi8ZS2FtwcWr9z_ZcMp3r_9RH98xPKzR5xmtxH_kSgWF0e3ILfll8ijZ2_FTAWZpK74xVhh-Z0=)
32. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEL3y2aZDAMepe5jK2LkJV9YetmR0w4k0JMiMjwgL37-DIcpGWRj6bTht4vR6d9j0Zy67jSVndjE16ty9YynRzYxyehJZ1ldZ1QSrZZ_dzBGVKaONciFiIp0ciMwvKmzSyWkg==)
33. [shanghaitech.edu.cn](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFQZEmJ9BWkIBYQ6ghXDgrUTl84Y5DCWSE7543zMN1KOooFDM6rIiNisaLklut4V4UHk7RptgzDrCXRdIRifXaag_Y_MYceGilpfgiopVToRJpMoxuaFOmZHYvfvRDWp0aAsoxCMZzn2i_Ughf7fTyZvQbM)
34. [alvarestech.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGDrVp3pUMox0ZV2W3gK5sYOyOGpgwu6T-DbMfhVg0JkHE5f4BtMExZJG2B63j-5bQMGeCd8ouZYgIoZS2FgyQ_MsDCedHeuXj3_LyYlKJJFoS_NdGnob00nQUYrfRJf3wIG7zpHPOzWphZpN2yA7yZ3by9)
35. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAl3RIYTzT2YYp7zSmcoGhORzh1S2R7jQD1XYfFudaKSwJ9FgKGtSJxzCREIgxmdn2C6dTBZQ_q5nY4-59jgyKO7SLAYvbbN8Xijxxpx8FpgqxFnu18M7qmq7aYA==)
36. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtSDoOoMPXr5ClXhkx3gD9c3qsow6caBtdGBTwsjd-wDffkqN5O2pQ1yHhOqT9MZYajHOLwoFW0snzlrXAfw82YBfB2j4fpWdakpyuZXOc9eaO0VnQ2rhsGZTeq_HBKtoo4Qy5jAhu-r72i5b0LAHQ5rQcHcj6NhfU9QhQfK9VvJvb18e-Vw==)
37. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFlzIdP2jyON1vJUJH10Dm5tzax9RMQqSVlp_kWw6_wJwQk-nZGmeXJ5qxMz2UTio4sTeXsc0e7A782Cti0h12c2GtCYamDbsnwjuJcQQsEiikuFYgy3KWl8g_AtXugKm8auy8kRl9-LCwXrRCELkaJ9P5pDx00)
38. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTWgZN-anWTdZq2WA8YEylwz-JnQu1WR8Kb_N49dmwTPsK0WBIruKZerCqfrS6Kn92Jbi5dpqGe2m-OaRVMPL76B7Vhui4xTHwREqWqbKDpFqYG1lgmT-oft-rIUYvGfQE7mndp1ICezw7XnmscZ48aF_RExs0XKzNrEx9UBha6-_JOlRK)
39. [pandaimembagi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGXbyQvmh0gEXzIuFf8tubC2SIf6FBHC8Ro3ZxZgGyqTElKhYup-26wwJgP202EPhuNjANoqiO83-muWl86OHndYdPbybcPrtE_cXhHqGkQc_d_XuqcI8SBaZ7ux8Mrxz9Yqy8qXvhL7KBb37YyE6j7q6yScaNc8czGHJsOpDz9mUGTmdoh)
40. [numpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYZE1W4PVC8nF20XOk6EPMYPqv22EKw_baOTdP2cAVH8ATX86880878WB6U38q5gk2HiuSl_fDpAQwaVeVLEv3nfCfOVlkQp2SckVmC_4wmgkHdBSwtquHAdCGMKGTGnrLvf3TGG7iARfKONre-iDDwPiQQR-o8lok)
41. [southampton.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECea6wTISssBCU7iFKEpuFZtX0vAqAEfb9IN-hka6Ar70Uj2PdQeUGwPJr31CxhZxkUovI0_u6DoZJlDsADh-8Qysyt8STTDf_3-_CY49deHwatwV5HkU-155a_RaJVQsKtCJK65A9iTROd717eH7uAxDZibQMqvK7SsL-MlwebGsnTOA=)
42. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcrbjwc_moFuZWf2hpc_My7afn5lQLt__HhEUdLIsxgi4zUDElleoELedqtzj9c3hi8pWm_UCcQE22qcQ9LhMzq85XQRMmDn9R9u5g8uW1kglYsEXK1qkN9USJKrBjyb-0T3zvusm_w1AzVn13hN6R)
43. [numpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHC-Wz76LPMckKLN9ARyouF5HtFTBmk5fjDJteEWuy64nvpHeYOmWm96agmNcwZi6PiOtI6n2b45OSf4sjTOIhjmkI9Up5HtJeEUOyS4Z_Brcv-__Mew9iAru_1_nY=)
44. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7WM1rXN4pGHrgfWZ9xd7qsAycBq_2q7J2-AHU7DmB9KRtaXJ4Z3UeeykMx-EKBuQ71nGDJJeCAZ0NOiB04TFJxeOU5ycAorjHGSAfms4chzA0zxxUh4IrjShxAs758trSCh6CCjfMcQ==)
