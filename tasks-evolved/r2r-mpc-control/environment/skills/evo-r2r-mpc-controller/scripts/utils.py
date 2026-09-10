import numpy as np
import json
from scipy.linalg import solve_discrete_are
from scipy.optimize import minimize


def build_prediction_matrices(Ad, Bd, N):
    """Build MPC prediction matrices Phi and Gamma."""
    nx, nu = Ad.shape[0], Bd.shape[1]
    Phi = np.zeros((N * nx, nx))
    Gamma = np.zeros((N * nx, N * nu))
    
    A_power = Ad.copy()
    for i in range(N):
        Phi[i*nx:(i+1)*nx, :] = A_power
        A_power_b = np.eye(nx)
        for j in range(i, -1, -1):
            Gamma[i*nx:(i+1)*nx, j*nu:(j+1)*nu] = A_power_b @ Bd
            A_power_b = A_power_b @ Ad
        A_power = A_power @ Ad
    
    return Phi, Gamma


def build_qp_matrices(Phi, Gamma, Q, R_mat, P, N):
    """Build QP Hessian H and gradient matrix F."""
    nx = Q.shape[0]
    nu = R_mat.shape[0]
    
    Q_bar = np.kron(np.eye(N), Q)
    Q_bar[-nx:, -nx:] = P
    R_bar = np.kron(np.eye(N), R_mat)
    
    H = Gamma.T @ Q_bar @ Gamma + R_bar
    F = Gamma.T @ Q_bar @ Phi
    
    return H, F


def solve_mpc_step(H, F, dx, N, nu, u_ss=None, u_min=None, u_max=None):
    """Solve one MPC step. Returns optimal delta-u."""
    f = F @ dx
    try:
        du_all = np.linalg.solve(H, -f)
        du_opt = du_all[:nu]
    except np.linalg.LinAlgError:
        du_opt = np.zeros(nu)
    return du_opt


def compute_performance_metrics(log_data, T_ref_final, step_time=0.5):
    """
    Compute performance metrics from simulation log.
    
    Settling time: time for T3 to stay within 2N of 44N after step change.
    SSE: mean absolute error in last 1s vs final reference.
    """
    T_ref_final = np.array(T_ref_final)
    
    all_tensions = np.array([d['tensions'] for d in log_data])
    all_times = np.array([d['time'] for d in log_data])
    
    max_tension = float(np.max(all_tensions))
    min_tension = float(np.min(all_tensions))
    
    # Steady-state error: mean absolute error in last 1 second
    last_1s_mask = all_times >= (all_times[-1] - 1.0)
    last_tensions = all_tensions[last_1s_mask]
    sse = float(np.mean(np.abs(last_tensions - T_ref_final)))
    
    # Settling time for section 3 (index 2)
    # Use 2N absolute tolerance band around reference
    T3 = all_tensions[:, 2]
    T3_ref = T_ref_final[2]  # 44N
    tolerance = 2.0  # 2N absolute tolerance
    
    settling_time = float(all_times[-1] - step_time)  # default
    post_step_mask = all_times >= step_time
    post_step_indices = np.where(post_step_mask)[0]
    
    for idx in post_step_indices:
        remaining = T3[idx:]
        if len(remaining) > 0 and np.all(np.abs(remaining - T3_ref) <= tolerance):
            settling_time = float(all_times[idx] - step_time)
            break
    
    return {
        'steady_state_error': round(sse, 4),
        'settling_time': round(settling_time, 4),
        'max_tension': round(max_tension, 4),
        'min_tension': round(min_tension, 4)
    }


def save_output_files(controller_params, log_data, metrics, output_dir='/root'):
    """Save all three output JSON files."""
    import os
    
    with open(os.path.join(output_dir, 'controller_params.json'), 'w') as f:
        json.dump(controller_params, f, indent=2)
    
    control_log = {
        'phase': 'control',
        'data': log_data
    }
    with open(os.path.join(output_dir, 'control_log.json'), 'w') as f:
        json.dump(control_log, f, indent=2)
    
    with open(os.path.join(output_dir, 'metrics.json'), 'w') as f:
        json.dump(metrics, f, indent=2)
