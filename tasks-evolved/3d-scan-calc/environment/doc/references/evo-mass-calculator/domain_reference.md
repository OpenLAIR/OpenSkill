# Domain Reference for evo-mass-calculator

**Responsibility**: Signed volume computation via divergence theorem (vectorized NumPy), markdown density table parsing, unit conversion (mm³ to cm³), mass calculation, and JSON output formatting.

**Key functions to implement**: calculate_mesh_volume_cm3, parse_material_density_table, compute_mass, write_mass_report

---

## 3. Mathematical Computation of Signed Volume


Computing the exact volume of a closed triangulated mesh relies on an application of the **Divergence Theorem** (also colloquially referred to as the Signed Tetrahedron Method).

### 3.1 Mathematical Theory

If we imagine a vector field $\mathbf{F}(\mathbf{r}) = \mathbf{r}$, the divergence is $\nabla \cdot \mathbf{F} = 3$. By the Divergence Theorem, the volume integral inside a closed boundary surface $S$ is related to the surface integral:
$$ \iiint_V (\nabla \cdot \mathbf{F}) dV = \iint_S \mathbf{F} \cdot \mathbf{\hat{n}} dS \implies 3V = \iint_S \mathbf{r} \cdot \mathbf{\hat{n}} dS $$
$$ V = \frac{1}{3} \iint_S \mathbf{r} \cdot \mathbf{\hat{n}} dS $$

For a triangulated surface, we break the surface integral into a discrete sum over all triangles. For a triangle defined by vertices $\mathbf{v}_1, \mathbf{v}_2, \mathbf{v}_3$, the surface area normal (which is area times unit normal) is derived from the cross product: $\frac{1}{2}(\mathbf{v}_2 - \mathbf{v}_1) \times (\mathbf{v}_3 - \mathbf{v}_1)$. However, it mathematically simplifies beautifully when evaluating from the origin.

The signed volume of a tetrahedron formed by the origin $(0,0,0)$ and the triangle $(\mathbf{v}_1, \mathbf{v}_2, \mathbf{v}_3)$ is the scalar triple product divided by 6:
$$ V_{\text{tetra}} = \frac{1}{6} \mathbf{v}_1 \cdot (\mathbf{v}_2 \times \mathbf{v}_3) $$

By summing $V_{\text{tetra}}$ for every triangle in the mesh, the internal tetrahedrons cancel each other out, leaving exactly the volume enclosed by the mesh.

### 3.2 Sign Convention, Units, and `abs()`

*   **Sign Convention:** The cross product $\mathbf{v}_2 \times \mathbf{v}_3$ adheres to the right-hand rule. If the vertices of each triangle are wound counter-clockwise when viewed from the outside (meaning the normal points *outward* from the solid body), the sum will be positive. If the mesh is perfectly intact but "inside-out" (normals pointing inward), the sum will be negative. Therefore, taking the `abs(total_volume)` is standard practice to safeguard against inverted, watertight meshes.
*   **Unit Conversion:** STL files are mathematically unitless. However, in modern 3D printing and CAD ecosystems, $1 \text{ unit} \equiv 1 \text{ mm}$ [cite: 1]. Since density is often provided in $\text{g/cm}^3$, the computed volume must be translated from $\text{mm}^3$ to $\text{cm}^3$. Because volume represents cubic space, the scaling factor is $10^3 = 1000$. Hence, $V_{\text{cm}^3} = V_{\text{mm}^3} / 1000.0$.
*   **Degenerate Triangles:** If a triangle has zero area (e.g., vertices are collinear or identical), the cross product $\mathbf{v}_2 \times \mathbf{v}_3$ evaluates to the zero vector $$, yielding a tetrahedron volume of $0$. Degenerate triangles gracefully contribute nothing to the volume calculation, causing no mathematical errors.

### 3.3 Vectorized Python/NumPy Implementation


```python
import numpy as np

def calculate_mesh_volume_cm3(vertices: np.ndarray) -> float:
    """
    Computes the signed volume of a triangulated mesh in cm³, assuming 
    the input vertices are in mm.
    
    Args:
        vertices (np.ndarray): Shape (N, 3, 3) representing N triangles,
                               each with 3 vertices, each with 3 (x,y,z) coords.
                               
    Returns:
        float: Absolute volume in cubic centimeters.
    """
    # Extract the three vertices for all triangles
    v1 = vertices[:, 0, :]
    v2 = vertices[:, 1, :]
    v3 = vertices[:, 2, :]
    
    # Calculate cross product of v2 and v3
    cross_v2_v3 = np.cross(v2, v3)
    
    # Calculate dot product of v1 with the cross product
    # np.einsum('ij,ij->i') is a highly optimized way to perform row-wise dot products
    dot_products = np.einsum('ij,ij->i', v1, cross_v2_v3)
    
    # Sum over all triangles and divide by 6
    total_volume_mm3 = np.sum(dot_products) / 6.0
    
    # The sign of the volume depends on the normal orientation. 
    # Taking the absolute value guarantees a positive physical volume.
    total_volume_mm3 = abs(total_volume_mm3)
    
    # Convert mm³ to cm³
    total_volume_cm3 = total_volume_mm3 / 1000.0
    
    return total_volume_cm3
```

---

### 6.4 Scale and Units

The STL format relies heavily on the "handshake" agreement between export and import software [cite: 1]. Neither binary nor ASCII STL files possess a parameter denoting mm, cm, or inches. In standard 3D printing contexts (Cura, PrusaSlicer), $1.0$ is interpreted as $1 \text{ mm}$. If your material density table expresses density in $\text{g/cm}^3$, you must firmly document that the pipeline assumes mm geometries and scales the resultant volume by dividing by 1000.

---

## 7. Converting the Material Density Table from Markdown


When maintaining material configurations, it is common to parse external files like markdown tables. Because Markdown represents tables textually utilizing pipe characters `|`, extracting the Material ID (integer) and the Density (float) is achievable via raw string manipulation or regular expressions.

Assuming a markdown configuration that looks like this:
```markdown
| Material ID | Density (g/cm³) | Material Name |
| ----------- | --------------- | ------------- |
| 1           | 1.04            | ABS           |
| 2           | 1.24            | PLA           |
| 15          | 1.27            | PETG          |
```

Here is a robust Python parser to extract this mapping:

```python
import re
from typing import Dict

def parse_density_markdown(markdown_text: str) -> Dict[int, float]:
    """
    Parses a markdown table to extract Material ID to Density mapping.
    Assumes the first column is the ID and the second is the Density.
    
    Args:
        markdown_text (str): The raw string content of the markdown file.
        
    Returns:
        Dict[int, float]: Mapping from Material ID to Density in g/cm³
    """
    material_density_map = {}
    
    # Regex breakdown:
    # ^\|                : Starts with a pipe
    # \s*(\d+)\s*        : Captures an integer (Material ID) surrounded by spaces
    # \|                 : Separator pipe
    # \s*([0-9]*\.?[0-9]+)\s* : Captures a floating point number (Density)
    # \|                 : Separator pipe
    row_pattern = re.compile(r'^\|\s*(\d+)\s*\|\s*([0-9]*\.?[0-9]+)\s*\|', re.MULTILINE)
    
    for match in row_pattern.finditer(markdown_text):
        mat_id = int(match.group(1))
        density = float(match.group(2))
        material_density_map[mat_id] = density
        
    return material_density_map