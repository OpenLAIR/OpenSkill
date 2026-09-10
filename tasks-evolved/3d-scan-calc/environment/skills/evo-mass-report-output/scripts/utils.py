"""Mass report output: orchestrates the full pipeline and writes JSON report.

Pipeline:
1. Parse binary STL -> list of (v1, v2, v3, material_id) tuples
2. Find largest connected component (vertex-based adjacency, 4-decimal quantization)
3. Extract Material ID from first triangle of largest component
4. Look up density from material density table
5. Compute volume (mm^3) using signed tetrahedron method
6. Convert mm^3 to cm^3 (divide by 1000)
7. Calculate mass = volume_cm3 * density_g_cm3
8. Round mass to 2 decimal places
9. Write JSON report
"""

import json
import sys
from typing import Dict

# Import from sibling skills
sys.path.insert(0, '/app/environment/skills/evo-stl-binary-parser/scripts')
sys.path.insert(0, '/app/environment/skills/evo-mesh-geometry-analysis/scripts')


def run_mass_calculation_pipeline(
    stl_path: str = '/root/scan_data.stl',
    density_table_path: str = '/root/material_density_table.md',
    output_path: str = '/root/mass_report.json'
) -> Dict:
    """
    Run the complete mass calculation pipeline.
    
    Steps:
    1. Parse binary STL
    2. Find largest connected component
    3. Get material ID from first triangle of largest component
    4. Look up density
    5. Compute volume, convert units, calculate mass
    6. Write JSON report
    
    Returns dict with main_part_mass and material_id.
    """
    from utils import parse_binary_stl as _parse  # avoid name collision
    # Re-import with explicit module references
    sys.path.insert(0, '/app/environment/skills/evo-stl-binary-parser/scripts')
    import importlib
    import utils as stl_utils
    importlib.reload(stl_utils)
    
    sys.path.insert(0, '/app/environment/skills/evo-mesh-geometry-analysis/scripts')
    import utils as mesh_utils
    importlib.reload(mesh_utils)
    
    # 1. Parse STL
    print(f"Parsing STL: {stl_path}")
    triangles = stl_utils.parse_binary_stl(stl_path)
    print(f"Total triangles: {len(triangles)}")
    
    # Show material distribution
    from collections import Counter
    mat_counts = Counter(t[3] for t in triangles)
    print(f"Material distribution: {dict(mat_counts)}")
    
    # 2. Find largest connected component
    print("Finding largest connected component...")
    largest_comp = mesh_utils.get_largest_connected_component(triangles)
    print(f"Largest component: {len(largest_comp)} triangles")
    
    # 3. Get material ID from first triangle
    material_id = largest_comp[0][3]
    print(f"Material ID: {material_id}")
    
    # 4. Look up density
    density = stl_utils.lookup_density(material_id)
    print(f"Density: {density} g/cm³")
    
    # 5. Compute volume
    volume_mm3 = mesh_utils.compute_mesh_volume(largest_comp)
    print(f"Volume (mm³): {volume_mm3:.4f}")
    
    # 6. Convert to cm³
    volume_cm3 = mesh_utils.convert_volume_mm3_to_cm3(volume_mm3)
    print(f"Volume (cm³): {volume_cm3:.6f}")
    
    # 7. Calculate mass
    mass = mesh_utils.calculate_mass(volume_cm3, density)
    print(f"Mass: {mass:.4f} g")
    
    # 8. Round and write report
    result = {
        "main_part_mass": round(mass, 2),
        "material_id": int(material_id)
    }
    
    write_mass_report_json(output_path, result)
    return result


def write_mass_report_json(filepath: str, result: Dict) -> None:
    """
    Write mass report as JSON.
    
    Output format:
    {
      "main_part_mass": 34.65,
      "material_id": 42
    }
    """
    with open(filepath, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Report written to {filepath}")
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    result = run_mass_calculation_pipeline()
    print(f"\nFinal result: {result}")
