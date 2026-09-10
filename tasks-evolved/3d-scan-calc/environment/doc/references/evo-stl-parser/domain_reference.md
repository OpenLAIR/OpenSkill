# Domain Reference for evo-stl-parser

**Responsibility**: Binary STL parsing with attribute byte extraction, vertex rounding for adjacency, face adjacency graph construction, BFS-based connected component detection, and returning the largest component's face indices along with their material IDs.

**Key functions to implement**: parse_binary_stl, find_largest_connected_component, get_component_vertices_and_material

---

## 1. The Binary STL Specification and Manual Parsing


The STL (Stereolithography) file format, created by 3D Systems in 1987, remains the ubiquitous standard for 3D printing and rudimentary geometry exchange [cite: 1]. Despite its widespread use, the format is notoriously limited in terms of metadata and structure [cite: 1]. It lacks inherent scale, units, material properties, and scene hierarchy definitions.

### 1.1 Byte-Level Anatomy of the Binary STL


The binary STL format was introduced to drastically reduce the file size overhead of ASCII STL representation. A strictly conforming binary STL file utilizes a rigid little-endian byte structure [cite: 2]. The exact byte layout is standardized as follows [cite: 3, 4]:

1.  **Header (80 bytes):** `UINT8`. A free-form text or binary header. Historically, it was strictly prohibited to begin this header with the word `solid` to avoid confusion with the ASCII STL format, though many modern parsers are resilient to this violation. This is the only place broad metadata can be stored [cite: 1].
2.  **Triangle Count (4 bytes):** `UINT32`. An unsigned 32-bit integer indicating the total number of triangular facets contained in the file.
3.  **Triangle Records (50 bytes each):** For each triangle specified by the count, a 50-byte sequence follows:
    *   **Normal Vector (12 bytes):** `REAL32[cite: 5]`. Three 32-bit floating-point numbers representing the $(x, y, z)$ coordinates of the facet's surface normal.
    *   **Vertex 1 (12 bytes):** `REAL32[cite: 5]`. The $(x, y, z)$ coordinates of the first vertex.
    *   **Vertex 2 (12 bytes):** `REAL32[cite: 5]`. The $(x, y, z)$ coordinates of the second vertex.
    *   **Vertex 3 (12 bytes):** `REAL32[cite: 5]`. The $(x, y, z)$ coordinates of the third vertex.
    *   **Attribute Byte Count (2 bytes):** `UINT16`. Traditionally expected to be zero, this 16-bit unsigned integer represents the "attribute byte count." However, certain software packages and customized pipelines repurpose these two bytes to encode 15-bit color profiles (RGB555) or, as in your use case, Material IDs [cite: 4, 6, 7].

### 1.2 Manual Parsing Implementation using the `struct` Module


To manually parse this utilizing Python's built-in `struct` module—without relying on third-party libraries that might arbitrarily discard the 2-byte attribute field—we can define format strings matching the byte representations. Because the binary STL file format is universally little-endian [cite: 2], the `<` prefix is mandatory in Python's `struct` format string to force little-endian decoding across all system architectures.

The format string for a single triangle is `<12fH` [cite: 8, 9]. This indicates:
*   `<` : Little-endian byte order.
*   `12f` : Twelve standard 32-bit IEEE 754 floats ($3 \text{ for normal} + 9 \text{ for vertices}$).
*   `H` : One 16-bit unsigned integer (the attribute byte count).

Below is the complete, robust, and tested Python utility code for parsing a binary STL file manually, extracting the normal vectors, vertices, and the repurposed Material ID (attribute byte count).

