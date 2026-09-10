"""
Main entry point for DC-OPF with Reserve Co-optimization.

Full pipeline: parse network → build model → optimize → generate report.
"""

import subprocess
import sys

# Ensure dependencies are installed
def ensure_deps():
    """Install cvxpy and clarabel if not available."""
    try:
        import cvxpy
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cvxpy", "clarabel", "-q"])
    try:
        import clarabel
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "clarabel", "-q"])

ensure_deps()

import numpy as np

# Import skill modules
import os
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

from data_loader import load_network, build_bus_index_map, get_slack_bus_index
from network_model import build_b_matrix, get_gen_bus_indices, get_branch_flow_data
from optimizer import solve_dcopf_with_reserves
from report_generator import compute_line_loadings, build_report, save_report


def main(input_path="/root/network.json", output_path="/root/report.json"):
    """Run the full DC-OPF with reserves pipeline.

    Args:
        input_path: path to MATPOWER JSON network file
        output_path: path to write report.json
    """
    print(f"Loading network from {input_path}...")
    network = load_network(input_path)

    buses = network['bus']
    gens = network['gen']
    branches = network['branch']
    gencost = network['gencost']
    baseMVA = network['baseMVA']
    reserve_capacity = network['reserve_capacity']
    reserve_requirement = network['reserve_requirement']

    n_bus = len(buses)
    n_gen = len(gens)
    n_branch = len(branches)
    print(f"Network: {n_bus} buses, {n_gen} generators, {n_branch} branches")
    print(f"Base MVA: {baseMVA}")
    print(f"Reserve requirement: {reserve_requirement} MW")
    print(f"Total load: {np.sum(buses[:, 2]):.2f} MW")

    # Build bus index map
    ext2int = build_bus_index_map(buses)

    # Find slack bus
    slack_idx = get_slack_bus_index(buses, ext2int)
    print(f"Slack bus internal index: {slack_idx}")

    # Build susceptance matrix
    B = build_b_matrix(branches, n_bus, ext2int)

    # Get generator bus indices
    gen_bus_indices = get_gen_bus_indices(gens, ext2int)

    # Get branch flow data
    branch_flow_data = get_branch_flow_data(branches, ext2int)

    # Handle reserve capacity: if not provided, default to Pmax for each gen
    if len(reserve_capacity) == 0:
        reserve_capacity = gens[:, 8].copy()  # Pmax as default reserve capacity
        print("No reserve_capacity in data; defaulting to Pmax for each generator")

    # Solve DC-OPF with reserves
    print("Solving DC-OPF with reserve co-optimization...")
    result = solve_dcopf_with_reserves(
        buses=buses,
        gens=gens,
        branches=branches,
        gencost=gencost,
        baseMVA=baseMVA,
        reserve_capacity=reserve_capacity,
        reserve_requirement=reserve_requirement,
        ext2int=ext2int,
        slack_idx=slack_idx,
        B=B,
        branch_flow_data=branch_flow_data,
        gen_bus_indices=gen_bus_indices,
    )

    print(f"Solver status: {result['status']}")
    print(f"Optimal cost: {result['cost']:.4f} $/hr")

    Pg_MW = result['Pg_MW']
    Rg_MW = result['Rg_MW']
    theta = result['theta']

    # Compute line loadings
    line_loadings = compute_line_loadings(theta, branch_flow_data, baseMVA)

    # Build and save report
    report = build_report(
        gens=gens,
        Pg_MW=Pg_MW,
        Rg_MW=Rg_MW,
        gencost=gencost,
        baseMVA=baseMVA,
        buses=buses,
        line_loadings=line_loadings,
        reserve_requirement=reserve_requirement,
    )

    save_report(report, output_path)
    print(f"Report saved to {output_path}")
    print(f"Total cost: {report['totals']['cost_dollars_per_hour']:.4f} $/hr")
    print(f"Total generation: {report['totals']['generation_MW']:.4f} MW")
    print(f"Total reserve: {report['totals']['reserve_MW']:.4f} MW")
    print(f"Operating margin: {report['operating_margin_MW']:.4f} MW")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DC-OPF with Reserve Co-optimization")
    parser.add_argument("--input", default="/root/network.json", help="Input network JSON file")
    parser.add_argument("--output", default="/root/report.json", help="Output report JSON file")
    args = parser.parse_args()
    main(args.input, args.output)