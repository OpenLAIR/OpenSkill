"""Mesh geometry analysis: connected components and volume computation.

Key design decisions (from docs):
- Vertex quantization: 4 decimal places for vertex matching
- Adjacency: vertex-based (triangles sharing any vertex are connected)
- Volume: signed tetrahedron method V = abs(sum(v1.(v2 x v3))) / 6.0
- Unit conversion: mm^3 to cm^3 by dividing by 1000
- Mass = volume_cm3 * density_g_cm3
"""

import collections
from typing import List, Tuple, Dict


def quantize_vertex(v: Tuple[float, float, float], decimals: int = 4) -> Tuple[float, float, float]:
    """Quantize vertex coordinates to specified decimal places for robust matching."""
    return (round(v[0], decimals), round(v[1], decimals), round(v[2], decimals))


def get_largest_connected_component(triangles: List[Tuple], rounding_decimals: int = 4) -> List[Tuple]:
    """
    Find the largest connected component using vertex-based adjacency.
    
    Two triangles are connected if they share at least one vertex
    (after quantization to rounding_decimals decimal places).
    
    Uses BFS. Returns the component with the most triangles.
    """
    if not triangles:
        return []
    
    # Build vertex -> triangle index mapping
    vertex_map = collections.defaultdict(list)
    for i, t in enumerate(triangles):
        for v in t[:3]:
            qv = quantize_vertex(v, rounding_decimals)
            vertex_map[qv].append(i)
    
    # BFS to find all connected components
    visited = set()
    components = []
    
    for i in range(len(triangles)):
        if i in visited:
            continue
        comp_indices = []
        queue = collections.deque([i])
        visited.add(i)
        
        while queue:
            curr = queue.popleft()
            comp_indices.append(curr)
            for v in triangles[curr][:3]:
                qv = quantize_vertex(v, rounding_decimals)
                for n_idx in vertex_map[qv]:
                    if n_idx not in visited:
                        visited.add(n_idx)
                        queue.append(n_idx)
        
        components.append(comp_indices)
    
    # Find largest component by triangle count
    largest_indices = max(components, key=len)
    return [triangles[idx] for idx in largest_indices]


def compute_mesh_volume(triangles: List[Tuple]) -> float:
    """
    Compute volume of closed triangulated mesh using signed tetrahedron method.
    
    Formula: V = abs(sum(v1 . (v2 x v3))) / 6.0
    
    Returns volume in the same cubic units as the vertex coordinates (mm^3 if coords are in mm).
    """
    if not triangles:
        return 0.0
    
    vol = 0.0
    for t in triangles:
        v1, v2, v3 = t[0], t[1], t[2]
        # Cross product v2 x v3
        cx = v2[1] * v3[2] - v2[2] * v3[1]
        cy = v2[2] * v3[0] - v2[0] * v3[2]
        cz = v2[0] * v3[1] - v2[1] * v3[0]
        # Dot product v1 . cross
        vol += v1[0] * cx + v1[1] * cy + v1[2] * cz
    
    return abs(vol) / 6.0


def convert_volume_mm3_to_cm3(volume_mm3: float) -> float:
    """
    Convert volume from mm^3 to cm^3.
    1 cm = 10 mm, so 1 cm^3 = 1000 mm^3.
    """
    return volume_mm3 / 1000.0


def calculate_mass(volume_cm3: float, density_g_cm3: float) -> float:
    """
    Calculate mass from volume (cm^3) and density (g/cm^3).
    Mass = Volume * Density
    """
    return volume_cm3 * density_g_cm3
