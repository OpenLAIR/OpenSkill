# Skill Creation Plan

**Task**: Implement a PID temperature controller: calibrate HVAC system, identify parameters, tune controller gains, run closed-loop control to 22.0C, and compute performance metrics.

**Rationale**: The task has four sequential phases (calibration, system identification, controller tuning, closed-loop control+metrics) but they share tight coupling through the simulator and PID logic. Decomposing into two skills: (1) system identification from step-response data, and (2) PID controller with tuning and metrics computation, provides clean separation of concerns while avoiding over-decomposition.

**Number of skills**: 2

---

## Skill 1: evo-thermal-sysid

**Description**: System identification utilities for first-order thermal systems. Runs open-loop step tests on the HVAC simulator, collects calibration data, fits first-order exponential model using scipy.optimize.curve_fit, and outputs estimated parameters (K, tau) with fit quality metrics.

**Responsibility**: Open-loop calibration data collection, noise filtering (Savitzky-Golay), first-order step response curve fitting, parameter estimation (K, tau), R-squared calculation, and JSON serialization of calibration_log.json and estimated_params.json.

**Key functions**: `run_calibration_test`, `first_order_step_response`, `identify_system_params`, `filter_temperature_data`, `calculate_fit_metrics`, `save_calibration_results`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-thermal-sysid/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-thermal-pid-control

**Description**: PID controller tuning, discrete-time PID implementation with anti-windup, closed-loop simulation execution, and control performance metrics computation. Takes estimated system parameters, computes SIMC gains, runs the controller against the HVAC simulator, and evaluates rise time, overshoot, settling time, and steady-state error.

**Responsibility**: SIMC/IMC gain calculation (Kp, Ki, Kd), discrete-time PID controller with trapezoidal integration and anti-windup clamping, closed-loop simulation loop management, performance metrics calculation (rise_time, overshoot, settling_time, steady_state_error, max_temp), and JSON serialization of tuned_gains.json, control_log.json, and metrics.json.

**Key functions**: `calculate_simc_gains`, `DiscretePID`, `run_closed_loop_control`, `calculate_control_metrics`, `save_control_results`

**Depends on**: evo-thermal-sysid


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-thermal-pid-control/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
