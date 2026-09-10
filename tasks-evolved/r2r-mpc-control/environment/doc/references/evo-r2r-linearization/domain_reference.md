# Domain Reference for evo-r2r-linearization

**Responsibility**: Compute steady-state equilibrium (velocities, torques) for any tension reference vector, construct continuous A and B Jacobian matrices via exact partial derivatives at the operating point, discretize using scipy.signal.cont2discrete, and solve the DARE for LQR gain computation.

**Key functions to implement**: compute_steady_state_velocities, compute_steady_state_torques, build_continuous_AB, discretize_system, compute_lqr_gain

---

## 1. R2R Web Tension-Velocity Dynamics Linearization


The continuous operation of an R2R system is defined by interconnected, nonlinear physical dynamics governing web tension and roller velocity [cite: 5, 6]. To implement linear Model Predictive Control (MPC), we must extract a linearized state-space representation.

## 2. Steady-State Target Computation


Model Predictive Control manages transient variations around an equilibrium point. When a reference setpoint changes (e.g., Section 3 tension changes from 20N to 44N), the system's equilibrium shifts [cite: 1, 3]. The MPC controller must be given a newly computed target state vector $\mathbf{x}_{ss}$ and control vector $\mathbf{u}_{ss}$ [cite: 5, 8].

## 3. Continuous-to-Discrete Conversion


Digital control systems execute at discrete intervals $dt$ (e.g., $dt=0.01$ seconds). The continuous state-space matrices $(A, B)$ must be accurately transformed into discrete matrices $(A_d, B_d)$.

## 4. LQR Gain Computation in Python


Before deploying constrained MPC, an unconstrained linear quadratic regulator (LQR) is typically formulated. In MPC theory, the optimal LQR cost-to-go is frequently utilized as the terminal cost matrix $P$ to guarantee closed-loop stability over a finite prediction horizon.

## 8. Common Pitfalls in Implementation

