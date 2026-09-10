import numpy as np
import json
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter


def first_order_step_response(t, K, tau, T_amb, U_step):
    """First-order step response: T(t) = T_amb + K * U_step * (1 - exp(-t/tau))"""
    return T_amb + K * U_step * (1.0 - np.exp(-t / tau))


def filter_temperature_data(temp_data, window_length=11, polyorder=2):
    """Apply Savitzky-Golay filter to smooth noisy temperature data."""
    if len(temp_data) < 5:
        return np.array(temp_data)
    if window_length % 2 == 0:
        window_length += 1
    if window_length > len(temp_data):
        window_length = len(temp_data) if len(temp_data) % 2 == 1 else len(temp_data) - 1
    if window_length < 3:
        window_length = 3
    if polyorder >= window_length:
        polyorder = window_length - 1
    return savgol_filter(temp_data, window_length, polyorder, mode='interp')


def calculate_fit_metrics(T_actual, T_predicted):
    """Calculate R-squared and RMSE between actual and predicted temperatures."""
    T_actual = np.array(T_actual)
    T_predicted = np.array(T_predicted)
    ss_res = np.sum((T_actual - T_predicted) ** 2)
    ss_tot = np.sum((T_actual - np.mean(T_actual)) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    rmse = np.sqrt(ss_res / len(T_actual))
    return r_squared, rmse


def run_calibration_test(sim, heater_power=50.0, duration=60.0):
    """
    Run open-loop calibration test on the HVAC simulator.
    Collects step response data with constant heater power.
    
    Args:
        sim: HVACSimulator instance
        heater_power: constant heater power to apply (0-100%)
        duration: test duration in seconds
    
    Returns:
        dict with calibration data suitable for calibration_log.json
    """
    sim.reset()
    dt = sim.get_dt()
    steps = int(duration / dt)
    
    data = []
    # Record initial state
    initial_temp = sim._get_measurement()
    data.append({
        "time": 0.0,
        "temperature": round(initial_temp, 4),
        "heater_power": 0.0
    })
    
    for i in range(steps):
        result = sim.step(heater_power)
        data.append({
            "time": result["time"],
            "temperature": result["temperature"],
            "heater_power": result["heater_power"]
        })
    
    calibration_log = {
        "phase": "calibration",
        "heater_power_test": heater_power,
        "data": data
    }
    return calibration_log


def identify_system_params(calibration_log):
    """
    Identify system parameters K and tau from calibration data.
    Uses scipy.optimize.curve_fit to fit first-order step response.
    
    Args:
        calibration_log: dict from run_calibration_test
    
    Returns:
        dict with K, tau, r_squared, fitting_error for estimated_params.json
    """
    data = calibration_log["data"]
    U_step = calibration_log["heater_power_test"]
    
    times = np.array([d["time"] for d in data])
    temps = np.array([d["temperature"] for d in data])
    
    # Filter the temperature data
    if len(temps) > 5:
        temps_filtered = filter_temperature_data(temps)
    else:
        temps_filtered = temps
    
    # Initial temperature estimate (ambient)
    T_amb = temps_filtered[0]
    
    # Estimate initial guesses
    T_final = np.mean(temps_filtered[-10:])
    K_guess = (T_final - T_amb) / U_step if U_step > 0 else 0.1
    if K_guess <= 0:
        K_guess = 0.1
    
    # Estimate tau from 63.2% point
    target_632 = T_amb + 0.632 * (T_final - T_amb)
    tau_guess = 40.0
    indices = np.where(temps_filtered >= target_632)[0]
    if len(indices) > 0:
        tau_guess = times[indices[0]]
    if tau_guess <= 0:
        tau_guess = 40.0
    
    # Create wrapper function with fixed T_amb and U_step
    def model_func(t, K_val, tau_val):
        return first_order_step_response(t, K_val, tau_val, T_amb, U_step)
    
    # Fit using curve_fit with bounds
    p0 = [K_guess, tau_guess]
    bounds = ([0.001, 1.0], [1.0, 200.0])
    
    try:
        popt, pcov = curve_fit(model_func, times, temps_filtered, p0=p0, 
                               bounds=bounds, maxfev=10000)
        K_est, tau_est = popt
    except RuntimeError:
        K_est, tau_est = K_guess, tau_guess
    
    # Calculate fit quality
    T_predicted = model_func(times, K_est, tau_est)
    r_squared, rmse = calculate_fit_metrics(temps_filtered, T_predicted)
    
    estimated_params = {
        "K": round(float(K_est), 6),
        "tau": round(float(tau_est), 2),
        "r_squared": round(float(r_squared), 4),
        "fitting_error": round(float(rmse), 4)
    }
    return estimated_params


def save_calibration_results(calibration_log, estimated_params, 
                             calib_path="/root/calibration_log.json",
                             params_path="/root/estimated_params.json"):
    """Save calibration log and estimated parameters to JSON files."""
    with open(calib_path, 'w') as f:
        json.dump(calibration_log, f, indent=2)
    with open(params_path, 'w') as f:
        json.dump(estimated_params, f, indent=2)
    return calib_path, params_path
