# Comprehensive Analysis of Binary STL File Parsing, Mesh Volume Computation, and Topological Component Filtering in Python

**Key Points:**
*   It is generally understood that the binary STL file format contains an 80-byte header, a 4-byte triangle count, and sequentially packed 50-byte facet records, though variations exist.
*   Research suggests that Python's `struct` module is highly effective for unpacking binary layouts, particularly using the `<12fH` format string for extracting 3D floating-point coordinates and 16-bit integers.
*   The volume of closed 3D meshes can likely be calculated most efficiently using the Divergence Theorem, summing the signed volumes of tetrahedra formed by each triangle and the origin.
*   Evidence leans toward using the Disjoint Set Union (Union-Find) data structure to identify connected components in a mesh, which often helps filter out disconnected geometric "debris."
*   It seems highly probable that `numpy-stl`, a specialized library, exposes the attribute byte count natively as a `uint16` array, providing a robust alternative to manual parsing.

The extraction and analysis of stereolithography (STL) files remain fundamental to modern 3D printing, computer-aided manufacturing (CAM), and computational geometry. Despite its simplicity and age, the STL format is ubiquitous, acting as the lowest common denominator for representing tessellated 3D surfaces. When handling these files, users frequently encounter the need to perform precise binary parsing, volume calculations, and topological filtering. 

This report provides an accessible but exhaustive guide to processing binary STL files using Python. It explores the exact structural layout of the format, how to convert binary streams into actionable numeric arrays without third-party dependencies, and how to utilize external tools if preferred. Furthermore, we explore advanced geometric algorithms, specifically measuring part mass using vector calculus and filtering out floating artifacts using graph theory.

The methods discussed herein attempt to balance theoretical rigor with practical implementation. Whether dealing with pure floating-point operations, memory-safe byte extraction, or complex topological structures, the solutions prioritize efficiency and accuracy. By synthesizing these computational techniques, one can reliably isolate specific components of a 3D model, calculate their physical properties, and output the data into standardized formats like JSON.

## The Binary STL File Format Specification

The STereoLithography (STL) file format, originally developed by 3D Systems, describes raw unstructured triangulated surfaces using a three-dimensional Cartesian coordinate system [cite: 1, 2]. The format lacks complex topological data, scale information, and units, relying entirely on the unit normal and vertices of simple triangles [cite: 1, 3]. Due to the sheer size of ASCII-encoded STL files for complex meshes, the binary variant of the format is overwhelmingly preferred in industrial and research settings [cite: 1, 2].

A standard binary STL file strictly adheres to a sequential byte layout. Unlike many modern file formats, it does not use complex chunking or compression, but rather sequential packed binary records.

### Exact Byte Layout

The layout of a binary STL file is segmented into three distinct sections: the header, the facet count, and the array of facet records [cite: 1, 2]. 

**Table 1: Binary STL File Byte Layout**

| Offset (Bytes) | Size (Bytes) | Data Type | Description |
| :--- | :--- | :--- | :--- |
| `0` | `80` | `uint8` | Header (Arbitrary ASCII/binary data). |
| `80` | `4` | `uint32` | Number of triangular facets in the file. |
| `84` | `50 * N` | `Facet Record` | Sequential list of all triangles. |

Each triangle (facet) record is precisely 50 bytes long and contains the geometric data defining the triangle, as well as an often-misunderstood attribute field [cite: 4, 5].

**Table 2: 50-Byte Facet Record Layout**

| Local Offset | Size | Data Type | Description |
| :--- | :--- | :--- | :--- |
| `0` | `12` | `float32[cite: 6]` | Normal vector (\(N_x, N_y, N_z\)) |
| `12` | `12` | `float32[cite: 6]` | Vertex 1 (\(V1_x, V1_y, V1_z\)) |
| `24` | `12` | `float32[cite: 6]` | Vertex 2 (\(V2_x, V2_y, V2_z\)) |
| `36` | `12` | `float32[cite: 6]` | Vertex 3 (\(V3_x, V3_y, V3_z\)) |
| `48` | `2` | `uint16` | Attribute byte count (e.g., Material ID, Color) |

### Endianness and the Attribute Byte Count

The STL specification implies, and all compliant implementations enforce, that numerical data is stored in **little-endian** format [cite: 2, 7]. This means the least significant byte of a numerical value is stored at the lowest memory address.

