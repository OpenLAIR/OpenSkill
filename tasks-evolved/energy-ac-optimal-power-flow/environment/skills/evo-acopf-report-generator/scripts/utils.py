import pyomo.environ as pyo
import math
import json

def extract_generator_results(model, baseMVA):
    """Extract generator dispatch results in MW/MVAr."""
    gens = model._gens
    results = []
    for g_id in sorted(gens.keys(), key=lambda x: int(x)):
        g = gens[g_id]
        results.append({
            'id': int(g_id),
            'bus': int(g['gen_bus']),
            'pg_MW': round(pyo.value(model.pg[g_id]) * baseMVA, 2),
            'qg_MVAr': round(pyo.value(model.qg[g_id]) * baseMVA, 2),
            'pmin_MW': round(g['pmin'] * baseMVA, 2),
            'pmax_MW': round(g['pmax'] * baseMVA, 2),
            'qmin_MVAr': round(g['qmin'] * baseMVA, 2),
            'qmax_MVAr': round(g['qmax'] * baseMVA, 2)
        })
    return results


def extract_bus_results(model, baseMVA):
    """Extract bus voltage results."""
    buses = model._buses
    results = []
    for b_id in sorted(buses.keys(), key=lambda x: int(x)):
        b = buses[b_id]
        results.append({
            'id': int(b_id),
            'vm_pu': round(pyo.value(model.vm[b_id]), 4),
            'va_deg': round(math.degrees(pyo.value(model.va[b_id])), 4),
            'vmin_pu': b['vmin'],
            'vmax_pu': b['vmax']
        })
    return results


def compute_branch_flows_and_loading(model, baseMVA):
    """Compute branch flows and loading percentages. Return all branches sorted by loading."""
    branches = model._branches
    branch_data = []
    for br_id in branches:
        br = branches[br_id]
        p_fr = pyo.value(model.P_fr[br_id])
        q_fr = pyo.value(model.Q_fr[br_id])
        p_to = pyo.value(model.P_to[br_id])
        q_to = pyo.value(model.Q_to[br_id])
        
        s_fr = math.sqrt(p_fr**2 + q_fr**2) * baseMVA
        s_to = math.sqrt(p_to**2 + q_to**2) * baseMVA
        
        limit_mva = br.get('rate_a_mva', br['rate_a'] * baseMVA)
        
        loading_pct = 0.0
        if limit_mva is not None and limit_mva > 0:
            max_flow = max(s_fr, s_to)
            loading_pct = (max_flow / limit_mva) * 100
        
        branch_data.append({
            'from_bus': int(br['f_bus']),
            'to_bus': int(br['t_bus']),
            'loading_pct': round(loading_pct, 2),
            'flow_from_MVA': round(s_fr, 2),
            'flow_to_MVA': round(s_to, 2),
            'limit_MVA': round(limit_mva, 2) if limit_mva else 0.0,
            'p_fr_pu': p_fr,
            'q_fr_pu': q_fr,
            'p_to_pu': p_to,
            'q_to_pu': q_to
        })
    
    branch_data.sort(key=lambda x: x['loading_pct'], reverse=True)
    return branch_data


def compute_feasibility_check(model, baseMVA):
    """Compute power balance mismatches and constraint violations."""
    buses = model._buses
    branches = model._branches
    
    # Power balance mismatches
    max_p_mismatch = 0.0
    max_q_mismatch = 0.0
    for b_id in buses:
        p_body = pyo.value(model.bal_P[b_id].body)
        q_body = pyo.value(model.bal_Q[b_id].body)
        max_p_mismatch = max(max_p_mismatch, abs(p_body) * baseMVA)
        max_q_mismatch = max(max_q_mismatch, abs(q_body) * baseMVA)
    
    # Voltage violations
    max_v_violation = 0.0
    for b_id in buses:
        vm = pyo.value(model.vm[b_id])
        vmin = buses[b_id]['vmin']
        vmax = buses[b_id]['vmax']
        if vm < vmin:
            max_v_violation = max(max_v_violation, vmin - vm)
        elif vm > vmax:
            max_v_violation = max(max_v_violation, vm - vmax)
    
    # Branch overloads
    max_overload = 0.0
    for br_id in branches:
        br = branches[br_id]
        limit_pu = br['rate_a']
        if limit_pu is None or limit_pu <= 0:
            continue
        p_fr = pyo.value(model.P_fr[br_id])
        q_fr = pyo.value(model.Q_fr[br_id])
        p_to = pyo.value(model.P_to[br_id])
        q_to = pyo.value(model.Q_to[br_id])
        s_fr = math.sqrt(p_fr**2 + q_fr**2)
        s_to = math.sqrt(p_to**2 + q_to**2)
        max_s = max(s_fr, s_to)
        if max_s > limit_pu:
            max_overload = max(max_overload, (max_s - limit_pu) * baseMVA)
    
    return {
        'max_p_mismatch_MW': round(max_p_mismatch, 6),
        'max_q_mismatch_MVAr': round(max_q_mismatch, 6),
        'max_voltage_violation_pu': round(max_v_violation, 6),
        'max_branch_overload_MVA': round(max_overload, 6)
    }


def compute_summary_statistics(model, baseMVA, solver_results):
    """Compute summary statistics."""
    gens = model._gens
    buses = model._buses
    loads_by_bus = model._loads_by_bus
    
    total_gen_p = sum(pyo.value(model.pg[g]) for g in gens) * baseMVA
    total_gen_q = sum(pyo.value(model.qg[g]) for g in gens) * baseMVA
    total_load_p = sum(loads_by_bus[b]['pd'] for b in buses) * baseMVA
    total_load_q = sum(loads_by_bus[b]['qd'] for b in buses) * baseMVA
    total_losses = total_gen_p - total_load_p
    
    # Get objective value (total cost)
    total_cost = pyo.value(model.obj)
    
    # Solver status
    solver_status = 'optimal'
    from pyomo.opt import TerminationCondition
    tc = solver_results.solver.termination_condition
    if tc == TerminationCondition.optimal:
        solver_status = 'optimal'
    elif tc == TerminationCondition.locallyOptimal:
        solver_status = 'optimal'
    else:
        solver_status = str(tc)
    
    return {
        'total_cost_per_hour': round(total_cost, 2),
        'total_load_MW': round(total_load_p, 2),
        'total_load_MVAr': round(total_load_q, 2),
        'total_generation_MW': round(total_gen_p, 2),
        'total_generation_MVAr': round(total_gen_q, 2),
        'total_losses_MW': round(total_losses, 2),
        'solver_status': solver_status
    }


def generate_report_json(model, baseMVA, solver_results, output_path='report.json', top_n_branches=5):
    """Generate the full report.json."""
    summary = compute_summary_statistics(model, baseMVA, solver_results)
    generators = extract_generator_results(model, baseMVA)
    bus_results = extract_bus_results(model, baseMVA)
    branch_data = compute_branch_flows_and_loading(model, baseMVA)
    feasibility = compute_feasibility_check(model, baseMVA)
    
    # Top N most loaded branches
    most_loaded = []
    for bd in branch_data[:top_n_branches]:
        most_loaded.append({
            'from_bus': bd['from_bus'],
            'to_bus': bd['to_bus'],
            'loading_pct': bd['loading_pct'],
            'flow_from_MVA': bd['flow_from_MVA'],
            'flow_to_MVA': bd['flow_to_MVA'],
            'limit_MVA': bd['limit_MVA']
        })
    
    report = {
        'summary': summary,
        'generators': generators,
        'buses': bus_results,
        'most_loaded_branches': most_loaded,
        'feasibility_check': feasibility
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report
