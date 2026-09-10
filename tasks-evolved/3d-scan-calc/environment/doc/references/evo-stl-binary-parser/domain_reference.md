# Domain Reference for evo-stl-binary-parser

**Responsibility**: Read binary STL file layout (80-byte header, 4-byte count, 50-byte facet records), unpack all triangle data, and expose vertices and material IDs as structured data. Also parse the material density markdown table.

**Key functions to implement**: parse_binary_stl, parse_material_density_table, filter_facets_by_material_id, detect_material_id

---

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