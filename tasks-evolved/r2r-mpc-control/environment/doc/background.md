# Model Predictive Control for Roll-to-Roll Web Handling Systems: A Comprehensive Guide

**Key Points**
*   Research suggests that Model Predictive Control (MPC) significantly outperforms traditional PID controllers in strongly coupled Roll-to-Roll (R2R) systems by accounting for multivariable interactions and physical constraints. 
*   Deriving a linearized state-space model at a specific steady-state equilibrium is a critical first step, as the non-linear elastohydrodynamic and physical tension-velocity equations cannot be directly used in standard linear MPC frameworks.
*   The `scipy.signal.cont2discrete` and `scipy.linalg.solve_discrete_are` functions provide robust native solutions for discretizing continuous models and computing optimal baseline control gains, though care must be taken regarding numerical conditioning.
*   Implementing a custom Quadratic Programming (QP) solver using `scipy.optimize.minimize` with the SLSQP method allows for constrained MPC without relying on external optimization libraries, which is vital for constrained hardware deployments.
*   It seems likely that defining the MPC state as the deviation from a dynamically recomputed steady-state origin is the most robust approach for handling piecewise-constant reference tracking, such as sudden setpoint changes in individual web sections.

**Understanding Roll-to-Roll Control Challenges**
Roll-to-roll (R2R) manufacturing processes are utilized to fabricate products on continuous, flexible substrates (webs) such as electronics, battery films, and packaging. The primary objective in R2R control is to maintain optimal web tension and transport velocity. If the tension is too high, the web may stretch plastically, break, or suffer severe mechanical damage. If the tension is too low, the web will go slack, causing wrinkles and lateral displacement (wandering) [cite: 1, 2]. 

**The Need for Advanced Multivariable Control**
In a multi-span system, a change in the velocity of one roller immediately impacts the tension in both the upstream and downstream spans. This strong dynamic coupling means that decentralized control (e.g., individual PID loops for each roller) often struggles to handle transients, acceleration phases, and reference step changes. Model Predictive Control utilizes a mathematical model of the entire system to predict future behaviors, calculating the exact control effort needed to decouple these variables and drive the system to its setpoints while explicitly respecting bounds on motor torques and substrate physical limits [cite: 3, 4].

***

## 1. R2R Web Tension-Velocity Dynamics Linearization

The continuous operation of an R2R system is defined by interconnected, nonlinear physical dynamics governing web tension and roller velocity [cite: 5, 6]. To implement linear Model Predictive Control (MPC), we must extract a linearized state-space representation. 

### 1.1 The Nonlinear R2R Dynamics Equations
The user-provided mathematical model for a specific span $i$ bounded by roller $i-1$ and roller $i$ is defined by the following coupled differential equations.

**Tension Dynamics:**
Based on the principles of mass conservation and Hooke's Law for an elastic web [cite: 4, 6]:
\[ \frac{dT_i}{dt} = \frac{EA}{L_i}(v_i - v_{i-1}) + \frac{1}{L_i}(v_{i-1}T_{i-1} - v_i T_i) \]
Where:
*   $T_i$: Web tension in span $i$ (N)
*   $v_i$: Tangential velocity of roller $i$ (m/s)
*   $E$: Young's modulus of the web material (N/m²)
*   $A$: Cross-sectional area of the web (m²)
*   $L_i$: Length of the web span between roller $i-1$ and roller $i$ (m)

**Velocity Dynamics:**
Based on Newton's Second Law for rotating bodies:
\[ \frac{dv_i}{dt} = \frac{R_i^2}{J_i}(T_{i+1} - T_i) + \frac{R_i}{J_i} u_i - \frac{f_{b,i}}{J_i} v_i \]
Where:
*   $R_i$: Radius of roller $i$ (m)
*   $J_i$: Moment of inertia of roller $i$ (kg·m²)
*   $u_i$: Control input (motor torque applied to roller $i$) (N·m)
*   $f_{b,i}$: Viscous friction coefficient of the motor/bearings (N·m·s/rad)

### 1.2 State Vector and Control Input Definitions
For a 6-section R2R system, we define the 12-dimensional state vector $\mathbf{x}$ and the 6-dimensional input vector $\mathbf{u}$ as follows:
\[ \mathbf{x} = [T_1, T_2, T_3, T_4, T_5, T_6, v_1, v_2, v_3, v_4, v_5, v_6]^T \]
\[ \mathbf{u} = [u_1, u_2, u_3, u_4, u_5, u_6]^T \]

### 1.3 Exact Jacobian Derivation
To form the linear time-invariant (LTI) state-space model $\dot{\mathbf{x}} \approx A\Delta\mathbf{x} + B\Delta\mathbf{u}$, we evaluate the partial derivatives of the nonlinear equations with respect to every state and input at a predefined steady-state operating point $(\mathbf{x}_{ss}, \mathbf{u}_{ss})$ [cite: 1, 3].

Let $f_{T,i} = \frac{dT_i}{dt}$ and $f_{v,i} = \frac{dv_i}{dt}$. The exact partial derivatives are:

**Tension Equation Partial Derivatives:**
1.  **w.r.t $T_i$:** 
    \[ \frac{\partial f_{T,i}}{\partial T_i} = -\frac{v_{ss,i}}{L_i} \]
2.  **w.r.t $T_{i-1}$:** 
    \[ \frac{\partial f_{T,i}}{\partial T_{i-1}} = \frac{v_{ss,i-1}}{L_i} \]
