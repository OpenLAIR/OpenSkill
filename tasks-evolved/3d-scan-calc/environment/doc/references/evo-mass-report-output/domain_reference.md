# Domain Reference for evo-mass-report-output

**Responsibility**: Coordinate the end-to-end workflow: invoke STL parsing, determine the dominant Material ID, filter by material, find largest connected component, compute volume and mass, round results, and serialize to /root/mass_report.json with the exact required schema.

**Key functions to implement**: run_mass_calculation_pipeline, write_mass_report_json

---

## JSON Data Finalization


After extracting the geometry, isolating the largest connected component, and evaluating the scaled volume, the data usually informs mass calculations. If a material density is provided, mass is evaluated as \(Mass = Volume_{\text{cm}^3} \times Density_{\text{g/cm}^3}\).

To serialize this properly in JSON to exactly 2 decimal places, Python's `json` module combined with `round()` is required. Standard floating-point representation can yield extended decimals (e.g., `45.120000000000005`). Using `round(value, 2)` ensures the number outputs correctly.

## Complete Integrated Python Script


The following code encapsulates the entirety of the pipeline utilizing the pure `struct` approach. It reads the binary STL, filters by Material ID, applies Union-Find to drop scanning debris, calculates the signed volume via the Divergence Theorem, converts to cubic centimeters, and dumps the result to JSON.

```python
import struct
import os
import json
import numpy as np

class UnionFind:
    def __init__(self):
        self.parent = {}
        self.size = {}

    def add(self, item):
        if item not in self.parent:
            self.parent[item] = item
            self.size[item] = 1

    def find(self, item):
        root = item
        while self.parent[root] != root:
            self.parent[root] = self.parent[self.parent[root]]
            root = self.parent[root]
        return root

    def union(self, item1, item2):
        self.add(item1)
        self.add(item2)
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            if self.size[root1] < self.size[root2]:
                root1, root2 = root2, root1
            self.parent[root2] = root1
            self.size[root1] += self.size[root2]


def parse_binary_stl(filepath):
    """
    Parses binary STL strictly using struct, returning a structured list.
    """
    file_size = os.path.getsize(filepath)
    if file_size < 84:
        raise ValueError("Invalid STL file size.")

    facets = []
    with open(filepath, 'rb') as f:
        _ = f.read(80) # Skip header
        num_triangles = struct.unpack('<I', f.read(4))
        
        expected_size = 84 + (num_triangles * 50)
        if file_size < expected_size:
            raise ValueError("File is truncated.")
            
        buffer = f.read(num_triangles * 50)
        offset = 0
        facet_format = '<12fH'
        
        for _ in range(num_triangles):
            data = struct.unpack_from(facet_format, buffer, offset)
            facet = {
                'v1': (data[cite: 6], data[cite: 9], data[cite: 10]),
                'v2': (data[cite: 13], data[cite: 14], data[cite: 15]),
                'v3': (data[cite: 16], data[cite: 17], data[cite: 18]),
                'material_id': data[cite: 19]
            }
            facets.append(facet)
            offset += 50
            
    return facets


def get_largest_connected_component(triangles, rounding_decimals=5):
    """
    Finds the largest connected component utilizing Union-Find.
    """
    uf = UnionFind()
    
    def canonical(v):
        return (round(v, rounding_decimals), 
                round(v[cite: 11], rounding_decimals), 
                round(v[cite: 12], rounding_decimals))
                
    for tri in triangles:
        v1, v2, v3 = canonical(tri['v1']), canonical(tri['v2']), canonical(tri['v3'])
        uf.add(v1)
        uf.add(v2)
        uf.add(v3)
        uf.union(v1, v2)
        uf.union(v2, v3)
        
    component_groups = {}
    for tri in triangles:
        root = uf.find(canonical(tri['v1']))
        if root not in component_groups:
            component_groups[root] = []
        component_groups[root].append(tri)
        
    largest_component = []
    max_size = -1
    for group in component_groups.values():
        if len(group) > max_size:
            max_size = len(group)
            largest_component = group
            
    return largest_component


def compute_volume(triangles):
    """
    Computes volume using the signed tetrahedron method.
    """
    if not triangles:
        return 0.0
        
    # Convert list of dicts to a numpy array for vectorized computation
    v_array = np.array([[tri['v1'], tri['v2'], tri['v3']] for tri in triangles])
    
    v1 = v_array[:, 0, :]
    v2 = v_array[:, 1, :]
    v3 = v_array[:, 2, :]
    
    cross_prod = np.cross(v2, v3)
    dot_prod = np.einsum('ij,ij->i', v1, cross_prod)
    
    return np.abs(np.sum(dot_prod)) / 6.0


def process_stl_pipeline(filepath, target_material_id, material_density_g_cm3):
    """
    Executes the full parsing, filtering, and calculation pipeline.
    """
    # 1. Parse File
    all_facets = parse_binary_stl(filepath)
    
    # 2. Filter by Material ID
    filtered_facets = [f for f in all_facets if f['material_id'] == target_material_id]
    
    # 3. Filter topological scanning debris
    main_part_facets = get_largest_connected_component(filtered_facets)
    
    # 4. Compute Volume (mm^3)
    volume_mm3 = compute_volume(main_part_facets)
    
    # 5. Convert to cm^3
    volume_cm3 = volume_mm3 / 1000.0
    
    # 6. Compute mass
    mass = volume_cm3 * material_density_g_cm3
    
    # 7. Output JSON
    output = {
        "main_part_mass": round(mass, 2)
    }
    
    return json.dumps(output, indent=4)