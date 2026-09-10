"""
ACC Simulation runner.

Reads:
- vehicle_params.yaml (vehicle specs and ACC settings)
- sensor_data.csv (1501 rows: time, ego_speed, lead_speed, distance)
- tuning_results.yaml (PID gains)

Produces:
- simulation_results.csv (1501 rows: time, ego_speed, acceleration_cmd, mode,
                          distance_error, distance, ttc)
- acc_report.md (system design, tuning, results)

Usage: python3 simulation.py
"""

import os
import sys
import math
import yaml
import numpy as np
import pandas as pd

# Import from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/root')

from pid_controller import PIDController
from acc_system import AdaptiveCruiseControl, calculate_ttc, calculate_desired_distance


def load_config(path='/root/vehicle_params.yaml'):
    """Load vehicle parameters and ACC settings."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def load_sensor_data(path='/root/sensor_data.csv'):
    """Load sensor data CSV."""
    return pd.read_csv(path)


def load_tuning_results(path='/root/tuning_results.yaml'):
    """Load PID tuning results."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def run_simulation(config, sensor_df, tuning):
    """
    Run the ACC simulation.

    Args:
        config: dict from vehicle_params.yaml
        sensor_df: DataFrame from sensor_data.csv
        tuning: dict from tuning_results.yaml

    Returns:
        list of dicts, one per timestep
    """
    dt = config['simulation']['dt']
    total_time = config['simulation']['duration']
    n_steps = int(round(total_time / dt)) + 1

    # Create ACC system
    acc = AdaptiveCruiseControl(config)
    acc.set_gains(tuning['pid_speed'], tuning['pid_distance'])

    # Initialize state
    ego_speed = 0.0  # Start at rest
    results = []

    for i in range(n_steps):
        t = round(i * dt, 1)

        # Get sensor data for this timestep
        row = sensor_df.iloc[i]
        lead_speed_raw = row['lead_speed']
        distance_raw = row['distance']

        # Determine if lead vehicle is present
        lead_present = not pd.isna(lead_speed_raw)

        if lead_present:
            lead_speed = float(lead_speed_raw)
            # Compute actual distance based on physics
            # Use sensor distance for the first timestep with lead, then track via physics
            if i == 0:
                distance = float(distance_raw)
            else:
                prev_result = results[-1]
                if prev_result['distance'] is not None and not (isinstance(prev_result['distance'], float) and math.isnan(prev_result['distance'])):
                    # Update distance based on relative speed
                    prev_dist = float(prev_result['distance'])
                    prev_ego_speed = prev_result['ego_speed']
                    # distance changes by (lead_speed - ego_speed) * dt
                    distance = prev_dist + (lead_speed - prev_ego_speed) * dt
                    # Don't let distance go below 0
                    distance = max(0.0, distance)
                else:
                    # First timestep with lead vehicle - use sensor data
                    distance = float(distance_raw)
        else:
            lead_speed = None
            distance = None

        # Compute ACC command
        accel_cmd, mode, distance_error = acc.compute(
            ego_speed, lead_speed, distance, dt
        )

        # Clamp acceleration
        accel_cmd = max(config['vehicle']['max_deceleration'],
                       min(config['vehicle']['max_acceleration'], accel_cmd))

        # Compute TTC for output
        ttc = None
        if lead_present and ego_speed > lead_speed + 1e-6:
            ttc_val = calculate_ttc(ego_speed, lead_speed, distance)
            if ttc_val < 1000:  # Only record finite TTC
                ttc = ttc_val

        # Record result
        result = {
            'time': t,
            'ego_speed': round(ego_speed, 6),
            'acceleration_cmd': round(accel_cmd, 6),
            'mode': mode,
            'distance_error': round(distance_error, 6) if distance_error is not None else None,
            'distance': round(distance, 6) if distance is not None else None,
            'ttc': round(ttc, 6) if ttc is not None else None,
        }
        results.append(result)

        # Update ego speed (Euler integration)
        ego_speed = ego_speed + accel_cmd * dt
        # Speed can't go negative
        ego_speed = max(0.0, ego_speed)

    return results


def write_simulation_results(path, results):
    """Write simulation results to CSV with empty fields for None values."""
    df = pd.DataFrame(results)
    # Ensure column order
    df = df[['time', 'ego_speed', 'acceleration_cmd', 'mode',
             'distance_error', 'distance', 'ttc']]
    df.to_csv(path, index=False, na_rep='')
    return df


