import json

def compute_impact_analysis(base_cost, cf_cost):
    """Compute cost reduction between base and counterfactual."""
    return round(float(base_cost - cf_cost), 2)

def find_top_lmp_drops(base_lmps, cf_lmps, n=3):
    """Find top n buses with largest LMP drop.
    base_lmps and cf_lmps are lists of {bus, lmp_dollars_per_MWh}."""
    # Create lookup by bus
    base_dict = {item['bus']: item['lmp_dollars_per_MWh'] for item in base_lmps}
    cf_dict = {item['bus']: item['lmp_dollars_per_MWh'] for item in cf_lmps}
    
    drops = []
    for bus in base_dict:
        if bus in cf_dict:
            delta = cf_dict[bus] - base_dict[bus]  # negative means drop
            drops.append({
                'bus': bus,
                'base_lmp': base_dict[bus],
                'cf_lmp': cf_dict[bus],
                'delta': round(delta, 2)
            })
    
    # Sort by delta ascending (most negative first = largest drop)
    drops.sort(key=lambda x: x['delta'])
    return drops[:n]

def check_congestion_relieved(cf_binding_lines, f_bus, t_bus):
    """Check if the specified line is NOT binding in counterfactual.
    Returns True if congestion is relieved (line not binding)."""
    for line in cf_binding_lines:
        if line['from'] == f_bus and line['to'] == t_bus:
            return False
    return True

def build_report_json(base_result, cf_result, base_lmps, cf_lmps,
                      base_reserve_mcp, cf_reserve_mcp,
                      base_binding, cf_binding,
                      base_cost, cf_cost,
                      f_bus=64, t_bus=1501):
    """Build the complete report.json structure."""
    cost_reduction = compute_impact_analysis(base_cost, cf_cost)
    top_drops = find_top_lmp_drops(base_lmps, cf_lmps, n=3)
    congestion_relieved = check_congestion_relieved(cf_binding, f_bus, t_bus)
    
    report = {
        "base_case": {
            "total_cost_dollars_per_hour": base_cost,
            "lmp_by_bus": base_lmps,
            "reserve_mcp_dollars_per_MWh": base_reserve_mcp,
            "binding_lines": base_binding
        },
        "counterfactual": {
            "total_cost_dollars_per_hour": cf_cost,
            "lmp_by_bus": cf_lmps,
            "reserve_mcp_dollars_per_MWh": cf_reserve_mcp,
            "binding_lines": cf_binding
        },
        "impact_analysis": {
            "cost_reduction_dollars_per_hour": cost_reduction,
            "buses_with_largest_lmp_drop": top_drops,
            "congestion_relieved": congestion_relieved
        }
    }
    return report

def export_report(report, filepath='/root/report.json'):
    """Write report to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2)
    return filepath