The 2-byte field located at bytes 48-49 of each facet record is formally termed the **attribute byte count** [cite: 1, 2]. In standard practice, software sets this field to zero [cite: 1, 7]. However, non-standard implementations co-opt these two bytes to store 15-bit RGB color data (e.g., VisCAM, SolidView) or to tag triangles with specific group or material identifiers [cite: 2]. Interpreting this field as an unsigned 16-bit integer (`uint16`) allows us to extract the **Material ID** safely and deterministically [cite: 4].

### Common Pitfalls in Binary STL Recognition

1. **The "Solid" Header Confusion**: ASCII STL files must begin with the string `solid` [cite: 2, 8]. A binary STL file has an 80-byte header that may contain arbitrary data. If a binary file's header happens to start with the characters `solid`, naive parsers will mistakenly attempt to decode it as an ASCII file [cite: 1, 2]. Therefore, robust parsers usually verify the file size against the expected size calculated from the triangle count (`84 + 50 * N`) rather than relying purely on a string check.
2. **Trailing Data**: Some proprietary 3D software applications append additional undocumented metadata at the end of the file after the declared number of triangles [cite: 4]. A proper parser must only read exactly `N` triangles and ignore trailing bytes.

## Parsing Binary STL Using Python's `struct` Module

Python's built-in `struct` module facilitates the conversion between Python values and C structs represented as Python `bytes` objects [cite: 9, 10]. This is an ideal tool for unpacking the tightly structured binary STL format.

### Struct Format Strings

To parse the 50-byte facet block efficiently, a `struct` format string must be constructed. Format strings use special characters to dictate byte order, size, and alignment [cite: 10].

*   `<` signifies **little-endian** standard size [cite: 9].
*   `f` signifies an IEEE 754 32-bit floating-point number (4 bytes) [cite: 10].
*   `H` signifies an unsigned short integer (2 bytes) [cite: 9].

The complete format string for a single 50-byte facet is `<12fH` [cite: 4, 5]. This tells the `struct` module to unpack twelve little-endian `float32` values followed by one little-endian `uint16` value [cite: 4, 9].

### Pure Python Implementation

The following is a robust, purely self-contained Python function that parses a binary STL file without external dependencies. It uses `struct.unpack_from` for efficient memory extraction with specific offset arithmetic to avoid copying redundant byte arrays into memory.

```python
import struct
import os

def parse_binary_stl_pure(filepath):
    """
    Parses a binary STL file using the struct module.
    Returns a list of dictionaries, each containing the facet's normal, 
    vertices, and attribute byte count (Material ID).
    """
    # Verify file size logic to avoid reading mangled files
    file_size = os.path.getsize(filepath)
    if file_size < 84:
        raise ValueError("File is too small to be a valid binary STL.")

    facets = []
    
    with open(filepath, 'rb') as f:
        # Read the 80-byte header (ignored)
        header = f.read(80)
        
        # Read the 4-byte little-endian unsigned integer for triangle count
        count_bytes = f.read(4)
        num_triangles = struct.unpack('<I', count_bytes)
        
        # Verify the expected file size to prevent over-reading
        expected_size = 84 + (num_triangles * 50)
        if file_size < expected_size:
            raise ValueError("File size does not match the declared triangle count.")
            
        # Read the remainder of the file into a buffer
        # This is more efficient than reading 50 bytes at a time
        buffer = f.read(num_triangles * 50)
        
        # Parse each facet using struct.unpack_from and offset arithmetic
        offset = 0
        facet_format = '<12fH'
        
        for _ in range(num_triangles):
            # Unpack 13 values: 3 for normal, 9 for vertices, 1 for attribute
            data = struct.unpack_from(facet_format, buffer, offset)
            
            facet = {
                'normal': (data, data[cite: 11], data[cite: 12]),
                'v1': (data[cite: 6], data[cite: 9], data[cite: 10]),
                'v2': (data[cite: 13], data[cite: 14], data[cite: 15]),
                'v3': (data[cite: 16], data[cite: 17], data[cite: 18]),
                'attribute_byte_count': data[cite: 19] # Extracted Material ID
            }
            facets.append(facet)
            
            # Increment the offset by exactly 50 bytes
            offset += 50
            
    return facets
```

Using `struct.unpack_from` with a buffer is substantially faster than calling `f.read(50)` iteratively within a loop, as it reduces I/O calls to the operating system and leverages memory views.

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

#### Approach 1: Snapping and Graph Building
Vertex coordinates must be canonicalized by rounding to a small number of decimal places (e.g., 4 or 5) to snap nearby vertices together [cite: 23, 24]. These canonical coordinates can be hashed into a dictionary assigning a unique integer ID to each unique spatial location.

