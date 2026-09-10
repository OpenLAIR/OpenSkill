# Skill Creation Plan

**Task**: Implement an Adaptive Cruise Control simulation with PID controllers, mode selection logic, and 150s vehicle simulation producing results CSV and report.

**Rationale**: The task has three clear functional domains: (1) the reusable PID controller component, (2) the ACC system with mode selection logic, and (3) the simulation runner with data I/O, tuning, and reporting. Separating these matches the task's explicit file structure (pid_controller.py, acc_system.py, simulation.py) and ensures each skill has a non-overlapping responsibility.

**Number of skills**: 3

---

## Skill 1: evo-control-pid-controller

**Description**: Implements a discrete PID controller class with anti-windup (conditional integration/clamping) and proper first-timestep handling. This is the foundational control building block used by the ACC system.

**Responsibility**: Provide a standalone PIDController class with reset() and compute(error, dt) methods, including output limits and integral windup prevention via clamping.

**Key functions**: `PIDController.__init__`, `PIDController.reset`, `PIDController.compute`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-control-pid-controller/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-acc-system-logic

**Description**: Implements the AdaptiveCruiseControl class with mode selection (cruise/follow/emergency), TTC calculation, desired distance computation, and minimum acceleration blending strategy. Reads config from vehicle_params.yaml structure.

**Responsibility**: Provide ACC mode selection logic, TTC safety checks, desired distance calculation (time headway policy), and acceleration command selection using minimum acceleration strategy across dual PID controllers.

**Key functions**: `AdaptiveCruiseControl.__init__`, `AdaptiveCruiseControl.compute`, `calculate_ttc`, `calculate_desired_distance`

**Depends on**: evo-control-pid-controller


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-acc-system-logic/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-acc-simulation-runner

**Description**: Implements the simulation loop, data I/O pipeline, PID tuning results generation, and report writing. Reads sensor_data.csv and vehicle_params.yaml, loads PID gains from tuning_results.yaml, runs 150s closed-loop simulation with Euler integration, and outputs simulation_results.csv and acc_report.md.

**Responsibility**: Handle all file I/O (YAML config loading/writing, CSV reading/writing), the 1501-step simulation loop with proper physics integration, tuning_results.yaml creation with recommended PID gains, simulation_results.csv output with correct NaN handling, and acc_report.md generation.

**Key functions**: `load_config`, `load_sensor_data`, `write_tuning_results`, `run_simulation`, `write_simulation_results`, `generate_report`

**Depends on**: evo-control-pid-controller, evo-acc-system-logic


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-acc-simulation-runner/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
