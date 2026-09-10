# Domain Reference for evo-thermal-sysid

**Responsibility**: Open-loop calibration data collection, noise filtering (Savitzky-Golay), first-order step response curve fitting, parameter estimation (K, tau), R-squared calculation, and JSON serialization of calibration_log.json and estimated_params.json.

**Key functions to implement**: run_calibration_test, first_order_step_response, identify_system_params, filter_temperature_data, calculate_fit_metrics, save_calibration_results

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

## 6. Specific APIs: NumPy 1.26.4 & SciPy 1.13.0


Working with modern iterations of the SciPy stack requires awareness of changing interfaces.

### 7.3 Curve Fitting Convergence Failures

*   **Problem**: `scipy.optimize.curve_fit` returning `RuntimeError: Optimal parameters not found`.
*   **Mitigation**: Non-linear optimization requires walking down a gradient. If you initialize $\tau = 1$ when the true $\tau = 1000$, the gradient space is flat, and the algorithm gets lost [cite: 11, 44]. Providing `p0` via analytical estimates (finding the 63.2% point of the step response in the array) guarantees the solver starts in the correct localized valley of the cost function.