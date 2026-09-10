import numpy as np
from scipy.signal import cont2discrete
from scipy.linalg import solve_discrete_are


def compute_steady_state_velocities(T_ref, EA, v0):
    """
    Compute steady-state velocities for given tension references.
    
    From dT_i/dt = 0:
      0 = EA*(v_i - v_{i-1}) + v_{i-1}*T_{i-1} - v_i*T_i
      v_i*(EA - T_i) = v_{i-1}*(EA - T_{i-1})
      v_i = v_{i-1} * (EA - T_{i-1}) / (EA - T_i)
    
    NOTE: Uses (EA - T) formula matching the simulator dynamics.
    T_0 = 0 (no tension before first section), v_0 = inlet velocity.
    
    Args:
        T_ref: array of 6 reference tensions
        EA: web stiffness (N)
        v0: inlet velocity (m/s)
    
    Returns:
        v_ref: array of 6 steady-state velocities
    """
    n = len(T_ref)
    v_ref = np.zeros(n)
    v_prev = v0
    T_prev = 0.0  # T_0 = 0
    for i in range(n):
        v_ref[i] = v_prev * (EA - T_prev) / (EA - T_ref[i])
        v_prev = v_ref[i]
        T_prev = T_ref[i]
    return v_ref


def compute_steady_state_torques(T_ref, v_ref, R, fb, num_sections=6):
    """
    Compute steady-state control inputs (motor torques).
    
    From dv_i/dt = 0:
      0 = (R^2/J)*(T_{i+1} - T_i) + (R/J)*u_i - (fb/J)*v_i
      u_i = (fb/R)*v_i - R*(T_{i+1} - T_i)
    
    T_{n+1} = 0 (no tension after last section).
    
    Args:
        T_ref: array of 6 reference tensions
        v_ref: array of 6 steady-state velocities
        R: roller radius (m)
        fb: friction coefficient
        num_sections: number of sections (6)
    
    Returns:
        u_ref: array of 6 steady-state torques
    """
    u_ref = np.zeros(num_sections)
    for i in range(num_sections):
        T_next = T_ref[i + 1] if i < num_sections - 1 else 0.0
        u_ref[i] = (fb / R) * v_ref[i] - R * (T_next - T_ref[i])
    return u_ref


def build_continuous_AB(T_ss, v_ss, EA, L, R, J, fb, v0, num_sections=6):
    """
    Build continuous-time A and B matrices by computing Jacobians
    of the nonlinear dynamics at the steady-state operating point.
    
    State: x = [T1..T6, v1..v6] (12 states)
    Input: u = [u1..u6] (6 inputs)
    
    Tension dynamics:
      dT_i/dt = (EA/L)*(v_i - v_{i-1}) + (1/L)*(v_{i-1}*T_{i-1} - v_i*T_i)
    
    Velocity dynamics:
      dv_i/dt = (R^2/J)*(T_{i+1} - T_i) + (R/J)*u_i - (fb/J)*v_i
    
    Args:
        T_ss: steady-state tensions (6,)
        v_ss: steady-state velocities (6,)
        EA: web stiffness
        L: section length
        R: roller radius
        J: roller inertia
        fb: friction coefficient
        v0: inlet velocity (used as v_{i-1} for i=1)
        num_sections: 6
    
    Returns:
        A: 12x12 continuous state matrix
        B: 12x6 continuous input matrix
    """
    n = num_sections
    A = np.zeros((2 * n, 2 * n))
    B = np.zeros((2 * n, n))
    
    # Build velocity array including inlet: [v0, v1, v2, ..., v6]
    v_all = np.concatenate([[v0], v_ss])
    # Build tension array including boundaries: [T0=0, T1, ..., T6, T7=0]
    T_all = np.concatenate([[0.0], T_ss, [0.0]])
    
    for i in range(n):
        # Tension equation for T_{i+1} (1-indexed) -> index i in state
        # dT_{i+1}/dt depends on T_{i+1}, T_i, v_{i+1}, v_i
        # In 0-indexed arrays: tension state i, previous tension state i-1
        
        # Partial derivatives of tension equation i
        # w.r.t T_i (self): -v_ss_i / L
        A[i, i] = -v_ss[i] / L
        
        # w.r.t T_{i-1}: v_ss_{i-1} / L
        if i > 0:
            A[i, i - 1] = v_all[i] / L  # v_{i-1} in 1-indexed = v_all[i] in 0-indexed
        # For i=0, T_{i-1} = T_0 = 0 (constant), so no contribution
        
        # w.r.t v_i (self): (EA - T_ss_i) / L
        A[i, n + i] = (EA - T_ss[i]) / L
        
        # w.r.t v_{i-1}: -(EA - T_ss_{i-1}) / L
        if i > 0:
            A[i, n + i - 1] = -(EA - T_ss[i - 1]) / L
        # For i=0, v_{i-1} = v0 (constant), so no contribution to A
        
        # Velocity equation for v_{i+1} (1-indexed) -> index n+i in state
        # w.r.t T_i (self): -R^2/J
        A[n + i, i] = -(R**2) / J
        
        # w.r.t T_{i+1}: R^2/J
        if i < n - 1:
            A[n + i, i + 1] = (R**2) / J
        # For i=n-1, T_{i+1} = T_7 = 0 (constant), so no contribution
        
        # w.r.t v_i (self): -fb/J
        A[n + i, n + i] = -fb / J
        
        # B matrix: dv_i/dt w.r.t u_i = R/J
        B[n + i, i] = R / J
    
    return A, B