3.  **w.r.t $v_i$:** 
    \[ \frac{\partial f_{T,i}}{\partial v_i} = \frac{EA}{L_i} - \frac{T_{ss,i}}{L_i} = \frac{EA - T_{ss,i}}{L_i} \]
4.  **w.r.t $v_{i-1}$:** 
    \[ \frac{\partial f_{T,i}}{\partial v_{i-1}} = -\frac{EA}{L_i} + \frac{T_{ss,i-1}}{L_i} = -\frac{EA - T_{ss,i-1}}{L_i} \]

**Velocity Equation Partial Derivatives:**
1.  **w.r.t $T_{i+1}$:**
    \[ \frac{\partial f_{v,i}}{\partial T_{i+1}} = \frac{R_i^2}{J_i} \]
2.  **w.r.t $T_i$:**
    \[ \frac{\partial f_{v,i}}{\partial T_i} = -\frac{R_i^2}{J_i} \]
3.  **w.r.t $v_i$:**
    \[ \frac{\partial f_{v,i}}{\partial v_i} = -\frac{f_{b,i}}{J_i} \]
4.  **w.r.t $u_i$:**
    \[ \frac{\partial f_{v,i}}{\partial u_i} = \frac{R_i}{J_i} \]

### 1.4 Constructing the A and B Matrices
The matrices $A \in \mathbb{R}^{12 \times 12}$ and $B \in \mathbb{R}^{12 \times 6}$ are constructed from these derivatives. The structure exhibits distinct tridiagonal and bidiagonal couplings.

**Matrix A structure:**
We can partition $A$ into four $6 \times 6$ sub-matrices:
\[ A = \begin{bmatrix} A_{11} & A_{12} \\ A_{21} & A_{22} \end{bmatrix} \]

*   **$A_{11}$ (Tension w.r.t Tension):** Bidiagonal lower matrix. The main diagonal contains $-v_{ss,i}/L_i$. The sub-diagonal contains $v_{ss,i-1}/L_i$.
*   **$A_{12}$ (Tension w.r.t Velocity):** Bidiagonal lower matrix. The main diagonal contains $(EA - T_{ss,i})/L_i$. The sub-diagonal contains $-(EA - T_{ss,i-1})/L_i$.
*   **$A_{21}$ (Velocity w.r.t Tension):** Bidiagonal upper matrix. The main diagonal contains $-R_i^2/J_i$. The super-diagonal contains $R_i^2/J_i$.
*   **$A_{22}$ (Velocity w.r.t Velocity):** Diagonal matrix. The elements are $-f_{b,i}/J_i$.

**Matrix B structure:**
\[ B = \begin{bmatrix} 0 \\ B_{21} \end{bmatrix} \]
Where the top half (tension states) is entirely zero, and $B_{21}$ is a diagonal $6 \times 6$ matrix where the elements are $R_i/J_i$.

### 1.5 Boundary Conditions and Coupling Effects
The first span ($i=1$) depends on $T_0$ and $v_0$. Typically, $v_0$ is the unwinder speed, and $T_0$ is the initial tension (often near zero or dictated by an unwinding brake). 
*   **Because $v_0$ and $T_0$ are known inlet conditions, they do not appear in the state vector.** 
*   In the $\Delta \mathbf{x}$ formulation, if the inlet velocity $v_0$ is perfectly constant, $\Delta v_0 = 0$, so the derivatives with respect to $v_0$ evaluate to zero in the state matrix. If $v_0$ fluctuates, it acts as a measurable disturbance $\mathbf{d}$ in the affine equation $\dot{\mathbf{x}} = A\mathbf{x} + B\mathbf{u} + B_d \mathbf{d}$. 
*   Similarly, the velocity dynamics of roller 6 depend on $T_7$, the rewinder tension. If $T_7$ is controlled independently or is zero, its deviation is zero.

**Coupling impacts:** This matrix structure mathematically demonstrates that tension $T_i$ is strongly coupled downstream via velocity $v_i$, and velocity $v_i$ is strongly coupled upstream via tension $T_i$. Ignoring off-diagonal elements in the controller design leads to severe steady-state errors and oscillatory limits [cite: 4, 7].

***

## 2. Steady-State Target Computation

Model Predictive Control manages transient variations around an equilibrium point. When a reference setpoint changes (e.g., Section 3 tension changes from 20N to 44N), the system's equilibrium shifts [cite: 1, 3]. The MPC controller must be given a newly computed target state vector $\mathbf{x}_{ss}$ and control vector $\mathbf{u}_{ss}$ [cite: 5, 8].

### 2.1 Velocity Equilibrium
At steady state, the derivatives are zero: $\frac{dT_i}{dt} = 0$ and $\frac{dv_i}{dt} = 0$.
Setting the tension dynamics to zero:
\[ 0 = EA(v_{ss,i} - v_{ss,i-1}) + v_{ss,i-1}T_{ss,i-1} - v_{ss,i} T_{ss,i} \]
Rearranging to solve for $v_{ss,i}$ sequentially from $i=1$ to $6$:
\[ v_{ss,i} (EA + T_{ss,i}) = v_{ss,i-1} (EA + T_{ss,i-1}) \]
\[ v_{ss,i} = v_{ss,i-1} \left( \frac{EA + T_{ss,i-1}}{EA + T_{ss,i}} \right) \]
*Given known target tensions $T_{ss,i}$ and a known baseline entry velocity $v_0$, the steady-state velocities must be cascaded downstream.* This mathematically proves that a change in one intermediate tension reference fundamentally alters the required steady-state velocities of all downstream rollers.