```python
import struct
import numpy as np
from typing import List, Tuple, Dict

def parse_binary_stl_manual(filepath: str) -> Dict[str, np.ndarray]:
    """
    Manually parses a binary STL file using the `struct` module.
    Extracts the normals, vertices, and the 2-byte attribute count (Material ID).
    
    Args:
        filepath (str): The path to the binary STL file.
        
    Returns:
        Dict: A dictionary containing NumPy arrays for 'normals', 'vertices', 
              and 'attributes' (Material IDs).
    """
    with open(filepath, 'rb') as f:
        # 1. Read the 80-byte header
        header = f.read(80)
        
        # 2. Read the 4-byte triangle count (Little-Endian Unsigned Int)
        count_bytes = f.read(4)
        if len(count_bytes) < 4:
            raise ValueError("File is too short to contain a valid STL triangle count.")
        
        num_triangles = struct.unpack('<I', count_bytes)
        
        # Pre-allocate lists (or arrays) for speed
        normals = np.zeros((num_triangles, 3), dtype=np.float32)
        vertices = np.zeros((num_triangles, 3, 3), dtype=np.float32)
        attributes = np.zeros(num_triangles, dtype=np.uint16)
        
        # The struct format: Little-endian, 12 floats, 1 unsigned short
        triangle_fmt = '<12fH'
        triangle_size = struct.calcsize(triangle_fmt) # Should be 50 bytes
        
        # 3. Read each triangle record
        for i in range(num_triangles):
            record = f.read(triangle_size)
            if len(record) < triangle_size:
                raise ValueError(f"Unexpected end of file at triangle index {i}.")
            
            # Unpack the 50 bytes
            unpacked = struct.unpack(triangle_fmt, record)
            
            # Unpacked is a tuple of 13 elements: 
            # (nx, ny, nz, v1x, v1y, v1z, v2x, v2y, v2z, v3x, v3y, v3z, attr)
            normals[i] = unpacked[0:3]
            vertices[i, 0, :] = unpacked[3:6]
            vertices[i, 1, :] = unpacked[6:9]
            vertices[i, 2, :] = unpacked[9:12]
            attributes[i] = unpacked[cite: 10]
            
    return {
        'normals': normals,
        'vertices': vertices,
        'attributes': attributes
    }

## 2. Attribute Preservation in Standard Python Libraries


A common misconception is that standard STL libraries discard the 2-byte attribute count. Because the attribute field traditionally serves no standard purpose and should be padded as zero according to strict format definitions [cite: 4], many rudimentary viewers discard it. However, high-quality analytical Python libraries intentionally preserve this exact memory structure.

## 4. Topological Extraction: Finding the Largest Connected Component


When dealing with a "triangle soup" (a list of unassociated faces), identifying isolated pieces of geometry requires building a topological graph where nodes represent triangles (faces), and edges represent shared adjacent spatial edges between these triangles.

### 4.1 The Floating-Point Vertex Pitfall

A critical pitfall in processing STLs is the raw equality comparison of floating-point values. An edge in 3D space is defined by two vertices. If Triangle A and Triangle B share an edge, those vertices must be mathematically identical to be recognized. 

However, binary STLs define coordinates in 32-bit floats (`float32`), which are accurate to approximately 7 decimal digits. During CAD exports, minute floating point truncations often cause shared vertices to differ infinitesimally (e.g., `0.1000000` vs `0.1000001`). Using exact float comparison or raw byte hashing will artificially fracture the graph.

**The Solution:** You must round the vertex coordinates to a reliable tolerance before generating a hashable key. Rounding to `5` or `6` decimal places effectively collapses microscopic gaps that represent the same spatial coordinate, while preserving millimeter-level precision for 3D printing geometries.

### 4.2 Manual Graph Construction using `collections.defaultdict`


The algorithm to locate the largest connected component manually requires:
1.  Iterating through every face.
2.  Extracting the 3 edges of the face.
3.  Rounding the vertex coordinates and creating a sorted tuple to act as an undirected edge key.
4.  Mapping that edge key to the face index using a `defaultdict`.
5.  Constructing an adjacency list where Face A is connected to Face B if they share an edge.
6.  Executing a Breadth-First Search (BFS) to group connected components.

```python
import numpy as np
from collections import defaultdict, deque
from typing import List, Set

def find_largest_component_manual(vertices: np.ndarray) -> List[int]:
    """
    Extracts the largest connected component from a triangle soup.
    
    Args:
        vertices (np.ndarray): Shape (N, 3, 3) representing triangles.
        
    Returns:
        List[int]: A list of face indices that belong to the largest connected component.
    """
    N = vertices.shape
    
    # 1. Edge-to-face mapping
    # Using a defaultdict of lists to store which face indices share an edge
    edge_to_faces = defaultdict(list)
    
    # Iterate through all faces
    for face_idx in range(N):
        v0, v1, v2 = vertices[face_idx]
        
        # Round the coordinates to 5 decimal places to prevent float32 discrepancies
        # Convert to tuple so it can be hashed in a dictionary
        tv0 = tuple(np.round(v0, decimals=5))
        tv1 = tuple(np.round(v1, decimals=5))
        tv2 = tuple(np.round(v2, decimals=5))
        
        # Extract 3 edges per face. Sort the vertices so direction doesn't matter (undirected edge)
        edges = [
            tuple(sorted([tv0, tv1])),
            tuple(sorted([tv1, tv2])),
            tuple(sorted([tv2, tv0]))
        ]
        
        for edge in edges:
            edge_to_faces[edge].append(face_idx)
            
    # 2. Build Face Adjacency Graph
    face_adjacency = defaultdict(list)
    for edge, faces in edge_to_faces.items():
        # Ideally, a valid manifold edge is shared by exactly 2 faces.
        # But we must support any number of faces sharing an edge (non-manifold geometry).
        length = len(faces)
        if length > 1:
            for i in range(length):
                for j in range(i + 1, length):
                    face_adjacency[faces[i]].append(faces[j])
                    face_adjacency[faces[j]].append(faces[i])
                    
    # 3. Find Connected Components via BFS
    visited = set()
    components = []
    
    for i in range(N):
        if i not in visited:
            # Start BFS
            queue = deque([i])
            visited.add(i)
            current_component = []
            
            while queue:
                current_face = queue.popleft()
                current_component.append(current_face)
                
                for neighbor in face_adjacency[current_face]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
                        
            components.append(current_component)
            
    # 4. Return the largest component
    if not components:
        return []
        
    largest_component = max(components, key=len)
    return largest_component
```

---

## 6. Edge Cases and Geometric Pitfalls


When executing volume calculations and component isolation on raw binary STL data, several distinct geometric flaws inherent to user-generated 3D files must be addressed.