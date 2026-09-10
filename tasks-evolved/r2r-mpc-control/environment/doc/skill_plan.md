# Skill Creation Plan

**Task**: Implement an MPC controller for a 6-section Roll-to-Roll manufacturing line to stabilize web tensions during a section 3 reference change from 20N to 44N at t=0.5s, using the provided r2r_simulator.py without modification.

**Rationale**: The task naturally decomposes into two concerns: (1) deriving the linearized state-space model with steady-state computations, and (2) implementing the MPC controller and running the simulation loop. The linearization/model is foundational and must be correct before the controller can work, while the MPC controller, simulation execution, and metrics computation form a cohesive second skill that consumes the model.

**Number of skills**: 2

---

## Skill 1: evo-r2r-linearization

**Description**: Derives the linearized state-space model (A, B matrices) for a 6-section R2R system from nonlinear tension-velocity dynamics, computes steady-state operating points (velocities and torques) for given tension references, and performs continuous-to-discrete conversion.

**Responsibility**: Compute steady-state equilibrium (velocities, torques) for any tension reference vector, construct continuous A and B Jacobian matrices via exact partial derivatives at the operating point, discretize using scipy.signal.cont2discrete, and solve the DARE for LQR gain computation.

**Key functions**: `compute_steady_state_velocities`, `compute_steady_state_torques`, `build_continuous_AB`, `discretize_system`, `compute_lqr_gain`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-r2r-linearization/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-r2r-mpc-controller

**Description**: Implements the MPC controller with prediction matrices, QP formulation, and the full simulation loop interfacing with r2r_simulator.py. Handles reference step changes via deviation formulation, runs the simulation for at least 5 seconds, logs control data, and computes performance metrics.

**Responsibility**: Build MPC prediction matrices (Phi, Gamma), formulate and solve the dense QP (unconstrained or constrained via scipy.optimize.minimize), implement the receding horizon control loop with the R2R simulator, handle the reference change at t=0.5s by recomputing steady-state targets and re-linearizing, generate controller_params.json, control_log.json, and metrics.json output files.

**Key functions**: `build_prediction_matrices`, `build_qp_matrices`, `solve_mpc_step`, `run_simulation_loop`, `compute_performance_metrics`, `save_output_files`

**Depends on**: evo-r2r-linearization


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-r2r-mpc-controller/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