def discretize_system(A_cont, B_cont, dt, method='zoh'):
    """
    Discretize continuous state-space model using scipy.
    
    Args:
        A_cont: 12x12 continuous A matrix
        B_cont: 12x6 continuous B matrix
        dt: sampling time
        method: discretization method ('zoh' or 'bilinear')
    
    Returns:
        Ad: 12x12 discrete A matrix
        Bd: 12x6 discrete B matrix
    """
    nx = A_cont.shape[0]
    nu = B_cont.shape[1]
    C = np.eye(nx)
    D = np.zeros((nx, nu))
    
    sys_c = (A_cont, B_cont, C, D)
    Ad, Bd, _, _, _ = cont2discrete(sys_c, dt=dt, method=method)
    
    return Ad, Bd


def compute_lqr_gain(Ad, Bd, Q, R_mat):
    """
    Compute LQR gain matrix by solving the DARE.
    
    K_lqr = (R + Bd^T P Bd)^{-1} Bd^T P Ad
    
    Args:
        Ad: 12x12 discrete A matrix
        Bd: 12x6 discrete B matrix
        Q: 12x12 state cost matrix
        R_mat: 6x6 control cost matrix
    
    Returns:
        K_lqr: 6x12 LQR gain matrix
        P: 12x12 solution to DARE (terminal cost)
    """
    # Add small regularization for numerical stability
    Q_reg = Q + np.eye(Q.shape[0]) * 1e-8
    
    P = solve_discrete_are(Ad, Bd, Q_reg, R_mat)
    
    # K = (R + Bd^T P Bd)^{-1} Bd^T P Ad
    K_lqr = np.linalg.solve(R_mat + Bd.T @ P @ Bd, Bd.T @ P @ Ad)
    
    return K_lqr, P


def get_full_reference_state(T_ref, EA, v0, R, fb, num_sections=6):
    """
    Compute full reference state and control vectors.
    
    Args:
        T_ref: array of 6 reference tensions
        EA: web stiffness
        v0: inlet velocity
        R: roller radius
        fb: friction coefficient
    
    Returns:
        x_ref: 12-element reference state [T1..T6, v1..v6]
        u_ref: 6-element reference control [u1..u6]
    """
    v_ref = compute_steady_state_velocities(T_ref, EA, v0)
    u_ref = compute_steady_state_torques(T_ref, v_ref, R, fb, num_sections)
    x_ref = np.concatenate([T_ref, v_ref])
    return x_ref, u_ref