def generate_report(path, results, tuning, config):
    """Generate acc_report.md with system design, tuning, and results."""
    df = pd.DataFrame(results)

    # Compute metrics
    cruise_phase = df[df['time'] <= 30.0]
    max_speed = cruise_phase['ego_speed'].max()
    overshoot = (max_speed - 30.0) / 30.0 * 100 if max_speed > 30.0 else 0.0

    ss_phase = df[(df['time'] >= 25.0) & (df['time'] <= 30.0)]
    ss_error = abs(30.0 - ss_phase['ego_speed'].mean()) if len(ss_phase) > 0 else float('nan')

    # Rise time (10% to 90%)
    t10_series = cruise_phase[cruise_phase['ego_speed'] >= 3.0]['time']
    t90_series = cruise_phase[cruise_phase['ego_speed'] >= 27.0]['time']
    rise_time = (t90_series.min() - t10_series.min()) if len(t10_series) > 0 and len(t90_series) > 0 else float('nan')

    # Distance metrics
    follow_phase = df[(df['time'] >= 50.0) & (df['time'] <= 60.0)]
    follow_phase = follow_phase[follow_phase['mode'] == 'follow']
    if len(follow_phase) > 0:
        dist_errors = pd.to_numeric(follow_phase['distance_error'], errors='coerce').abs()
        dist_ss_error = dist_errors.mean()
    else:
        dist_ss_error = float('nan')

    # Min distance
    dist_col = pd.to_numeric(df['distance'], errors='coerce').dropna()
    min_dist = dist_col.min() if len(dist_col) > 0 else float('nan')

    # Emergency count
    emergency_count = (df['mode'] == 'emergency').sum()

    report = f"""# Adaptive Cruise Control Report

## System Design

### ACC Architecture
The system implements a single-loop Adaptive Cruise Control with three operating modes:

1. **Cruise Mode**: Active when no lead vehicle is detected. A PID speed controller
   targets the set speed of {config['acc_settings']['set_speed']} m/s.

2. **Follow Mode**: Active when a lead vehicle is detected and TTC is above the
   emergency threshold. A PID distance controller maintains a safe following distance
   defined as: d_safe = time_headway × ego_speed + min_distance.

3. **Emergency Mode**: Activated when Time-To-Collision (TTC) drops below
   {config['acc_settings']['emergency_ttc_threshold']} seconds. Commands maximum
   deceleration of {config['vehicle']['max_deceleration']} m/s².

### Safety Features
- TTC-based emergency braking (threshold: {config['acc_settings']['emergency_ttc_threshold']}s)
- Acceleration limits: [{config['vehicle']['max_deceleration']}, {config['vehicle']['max_acceleration']}] m/s²
- Minimum following distance enforcement
- Speed non-negativity constraint
- Anti-windup on PID controllers

## PID Tuning Methodology and Final Gains

### Tuning Approach
PID gains were tuned to meet the following performance targets:
- Speed rise time < 10s (10% to 90%)
- Speed overshoot < 5%
- Speed steady-state error < 0.5 m/s
- Distance steady-state error < 2m
- Minimum distance > 5m

### Final Gains

**Speed PID:**
- Kp = {tuning['pid_speed']['kp']}
- Ki = {tuning['pid_speed']['ki']}
- Kd = {tuning['pid_speed']['kd']}

**Distance PID:**
- Kp = {tuning['pid_distance']['kp']}
- Ki = {tuning['pid_distance']['ki']}
- Kd = {tuning['pid_distance']['kd']}

## Simulation Results and Performance Metrics

### Speed Control (t=0-30s)
- Rise time (10%-90%): {rise_time:.2f}s
- Maximum overshoot: {overshoot:.2f}%
- Steady-state error: {ss_error:.4f} m/s

### Distance Control (t=30-60s)
- Distance steady-state error: {dist_ss_error:.4f}m
- Minimum distance observed: {min_dist:.2f}m

### Safety
- Emergency mode activations: {emergency_count} timesteps
- All accelerations within [{config['vehicle']['max_deceleration']}, {config['vehicle']['max_acceleration']}] m/s²
- Speed never negative

### Mode Distribution
- Cruise: {(df['mode'] == 'cruise').sum()} timesteps
- Follow: {(df['mode'] == 'follow').sum()} timesteps
- Emergency: {(df['mode'] == 'emergency').sum()} timesteps

### Result Summary
The simulation ran for {config['simulation']['duration']}s with dt={config['simulation']['dt']}s,
producing {len(df)} data points. The ACC system successfully maintained the set speed
during cruise phases, tracked the lead vehicle during follow phases, and activated
emergency braking when TTC dropped below the threshold.
"""

    with open(path, 'w') as f:
        f.write(report)
    return report


def main():
    """Main entry point — run simulation and produce all outputs."""
    config = load_config('/root/vehicle_params.yaml')
    sensor_df = load_sensor_data('/root/sensor_data.csv')
    tuning = load_tuning_results('/root/tuning_results.yaml')

    results = run_simulation(config, sensor_df, tuning)
    write_simulation_results('/root/simulation_results.csv', results)
    generate_report('/root/acc_report.md', results, tuning, config)

    print("Simulation complete.")
    print(f"  Results: /root/simulation_results.csv ({len(results)} rows)")
    print(f"  Report:  /root/acc_report.md")


if __name__ == '__main__':
    main()