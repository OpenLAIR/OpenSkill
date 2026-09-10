import numpy as np
import qutip

def build_local_spin_op(op, i, N):
    """
    Place operator `op` at position i in an N-qubit tensor product.
    All other positions get identity.
    Returns: Qobj in the N-qubit tensor product space.
    """
    op_list = [qutip.qeye(2)] * N
    op_list[i] = op
    return qutip.tensor(op_list)

def _spin_identity(N):
    """Build identity for N-qubit space as tensor product of individual identities."""
    return qutip.tensor([qutip.qeye(2)] * N)

def build_collective_spin_ops(N):
    """
    Build collective spin operators Jz, Jp, Jm from local operators.
    Jz = sum_i sigma_z^(i) / 2
    Jm = sum_i sigma_-^(i)
    Jp = Jm.dag()
    Returns: (Jz, Jp, Jm) in N-qubit tensor product space.
    """
    Jz = sum([build_local_spin_op(qutip.sigmaz(), i, N) for i in range(N)]) / 2.0
    Jm = sum([build_local_spin_op(qutip.sigmam(), i, N) for i in range(N)])
    Jp = Jm.dag()
    return Jz, Jp, Jm

def build_dicke_hamiltonian(N_cav, N_spin, wc, w0, g):
    """
    Build the Dicke Hamiltonian in composite space:
    H = wc * a^dag a + w0 * Jz + g * (a^dag + a)(J+ + J-)
    
    Composite space: tensor(Cavity, qubit_0, qubit_1, ..., qubit_{N-1})
    N_cav: Fock space dimension (n_max + 1)
    N_spin: number of two-level systems
    
    Returns: (H, a_comp, Jz_comp, Jp_comp, Jm_comp)
    """
    # Base operators
    a = qutip.destroy(N_cav)
    I_cav = qutip.qeye(N_cav)
    I_spin = _spin_identity(N_spin)
    
    # Collective spin operators in spin-only space
    Jz, Jp, Jm = build_collective_spin_ops(N_spin)
    
    # Composite space operators: tensor(cavity, qubit_0, ..., qubit_{N-1})
    a_comp = qutip.tensor(a, I_spin)
    Jz_comp = qutip.tensor(I_cav, Jz)
    Jp_comp = qutip.tensor(I_cav, Jp)
    Jm_comp = qutip.tensor(I_cav, Jm)
    
    # Hamiltonian
    H = wc * a_comp.dag() * a_comp + \
        w0 * Jz_comp + \
        g * (a_comp.dag() + a_comp) * (Jp_comp + Jm_comp)
    
    return H, a_comp, Jz_comp, Jp_comp, Jm_comp

def build_collapse_operators(a_comp, Jp_comp, Jm_comp, N_cav, N_spin,
                             kappa=0, gamma_phi=0, gamma_down=0, gamma_up=0,
                             gamma_down_col=0, gamma_up_col=0):
    """
    Build collapse operators for the open Dicke model.
    
    Parameters:
    - a_comp: cavity annihilation operator in composite space
    - Jp_comp, Jm_comp: collective spin operators in composite space
    - N_cav: Fock space dimension
    - N_spin: number of qubits
    - kappa: cavity loss rate
    - gamma_phi: local dephasing rate
    - gamma_down: local emission rate
    - gamma_up: local pumping rate  
    - gamma_down_col: collective emission rate
    - gamma_up_col: collective pumping rate
    
    Returns: list of collapse operators
    """
    I_cav = qutip.qeye(N_cav)
    c_ops = []
    
    # Cavity loss
    if kappa > 0:
        c_ops.append(np.sqrt(kappa) * a_comp)
    
    # Local dissipation channels
    for i in range(N_spin):
        if gamma_phi > 0:
            sz_i = build_local_spin_op(qutip.sigmaz(), i, N_spin)
            c_ops.append(np.sqrt(gamma_phi) * qutip.tensor(I_cav, sz_i))
        if gamma_down > 0:
            sm_i = build_local_spin_op(qutip.sigmam(), i, N_spin)
            c_ops.append(np.sqrt(gamma_down) * qutip.tensor(I_cav, sm_i))
        if gamma_up > 0:
            sp_i = build_local_spin_op(qutip.sigmap(), i, N_spin)
            c_ops.append(np.sqrt(gamma_up) * qutip.tensor(I_cav, sp_i))
    
    # Collective dissipation channels
    if gamma_down_col > 0:
        c_ops.append(np.sqrt(gamma_down_col) * Jm_comp)
    if gamma_up_col > 0:
        c_ops.append(np.sqrt(gamma_up_col) * Jp_comp)
    
    return c_ops

def solve_steady_state(H, c_ops):
    """
    Solve for the steady state density matrix.
    Uses direct method with RCM reordering for efficiency.
    
    Returns: rho_ss (Qobj density matrix)
    """
    rho_ss = qutip.steadystate(H, c_ops, method='direct', use_rcm=True)
    return rho_ss

def get_cavity_state(rho_ss):
    """
    Trace out spin degrees of freedom to get reduced cavity density matrix.
    Assumes composite space is tensor(Cavity, qubit_0, ..., qubit_{N-1}).
    Cavity is index 0.
    
    Returns: rho_cavity (Qobj density matrix)
    """
    rho_cavity = rho_ss.ptrace(0)
    return rho_cavity
