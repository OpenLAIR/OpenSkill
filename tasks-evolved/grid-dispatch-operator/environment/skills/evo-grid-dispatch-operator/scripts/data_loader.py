"""
MATPOWER JSON data loader.

Handles loading network data, building bus index maps, and finding the slack bus.
"""

import json
import numpy as np


def load_network(filepath):
    """Load MATPOWER JSON and return structured data with numpy arrays.

    Handles varying row lengths in gencost by padding shorter rows with zeros.
    """
    with open(filepath) as f:
        data = json.load(f)

    # Handle gencost rows of varying length
    gencost_raw = data.get('gencost', [])
    if gencost_raw:
        max_len = max(len(row) for row in gencost_raw)
        gencost_padded = []
        for row in gencost_raw:
            padded = list(row) + [0.0] * (max_len - len(row))
            gencost_padded.append(padded)
        gencost_arr = np.array(gencost_padded, dtype=float)
    else:
        gencost_arr = np.array([])

    return {
        'baseMVA': float(data.get('baseMVA', 100.0)),
        'bus': np.array(data['bus'], dtype=float),
        'gen': np.array(data['gen'], dtype=float),
        'branch': np.array(data['branch'], dtype=float),
        'gencost': gencost_arr,
        'reserve_capacity': np.array(data.get('reserve_capacity', []), dtype=float),
        'reserve_requirement': float(data.get('reserve_requirement', 0.0)),
    }


def build_bus_index_map(bus_data):
    """Build external-to-internal bus ID mapping.

    MATPOWER uses arbitrary (often 1-based) bus numbering.
    Returns dict: external_bus_id -> internal_index (0-based).
    """
    ext2int = {}
    for i, row in enumerate(bus_data):
        ext2int[int(row[0])] = i
    return ext2int


def get_slack_bus_index(bus_data, ext2int):
    """Find the slack/reference bus (BUS_TYPE == 3) internal index.

    Falls back to first bus if no type-3 bus found.
    """
    for row in bus_data:
        if int(row[1]) == 3:
            return ext2int[int(row[0])]
    return 0