#### Approach 2: Disjoint Set Union (Union-Find)
The most computationally optimal algorithm to find connected sets across relationships is the Disjoint Set Union (DSU) or Union-Find algorithm [cite: 22, 23, 25]. 

*   **Make-Set**: Each unique vertex ID starts in its own component.
*   **Union**: For every triangle, we instruct the DSU to unite the sets containing vertex 1, vertex 2, and vertex 3.
*   **Find**: Traces a vertex back to its root component ID, applying path compression to maintain near \(O(1)\) time complexity [cite: 22].

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

## The `numpy-stl` Ecosystem Alternative

While pure `struct` parsing is robust and free from dependencies, the specialized `numpy-stl` library provides a high-performance, vectorized interface for working with STL geometries [cite: 18, 26]. 

### Does `numpy-stl` expose the Attribute Byte Count?

Yes. Research conclusively shows that the structured NumPy array utilized natively by `numpy-stl`'s `Mesh` object includes three fields: `normals` (`<f4`), `vectors` (`<f4`), and importantly, **`attr`** (`<u2`) [cite: 26, 27]. 

The API to load a mesh is:
```python
from stl import mesh
my_mesh = mesh.Mesh.from_file('model.stl')
```
Once loaded, the object exposes [cite: 26, 27]:
*   `my_mesh.vectors`: An \(N \times 3 \times 3\) NumPy array of the vertices.
*   `my_mesh.normals`: An \(N \times 3\) NumPy array of the unit normals.
*   `my_mesh.attr`: An \(N \times 1\) NumPy array of type `uint16`, representing the exact 2-byte attribute byte count (Material ID).

Using `numpy-stl` eliminates the need to perform manual byte offsets and `struct` unpacking, while providing instantaneous access to the data needed for algorithmic masking:

```python
# Using numpy-stl to filter by Material ID (e.g., Target ID = 42)
target_material_id = 42
# attr is shape (N, 1), so we flatten it for boolean indexing
mask = my_mesh.attr.flatten() == target_material_id
filtered_vectors = my_mesh.vectors[mask]
```

Since the prompt requests evaluating options and providing working Python code using `struct`, we provide the manual `struct` variant as the definitive primary solution to demonstrate an algorithmic understanding of the byte layout.

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

