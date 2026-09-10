import numpy as np
import json


def calculate_simc_gains(K, tau, tau_c=None):
    """
    Calculate SIMC PI gains for a first-order system without dead time.
    
    SIMC rules:
        Kp = tau / (K * tau_c)
        Ti = min(tau, 4 * tau_c)
        Ki = Kp / Ti
        Kd = 0.0
    
    Args:
        K: process gain (C per % power)
        tau: time constant (seconds)
        tau_c: desired closed-loop time constant. If None, defaults to 25.0s
    
    Returns:
        dict with Kp, Ki, Kd, lambda (tau_c)
    """
    if tau_c is None:
        tau_c = 25.0  # gives settling time ~100s < 120s
    
    if K == 0 or tau_c == 0:
        raise ValueError("K and tau_c must be non-zero")
    
    Kp = tau / (K * tau_c)
    Ti = min(tau, 4.0 * tau_c)
    Ki = Kp / Ti
    Kd = 0.0
    
    return {
        "Kp": round(float(Kp), 4),
        "Ki": round(float(Ki), 4),
        "Kd": round(float(Kd), 4),
        "lambda": round(float(tau_c), 2)
    }


class DiscretePID:
    """Discrete-time PID controller with anti-windup and derivative on measurement."""
    
    def __init__(self, Kp, Ki, Kd, dt, output_min=0.0, output_max=100.0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.dt = dt
        self.output_min = output_min
        self.output_max = output_max
        
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_measurement = None
    
    def update(self, setpoint, measurement):
        """Compute PID output for current timestep."""
        error = setpoint - measurement
        
        if self.prev_measurement is None:
            self.prev_measurement = measurement
            self.prev_error = error
        
        # Proportional
        P = self.Kp * error
        
        # Integral (trapezoidal)
        tentative_integral = self.integral + self.Ki * (self.dt / 2.0) * (error + self.prev_error)
        
        # Derivative on measurement (no derivative kick)
        if self.Kd > 0:
            D = -self.Kd * (measurement - self.prev_measurement) / self.dt
        else:
            D = 0.0
        
        # Tentative output
        v = P + tentative_integral + D
        
        # Output saturation
        output = np.clip(v, self.output_min, self.output_max)
        
        # Anti-windup clamping
        is_saturated = (output != v)
        if not is_saturated or np.sign(error) != np.sign(v):
            self.integral = tentative_integral
        
        self.prev_error = error
        self.prev_measurement = measurement
        
        return float(output)
    
    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_measurement = None


def run_closed_loop_control(sim, Kp, Ki, Kd, setpoint=22.0, duration=180.0):
    """
    Run closed-loop PID control on the HVAC simulator.
    
    Args:
        sim: HVACSimulator instance (already calibrated, NOT reset)
        Kp, Ki, Kd: PID gains
        setpoint: target temperature
        duration: control duration in seconds
    
    Returns:
        dict suitable for control_log.json
    """
    dt = sim.get_dt()
    pid = DiscretePID(Kp, Ki, Kd, dt, output_min=0.0, output_max=100.0)
    
    steps = int(duration / dt)
    data = []
    
    # Get initial measurement
    current_temp = sim._get_measurement()
    start_time = sim.time
    
    for i in range(steps):
        # Compute control action
        heater_power = pid.update(setpoint, current_temp)
        
        # Step simulator
        result = sim.step(heater_power)
        current_temp = result["temperature"]
        
        error = setpoint - current_temp
        data.append({
            "time": round(result["time"] - start_time, 2),
            "temperature": result["temperature"],
            "setpoint": setpoint,
            "heater_power": result["heater_power"],
            "error": round(error, 4)
        })
    
    control_log = {
        "phase": "control",
        "setpoint": setpoint,
        "data": data
    }
    return control_log


def calculate_control_metrics(control_log):
    """
    Calculate control performance metrics from control log.
    
    Returns:
        dict with rise_time, overshoot, settling_time, steady_state_error, max_temp
    """
    data = control_log["data"]
    setpoint = control_log["setpoint"]
    
    times = np.array([d["time"] for d in data])
    temps = np.array([d["temperature"] for d in data])
    
    # Steady-state error: average of last 20 points
    sse_window = min(20, len(temps))
    steady_state_val = np.mean(temps[-sse_window:])
    sse = abs(setpoint - steady_state_val)
    
    # Max temperature
    max_temp = float(np.max(temps))
    
    # Overshoot (fraction, not percentage)
    peak_val = np.max(temps)
    if peak_val > setpoint:
        overshoot = (peak_val - setpoint) / abs(setpoint - temps[0])
    else:
        overshoot = 0.0
    
    # Rise time: 10% to 90% of setpoint change
    start_val = temps[0]
    delta = setpoint - start_val
    target_10 = start_val + 0.10 * delta
    target_90 = start_val + 0.90 * delta
    
    rise_time = float('inf')
    try:
        t_10_indices = np.where(temps >= target_10)[0]
        t_90_indices = np.where(temps >= target_90)[0]
        if len(t_10_indices) > 0 and len(t_90_indices) > 0:
            rise_time = times[t_90_indices[0]] - times[t_10_indices[0]]
    except (IndexError, ValueError):
        pass
    
    # Settling time: trace backward, find last time outside +/- 0.5C band
    threshold = 0.5
    upper = setpoint + threshold
    lower = setpoint - threshold
    
    outside = np.where((temps > upper) | (temps < lower))[0]
    
    if len(outside) == 0:
        settling_time = 0.0
    elif outside[-1] >= len(temps) - 1:
        settling_time = float('inf')
    else:
        settling_time = times[outside[-1] + 1] - times[0]
    
    metrics = {
        "rise_time": round(float(rise_time), 2),
        "overshoot": round(float(overshoot), 4),
        "settling_time": round(float(settling_time), 2),
        "steady_state_error": round(float(sse), 4),
        "max_temp": round(float(max_temp), 4)
    }
    return metrics


def save_control_results(tuned_gains, control_log, metrics,
                         gains_path="/root/tuned_gains.json",
                         control_path="/root/control_log.json",
                         metrics_path="/root/metrics.json"):
    """Save tuned gains, control log, and metrics to JSON files."""
    with open(gains_path, 'w') as f:
        json.dump(tuned_gains, f, indent=2)
    with open(control_path, 'w') as f:
        json.dump(control_log, f, indent=2)
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    return gains_path, control_path, metrics_path
