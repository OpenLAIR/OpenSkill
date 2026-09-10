import json
import math

def parse_network_json(filepath):
    """Parse Matpower-style network.json into solver-ready structures.
    Returns: baseMVA, buses, gens, branches, loads_by_bus, shunts_by_bus, gencosts
    All power values converted to per-unit."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    baseMVA = data.get('baseMVA', 100.0)
    
    # Parse buses - array format: [BUS_I, BUS_TYPE, PD, QD, GS, BS, AREA, VM, VA, BASE_KV, ZONE, VMAX, VMIN]
    buses = {}
    for row in data.get('bus', []):
        bus_id = str(int(row[0]))
        buses[bus_id] = {
            'bus_i': int(row[0]),
            'bus_type': int(row[1]),
            'pd': row[2] / baseMVA,      # MW -> pu
            'qd': row[3] / baseMVA,      # MVAr -> pu
            'gs': row[4] / baseMVA,      # MW -> pu
            'bs': row[5] / baseMVA,      # MVAr -> pu
            'vm': row[7],
            'va': math.radians(row[8]),   # degrees -> radians
            'vmax': row[11],
            'vmin': row[12]
        }
    
    # Parse generators - [GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, PMAX, PMIN]
    gens = {}
    for idx, row in enumerate(data.get('gen', [])):
        gen_id = str(idx + 1)
        if int(row[7]) == 0:  # skip out-of-service
            continue
        gens[gen_id] = {
            'gen_bus': str(int(row[0])),
            'pg': row[1] / baseMVA,
            'qg': row[2] / baseMVA,
            'qmax': row[3] / baseMVA,
            'qmin': row[4] / baseMVA,
            'vg': row[5],
            'mbase': row[6],
            'pmax': row[8] / baseMVA,
            'pmin': row[9] / baseMVA
        }
    
    # Parse gencost - [MODEL, STARTUP, SHUTDOWN, NCOST, COST...]
    # Cost coefficients are for MW-based evaluation
    # For per-unit solver: c2_pu = c2 * baseMVA^2, c1_pu = c1 * baseMVA, c0_pu = c0
    gencosts = {}
    for idx, row in enumerate(data.get('gencost', [])):
        gen_id = str(idx + 1)
        if gen_id not in gens:
            continue
        model_type = int(row[0])
        ncost = int(row[3])
        coeffs = row[4:4+ncost]
        if model_type == 2:  # polynomial
            if ncost == 3:
                # coeffs = [c2, c1, c0] for C(P_MW) = c2*P^2 + c1*P + c0
                # For pu solver: C(p_pu) = c2*(baseMVA*p)^2 + c1*(baseMVA*p) + c0
                #                        = c2*baseMVA^2*p^2 + c1*baseMVA*p + c0
                gencosts[gen_id] = {
                    'c2': coeffs[0] * baseMVA**2,
                    'c1': coeffs[1] * baseMVA,
                    'c0': coeffs[2]
                }
            elif ncost == 2:
                gencosts[gen_id] = {
                    'c2': 0.0,
                    'c1': coeffs[0] * baseMVA,
                    'c0': coeffs[1]
                }
            elif ncost == 1:
                gencosts[gen_id] = {'c2': 0.0, 'c1': 0.0, 'c0': coeffs[0]}
            else:
                gencosts[gen_id] = {'c2': 0.0, 'c1': 0.0, 'c0': 0.0}
        else:
            gencosts[gen_id] = {'c2': 0.0, 'c1': 0.0, 'c0': 0.0}
    
    # Attach costs to gens
    for g_id in gens:
        if g_id in gencosts:
            gens[g_id]['cost'] = [gencosts[g_id]['c2'], gencosts[g_id]['c1'], gencosts[g_id]['c0']]
        else:
            gens[g_id]['cost'] = [0.0, 0.0, 0.0]
    
    # Parse branches - [F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, TAP, SHIFT, STATUS, ANGMIN, ANGMAX]
    branches = {}
    for idx, row in enumerate(data.get('branch', [])):
        br_id = str(idx + 1)
        if int(row[10]) == 0:  # skip out-of-service
            continue
        branches[br_id] = compute_branch_pi_params(row, baseMVA)
    
    # Aggregate loads and shunts by bus (embedded in bus data)
    loads_by_bus = aggregate_loads_by_bus(buses)
    shunts_by_bus = aggregate_shunts_by_bus(buses)
    
    return baseMVA, buses, gens, branches, loads_by_bus, shunts_by_bus


def compute_branch_pi_params(row, baseMVA):
    """Compute Pi-section parameters from branch data row."""
    f_bus = str(int(row[0]))
    t_bus = str(int(row[1]))
    r = row[2]
    x = row[3]
    b_total = row[4]
    rate_a = row[5] / baseMVA  # MVA -> pu
    tap = row[8]
    shift = math.radians(row[9])  # degrees -> radians
    angmin = math.radians(row[11])
    angmax = math.radians(row[12])
    
    if tap == 0.0:
        tap = 1.0
    
    # Series admittance y = 1/(r+jx) = g + jb
    z_mag2 = r**2 + x**2
    g_ij = r / z_mag2
    b_ij = -x / z_mag2
    
    # Line charging split equally
    b_fr = b_total / 2.0
    b_to = b_total / 2.0
    
    return {
        'f_bus': f_bus,
        't_bus': t_bus,
        'g': g_ij,
        'b': b_ij,
        'b_fr': b_fr,
        'b_to': b_to,
        'tap': tap,
        'shift': shift,
        'rate_a': rate_a,
        'angmin': angmin,
        'angmax': angmax,
        'rate_a_mva': row[5]  # keep original MVA for reporting
    }


def aggregate_loads_by_bus(buses):
    """Extract load data from bus entries (PD, QD already in pu)."""
    loads = {}
    for bus_id, bus in buses.items():
        loads[bus_id] = {'pd': bus['pd'], 'qd': bus['qd']}
    return loads


def aggregate_shunts_by_bus(buses):
    """Extract shunt data from bus entries (GS, BS already in pu)."""
    shunts = {}
    for bus_id, bus in buses.items():
        shunts[bus_id] = {'gs': bus['gs'], 'bs': bus['bs']}
    return shunts


def map_generators_to_buses(gens, buses):
    """Map generators to their buses."""
    gen_at_bus = {b: [] for b in buses}
    for g_id, g in gens.items():
        bus_id = g['gen_bus']
        if bus_id in gen_at_bus:
            gen_at_bus[bus_id].append(g_id)
    return gen_at_bus


def identify_reference_buses(buses):
    """Return list of reference bus IDs (bus_type==3)."""
    return [b_id for b_id, b in buses.items() if b['bus_type'] == 3]


def get_branch_bus_mappings(branches, buses):
    """Get branch-from and branch-to mappings per bus."""
    branch_from = {b: [] for b in buses}
    branch_to = {b: [] for b in buses}
    for br_id, br in branches.items():
        branch_from[br['f_bus']].append(br_id)
        branch_to[br['t_bus']].append(br_id)
    return branch_from, branch_to
