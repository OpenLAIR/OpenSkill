"""
DC-OPF with Reserve Co-optimization solver using cvxpy.

Formulation follows Chen et al., "End-to-End Feasible Optimization Proxies
for Large-Scale Economic Dispatch", IEEE Transactions on Power Systems, 2023.

Uses CLARABEL solver (interior-point) for robust QP/LP solving.
"""

import cvxpy as cp
import numpy as np


def solve_dcopf_with_reserves(
    buses, gens, branches, gencost, baseMVA,
    reserve_capacity, reserve_requirement,
    ext2int, slack_idx, B, branch_flow_data, gen_bus_indices
):
    """Formulate and solve DC-OPF with spinning reserve co-optimization.

    Decision variables:
    - Pg: generator active power output (per-unit)
    - Rg: generator reserve allocation (MW)
    - theta: bus voltage angles (radians)

    Returns dict with:
    - Pg_MW: generator outputs in MW
    - Rg_MW: reserve allocations in MW
    - theta: bus angles in radians
    - cost: total cost in $/hr
    - status: solver status string
    """
    n_bus = len(buses)
    n_gen = len(gens)

    # Decision variables
    Pg = cp.Variable(n_gen)      # Generator output in per-unit
    Rg = cp.Variable(n_gen)      # Generator reserve in MW
    theta = cp.Variable(n_bus)   # Bus voltage angles in radians

    # === Objective: minimize total generation cost ===
    cost = 0
    for i in range(n_gen):
        ncost = int(gencost[i, 3]) if gencost.shape[1] > 3 else 3
        if ncost >= 3:
            c2 = gencost[i, 4]
            c1 = gencost[i, 5]
            c0 = gencost[i, 6]
        elif ncost == 2:
            c2 = 0.0
            c1 = gencost[i, 4]
            c0 = gencost[i, 5]
        elif ncost == 1:
            c2 = 0.0
            c1 = 0.0
            c0 = gencost[i, 4]
        else:
            c2 = gencost[i, 4]
            c1 = gencost[i, 5]
            c0 = gencost[i, 6]

        Pg_MW = Pg[i] * baseMVA
        if c2 != 0:
            cost += c2 * cp.square(Pg_MW) + c1 * Pg_MW + c0
        else:
            cost += c1 * Pg_MW + c0

    # === Constraints ===
    constraints = []

    # Generator output limits: Pmin <= Pg <= Pmax (per-unit)
    for i in range(n_gen):
        pmin = gens[i, 9] / baseMVA
        pmax = gens[i, 8] / baseMVA
        constraints.append(Pg[i] >= pmin)
        constraints.append(Pg[i] <= pmax)

    # Reserve constraints
    constraints.append(Rg >= 0)
    for i in range(n_gen):
        # Reserve capacity limit
        constraints.append(Rg[i] <= reserve_capacity[i])
        # Capacity coupling: Pg_MW + Rg <= Pmax_MW
        Pg_MW = Pg[i] * baseMVA
        pmax_MW = gens[i, 8]
        constraints.append(Pg_MW + Rg[i] <= pmax_MW)

    # Minimum system reserve requirement
    constraints.append(cp.sum(Rg) >= reserve_requirement)

    # Slack bus angle = 0
    constraints.append(theta[slack_idx] == 0)

    # Nodal power balance: sum(Pg at bus) - Pd = B_row @ theta
    # Build generator-to-bus mapping
    gen_bus_map = {}
    for i in range(n_gen):
        bus_idx = gen_bus_indices[i]
        if bus_idx not in gen_bus_map:
            gen_bus_map[bus_idx] = []
        gen_bus_map[bus_idx].append(i)

    for i in range(n_bus):
        Pd_pu = buses[i, 2] / baseMVA  # Bus demand in per-unit
        gen_at_bus = sum(Pg[j] for j in gen_bus_map.get(i, []))
        net_injection = gen_at_bus - Pd_pu
        power_flow = B[i, :] @ theta
        constraints.append(net_injection == power_flow)

    # Line flow limits: |flow_MW| <= RATE_A
    for k, bfd in enumerate(branch_flow_data):
        rate_a = bfd['rate_a']
        if rate_a > 0:
            b = bfd['b']
            f_idx = bfd['f_idx']
            t_idx = bfd['t_idx']
            flow_MW = b * (theta[f_idx] - theta[t_idx]) * baseMVA
            constraints.append(flow_MW <= rate_a)
            constraints.append(flow_MW >= -rate_a)

    # === Solve ===
    prob = cp.Problem(cp.Minimize(cost), constraints)
    prob.solve(solver=cp.CLARABEL)

    if prob.status not in ('optimal', 'optimal_inaccurate'):
        # Try SCS as fallback
        prob.solve(solver=cp.SCS, max_iters=10000)

    if prob.status not in ('optimal', 'optimal_inaccurate'):
        raise RuntimeError(f"Optimization failed with status: {prob.status}")

    Pg_val = Pg.value
    Rg_val = Rg.value
    theta_val = theta.value

    # Clean up near-zero values
    Pg_val = np.where(np.abs(Pg_val) < 1e-8, 0.0, Pg_val)
    Rg_val = np.where(np.abs(Rg_val) < 1e-8, 0.0, Rg_val)
    theta_val = np.where(np.abs(theta_val) < 1e-8, 0.0, theta_val)

    # Clamp reserves to be non-negative (numerical noise)
    Rg_val = np.maximum(Rg_val, 0.0)

    return {
        'Pg_MW': Pg_val * baseMVA,
        'Rg_MW': Rg_val,
        'theta': theta_val,
        'cost': prob.value,
        'status': prob.status,
    }