# Example usage:
# result_json = process_stl_pipeline("part.stl", target_material_id=2, material_density_g_cm3=1.04)
# print(result_json)
```

**Sources:**
1. [brandeis.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHk9xYK94s1CXa0Y9-BOY1lwV7vzOat9cMQjWsf6kTMK5oSkAzq4pMGqpjQzIqLj-nHGXt988Svhod9LUC3QEdKj8om8GiYW3YYjx45iLxuL1yXnJ2WqNk6hILKiBcvh03Z-86ilpasJTWrJnNZghjUBOJjsXc1pLufunES087eDdypL7lmoGIk5Zknf7Ta_kxJeELNp1l1TA==)
2. [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGt7EGaVgQeBeUViXJv_RoIZrdilx_9VPt_CifPGmVaoMUNQWfXS4CS6qBdlcUYqivmnT0P7wwemk2Z3G0TB3sbctEAzd7DL7qDTEbJmG746bFWtF5e1My15_crI9lA3yq_Bn16)
3. [goldensoftware.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHc6nVfgDyYf58ubBvoRcOunUh75zhmAgwkQJRpQw-CNwzjT1Cx8ta-HjyhN6fG5PVB_exPUkJW7HE4DVdegBxdDondt01DRNWdWxwAnSo-Ei7G0zSbF9f9OfvEz3ll6ZCbVZBlbpb4mjlLci0u7Dyymdh7R1S3IsSdtL3SdWcrCW2Mk4cuTFIzXyteZEEanmaiQmI=)
4. [dream3d.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-XqEJr4BEE0DTNwIDoCsmGG1tkjGK1OV5CNY530aUXgluBnif97ex9ikO8regUsYrSgYEX5B6qpCnyVNCP599XlkIE-0Ok6LOIBXgBhWHkQQV1JYQcQb7_ihuJxObOxj_vR8UNA7HLT6iboC3Uui_mdArRn2sN_oiTkuG2w7ARhjlIXuZ4a8=)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHISWn7QVkTvekKeNReeg0gil1pauSyLwF-C0GZanl6sw1p1kF2lcY-CJjbljJkR74S7ut5YxrGjb5_-Rjuoa0tYzl4RvvJ-qnK6ikbMBSFYnuqx9Q1Amq2zPFVeEODmQqdF83-XjB-_J2y9tyW6dP-shEwMCRrHw==)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGz4oQMm14yMZMxNji4gbqsrboNwryDkTIaRIULIWd8LCZ3a5gVczOv3IqkDyyX2b2rKIw142cMCi3OQhLAKT5sVS4EEyZWT9qzjxE2SHHp4N-jhh7NoGYmR2xH7yZ5dXeoflrPzeLbS_0VyfDpa-DBETOkx3PAeX1oXXTMHYt5)
7. [radagast.ca](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2KAdDaKhrg7DiZQJL86ocPObSxbSRvhMuqWNU8pR9YjyZQ32Jw9LCehDxU0xqsQffrCmR4L8jGHax7aBA_1R5JD9PsY0OB7emAMnm5_bGSiGU0yaPfmzB79CS8KE22qrM6gW-t1w=)
8. [dptcorporate.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtnR0lvIRUH_mV27bZsM-RklEGxSJZy--VVvf-WE691C2ChU3hIXkK7PQyj7Ljpn708uDoBpK5cJze-Aua43ooi2-AFg5lnb5QR-sbhuLJQ3yvCySnbBztxwZUXGo28ddLCpCd-7acx6ngQ5NscNAF8zVoJYsa2OuiwUo=)
9. [digitalocean.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyZjftBoVK3hfCYFUsnm8K3DwtnYssqMq7xLCgNFCEF6snJj2TT7Z0dwJ02Sbi6unnabl4-Tzx1K0Jf6qfdUOdYWynUyeR8c33Uadzo2T0FjUs98Tg473LYRuA19xLZHjHRJkcGaj8NoBy02u1AFV-02yPP3TRHhfauEzfTAxR)
10. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHvyBu1zTIvcH3WeXF_aHATNW2LIMv17IVmxyeuKTNw0IcDIyHjS_qP3A4BlIVEv5h2SuBqouHdtsgoabEup0Z0FK5OnHDaV7TQ_Kgdl_l__qVpu7PM-R6S1214zaNXZYQ3Ow==)
11. [fluentpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESEMDwKXlhwNeMJx-FKpve55LUJjC-TxirBqXtbfhccBEjWBJLQHtvrUQdyq0Gqg5EMGqZOKByxQFW8_D9TDhkU8MLWiyn93SLiN4wFf_LDg_yUEmQgcpyCfCa3odwB2jEzOg2AFhENapc-59oCQ==)
12. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnFx2trLokrsQZkuGVzr1IoSX3p792nosOeZLSto3sCEH3JAs21NGTExHXNVvsNMEieh9D4UHiZCtngf4hd5jvzuG1VyeW7wElfw-1lMXQYpgACMU5C9-1eCACMut320RDzoOsKdAd3YccT_lPZLAGUGASyN24YXcN1VHXGfzR4R_X1cvfYuifKJodULGzXOEGpihS-VFg)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGt7Vt0avQH8Qo_GxdQVbgadVRCi-y_YVoH1aqro6e0q11WjP7m83VKsVhQPqJ33FxHSDDiUFz7UuxMHiEU4PSJjUGmHQS9zReUItX-yjNNF54xIlN7owcBDSwTGnE548ei4PzYuD3w0bL9uHZY4yKFJAzDvA7LqNJ82qrDIIBPuFRKB1pQNEL256Zm2adWuXyvFT81rprZykEjm1Z1e_CV-MBtDIAHII5AaKmgMCbQtA==)
14. [khronos.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEFieAmESPMUKB4hA7KxRSZX4toN8Irrx_iDTN6mAGINJy6seP7EfTxFnegiIG0OQqOXjcb990HCJbfJB36MHRrVPJ2kkutG4t_BB0lVrdNmVzJ2mIlHTX9wxGszrgGfimDI_9SddbFx5fB7ewHaRIjDD0Q)
15. [alyssarosenzweig.ca](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE3n8zv6WtUTLWlRedCJevApor57sv5OntMl2GMkBB_DV-mTA-pm11PMadaQMK2PNlqQyWL2dKW58PJoLhbzqdWQModHXF7qI_dchoA948tBChRf2UQiqEg_i2kyAuTfVsUjecOXN9_ixBpreMhK1CA8_TzG1yJWInBjV-cttIFaHyZ-Q8MlBt033DW_lCf8p2lQznh5kLamF7R)
16. [ctsolakis.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjr89kbO2UUsw6Gy5708PquJatDdJ2ZCEU0Yav-B9_ubmlfThgUH5sjgK0OduwJZvG_g0MSpH4GdZ_0meULVpjTbTRFWyunVu1eVViCcgf-xxkWibFgkGln6iZ_lN78KakdjcjxDU7ZQL5ssBr7C6QbTzihmex5ic=)
17. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPAE6gxrQxowSannKhB6xuJdHk9A3ddlH3e4_aPUy_uuMM0S85tsEdocH4KWrxnR3KvANrKv0qyI7JzW7PEcZ2B6srTJc0ADf3RhkKkBeOMaDQbIcbPMAI7ZVbhtcfzbanV2ywJLDHEhmsh9HQ-lKsA2la2B86cX0ntMrITdpvkkTe7xicdiRAFvJco2V3yIM=)
18. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF60Z-JEpK1shPOBPe5LjCFXtRh-9ZYuCxccRcRbHJO4Io9_-BE0GjWXIQ8i-2L7fFuDr4kFGixRE0oswWWFD17KERWA_lgm0sUJ58tJvoIpPHMIWnDLaSI7Qmq7l1Q2ZiEcgEKKkVMbTJ6_JLOydEu)
19. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGuaYwfOm3ZUEERZQhpKzbw829nvriZjzfCT9kiTSsgLn2R2AsZt6aAUBLB9qJJlc0P1MN5fG1FV54En9wDQR-tb_UevsiS0bRnoxnh3s9nm6buUMyXQWY-)
20. [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjKeY8HKp9nS5IGTJWVHGQ-Dr61DaWeGTP1x-QgBxnIqwXQOmdWbQ2-m515WwO5c8Ft3CBV4_gH27fSqiVz5Y2Wmxlv_YB_OMLxCtVjtdvbqkXB9Gg-hg8rAfcho2y2UAFxaUMKA==)
21. [uaf.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqzPUAfH4wkhKpwVLnHCEqpNdDWBve0OBOV45MUO_3HHqNIn2LkatN_Gx-Qd0Q6pb6zNTppzlGG3puNxqe6lIj2WvOnQ4raaP_fQXi3cJNwlhupfA-cjQb_dBjOXs0gRKhgmsmy_t-bkvObVJuuwyL3blNdyFCeA7P)
22. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmuVNwL1Fm5vyDsMh11eLRvqmqQLDcPQ45zXPPiC4Jw5sZdTt2QMkzR_ASMpH6TJRl4fWYj-IDPDeNitI3kGwNt76SuwcfJHi2RE19kqdlAe5NV15wOiwO)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHB3Q0yXixiMBDSmLNzqoLhOM92zJ9T7f2s3qFuknNCGHUCSa2HHEBLqXhACde2i5y2OfkMbQWvmCiU7vuMJwR1ii7edAIb43nALo5mEn7xz48ILu66rdsu5F5EynG0TfWOBTyUkAZHuQ==)
24. [aip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGoMFeFMLG6gO8Z2BpQlzHpU0ZC4gKLtNlNf5MYHrpPzDWkDGi4wLWBNk8DGc8_IDIjVl1ldAuD3e51y96EBcjS_dfmpTtEDv8a4hLHaAd1pSsjnB4Vg7cP5vb9_-Ua2TVPChOrj7RvE0hY9MZTy4qjHv2Tfj49F1WSzUeMFgw2Rf3y7na1nW7PnftE0d5ICIgzwZH2zy261xMFEd9ArhY=)
25. [scikit-image.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHc5VGyUvM7aqbRirQ8vcDVICVVNT3hWb2jETVCdznF6-eQk_8cs_aGM4ReH651y-Dtm_Nckg9EzChX6SBOZls3qHy6nPLcIvrTbUftzBBVRXomzuYdcVXglSjcCukG9j6pRNPHt0y62omvNplHDojbPok=)
26. [tessl.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHQi9oNvE6fHu4wvlfiPT7Vo-0e6yDfBFyKIcasBs35c74BaG3N-hZAdeeg5w0lWyXde0k1pzYKM4MBT48MdTibnWNe-C3Zp-IOUUtM_gGrjdkSt8nB2RXsi3EnJ5xd7_syBkg=)
27. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEFQfrmjUKzD24eXxjmOyyk5SQT6Kuc7SU0yrW7yyr8gzOf1h6y-OG2MYv0scI3pELbZb5a3qpm1RCKuL2omd-UYz3Ye_usRqnETm2p7Tg8WmwMULBh_wlCM5vofc5BxwopTPz1xR0FAQ==)
