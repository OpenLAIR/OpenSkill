To verify the correctness of the 3D object parsing and export process, you can use the following verification anchors and invariants. These are based on the deterministic nature of Three.js `BufferGeometry` and the Wavefront OBJ specification.

### 1. Independently Computable Reference Values
For standard Three.js primitives, the number of vertices in the `BufferGeometry` is deterministic based on the constructor parameters. You can use these to verify that your parser correctly identifies the geometry of each mesh.

*   **BoxGeometry**: For a default `BoxGeometry(1, 1, 1, 1, 1, 1)`, the geometry is non-indexed (or indexed depending on version, but typically produces 24 vertices). Each of the 6 faces is composed of 2 triangles (6 vertices per face).
    *   *Computation*: $6 \text{ faces} \times 2 \text{ triangles/face} \times 3 \text{ vertices/triangle} = 36 \text{ vertices}$ (if non-indexed).
*   **SphereGeometry**: For `SphereGeometry(radius, wS, hS)`, the number of vertices is determined by the segments.
    *   *Computation*: The number of vertices is $(wS + 1) \times (hS + 1)$.
    *   *Example*: `SphereGeometry(1, 32, 16)` produces $(32+1) \times (16+1) = 33 \times 17 = 561$ vertices.

### 2. Dataset-Level Statistical Invariants
Your output must satisfy these invariants to be considered valid:

*   **OBJ Structure**: Every generated `.obj` file must contain at least one `v` (vertex) line and one `f` (face) line.
*   **Completeness**: The number of unique `part_name` directories in `/root/output/part_meshes/` must match the number of `THREE.Group` or top-level `Object3D` entities identified in the `createScene()` function.
*   **Index Range**: In the OBJ files, all indices in `f` lines must be within the range `[1, N]`, where `N` is the total number of `v` lines in that specific file.
*   **File Count**: The number of `.obj` files in `/root/output/links/` must equal the number of distinct parts identified in the scene graph.

### 3. Cross-Validation Approaches
You can independently verify the OBJ output using standard command-line tools:

*   **OBJ Validation**: Use a simple Python script to validate the OBJ structure.
    ```python
    def validate_obj(filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()
            vertices = [l for l in lines if l.startswith('v ')]
            faces = [l for l in lines if l.startswith('f ')]
            assert len(vertices) > 0, f"No vertices found in {filepath}"
            assert len(faces) > 0, f"No faces found in {filepath}"
            # Check face indices
            for face in faces:
                indices = [int(i.split('/')[0]) for i in face.split()[1:]]
                for idx in indices:
                    assert 1 <= idx <= len(vertices), f"Index {idx} out of range"
    ```
*   **Geometry Comparison**: Use `trimesh` (a Python library) to load the exported OBJ and compare its vertex count/bounding box against the expected values derived from the Three.js parameters.

### 4. Benchmarks and Reference Implementations
*   **Wavefront OBJ Specification**: Refer to the [official OBJ format documentation](https://paulbourke.net/dataformats/obj/) for the definitive structure of `v`, `vn`, `vt`, and `f` records.
*   **Three.js Source**: The `OBJExporter.js` source code in the Three.js repository is the ultimate reference for how `Object3D` hierarchies are traversed and serialized. If your output deviates from the structure produced by `exporter.parse(scene)`, it is likely incorrect.