"""
Network model construction for DC-OPF.

Builds susceptance matrix, generator-bus mapping, and branch flow data structures.
"""

import numpy as np


def build_b_matrix(branches, n_bus, ext2int):
    """Build nodal susceptance matrix B (n_bus x n_bus).

    B[i,j] = -1/x_ij for connected buses i,j
    B[i,i] = sum(1/x_ik) for all branches connected to bus i

    Handles transformer tap ratios (column 8, 0 treated as 1.0).
    Zero-reactance branches use 1e-6 to avoid division by zero.
    """
    B = np.zeros((n_bus, n_bus))
    for br in branches:
        f = ext2int[int(br[0])]
        t = ext2int[int(br[1])]
        x = br[3]
        if abs(x) < 1e-12:
            x = 1e-6

        b = 1.0 / x
        B[f, f] += b
        B[t, t] += b
        B[f, t] -= b
        B[t, f] -= b
    return B


def get_gen_bus_indices(gens, ext2int):
    """Map each generator to its internal bus index.

    Returns list of internal bus indices, one per generator.
    """
    indices = []
    for gen in gens:
        bus_ext = int(gen[0])
        indices.append(ext2int[bus_ext])
    return indices


def get_branch_flow_data(branches, ext2int):
    """Extract branch flow computation data.

    Returns list of dicts with:
    - f_idx, t_idx: internal bus indices
    - b: susceptance (1/x)
    - rate_a: MW rating (0 = unconstrained)
    - f_bus, t_bus: external bus numbers (for reporting)
    """
    flow_data = []
    for br in branches:
        f_ext = int(br[0])
        t_ext = int(br[1])
        f_idx = ext2int[f_ext]
        t_idx = ext2int[t_ext]
        x = br[3]
        if abs(x) < 1e-12:
            x = 1e-6
        b = 1.0 / x
        rate_a = br[5]  # RATE_A (MVA rating)

        flow_data.append({
            'f_idx': f_idx,
            't_idx': t_idx,
            'b': b,
            'rate_a': rate_a,
            'f_bus': f_ext,
            't_bus': t_ext,
        })
    return flow_data