### 2.2 Control Input Equilibrium
Setting the velocity dynamics to zero:
\[ 0 = \frac{R_i^2}{J_i}(T_{ss,i+1} - T_{ss,i}) + \frac{R_i}{J_i} u_{ss,i} - \frac{f_{b,i}}{J_i} v_{ss,i} \]
Solving for $u_{ss,i}$:
\[ u_{ss,i} = \frac{1}{R_i} \left[ f_{b,i} v_{ss,i} - R_i^2 (T_{ss,i+1} - T_{ss,i}) \right] \]
This computes the exact steady-state baseline torque required to maintain the friction losses and the tension differentials across the roller.

***

## 3. Continuous-to-Discrete Conversion

Digital control systems execute at discrete intervals $dt$ (e.g., $dt=0.01$ seconds). The continuous state-space matrices $(A, B)$ must be accurately transformed into discrete matrices $(A_d, B_d)$. 

### 3.1 Using `scipy.signal.cont2discrete`
The precise function available in SciPy is `scipy.signal.cont2discrete` [cite: 9].

**Signature:**
```python
scipy.signal.cont2discrete(system, dt, method='zoh', alpha=None)
```
**Parameters:**
*   `system`: A tuple containing the continuous matrices `(A, B, C, D)`. For our full-state feedback MPC, $C$ is a $12 \times 12$ identity matrix, and $D$ is a $12 \times 6$ zero matrix.
*   `dt`: The sampling time (float, e.g., 0.01).
*   `method`: Discretization method. 
    *   `'zoh'` (Zero-Order Hold): Assumes the control input $u$ is constant over the sample period. This perfectly represents a digital-to-analog converter (DAC) outputting discrete values to a motor drive [cite: 9, 10].
    *   `'bilinear'` (Tustin's approximation): Uses trapezoidal integration. 
    *   `'euler'`: Forward differencing. Avoid for stiff systems.

**Return Shape and Calling Convention:**
```python
import numpy as np
from scipy.signal import cont2discrete

C = np.eye(12)
D = np.zeros((12, 6))

system_c = (A_cont, B_cont, C, D)
A_d, B_d, C_d, D_d, dt = cont2discrete(system_c, dt=0.01, method='zoh')
```
*   `A_d` is returned as a shape `(12, 12)` NumPy array.
*   `B_d` is returned as a shape `(12, 6)` NumPy array.

### 3.2 Numerical Stability and Stiffness Concerns
Web handling models possess extremely high stiffness [cite: 5]. The elastic term $EA$ is typically on the order of $10^4$ to $10^6$ Newtons, meaning the eigenvalues of the $A$ matrix have very large negative real parts (fast transient decay). 

When $dt = 0.01$s, the exact matrix exponential $e^{A \cdot dt}$ used by the `'zoh'` method can encounter numerical precision limits if the system condition number is extreme [cite: 9]. 
*   **Mitigation:** If numerical warnings appear during `cont2discrete`, verify that parameters like $E$ and $J$ are accurately scaled, or momentarily substitute `'bilinear'` which offers improved numerical stability for stiff matrices at the cost of slight frequency warping. However, `'zoh'` should remain the primary target as it faithfully represents the physical actuator operation.

***

## 4. LQR Gain Computation in Python

Before deploying constrained MPC, an unconstrained linear quadratic regulator (LQR) is typically formulated. In MPC theory, the optimal LQR cost-to-go is frequently utilized as the terminal cost matrix $P$ to guarantee closed-loop stability over a finite prediction horizon.

### 4.1 Solving the DARE via `scipy.linalg.solve_discrete_are`
The Discrete-time Algebraic Riccati Equation (DARE) is solved using `scipy.linalg.solve_discrete_are` [cite: 11].

**Signature and Parameter Ordering:**
```python
scipy.linalg.solve_discrete_are(a, b, q, r, e=None, s=None, balanced=True)
```
Where parameters map precisely to:
*   `a`: The discrete state transition matrix $A_d$ $(12 \times 12)$.
*   `b`: The discrete input matrix $B_d$ $(12 \times 6)$.
*   `q`: The state penalty matrix $Q$ $(12 \times 12)$.
*   `r`: The input penalty matrix $R$ $(6 \times 6)$.

**Matrix Dimension Requirements:**
$A_d$ and $Q$ must be symmetric, square $(N_x \times N_x)$ matrices. $B_d$ must be $(N_x \times N_u)$. $R$ must be a symmetric, square $(N_u \times N_u)$ matrix.

### 4.2 Exact Formula for the LQR Gain Matrix
Once the stationary solution $P \in \mathbb{R}^{12 \times 12}$ is obtained, the optimal feedback gain matrix $K_{lqr} \in \mathbb{R}^{6 \times 12}$ is calculated mathematically as:
\[ K_{lqr} = (R + B_d^T P B_d)^{-1} B_d^T P A_d \]

**Python Implementation:**
```python
from scipy.linalg import solve_discrete_are
import numpy as np

# Solve DARE
P = solve_discrete_are(A_d, B_d, Q, R)

# Compute optimal feedback gain K
R_inv = np.linalg.inv(R + B_d.T @ P @ B_d)
K_lqr = R_inv @ B_d.T @ P @ A_d
```

### 4.3 Matrix Conditioning and Fallbacks
**Pitfalls:** The `solve_discrete_are` function relies on QZ decomposition and stable subspace isolation. If $A_d$ contains eigenvalues identically equal to 1.0 (marginally stable states) that are completely uncontrollable, the algorithm will raise a `LinAlgError` ("Failed to find a finite solution") [cite: 11, 12]. Furthermore, if $Q$ is perfectly positive semi-definite (contains zeros on the diagonal), numerical noise during balancing can prevent convergence.

**Fallback Strategies:**
1.  **Damping:** Add a tiny positive factor to the diagonal of $Q$: `Q = Q + np.eye(12) * 1e-6`.
2.  **Balancing:** Ensure parameter `balanced=True` (the default) is kept [cite: 11]. If the matrix elements vary by orders of magnitude (e.g., $EA \approx 10^5$, velocities $\approx 10^{-2}$), pre-conditioning the state variables via unit scaling can resolve numerical divergence.

***

## 5. MPC Implementation Without External Optimization Libraries

In resource-constrained or specialized deployment environments where advanced C++ solvers like OSQP or CasADi cannot be installed, standard Python libraries (`numpy 1.26.4`, `scipy 1.13.0`) provide sufficient mathematical breadth to implement a full dense-QP MPC [cite: 13, 14, 15].

### 5.1 Constructing the Prediction Matrices ($\Phi$ and $\Gamma$)
For a prediction horizon $N$, the future states $X = [x_{1}, x_{2}, \dots, x_{N}]^T$ can be represented explicitly as a function of the current state $x_0$ and the sequence of future control actions $U = [u_{0}, u_{1}, \dots, u_{N-1}]^T$:
\[ X = \Phi x_0 + \Gamma U \]

Where $\Phi \in \mathbb{R}^{12N \times 12}$ and $\Gamma \in \mathbb{R}^{12N \times 6N}$ are defined as:
\[ \Phi = \begin{bmatrix} A_d \\ A_d^2 \\ \vdots \\ A_d^N \end{bmatrix}, \quad \Gamma = \begin{bmatrix} B_d & 0 & \dots & 0 \\ A_d B_d & B_d & \dots & 0 \\ \vdots & \vdots & \ddots & \vdots \\ A_d^{N-1} B_d & A_d^{N-2} B_d & \dots & B_d \end{bmatrix} \]

**Python construction logic:**
```python
def get_prediction_matrices(Ad, Bd, N):
    nx, nu = Bd.shape
    Phi = np.zeros((N * nx, nx))
    Gamma = np.zeros((N * nx, N * nu))
    
    A_power = Ad.copy()
    for i in range(N):
        # Fill Phi
        Phi[i*nx:(i+1)*nx, :] = A_power
        
        # Fill Gamma
        # For the i-th block row, fill j from 0 up to i
        A_power_b = np.eye(nx)
        for j in range(i, -1, -1):
            Gamma[i*nx:(i+1)*nx, j*nu:(j+1)*nu] = A_power_b @ Bd
            A_power_b = A_power_b @ Ad
            
        A_power = A_power @ Ad
        
    return Phi, Gamma
```

### 5.2 Formulating the Dense QP Cost Function
The standard MPC objective is to minimize deviations over the horizon:
\[ J = \sum_{k=0}^{N-1} (x_k^T Q x_k + u_k^T R u_k) + x_N^T P x_N \]
In dense vector form: $J = X^T \bar{Q} X + U^T \bar{R} U$, where $\bar{Q} = \text{blkdiag}(Q, Q, \dots, P)$ and $\bar{R} = \text{blkdiag}(R, R, \dots, R)$.

Substitute $X = \Phi x_0 + \Gamma U$:
\[ J(U) = (\Phi x_0 + \Gamma U)^T \bar{Q} (\Phi x_0 + \Gamma U) + U^T \bar{R} U \]
\[ J(U) = U^T (\Gamma^T \bar{Q} \Gamma + \bar{R}) U + 2 x_0^T \Phi^T \bar{Q} \Gamma U + x_0^T \Phi^T \bar{Q} \Phi x_0 \]

To match the standard QP form $\min_z \frac{1}{2} z^T H z + f^T z$, we identify:
*   **Hessian:** $H = 2 (\Gamma^T \bar{Q} \Gamma + \bar{R})$
*   **Gradient Vector:** $f = 2 \Gamma^T \bar{Q} \Phi x_0$
*(Note: To simplify the scale, the leading constant $2$ is universally removed in formulation, yielding $H = \Gamma^T \bar{Q} \Gamma + \bar{R}$ and $f = \Gamma^T \bar{Q} \Phi x_0$ without loss of generality).*

### 5.3 Solving the Unconstrained Solution using `scipy.linalg.solve`
If there are no physical limits on the motors (an ideal theoretical case), the global minimum is found analytically where the derivative of $J$ with respect to $U$ is zero [cite: 16].
\[ H U = -f \implies U = -H^{-1} f \]
The first control action $u_0$ is extracted from the vector $U$:
\[ K_{mpc} = - \text{first } N_u \text{ rows of } H^{-1} (\Gamma^T \bar{Q} \Phi) \]
```python
from scipy.linalg import solve

# f_vec = Gamma.T @ Q_bar @ Phi @ x0
# solve H * U = -f_vec directly
U_opt = solve(H, -f_vec, assume_a='pos') 
u0 = U_opt[0:nu]
```
*The `assume_a='pos'` parameter optimally routes the algorithm to use Cholesky factorization, accelerating real-time performance.*

### 5.4 Constrained QP using `scipy.optimize.minimize` (SLSQP)
In physical R2R systems, motor torques are constrained ($u_{min} \le u_k \le u_{max}$). The Sequential Least SQuares Programming (SLSQP) algorithm native to SciPy handles box bounds and generic constraints reliably [cite: 13, 14, 17].

**Objective Formulation:**
```python
def objective(U, H, f):
    return 0.5 * U.T @ H @ U + f.T @ U

def gradient(U, H, f):
    return H @ U + f
```

**Constraints and Bounds Formatting:**
Bounds strictly constrain the decision variables $U$.
```python
# Create bounds for all N steps
bounds = [(u_min[i%nu], u_max[i%nu]) for i in range(N*nu)]
```

If state constraints ($x_{min} \le X \le x_{max}$) are required, they must be formatted as SciPy constraints dictionaries. Since $X = \Phi x_0 + \Gamma U$:
\[ \Gamma U \ge X_{min} - \Phi x_0 \]
\[ -\Gamma U \ge -(X_{max} - \Phi x_0) \]

```python
# SLSQP dictionary requires function output to be >= 0 for inequalities
def state_constraint(U, Gamma, Phi, x0, X_max):
    X_pred = Phi @ x0 + Gamma @ U
    return X_max - X_pred # Requires X_max - X_pred >= 0 -> X_pred <= X_max

cons = ({'type': 'ineq', 'fun': state_constraint, 'args': (Gamma, Phi, x0, X_max)})
```

**Complete API Call:**
```python
from scipy.optimize import minimize

U_init = np.zeros(N * nu)
res = minimize(
    fun=objective, 
    x0=U_init, 
    args=(H, f_vec), 
    method='SLSQP', 
    jac=gradient, 
    bounds=bounds,
    # constraints=[cons], # Uncomment if state constraints applied
    options={'ftol': 1e-6, 'maxiter': 100, 'disp': False}
)

if res.success:
    u0 = res.x[0:nu]
else:
    u0 = U_init[0:nu] # Fallback
```
*Providing the exact analytical Jacobian `jac=gradient` reduces execution time drastically compared to numerical differentiation.* [cite: 14, 17]

***

## 6. Reference Tracking with Step Changes

In practical operations, tension references are rarely constant. A process recipe may demand Section 3 tension to step from 20N to 44N at $t = 0.5$s [cite: 3].

### 6.1 Formulation Strategies
There are three main paradigms in MPC design for tracking:
1.  **Delta Formulation (Incremental MPC):** The state is augmented to $[\Delta x_k^T, u_{k-1}^T]^T$ and the control target is $\Delta u_k$. This inherently integrates error, eliminating steady-state discrepancies at the cost of significantly inflating matrix dimensions (from 12 states to 18 states) and severely slowing down solving time.
2.  **Reference Tracking Augmented State:** Formulating the state to include the setpoint generator.
3.  **Deviation (Error-Based) Formulation:** The state $\mathbf{x}$ and control $\mathbf{u}$ are mapped as strict deviations from a known optimal steady state:
    \[ \delta \mathbf{x} = \mathbf{x}_{current} - \mathbf{x}_{ss} \]
    \[ \delta \mathbf{u} = \mathbf{u}_{current} - \mathbf{u}_{ss} \]

### 6.2 The Optimal Approach for Linear MPC
For a heavily coupled system executing on Python solvers, **the Deviation Formulation** is overwhelmingly preferred. 

**Standard Procedure:**
1.  At $t=0.5$s, a new reference $T_{ref} = 44N$ arrives.
2.  *Immediately* execute the steady-state target computations defined in Section 2, evaluating the nonlinear equilibrium to yield the new true targets $\mathbf{x}_{ss, new}$ and $\mathbf{u}_{ss, new}$ [cite: 1].
3.  Re-linearize the state-space matrices $(A, B)$ around $(\mathbf{x}_{ss, new}, \mathbf{u}_{ss, new})$ to capture the correct tangential dynamics.
4.  Compute the delta input state for the solver: $\delta x_0 = \mathbf{x}_{measured} - \mathbf{x}_{ss, new}$.
5.  Solve the QP.
6.  Inject real control effort: $\mathbf{u}_{applied} = \mathbf{u}_{ss, new} + \delta u_0$.

This paradigm maintains matrices at purely $12 \times 12$ dimensions, maximizing execution speed and utilizing physics to compute feed-forward equilibrium [cite: 1, 3].

***

## 7. Tuning Guidelines for Q and R matrices

The diagonal weighting matrices $Q \in \mathbb{R}^{12 \times 12}$ and $R \in \mathbb{R}^{6 \times 6}$ dictate control trade-offs [cite: 3, 18].

### 7.1 Relative Weightings: Tension vs. Velocity
In an R2R system, tension regulation directly dictates product quality (preventing deformation or scratching) [cite: 1, 2, 5]. The tangential velocity is vital for throughput but small deviations are tolerated as long as tension bounds hold. 

Therefore, a disparity in weights is structurally required:
*   **Tension weight ($Q_T$):** Large. Normalization strategies dictate that states with smaller tolerance limits receive higher weights. A standard heuristic is $Q_{T, i} \approx 100 / (T_{ref, i})^2$ [cite: 18]. This normalizes the squared error and aggressively penalizes single-digit Newton variations.
*   **Velocity weight ($Q_v$):** Small. Setting $Q_{v, i} \approx 0.1 / (v_{ref, i})^2$ allows the solver to momentarily sacrifice velocity tracking to rapidly suppress tension transients [cite: 3, 18]. The velocity acts as an internal energy sponge.

### 7.2 The Effect of the R Weighting
The $R$ matrix penalizes aggressive use of the motor torques $\Delta u$. 
*   **Low R values (e.g., $10^{-4}$):** Encourages immediate, sharp torque spikes. Reduces settling time drastically but risks mechanical shock, slip between the web and the roller, and control chatter.
*   **High R values (e.g., $1.0$):** Demands slow, conservative torque gradients. Creates sluggish responses and significant overshoot during step changes, but guarantees smooth electromechanical operations.

### 7.3 Prediction Horizon ($N$)
The typical prediction horizon for R2R processes ranges between $N = 10$ and $N = 30$ steps [cite: 3, 18].
*   At $dt = 0.01$s, $N=20$ yields a $0.2$s lookahead. This is typically sufficient because longitudinal acoustic waves propagate through webs virtually instantaneously, and dominant dynamics are captured.
*   If $N < 5$, the controller becomes myopic and will destabilize the tightly coupled interactions.
*   If $N > 40$, the $H$ matrix for the QP grows non-linearly ($N \cdot N_u \times N \cdot N_u$), resulting in geometric increases in SLSQP cycle time [cite: 13].

***

## 8. Common Pitfalls in Implementation

### 8.1 Sign Conventions in R2R Dynamics
A remarkably common error in R2R control theory involves sign inversion in the mass conservation equations. Tension $T_i$ pulls *backward* on the $i$-th roller, fighting its forward rotation. Conversely, tension $T_{i+1}$ from the downstream span pulls *forward* on the $i$-th roller [cite: 6, 19]. 
*   Ensure the term $(T_{i+1} - T_i)$ in the $\frac{dv_i}{dt}$ equation remains strictly ordered. Reversing this causes the modeled system to appear fundamentally unstable.

### 8.2 Off-By-One Indexing Errors
In academic formulations, span $i$ is situated directly between roller $i-1$ and roller $i$. 
*   This implies the velocity of the roller *preceding* the zone dictates the material feed-in rate $v_{i-1}$, and the roller *terminating* the zone dictates the pull-out rate $v_i$. 
*   Array indices in Python are zero-based. Array `T` maps to $T_1$, meaning it depends on `v` ($v_1$) and $v_0$ (inlet velocity). Hardcoding offsets properly prevents cross-wiring the controller's knowledge of the physical topology.

### 8.3 Ensuring Correct Coupling Structure
A linear model that has a fully diagonal $A_{12}$ sub-matrix is strictly flawed. As evaluated in Section 1, the variation $\frac{\partial f_{T,i}}{\partial v_{i-1}}$ maps to the sub-diagonal [cite: 1, 4]. If this coupling is inadvertently dropped in code formulation, the MPC will not recognize that accelerating an upstream roller relieves downstream tension. This creates severe phase lag during actual hardware deployment.

### 8.4 Handling Constant Inlet Velocity $v_0$
As derived, $v_0$ does not possess a differential equation $\frac{dv_0}{dt}$ within this scope and therefore strictly cannot exist in the state vector $\mathbf{x}$. 
*   If $v_0$ changes (for example, the master unwinder ramps up speed), this must be treated as a known measurable disturbance. 
*   The MPC handles this automatically if the reference tracking framework relies on continuous steady-state recalculation. When $v_0$ ramps up, $v_{ss,i}$ scales proportionately across the entire line [cite: 3, 8]. The state vector deviations remain near zero, and the MPC merely injects the new larger steady-state torques $u_{ss, i}$, providing perfect implicit feed-forward rejection.

***

## 9. Complete Python MPC Implementation Example

Synthesizing all derived algorithms, the following represents the core execution loop architecture using native SciPy for an integrated MPC cycle.

```python
import numpy as np
from scipy.signal import cont2discrete
from scipy.linalg import solve_discrete_are
from scipy.optimize import minimize

class R2R_MPC:
    def __init__(self, sys_params, dt, N):
        self.dt = dt
        self.N = N
        self.nx = 12
        self.nu = 6
        # Assume Q and R carefully tuned per Section 7
        self.Q = np.diag([100.0]*6 + [0.1]*6)
        self.R = np.eye(self.nu) * 0.05
        
    def prepare_matrices(self, A_cont, B_cont):
        # 1. Discretization
        C = np.eye(self.nx)
        D = np.zeros((self.nx, self.nu))
        Ad, Bd, _, _, _ = cont2discrete((A_cont, B_cont, C, D), self.dt, method='zoh')
        
        # 2. DARE for Terminal Cost
        P = solve_discrete_are(Ad, Bd, self.Q, self.R)
        
        # 3. Form Q_bar and R_bar
        Q_bar = np.kron(np.eye(self.N), self.Q)
        Q_bar[-self.nx:, -self.nx:] = P # Apply terminal cost
        R_bar = np.kron(np.eye(self.N), self.R)
        
        # 4. Construct Phi and Gamma
        Phi = np.zeros((self.N * self.nx, self.nx))
        Gamma = np.zeros((self.N * self.nx, self.N * self.nu))
        A_power = Ad.copy()
        
        for i in range(self.N):
            Phi[i*self.nx:(i+1)*self.nx, :] = A_power
            A_power_b = np.eye(self.nx)
            for j in range(i, -1, -1):
                Gamma[i*self.nx:(i+1)*self.nx, j*self.nu:(j+1)*self.nu] = A_power_b @ Bd
                A_power_b = A_power_b @ Ad
            A_power = A_power @ Ad
            
        # 5. Hessian H
        self.H = Gamma.T @ Q_bar @ Gamma + R_bar
        self.Gamma_T_Q = Gamma.T @ Q_bar @ Phi
        
    def step(self, x_meas, x_ss, u_ss, u_min_abs, u_max_abs):
        # Calculate deviation state
        dx = x_meas - x_ss
        
        # Calculate f vector
        f = self.Gamma_T_Q @ dx
        
        # Define bounds (deviation bounds based on ss)
        bounds = []
        for i in range(self.N * self.nu):
            idx = i % self.nu
            bounds.append((u_min_abs[idx] - u_ss[idx], u_max_abs[idx] - u_ss[idx]))
            
        def obj(U):
            return 0.5 * U.T @ self.H @ U + f.T @ U
            
        def grad(U):
            return self.H @ U + f
            
        # Initial guess
        U0 = np.zeros(self.N * self.nu)
        
        # Solve constrained QP
        res = minimize(fun=obj, x0=U0, method='SLSQP', jac=grad, bounds=bounds, 
                       options={'disp': False, 'ftol': 1e-6})
                       
        if res.success:
            du_opt = res.x[:self.nu]
        else:
            # Fallback to unconstrained if SLSQP fails to converge gracefully
            du_opt = np.linalg.solve(self.H, -f)[:self.nu]
            
        # Return physical motor command
        return u_ss + du_opt
```

This extensive framework directly satisfies deployment demands by avoiding C++ wrapper dependencies (CasADi, CVXPY) while preserving analytical fidelity, constraints handling, and dynamic recalculation parameters essential to stabilizing robust R2R mechanisms.

**Sources:**
1. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEvzbRcJAQG5vXXQaSjZDL2y2Ydlh6osr1JAAwDLTONL8Bc5KhqBTfLUo2Cmn6wjZgDoOpEEI5dcb6nfBdJZnDQLUJW44UEjTURX427LlYaS4xHqHuoM9cr)
2. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWeKDiFf4F-DdoWaIoy55ksMQoZrM7b_2DtZ9mdgefsb0BleL1CFt0Va5tevlfr3Vmzmdiv0fXBjQdVdLcytd03cPa3su_A4av-wQ-DkrhWprVBgkP5zKiPBE8TFcVaBehnHFIsnKu8kdI3TjAeOYu3HMiOhN1CXnb41qiLZKjlI5FRYioRuFPngxIOvuvxlNF9xzP76hgRxYP8Q2IjZ13txA7_TYybxOTTkqLB8kr84H8bdmvndOdJtnM21eX)
3. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0qWdN0LT_UI0eteO-MMJpulqBfWNTc2pS9oyDNp16OOGm2qjbdI_f00SrfMjcqQ3DFITGOwO6yvsj-v2wNnMxUrH5yRMfxs38QSZUM37p99xKKKvPlzoB)
4. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGX-YCqS4Z18sInSX8WYQtIYZ_vXcSqCMfCeU0rYfj5CIwcXvAPr-ERUO6dE_NGl7YUarZU1QvBpdSmjFbaoMnUvrAM5qlnNSrF3c-C88JaD-xCdnA-V2iN0_knnhhFUHIkSCf4ceX-V1UolQAnW_OdShbs2XRAcNCEOO2XZKnZpAnm9FPGE5Lu-pdICs0lEH-3_pQE7z9oVviVg08tynIrLrow2Sv1HeNebPwSqPfzW6aIKaI7rQczOpzbQqzgS_swo-rMj6qZGug=)
5. [rsc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjBtL9OF6dAHb62sWY6Kp3tDZoBd4WQPCcDRqHVUlWOUVyhVWvksgoY5D1mlvUXAS8jn8iFL-oBSfv5BREC1TLPc1vmtDGxq5EqFuIcG_kL1RCNf2cNkyRUL4INdfY27wXEupffoSZyUK4CVPuuYQabBK4)
6. [ieee.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFnpYX__Cmqs8SuUfs-edzVttrKJo4sywrpTvtKb5Okx3mRp0beZV2pzaMk_ZHklSN0vU4mu6Htgwiyu9qCYGaQAGaIZ61ZERK98EhQqTfHxcAivXG-ihrBZNcQ_uNruCUqqOg2Ie8huqRcEMt-1EydcYlv)
7. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFzwHZ12bJMwPNnrM9bkfts85kjw3d9rtjz6Ed-37r9Vn5v_hazDdeeFXJblzK4DI9sp03ttGPa5r-OJYDe_XnFVkxrzi5vLlh4FKaNEAWqzNFOoi8LcqOKOOZvM95qwx5RRPedip-TkRdCMlJIWZA0rwkQfvfvE24f8FlQsTA6ZF9h-M3Rx8lodsFxhcT0y23ZGGfpcePcYNO7zHk-cVdn4DXN0i1T5VmHsjaVmxfYeStnpn2MxyU=)
8. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHhkdCqCe4VKpInVmdg5FYZnCK5iyBzNP1annfDsHahmZKNXUwDEoqMCI3LJEABOULzyPz4mYcUavbDQkQWckWgji_eCX55_GPqu9bKeuQ5Shf-mkkzjIM6uw-E0X1YyoJ590vsq7khQgmiWibs-87DQLdvCafbIXSyC0UoyZMjxDZE_Ft_kIQYhZZh8Z_Lif7SLZOI3wf7jWrP7dz)
9. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7kFR8B6nrHqyihqWa1zne373xL60i5_mXCtauaTPGhI06D30JubCOnUTyuxh_JrTWxoXsQRY75_HNM_QeQfwm6IoNEGOG7Pnsk5WV0pTfb0suXfCxRrMOiPvJLEl46YL9OUlahMLNjJySF90g1NbEmaqwxAZySYPBYWPRsnRo0bMnX4610Va-5w==)
10. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHk70nj0p-5b1buXLSLArP8fG4eMsCagqvkc6ZPMAnXbfjeXWhltq0SySWFDAILgiR50wRRVcpH47jJXT629tdpo5yaDW2Bd9jmzDEICkbXErO-oensu3TVS94oHSi5pDQu9Ip4WNtuDN0UVvRiiQK_bAYFtPE5_-ahIWU3W_4aug==)
11. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFKSqfDoubcoFOQ1fBiEiFJsh_YsFDgeH39l-5Uf7DO8gkpCBuu3TfPsjBe70yjHGa69XKwFU1HAfxla0T_7ileyIfgr9yCsV59OOMzi_L2KsvFwhcG0Bjz4_vStMyTxQJ5d9nshqYjn9WNyfTDkWXN5VvFNXWkX8mkb2CoG6-IaVHKgW4Xd2ToXZcVz1YG)
12. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbascq_2PwFY-XWC0CYsV4rND8roVXBwVWgmutby_Dy7tljcd83-7o9MTHzuETPC03SInIF_eHfkZmfXqtEFWEr4ZUm4PPHF1oOq6ViPmmhYFL5L-84EsivpVixoIB4LemQhPhXhTFz6rFi_-bQ7GYZFj0diF7PXRanbUTviqjRTjl3qBOP8CMVfUcASMFvj4ajOB1eKUSy6WMbBzn_H8FBNLGRhlZxp2SbEhAbDHd6_XkkjLKv_E=)
13. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGcfW2x_GKQ7JuRanZp4sacdB66MirAsh_YensPhnh3ReCrmwzuc5jxuvEWcci2SfYGE88StrebBjIM2Y0zNjCp9enKkF5Atb_6yrC4TsqHVAXopKzXg2zpoh2NcM75SVJRl_VWB42WjUGH709F9rgrz7KoMMqWWMdbncWdotEAN9IKGtzlfA==)
14. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2SyjenrDWYUtM6_5YgKr3lL8aUF_adoqLaIQ1RrpAh-h7DHeC5B8Rv1bU5a1bttAvnTq5e2hpdgkmRCRMrUo_qUu51KA7vkmSCQsDaU_nDmzXwqbJKWEfA7USAa6SMRSHCtJwXWAVfl2nd0Sqkv80T_ULcSdLbopU8g6w)
15. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNX9zLMzTrgku8DMYINWWJd6t3v_G73WdBRraUswHfbOMaBjD2P0KX6R0aCgUOJBuBRSsbb_rJNhbRFZsdz6W-EVvCL7GNwhkD-xS_Pt-NpFYm4uG-gaqUmAS9A1HibNkmKSqieJ5H2rvAnChl-puSFWYqRVMcTxwJKLHRv1qNvkQCEw==)
16. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGS26jVk_BKIlYRd6laJLbU5zJm27eFg63XHxzSC-MswvJ_-3W-ZKP0UOeBqX9r4OCcW6FKVIymEDCDw61ly0EBRtJBoDdRb-7w4m8HVigBSdzGPj-0sCtZ-NqNwavK52bcszhLjAiGCk_92Q==)
17. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYhSoG0vpf0eA2Q6-kegidAdpEV54jPDYNlMSQT9O2tpt5OkJdMzPDPwHDeA4Ed-ztL97kyDFqOdM9WwCVjTFgPQCDjhMq73Hj-X0V7MD6WvHARdnCYF4z8TnKFmNSJ8Q7FDGnDs3WMMtQYx2z0XsyIDxXQpd8kxb3HOqxeKSWfJWX7KRS5j6xvYzexCPHaq6RyLGcuRQF)
18. [agnxi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdnW0p6GjuRVw8XHvviWdx3-8xeFJ00tg-fz2FDmNDPzV1nHcJ3pOqdBSonH_nWWT9EOhdLE8lCnujWQu_Xg31bgnjD1IlD5zIjKJ8pI02pK9B2uzOqCEWo7SD_O1IMfpr10CB79oBBfqxlkMD)
19. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaUbq15VyVIC6cCdPjoOjs4QvHB-mhPqEeRvAuNDN7aV-l9we5lNtKDuMRdgSzcU14-MpesJlPYqe7hTYUhljk4OJiWCiXknTv0u4P8-u90QSk31C78gVHvIBWoykodX7p9WXAAfkOnUqQdV6yWy83M_-9EJBZoGHh0ie62cGnvFGM3bq8nTF_3uZ6RaIosu_hXqBjeShXsGOMH7NutO-GM2JkA0OFaJ0r6IinvwHNgBqL)
