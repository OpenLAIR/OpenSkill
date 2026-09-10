import pyomo.environ as pyo
import math
import subprocess
import os

def install_solver():
    """Ensure IPOPT is available via idaes."""
    idaes_bin = os.path.expanduser('~/.idaes/bin')
    if idaes_bin not in os.environ.get('PATH', ''):
        os.environ['PATH'] = os.environ.get('PATH', '') + ':' + idaes_bin
    # Check if ipopt exists
    ipopt_path = os.path.join(idaes_bin, 'ipopt')
    if not os.path.exists(ipopt_path):
        subprocess.run(['idaes', 'get-extensions'], check=True)
    return True


def build_acopf_model(baseMVA, buses, gens, branches, loads_by_bus, shunts_by_bus,
                       gen_at_bus, branch_from, branch_to):
    """Build Pyomo ACOPF model in polar coordinates."""
    model = pyo.ConcreteModel()
    
    # ---- SETS ----
    model.BUSES = pyo.Set(initialize=list(buses.keys()))
    model.GENS = pyo.Set(initialize=list(gens.keys()))
    model.BRANCHES = pyo.Set(initialize=list(branches.keys()))
    
    # ---- VARIABLES ----
    def vm_bounds(m, i):
        return (buses[i]['vmin'], buses[i]['vmax'])
    model.vm = pyo.Var(model.BUSES, bounds=vm_bounds, initialize=lambda m, i: buses[i].get('vm', 1.0))
    
    model.va = pyo.Var(model.BUSES, initialize=lambda m, i: buses[i].get('va', 0.0))
    
    def pg_bounds(m, g):
        return (gens[g]['pmin'], gens[g]['pmax'])
    def qg_bounds(m, g):
        return (gens[g]['qmin'], gens[g]['qmax'])
    model.pg = pyo.Var(model.GENS, bounds=pg_bounds,
                       initialize=lambda m, g: max(gens[g]['pmin'], min(gens[g].get('pg', 0.0), gens[g]['pmax'])))
    model.qg = pyo.Var(model.GENS, bounds=qg_bounds,
                       initialize=lambda m, g: max(gens[g]['qmin'], min(gens[g].get('qg', 0.0), gens[g]['qmax'])))
    
    # ---- BRANCH FLOW EXPRESSIONS ----
    def p_from_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, tap, shift = b['g'], b['b'], b['tap'], b['shift']
        return (m.vm[f]**2 / tap**2) * g - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.cos(m.va[f] - m.va[t] - shift) + b_ij * pyo.sin(m.va[f] - m.va[t] - shift))
    model.P_fr = pyo.Expression(model.BRANCHES, rule=p_from_rule)

    def p_to_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, tap, shift = b['g'], b['b'], b['tap'], b['shift']
        return m.vm[t]**2 * g - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.cos(m.va[t] - m.va[f] + shift) + b_ij * pyo.sin(m.va[t] - m.va[f] + shift))
    model.P_to = pyo.Expression(model.BRANCHES, rule=p_to_rule)

    def q_from_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, b_fr, tap, shift = b['g'], b['b'], b['b_fr'], b['tap'], b['shift']
        return -(m.vm[f]**2 / tap**2) * (b_ij + b_fr) - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.sin(m.va[f] - m.va[t] - shift) - b_ij * pyo.cos(m.va[f] - m.va[t] - shift))
    model.Q_fr = pyo.Expression(model.BRANCHES, rule=q_from_rule)

    def q_to_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, b_to, tap, shift = b['g'], b['b'], b['b_to'], b['tap'], b['shift']
        return -m.vm[t]**2 * (b_ij + b_to) - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.sin(m.va[t] - m.va[f] + shift) - b_ij * pyo.cos(m.va[t] - m.va[f] + shift))
    model.Q_to = pyo.Expression(model.BRANCHES, rule=q_to_rule)

    # ---- CONSTRAINTS ----
    # Power Balance
    def p_balance_rule(m, i):
        p_gen = sum(m.pg[g] for g in gen_at_bus[i])
        p_load = loads_by_bus[i]['pd']
        p_shunt = m.vm[i]**2 * shunts_by_bus[i]['gs']
        p_flow = sum(m.P_fr[br] for br in branch_from[i]) + sum(m.P_to[br] for br in branch_to[i])
        return p_gen - p_load - p_shunt == p_flow
    model.bal_P = pyo.Constraint(model.BUSES, rule=p_balance_rule)

    def q_balance_rule(m, i):
        q_gen = sum(m.qg[g] for g in gen_at_bus[i])
        q_load = loads_by_bus[i]['qd']
        q_shunt = -m.vm[i]**2 * shunts_by_bus[i]['bs']
        q_flow = sum(m.Q_fr[br] for br in branch_from[i]) + sum(m.Q_to[br] for br in branch_to[i])
        return q_gen - q_load - q_shunt == q_flow
    model.bal_Q = pyo.Constraint(model.BUSES, rule=q_balance_rule)

    # Thermal Limits (squared formulation)
    def thermal_fr_rule(m, br):
        limit = branches[br]['rate_a']
        if limit is None or limit <= 0.0:
            return pyo.Constraint.Skip
        return m.P_fr[br]**2 + m.Q_fr[br]**2 <= limit**2
    model.limit_fr = pyo.Constraint(model.BRANCHES, rule=thermal_fr_rule)

    def thermal_to_rule(m, br):
        limit = branches[br]['rate_a']
        if limit is None or limit <= 0.0:
            return pyo.Constraint.Skip
        return m.P_to[br]**2 + m.Q_to[br]**2 <= limit**2
    model.limit_to = pyo.Constraint(model.BRANCHES, rule=thermal_to_rule)

    # Angle Difference Limits
    def ang_diff_rule(m, br):
        f, t = branches[br]['f_bus'], branches[br]['t_bus']
        return pyo.inequality(branches[br]['angmin'], m.va[f] - m.va[t], branches[br]['angmax'])
    model.ang_diff = pyo.Constraint(model.BRANCHES, rule=ang_diff_rule)

    # Reference Bus
    def ref_bus_rule(m, i):
        if buses[i]['bus_type'] == 3:
            return m.va[i] == 0.0
        return pyo.Constraint.Skip
    model.ref_bus = pyo.Constraint(model.BUSES, rule=ref_bus_rule)

    # ---- OBJECTIVE ----
    def obj_rule(m):
        cost = 0.0
        for g_id, g in gens.items():
            c = g['cost']  # [c2_pu, c1_pu, c0]
            cost += c[0] * (m.pg[g_id]**2) + c[1] * m.pg[g_id] + c[2]
        return cost
    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    
    # Store references for post-processing
    model._baseMVA = baseMVA
    model._buses = buses
    model._gens = gens
    model._branches = branches
    model._loads_by_bus = loads_by_bus
    model._shunts_by_bus = shunts_by_bus
    
    return model


def solve_acopf(model, tol=1e-6, max_iter=3000):
    """Solve ACOPF model with IPOPT."""
    install_solver()
    solver = pyo.SolverFactory('ipopt')
    solver.options['tol'] = tol
    solver.options['max_iter'] = max_iter
    solver.options['linear_solver'] = 'ma27'
    results = solver.solve(model, tee=True)
    return results


def build_and_solve_acopf(baseMVA, buses, gens, branches, loads_by_bus, shunts_by_bus,
                           gen_at_bus, branch_from, branch_to):
    """Build and solve ACOPF in one call."""
    model = build_acopf_model(baseMVA, buses, gens, branches, loads_by_bus, shunts_by_bus,
                               gen_at_bus, branch_from, branch_to)
    results = solve_acopf(model)
    return model, results
