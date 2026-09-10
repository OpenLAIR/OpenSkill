import numpy as np
import pulp

def solve_dcopf_with_reserves(nb, ng, nl, gen_info, branches, costs, load_p,
                               matrices, reserve_capacity, reserve_requirement,
                               Cg, baseMVA=100.0):
    """
    Solve DC-OPF with reserve co-optimization using PuLP.
    B-theta formulation with per-bus nodal balance for direct LMP extraction.
    """
    slack_idx = matrices['slack_idx']
    Bbranch_diag = matrices['Bbranch_diag']
    A_sparse = matrices['A']
    A = A_sparse.toarray()
    Bbus = matrices['Bbus'].toarray()
    
    pmax = gen_info['pmax']
    pmin = gen_info['pmin']
    gen_bus_int = gen_info['gen_bus_int']
    c1 = costs['c1']
    c0 = costs['c0']
    rate_a = branches['rate_a'].copy()
    br_status = branches['status']
    
    BIG_M = 1e6
    rate_a_eff = np.where(rate_a == 0, BIG_M, rate_a)
    
    prob = pulp.LpProblem("DCOPF_Reserve", pulp.LpMinimize)
    
    Pg = [pulp.LpVariable(f"Pg_{i}", lowBound=float(pmin[i]), upBound=float(pmax[i]))
          for i in range(ng)]
    Rg = [pulp.LpVariable(f"Rg_{i}", lowBound=0, upBound=float(reserve_capacity[i]))
          for i in range(ng)]
    Theta = [pulp.LpVariable(f"Th_{b}") for b in range(nb)]
    
    # Objective
    prob += pulp.lpSum([Pg[i] * float(c1[i]) + float(c0[i]) for i in range(ng)])
    
    # Capacity coupling
    for i in range(ng):
        prob += Pg[i] + Rg[i] <= float(pmax[i]), f"CC_{i}"
    
    # Reserve requirement
    prob += pulp.lpSum(Rg) >= float(reserve_requirement), "RR"
    
    # Slack bus angle = 0
    prob += Theta[slack_idx] == 0, "SlackAngle"
    
    # Precompute gens at each bus
    gens_at_bus = [[] for _ in range(nb)]
    for g in range(ng):
        gens_at_bus[gen_bus_int[g]].append(g)
    
    # Nodal power balance: Bbus @ theta + load = gen
    # Written as: Bbus[b,:] @ theta + load[b] == sum(Pg at bus b)
    # So: sum(Pg at bus b) - load[b] - Bbus[b,:] @ theta == 0
    # PuLP constraint: LHS == 0
    # pi = dObj/d(RHS). If we increase load by 1:
    #   LHS becomes (gen - (load+1) - Bbus@theta) = LHS_old - 1
    #   To restore feasibility, objective increases by pi * (-1) change in slack
    #   Actually for == constraint: increasing RHS by 1 means we need LHS = 1
    #   So increasing load by 1 is like decreasing RHS by 1
    #   Cost change = -pi * 1 = -pi => LMP = -pi? No...
    # 
    # Let me write it as: load[b] == sum(Pg at bus b) - Bbus[b,:] @ theta
    # Then pi = dObj/d(load[b]) = LMP directly
    # PuLP: load[b] == expr  =>  expr - load[b] == 0
    # So: sum(Pg) - Bbus@theta - load[b] == 0
    # pi = dObj/d(0) = dObj/d(RHS)
    # Increasing RHS by 1 means constraint becomes: gen - Bbus@theta - load = 1
    # This is like decreasing load by 1 => cost decreases => pi < 0
    # So LMP = -pi
    #
    # BUT WAIT: PuLP equality constraint "name": LHS == RHS
    # is stored as LHS - RHS == 0, and pi = dObj / d(constant_on_RHS)
    # For: gen - load - Bbus@theta == 0
    # If we parameterize as: gen - Bbus@theta == load + delta
    # => gen - Bbus@theta - load == delta
    # pi = dObj/d(delta). Increasing delta by 1 means gen must increase by 1 at this bus.
    # Cost of 1 more MW at this bus = LMP. So pi = LMP.
    
    for b in range(nb):
        gen_inj = pulp.lpSum([Pg[g] for g in gens_at_bus[b]])
        bbus_row = Bbus[b, :]
        nz = np.nonzero(bbus_row)[0]
        flow_out = pulp.lpSum([float(bbus_row[j]) * Theta[j] for j in nz])
        # Constraint: gen - load - flow_out == 0
        # Equivalent to: gen - flow_out == load
        # pi = dObj/d(load) when written this way
        prob += gen_inj - float(load_p[b]) - flow_out == 0, f"PB_{b}"
    
    # Thermal line limits: flow[l] = Bbranch[l] * A[l,:] @ theta
    active_lines = []
    for l in range(nl):
        if br_status[l] == 0 or Bbranch_diag[l] == 0:
            continue
        if rate_a_eff[l] >= BIG_M:
            continue
        a_row = A[l, :]
        nz = np.nonzero(a_row)[0]
        if len(nz) == 0:
            continue
        flow_expr = pulp.lpSum([float(Bbranch_diag[l] * a_row[b]) * Theta[b] for b in nz])
        prob += flow_expr <= float(rate_a_eff[l]), f"TF_{l}"
        prob += flow_expr >= -float(rate_a_eff[l]), f"TR_{l}"
        active_lines.append(l)
    
    solver = pulp.PULP_CBC_CMD(msg=0, mip=False)
    status = prob.solve(solver)
    
    if pulp.LpStatus[status] != 'Optimal':
        raise ValueError(f"Solver status: {pulp.LpStatus[status]}")
    
    Pg_vals = np.array([pulp.value(Pg[i]) for i in range(ng)])
    Rg_vals = np.array([pulp.value(Rg[i]) for i in range(ng)])
    Theta_vals = np.array([pulp.value(Theta[b]) for b in range(nb)])
    total_cost = float(pulp.value(prob.objective))
    
    # Extract LMPs directly from nodal balance duals
    lmps = np.zeros(nb)
    for b in range(nb):
        pi_val = prob.constraints[f"PB_{b}"].pi
        if pi_val is not None:
            lmps[b] = max(0.0, float(pi_val))
    
    # Reserve MCP
    reserve_mcp = prob.constraints["RR"].pi
    if reserve_mcp is None:
        reserve_mcp = 0.0
    reserve_mcp = abs(float(reserve_mcp))
    
    # Compute line flows
    line_flows = np.zeros(nl)
    for l in range(nl):
        if br_status[l] == 0 or Bbranch_diag[l] == 0:
            continue
        a_row = A[l, :]
        nz = np.nonzero(a_row)[0]
        line_flows[l] = sum(Bbranch_diag[l] * a_row[b] * Theta_vals[b] for b in nz)
    
    return {
        'Pg': Pg_vals, 'Rg': Rg_vals, 'lmps': lmps,
        'reserve_mcp': reserve_mcp, 'total_cost': total_cost,
        'line_flows': line_flows, 'status': pulp.LpStatus[status]
    }

def extract_lmps(result, int2ext):
    lmps = result['lmps']
    return [{'bus': int(int2ext[i]), 'lmp_dollars_per_MWh': round(float(lmps[i]), 2)} for i in range(len(lmps))]

def extract_reserve_mcp(result):
    return round(float(result['reserve_mcp']), 2)

def identify_binding_lines(result, branches, int2ext, threshold=0.99):
    line_flows = result['line_flows']
    rate_a = branches['rate_a']
    binding = []
    for l in range(branches['nl']):
        if branches['status'][l] == 0 or rate_a[l] <= 0:
            continue
        loading = abs(line_flows[l]) / rate_a[l]
        if loading >= threshold:
            binding.append({
                'from': int(branches['f_bus_ext'][l]),
                'to': int(branches['t_bus_ext'][l]),
                'flow_MW': round(float(abs(line_flows[l])), 2),
                'limit_MW': round(float(rate_a[l]), 2)
            })
    return binding

def compute_total_cost(result):
    return round(float(result['total_cost']), 2)
