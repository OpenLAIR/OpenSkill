# Domain Reference for evo-mesh-geometry-analysis

**Responsibility**: Identify the largest connected component of triangles via vertex adjacency (Union-Find with coordinate snapping), compute closed mesh volume using the scalar triple product formula, convert units from mm³ to cm³, and calculate mass given density.

**Key functions to implement**: get_largest_connected_component, compute_mesh_volume, convert_volume_mm3_to_cm3, calculate_mass

---

## Calculating the Signed Volume of a Closed Mesh


To evaluate physical properties such as mass, one must calculate the volume of the geometry defined by the 3D mesh. Rather than voxelizing the mesh, the most elegant and computationally efficient method is based on the **Divergence Theorem** (also known as Gauss's Theorem) [cite: 13, 15, 20].

### Mathematical Derivation of the Divergence Theorem


The Divergence Theorem relates the flux of a vector field through a closed surface to the divergence of the field in the volume enclosed by that surface [cite: 20]. Mathematically, it states:

\[ \iiint_{\Omega} (\nabla \cdot \mathbf{F}) \, dV = \iint_{\partial \Omega} (\mathbf{F} \cdot \mathbf{n}) \, dS \]

Where \(\Omega\) is the volume, \(\partial \Omega\) is the closed boundary surface, \(\mathbf{F}\) is a continuous vector field, and \(\mathbf{n}\) is the outward-pointing normal vector [cite: 20].

To calculate the volume, we define a vector field \(\mathbf{F}\) such that its divergence is exactly 1. A standard choice is:
\[ \mathbf{F}(x, y, z) = (x, 0, 0) \]
Since \(\nabla \cdot \mathbf{F} = \frac{\partial x}{\partial x} + 0 + 0 = 1\) [cite: 15].

Alternatively, a completely symmetrical field is \(\mathbf{F}(x, y, z) = \frac{1}{3}(x, y, z)\). Using this field, the volume integral becomes exactly the volume \(V\), and the surface integral breaks down into the sum of integrals over each triangular facet [cite: 14]. 

When we integrate over a single triangle with vertices \(\mathbf{v}_1, \mathbf{v}_2, \mathbf{v}_3\) (relative to the origin), the surface integral evaluates identically to the **signed volume of a tetrahedron** formed by the origin and the triangle's vertices [cite: 14, 15].

### The Signed Tetrahedron Formula


The volume contribution of a single tetrahedron is mathematically expressed using the scalar triple product:

\[ V_{\text{tetrahedron}} = \frac{1}{6} \left( \mathbf{v}_1 \cdot (\mathbf{v}_2 \times \mathbf{v}_3) \right) \]

In this formula:
*   \(\mathbf{v}_1, \mathbf{v}_2, \mathbf{v}_3\) are the position vectors of the three vertices of the triangle.
*   \(\times\) denotes the cross product.
*   \(\cdot\) denotes the dot product.
*   The division by 6.0 is required because the volume of a parallelopiped formed by three vectors is the absolute value of the scalar triple product, and the tetrahedron occupies exactly \(1/6\) of that volume [cite: 14, 17].

The total volume of the closed mesh is the sum of these signed tetrahedral volumes:

\[ V_{\text{total}} = \left| \sum_{i=1}^{N} \frac{\mathbf{v}_{i1} \cdot (\mathbf{v}_{i2} \times \mathbf{v}_{i3})}{6.0} \right| \]

### Common Pitfalls in Volume Calculation


1.  **Winding Order**: STL standard dictates that vertices must be ordered according to the right-hand rule relative to the outward normal [cite: 2, 7]. If a triangle is facing away from the origin, the cross product points inward, yielding a negative volume contribution [cite: 13, 14]. Summing these positive and negative values correctly adds the volumes of shapes that pass through the origin while subtracting volumes representing hollow areas or overlapping backsides [cite: 13]. 
2.  **Absolute Value Requirement**: If an entire object has an inverted winding order, or if its geometric center is placed arbitrarily, the net sum could be a negative value. Therefore, it is imperative to take the **absolute value** of the final sum [cite: 13, 14].
3.  **Closed Mesh Assumption**: The Divergence Theorem only holds for **closed, watertight** meshes (manifold without boundary) [cite: 13, 15]. If a mesh has holes or non-manifold edges, the flux integral does not perfectly map to the volume, and the result will be erroneous [cite: 21].

### Python Implementation using NumPy


```python
import numpy as np

def compute_volume(vertices_array):
    """
    Computes the volume of a closed triangulated mesh using the signed tetrahedron method.
    
    Parameters:
    vertices_array: numpy array of shape (N, 3, 3) representing N triangles,
                    each with 3 vertices, each with 3 coordinates (x, y, z).
    
    Returns:
    Total volume as a float.
    """
    # Extract vertex columns: v1, v2, v3
    v1 = vertices_array[:, 0, :]
    v2 = vertices_array[:, 1, :]
    v3 = vertices_array[:, 2, :]
    
    # Calculate the cross product of v2 and v3
    # cross_prod is of shape (N, 3)
    cross_prod = np.cross(v2, v3)
    
    # Calculate the dot product of v1 with the cross product
    # np.einsum is highly efficient for batched dot products: 
    # 'ij,ij->i' multiplies element-wise and sums along axis 1
    dot_prod = np.einsum('ij,ij->i', v1, cross_prod)
    
    # Calculate the signed volumes of the tetrahedra
    signed_volumes = dot_prod / 6.0
    
    # Sum them up and take the absolute value
    total_volume = np.abs(np.sum(signed_volumes))
    
    return total_volume
```

## Unit Conventions and Conversion


An STL file stores floating-point numbers without embedding physical unit tags [cite: 1, 3]. However, across engineering disciplines, CAD tools (like SolidWorks, Fusion 360, and FreeCAD) heavily default to exporting coordinates in **millimeters (mm)**.

Consequently, if the coordinates are in millimeters, the calculated volume will be in **cubic millimeters (mm³)**. To convert from cubic millimeters to cubic centimeters (cm³)—often used to evaluate part mass alongside material density in g/cm³—the mathematical conversion is:

*   \(1 \text{ cm} = 10 \text{ mm}\)
*   \(1 \text{ cm}^3 = (10 \text{ mm})^3 = 1000 \text{ mm}^3\)

Thus, to convert the computed volume to cm³, divide the result by 1000.

\[ V_{\text{cm}^3} = \frac{V_{\text{mm}^3}}{1000} \]

## Topological Filtering: Connected Components


3D scans frequently yield localized point clouds and disconnected triangles, colloquially known as "scanning debris" [cite: 22]. To isolate the primary geometry (the main part), one must perform a topological analysis to determine the **largest connected component** of the mesh.

### Adjacency Structures


Two triangles are connected if they share at least one vertex [cite: 23]. Given raw float32 coordinate sets, establishing adjacency poses a challenge due to floating-point imprecision. Two vertices that theoretically touch might differ by \(10^{-6}\) in one coordinate due to IEEE 754 truncation during exporting.

### Edge Case: Filtering by Material ID vs. Connected Components


A critical operational question arises when the prompt requires filtering by both **Material ID** and **Largest Connected Component**. Should one group connected components across the *entire* mesh first, or only group components *within* the targeted Material ID?

*   **Global Connectivity First**: If scanning debris mistakenly touches the main object but is tagged with a different Material ID, a global connectivity graph will join them. If you then filter by Material ID, you may clip off the debris properly, but the core connectivity graph represents an artificial union.
*   **Material ID First**: This is generally the safer and more physically meaningful approach. If the prompt explicitly asks to evaluate a specific object made of a specific material, we should first isolate all triangles possessing that Material ID. Then, we execute the Union-Find algorithm exclusively on this subset to find the largest contiguous mass of that *specific* material. This guarantees that "debris" of other materials never influences the topological mapping of the main part.

We adopt the **Material ID First** strategy for maximum robustness.

### Implementation of Union-Find for Triangle Meshes


```python
class UnionFind:
    def __init__(self):
        self.parent = {}
        self.size = {}

    def add(self, item):
        if item not in self.parent:
            self.parent[item] = item
            self.size[item] = 1

    def find(self, item):
        # Path compression
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
            # Union by rank/size
            if self.size[root1] < self.size[root2]:
                root1, root2 = root2, root1
            self.parent[root2] = root1
            self.size[root1] += self.size[root2]

def get_largest_connected_component(triangles, rounding_decimals=4):
    """
    Finds the largest connected component of triangles.
    
    Parameters:
    triangles: List of tuples/arrays, where each element is (v1, v2, v3)
               and vX is a tuple/array of (x,y,z).
               
    Returns:
    List of triangles belonging to the largest connected component.
    """
    uf = UnionFind()
    
    # Helper to canonicalize a vertex
    def canonical(v):
        return (round(v, rounding_decimals), 
                round(v[cite: 11], rounding_decimals), 
                round(v[cite: 12], rounding_decimals))
                
    # Build connections
    for i, tri in enumerate(triangles):
        v1, v2, v3 = canonical(tri), canonical(tri[cite: 11]), canonical(tri[cite: 12])
        uf.add(v1)
        uf.add(v2)
        uf.add(v3)
        uf.union(v1, v2)
        uf.union(v2, v3)
        
    # Group triangles by the root of their vertices
    component_groups = {}
    for i, tri in enumerate(triangles):
        # All vertices in the triangle share the same root now
        root = uf.find(canonical(tri))
        if root not in component_groups:
            component_groups[root] = []
        component_groups[root].append(tri)
        
    # Find the largest group
    largest_component = []
    max_size = -1
    for root, group in component_groups.items():
        if len(group) > max_size:
            max_size = len(group)
            largest_component = group
            
    return largest_component
```