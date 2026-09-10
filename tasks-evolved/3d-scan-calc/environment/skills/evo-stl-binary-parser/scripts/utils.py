"""Binary STL parser with Material ID extraction and density table parsing."""

import struct
import os
import re
from typing import List, Tuple, Dict


def parse_binary_stl(filepath: str) -> List[Tuple]:
    """
    Parse a binary STL file.
    
    Returns list of tuples: (v1, v2, v3, material_id)
    where v1/v2/v3 are (x,y,z) float tuples and material_id is uint16.
    
    Binary STL layout:
      - 80 bytes: header (ignored)
      - 4 bytes: uint32 triangle count (little-endian)
      - N x 50 bytes: facet records
        Each: 12 bytes normal + 36 bytes vertices (3x3 floats) + 2 bytes attribute
    """
    triangles = []
    with open(filepath, 'rb') as f:
        f.read(80)  # skip header
        count = struct.unpack('<I', f.read(4))[0]
        buf = f.read(count * 50)
        fmt = '<12fH'
        for i in range(count):
            offset = i * 50
            data = struct.unpack_from(fmt, buf, offset)
            # data[0:3] = normal, data[3:6] = v1, data[6:9] = v2, data[9:12] = v3, data[12] = attr
            v1 = (data[3], data[4], data[5])
            v2 = (data[6], data[7], data[8])
            v3 = (data[9], data[10], data[11])
            material_id = data[12]
            triangles.append((v1, v2, v3, material_id))
    return triangles


def parse_material_density_table(filepath: str) -> Dict[int, float]:
    """
    Parse a markdown material density table.
    Returns dict mapping Material ID -> density (g/cm³).
    """
    density_map = {}
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    header_found = False
    id_col = -1
    density_col = -1
    
    for i, line in enumerate(lines):
        if '|' not in line:
            continue
        lower = line.lower()
        if not header_found and 'material' in lower and 'density' in lower:
            cols = [c.strip().lower() for c in line.split('|')]
            for j, col in enumerate(cols):
                if 'material' in col and 'id' in col:
                    id_col = j
                elif 'density' in col:
                    density_col = j
            if id_col >= 0 and density_col >= 0:
                header_found = True
            continue
        
        if header_found:
            cols = [c.strip() for c in line.split('|')]
            # Skip separator lines
            if all(set(c) <= set('-: ') for c in cols if c):
                continue
            try:
                if id_col < len(cols) and density_col < len(cols):
                    id_str = re.sub(r'[*`]', '', cols[id_col]).strip()
                    density_str = re.sub(r'[*`]', '', cols[density_col]).strip()
                    if id_str and density_str:
                        density_map[int(id_str)] = float(density_str)
            except (ValueError, IndexError):
                continue
    
    return density_map


def filter_facets_by_material_id(triangles: List[Tuple], material_id: int) -> List[Tuple]:
    """Filter triangles to only those with the specified material_id."""
    return [t for t in triangles if t[3] == material_id]


def detect_material_id(triangles: List[Tuple]) -> int:
    """
    Detect the dominant Material ID (most common, excluding debris ID=1).
    Returns the material_id with the most triangles (ignoring ID 1).
    """
    from collections import Counter
    counts = Counter(t[3] for t in triangles)
    # Remove debris material (ID 1) from consideration
    if 1 in counts and len(counts) > 1:
        del counts[1]
    return counts.most_common(1)[0][0]


# Hardcoded density table as fallback
DENSITY_TABLE = {1: 0.10, 10: 7.85, 25: 2.70, 42: 5.55, 99: 11.34}


def lookup_density(material_id: int, density_table: Dict[int, float] = None) -> float:
    """Look up density for a material ID. Uses provided table or hardcoded fallback."""
    table = density_table if density_table else DENSITY_TABLE
    return table.get(material_id, 1.0)
