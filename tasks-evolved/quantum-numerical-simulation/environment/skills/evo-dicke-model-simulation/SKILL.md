---
name: evo-dicke-model-simulation
description: Builds the open Dicke model Hamiltonian and Lindblad collapse operators in the full 2^N tensor product Hilbert space, solves for the steady-state density matrix, and extracts the reduced cavity state via partial trace.
---

# evo-dicke-model-simulation

Simulates the open Dicke model with N two-level systems coupled to a cavity mode.
Supports local dephasing, local emission, local pumping, collective emission, and collective pumping.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-dicke-model-simulation/scripts')
from utils import (
    build_local_spin_op, build_collective_spin_ops,
    build_dicke_hamiltonian, build_collapse_operators,
    solve_steady_state, get_cavity_state
)

# Build Hamiltonian
N_cav = 17  # n_max + 1
N_spin = 4
H, a_comp, Jz_comp, Jp_comp, Jm_comp = build_dicke_hamiltonian(
    N_cav, N_spin, wc=1.0, w0=1.0, g=1.0
)

# Build collapse operators
c_ops = build_collapse_operators(
    a_comp, Jp_comp, Jm_comp, N_cav, N_spin,
    kappa=1.0, gamma_phi=0.01, gamma_down=0.1
)

# Solve steady state and get cavity state
rho_ss = solve_steady_state(H, c_ops)
rho_cavity = get_cavity_state(rho_ss)
```

## Key Functions

- `build_local_spin_op(op, i, N)`: Place operator at position i in N-qubit space
- `build_collective_spin_ops(N)`: Build Jz, Jp, Jm from local operators
- `build_dicke_hamiltonian(N_cav, N_spin, wc, w0, g)`: Build full Dicke Hamiltonian
- `build_collapse_operators(...)`: Build collapse operator list for all dissipation channels
- `solve_steady_state(H, c_ops)`: Find steady state density matrix
- `get_cavity_state(rho_ss)`: Partial trace to get cavity reduced state
