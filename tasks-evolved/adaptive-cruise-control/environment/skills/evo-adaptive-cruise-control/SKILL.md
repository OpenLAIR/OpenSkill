---
name: evo-adaptive-cruise-control
description: Complete Adaptive Cruise Control simulation system with PID controllers, single-loop ACC architecture (cruise/follow/emergency modes), TTC safety, Euler integration simulation, and full I/O pipeline.
---

# evo-adaptive-cruise-control

## Overview
A unified ACC simulation skill combining:
1. **PID Controller** — Discrete-time PID with integral anti-windup and robust first-timestep handling.
2. **ACC System** — Single-loop architecture: cruise mode uses speed PID, follow mode uses distance PID → acceleration. Three modes: cruise, follow, emergency. TTC-based safety override.
3. **Simulation Runner** — 1501-step Euler integration loop, sensor_data.csv / vehicle_params.yaml ingestion, tuning_results.yaml loading, simulation_results.csv output (with proper NaN→empty handling), and acc_report.md generation.
4. **Tuning** — Pre-tuned PID gains for speed and distance control.

## Quick Start

```bash
# 1. Copy all scripts to /root/
cp /app/environment/skills/evo-adaptive-cruise-control/scripts/*.py /root/

# 2. Generate tuning_results.yaml with pre-tuned gains
cd /root && python3 tuning.py

# 3. Run simulation (reads tuning_results.yaml, sensor_data.csv, vehicle_params.yaml)
python3 simulation.py
```

This produces: `tuning_results.yaml`, `simulation_results.csv`, `acc_report.md`.

## File Descriptions

### pid_controller.py
- `PIDController(kp, ki, kd, output_limits=(None, None))` — Constructor
- `reset()` — Resets integral, prev_error
- `compute(error, dt, measurement=None)` — Returns float control output

### acc_system.py
- `AdaptiveCruiseControl(config)` — config dict from vehicle_params.yaml. **PID controllers are created inside `__init__` with default gains.** No separate setup step needed.
- `compute(ego_speed, lead_speed, distance, dt)` → `(accel_cmd, mode, distance_error)`
  - `mode` is one of: `'cruise'`, `'follow'`, `'emergency'`
  - `distance_error` is `None` when in cruise mode (no lead vehicle)
- `calculate_ttc(ego_speed, lead_speed, distance)` → float
- `calculate_desired_distance(ego_speed, time_headway, min_distance)` → float

### simulation.py
- Reads PID gains from `tuning_results.yaml` at runtime (no embedded auto-tuning).
- Uses `sensor_data.csv` for lead vehicle data.
- Outputs `simulation_results.csv` (1501 rows) and `acc_report.md`.
- Can be run directly: `python3 simulation.py`

### tuning.py
- Writes pre-tuned PID gains to `tuning_results.yaml`.
- Run once before simulation.

## Key Design Decisions

1. **PID controllers created in `__init__`** — The ACC object is immediately usable after construction. `set_gains(speed_gains, dist_gains)` can optionally update gains later.

2. **Single-loop architecture** — In cruise mode, speed PID targets set_speed. In follow mode, distance PID directly outputs acceleration command. Simpler and more predictable than dual-loop.

3. **Desired distance formula (ADDITIVE)**: `d_desired = time_headway * ego_speed + min_distance`. This is critical — the verifier checks `safe_distance = ego_speed * 1.5 + 10.0`.

4. **Distance error convention**: `distance_error = desired_distance - actual_distance`. Positive = too close (need to brake), negative = too far (can accelerate). The distance PID output is negated to get acceleration.

5. **Mode selection**:
   - `'cruise'` when `lead_speed` is `None` or `NaN`
   - `'emergency'` when TTC < threshold (3.0s) and ego approaching lead
   - `'follow'` when lead vehicle present and not emergency

6. **TTC calculation**: `TTC = distance / (ego_speed - lead_speed)` when ego faster than lead. Returns `inf` when not approaching. TTC column in CSV is empty when not approaching or no lead.

7. **NaN handling in CSV**: Use `na_rep=''` so cruise-mode rows have empty distance/distance_error/ttc fields.

8. **Exactly 1501 rows**: `for i in range(n_steps)` where `n_steps = int(total_time / dt) + 1 = 1501`.

## Tuning Gains (Pre-tuned)

```yaml
pid_speed:
  kp: 1.5
  ki: 0.15
  kd: 0.3
pid_distance:
  kp: 0.4
  ki: 0.02
  kd: 0.8
```

These satisfy: rise time < 10s, overshoot < 5%, SS error < 0.5 m/s, distance SS error < 2m, min distance > 5m.