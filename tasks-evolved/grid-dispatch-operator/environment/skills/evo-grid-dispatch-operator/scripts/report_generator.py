"""
Report generation for DC-OPF with reserves.

Computes line loadings, assembles the structured report, and writes JSON.
"""

import json
import numpy as np


def compute_line_loadings(theta, branch_flow_data, baseMVA):
    """Compute line flows and loading percentages.

    Args:
        theta: bus voltage angles (radians)
        branch_flow_data: list of dicts from get_branch_flow_data()
        baseMVA: system base MVA

    Returns:
        list of dicts with flow_MW, loading_pct, f_bus, t_bus
    """
    results = []
    for bfd in branch_flow_data:
        f_idx = bfd['f_idx']
        t_idx = bfd['t_idx']
        b = bfd['b']
        rate_a = bfd['rate_a']

        flow_MW = b * (theta[f_idx] - theta[t_idx]) * baseMVA

        if rate_a > 0:
            loading_pct = abs(flow_MW) / rate_a * 100.0
        else:
            loading_pct = 0.0  # Unconstrained line

        results.append({
            'flow_MW': float(flow_MW),
            'loading_pct': float(loading_pct),
            'f_bus': bfd['f_bus'],
            't_bus': bfd['t_bus'],
            'rate_a': rate_a,
        })
    return results


def build_report(gens, Pg_MW, Rg_MW, gencost, baseMVA, buses, line_loadings, reserve_requirement):
    """Assemble the complete report dictionary.

    Args:
        gens: generator data array
        Pg_MW: generator outputs in MW
        Rg_MW: reserve allocations in MW
        gencost: generator cost data array
        baseMVA: system base MVA
        buses: bus data array
        line_loadings: list from compute_line_loadings()
        reserve_requirement: minimum reserve requirement in MW

    Returns:
        report dict matching the required schema
    """
    n_gen = len(gens)

    # Generator dispatch
    generator_dispatch = []
    for i in range(n_gen):
        pmax = float(gens[i, 8])
        output = float(Pg_MW[i])
        reserve = float(Rg_MW[i])

        # Clean up floating point artifacts
        if abs(output) < 1e-6:
            output = 0.0
        if abs(reserve) < 1e-6:
            reserve = 0.0

        generator_dispatch.append({
            'id': i + 1,  # 1-based generator ID
            'bus': int(gens[i, 0]),
            'output_MW': round(output, 6),
            'reserve_MW': round(reserve, 6),
            'pmax_MW': pmax,
        })

    # Compute total cost
    total_cost = 0.0
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

        p = float(Pg_MW[i])
        total_cost += c2 * p * p + c1 * p + c0

    # Totals
    total_load = float(np.sum(buses[:, 2]))
    total_generation = float(np.sum(Pg_MW))
    total_reserve = float(np.sum(Rg_MW))

    totals = {
        'cost_dollars_per_hour': round(total_cost, 4),
        'load_MW': round(total_load, 4),
        'generation_MW': round(total_generation, 4),
        'reserve_MW': round(total_reserve, 4),
    }

    # Most loaded lines (top 3, descending by loading_pct)
    # Only consider lines with rate_a > 0
    rated_lines = [l for l in line_loadings if l['rate_a'] > 0]
    rated_lines.sort(key=lambda x: x['loading_pct'], reverse=True)
    top_lines = rated_lines[:3]

    most_loaded_lines = []
    for l in top_lines:
        most_loaded_lines.append({
            'from': int(l['f_bus']),
            'to': int(l['t_bus']),
            'loading_pct': round(l['loading_pct'], 4),
        })

    # Operating margin = sum(Pmax - output - reserve) for all generators
    operating_margin = 0.0
    for g in generator_dispatch:
        operating_margin += g['pmax_MW'] - g['output_MW'] - g['reserve_MW']

    report = {
        'generator_dispatch': generator_dispatch,
        'totals': totals,
        'most_loaded_lines': most_loaded_lines,
        'operating_margin_MW': round(operating_margin, 4),
    }

    return report


def save_report(report, filepath):
    """Write report dict to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2)