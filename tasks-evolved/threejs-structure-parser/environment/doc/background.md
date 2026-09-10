# Comprehensive Technical Research Document: Three.js Scene Parsing and OBJ Export in Headless Node.js Environments

**Executive Summary**
*   **Three.js Environment:** Executing Three.js v0.170.0 in a headless Node.js environment requires configuring ES modules and occasionally providing global browser polyfills (e.g., `window`, `self`) [cite: 1, 2]. WebGL is not required for scene graph manipulation or geometric math.
*   **Geometry Paradigm:** The legacy `Geometry` class has been entirely removed in modern versions; all primitive geometries now inherit from `BufferGeometry`, storing data in highly optimized TypedArrays (e.g., `Float32Array`) [cite: 3]. 
*   **Matrix Transformations:** Accurately exporting Wavefront OBJ files necessitates a firm understanding of the difference between local transformations (`.matrix`) and world transformations (`.matrixWorld`). Developers must explicitly invoke `.updateMatrixWorld(true)` to ensure the hierarchy's absolute spatial coordinates are resolved before serialization [cite: 4, 5].
*   **Data Serialization:** The `OBJExporter` addon natively traverses `Object3D` hierarchies and outputs string-based Wavefront OBJ data [cite: 6]. However, when precise part-by-part decomposition is required, combining custom scene graph traversal algorithms with `BufferGeometryUtils.mergeGeometries` provides granular control over output assemblies [cite: 7, 8].
*   **Python/Node Integration:** Using Python's `subprocess` module to orchestrate Node.js scripts facilitates a robust pipeline where Python handles high-level agent logic while Node.js leverages the native Three.js ecosystem. IPC (Inter-Process Communication) is best handled via JSON over `stdout`.

---

## 1. Three.js Scene Graph and Primitive Geometries (v0.170.0)

In Three.js v0.170.0, the scene graph is a directed acyclic graph (DAG) where nodes are instances of `THREE.Object3D` or its derivations (such as `THREE.Mesh`, `THREE.Group`, and `THREE.Scene`). The mathematical foundation relies on a right-handed coordinate system. 

### 1.1 Primitive Geometry API and Constructor Signatures

Three.js provides a vast array of primitive geometries, each encapsulating a specific mathematical shape converted into a `BufferGeometry` [cite: 9]. Below is the exhaustive API signature for the requested geometries commonly utilized in procedural `createScene()` patterns.

**1. `THREE.BoxGeometry`**
Constructs a rectangular cuboid.
*   `constructor(width : Float, height : Float, depth : Float, widthSegments : Integer, heightSegments : Integer, depthSegments : Integer)`
*   *Defaults*: `width` (1), `height` (1), `depth` (1), `widthSegments` (1), `heightSegments` (1), `depthSegments` (1) [cite: 10, 11].

**2. `THREE.SphereGeometry`**
Constructs a sphere utilizing sweeping and calculating vertices around the Y (horizontal) and Z (vertical) axes.
*   `constructor(radius : Float, widthSegments : Integer, heightSegments : Integer, phiStart : Float, phiLength : Float, thetaStart : Float, thetaLength : Float)`
*   *Defaults*: `radius` (1), `widthSegments` (32), `heightSegments` (16), `phiStart` (0), `phiLength` (Math.PI * 2), `thetaStart` (0), `thetaLength` (Math.PI) [cite: 12, 13].

**3. `THREE.CylinderGeometry`**
Constructs a cylinder or cone-like shape if one radius is zero.
*   `constructor(radiusTop : Float, radiusBottom : Float, height : Float, radialSegments : Integer, heightSegments : Integer, openEnded : Boolean, thetaStart : Float, thetaLength : Float)`
*   *Defaults*: `radiusTop` (1), `radiusBottom` (1), `height` (1), `radialSegments` (32), `heightSegments` (1), `openEnded` (false), `thetaStart` (0), `thetaLength` (Math.PI * 2) [cite: 14, 15].

**4. `THREE.ConeGeometry`**
A specialized implementation of `CylinderGeometry` where the top radius is strictly 0.
*   `constructor(radius : Float, height : Float, radialSegments : Integer, heightSegments : Integer, openEnded : Boolean, thetaStart : Float, thetaLength : Float)`
*   *Defaults*: `radius` (1), `height` (1), `radialSegments` (32), `heightSegments` (1), `openEnded` (false), `thetaStart` (0), `thetaLength` (Math.PI * 2).

**5. `THREE.PlaneGeometry`**
Constructs a two-dimensional rectangular plane resting on the X-Y axes.
*   `constructor(width : Float, height : Float, widthSegments : Integer, heightSegments : Integer)`
*   *Defaults*: `width` (1), `height` (1), `widthSegments` (1), `heightSegments` (1) [cite: 16].

**6. `THREE.TorusGeometry`**
Constructs a torus (donut shape).
*   `constructor(radius : Float, tube : Float, radialSegments : Integer, tubularSegments : Integer, arc : Float)`
*   *Defaults*: `radius` (1), `tube` (0.4), `radialSegments` (12), `tubularSegments` (48), `arc` (Math.PI * 2).

**7. `THREE.CircleGeometry`**
Constructs a simple flat 2D polygon with high enough segments to approximate a circle.
*   `constructor(radius : Float, segments : Integer, thetaStart : Float, thetaLength : Float)`
*   *Defaults*: `radius` (1), `segments` (32), `thetaStart` (0), `thetaLength` (Math.PI * 2).

**8. `THREE.TetrahedronGeometry`**
Constructs a polyhedron with 4 triangular faces.
*   `constructor(radius : Float, detail : Integer)`
*   *Defaults*: `radius` (1), `detail` (0). Detail > 0 subdivides the faces, making it closer to a sphere.

**9. `THREE.IcosahedronGeometry`**
Constructs a polyhedron with 20 equilateral triangular faces.
*   `constructor(radius : Float, detail : Integer)`
*   *Defaults*: `radius` (1), `detail` (0).

**10. `THREE.DodecahedronGeometry`**
Constructs a polyhedron with 12 flat faces.
*   `constructor(radius : Float, detail : Integer)`
*   *Defaults*: `radius` (1), `detail` (0).

**11. `THREE.OctahedronGeometry`**
Constructs a polyhedron with 8 faces.
*   `constructor(radius : Float, detail : Integer)`
*   *Defaults*: `radius` (1), `detail` (0).

**12. `THREE.RingGeometry`**
Constructs a 2D ring (a disk with a hole).
*   `constructor(innerRadius : Float, outerRadius : Float, thetaSegments : Integer, phiSegments : Integer, thetaStart : Float, thetaLength : Float)`
*   *Defaults*: `innerRadius` (0.5), `outerRadius` (1), `thetaSegments` (32), `phiSegments` (1), `thetaStart` (0), `thetaLength` (Math.PI * 2).

**13. `THREE.CapsuleGeometry`**
Constructs a capsule shape by joining two hemispheres to a cylinder.
*   `constructor(radius : Float, length : Float, capSegments : Integer, radialSegments : Integer)`
*   *Defaults*: `radius` (1), `length` (1), `capSegments` (4), `radialSegments` (8) [cite: 17, 18].

**14. `THREE.LatheGeometry`**
Constructs a shape generated by revolving an array of `Vector2` points around the Y-axis.
*   `constructor(points : Array, segments : Integer, phiStart : Float, phiLength : Float)`
*   *Defaults*: `points` (required array of Vector2), `segments` (12), `phiStart` (0), `phiLength` (Math.PI * 2).

**15. `THREE.TorusKnotGeometry`**
Constructs a complex, self-intersecting knot shape based on coprime integers.
*   `constructor(radius : Float, tube : Float, tubularSegments : Integer, radialSegments : Integer, p : Integer, q : Integer)`
*   *Defaults*: `radius` (1), `tube` (0.4), `tubularSegments` (64), `radialSegments` (8), `p` (2), `q` (3) [cite: 19, 20].

### 1.2 Hierarchy, Transform Theory, and `Object3D` Properties

The `THREE.Object3D` class acts as the foundational entity of the spatial hierarchy [cite: 21]. 
*   **`.children` and `.parent`**: Each `Object3D` maintains an array of `.children`. Setting object hierarchies is performed via `.add(child)`, which automatically sets the child's `.parent` to the caller, removing it from its previous parent.
*   **`.name` and `.type`**: `.name` is an arbitrary string crucial for extracting part assemblies (e.g., identifying a semantic "Engine Block" group). `.type` returns a string literal (e.g., `"Mesh"`, `"Group"`). Type checking is optimally performed using boolean flags: `.isMesh` or `.isGroup`.
*   **Local Spatial Vectors**: Transformation states are maintained via three isolated properties in local object space:
    *   `.position` (`THREE.Vector3`)
    *   `.scale` (`THREE.Vector3`)
    *   `.quaternion` (`THREE.Quaternion`)
*   **`.rotation`**: An instance of `THREE.Euler`. Three.js seamlessly synchronizes the `.rotation` Euler angles and the `.quaternion` under the hood. Manipulating one automatically updates the other [cite: 22].

### 1.3 `updateMatrixWorld` vs `updateWorldMatrix`

The local coordinates describe the object relative to its parent. To map this into absolute global space, Three.js uses matrix multiplication, storing the result in `.matrixWorld` [cite: 4, 5].

1.  **`.updateMatrix()`**: Merely combines `.position`, `.quaternion`, and `.scale` into a 4x4 matrix, storing it in the local `.matrix` variable.
2.  **`.updateMatrixWorld(force)`**: Extremely vital for data extraction pipelines. It cascades down the entire hierarchy starting from the caller [cite: 4]. It evaluates the parent's `.matrixWorld`, multiplies it by the current object's `.matrix`, sets the current object's `.matrixWorld`, and then recursively calls `.updateMatrixWorld()` on all descendants [cite: 4, 5]. The `force` parameter guarantees recalculation even if the caching system flag `.matrixWorldNeedsUpdate` is false [cite: 4].
3.  **`.updateWorldMatrix(updateParents, updateChildren)`**: Provides granular control. If an object deep in a complex hierarchy moved, calling `.updateWorldMatrix(true, false)` climbs the tree updating parents to ensure the lineage is correct, without paying the performance tax of recursing down parallel, unaffected child branches [cite: 4, 23].

### 1.4 Traversal Algorithms

To parse the graph, developers utilize:
*   `.traverse(callback)`: Executes a depth-first search through the object and its descendants [cite: 4]. 
*   `.traverseVisible(callback)`: Identical, but short-circuits evaluation on branches where a node's `.visible === false` [cite: 4].

When building the Python-interfacing skill, using `.traverse()` allows the parser to identify subsets of the tree by reading `node.isGroup` or `node.isMesh`.

---

## 2. Mesh Geometry Internals

In modern Three.js, geometry data bypasses JavaScript's object overhead by utilizing flat, strictly typed memory allocations exposed to WebGL.

### 2.1 The Architecture of `BufferGeometry`

A `BufferGeometry` instance stores vertex data inside `THREE.BufferAttribute` instances.
*   **`.attributes.position`**: A `Float32BufferAttribute`. Contains the X, Y, Z coordinates linearly flat-packed. Vertex 0 is `[array, array[cite: 6], array[cite: 24]]`. To access the raw data, use `geometry.attributes.position.array`, which yields a standard `Float32Array`.
*   **`.attributes.normal`**: Stores normalized vectors representing face or vertex direction, crucial for lighting and OBJ `vn` exports.
*   **`.attributes.uv`**: Stores 2D texture coordinates mapped to vertices.

**Indexed vs. Non-Indexed Geometries**: 
In a non-indexed geometry, rendering a quad requires 6 distinct vertices in the position array. In an indexed geometry, `geometry.index` (a `Uint16Array` or `Uint32Array`) is provided. This array stores pointers back into the `position` array, reducing memory duplication by allowing vertices to be shared among adjacent faces [cite: 25].

### 2.2 Applying Matrices Directly to Vertices

By default, the vertices of a primitive (like a Box) are centered at `(0,0,0)` in local space. If the `Mesh` is scaled and moved, the `BufferGeometry` memory remains untouched; the hardware GPU applies the `matrixWorld` during rendering.

However, when exporting an OBJ for downstream processing in an absolute coordinate system, local transforms must be "baked" into the vertices.
```javascript
mesh.updateMatrixWorld(true);
mesh.geometry.applyMatrix4(mesh.matrixWorld);
mesh.position.set(0,0,0);
mesh.rotation.set(0,0,0);
mesh.scale.set(1,1,1);
mesh.updateMatrixWorld(true);
```
Using `geometry.applyMatrix4(object.matrixWorld)` mutates the `Float32Array` values natively [cite: 5, 26]. It computes the dot product of the transformation matrix against every vector. Notably, it also updates the normals via the inverse-transpose of the given matrix to ensure they remain perpendicular to the scaled/rotated faces.

### 2.3 Merging BufferGeometries via `BufferGeometryUtils`

Exporting hundreds of individual meshes is inefficient. `BufferGeometryUtils.mergeGeometries` combines an array of geometries into a single monolithic `BufferGeometry` [cite: 7, 25].

*   **API Transition**: Prior to r150, this was named `mergeBufferGeometries`. In v0.170.0, it is strictly `mergeGeometries` [cite: 3, 8].
*   **Location**: `import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';` [cite: 7, 25].
*   **Parameter Signature**: `mergeGeometries( geometries : Array<BufferGeometry>, useGroups : boolean ) : BufferGeometry | null` [cite: 7, 25].
*   **Strict Constraints**: The merging operation will return `null` and throw a console error if the array mixes indexed and non-indexed geometries [cite: 25]. To safely merge, the developer must standardize the array. Usually, converting indexed geometries to non-indexed is required via `geometry.toNonIndexed()`. Furthermore, all geometries must share the exact same attributes (e.g., if one geometry lacks an `.attributes.uv`, the merge will fail) [cite: 25].

---

## 3. OBJ Export from Three.js

The Wavefront OBJ format remains the universal lingua franca for 3D data portability. Three.js provides `OBJExporter`.

### 3.1 The `OBJExporter` API (v0.170.0)

*   **Location**: `import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';` [cite: 6].
*   **Usage**: 
    ```javascript
    const exporter = new OBJExporter();
    const objString = exporter.parse( object3D );
    ```
*   **Behavior**: When `parse(object)` is called, it recursively searches the hierarchy of the target object. It gathers every active `Mesh` and serializes it. If a root `Scene` or `Group` containing 10 meshes is passed, the resulting string will contain all vertices and faces grouped into a single OBJ file [cite: 6].
*   **World Transformations**: `OBJExporter` internally iterates through the `BufferAttribute` arrays. It applies the respective `mesh.matrixWorld` mathematically to the string generation, writing absolute coordinates to the string [cite: 26]. As such, it is *mandatory* that `mesh.updateMatrixWorld(true)` is executed prior to calling `.parse()` so that the matrices are current [cite: 5, 27].
*   **Materials**: `OBJExporter` only handles geometry. It will not write a `.mtl` file or apply color data [cite: 6]. Some iterations of Three.js loaders/exporters throw warnings if `mesh.material` is undefined, so providing a default `new THREE.MeshBasicMaterial()` during procedural generation is a safe fallback [cite: 28].

### 3.2 Alternative: Manual BufferGeometry Parsing

If `OBJExporter`'s aggregation behavior is undesirable, writing a manual exporter from a `BufferGeometry` is straightforward.

1.  Read `const pos = geometry.attributes.position.array;`
2.  Iterate `i` from `0` to `pos.length`, printing `v ${pos[i]} ${pos[i+1]} ${pos[i+2]}`.
3.  If `geometry.index` is present, read the indices and print 1-indexed faces: `f ${i1 + 1} ${i2 + 1} ${i3 + 1}`.
4.  If not indexed, face indices simply increment sequentially: `f 1 2 3`, `f 4 5 6`.

*Note: OBJ files are 1-indexed. Index 0 in Javascript equates to 1 in OBJ semantics.*

---

## 4. Executing Three.js Code from a Headless Node.js Environment

A critical operational challenge for the AI coding agent is orchestrating browser-native JavaScript in Node.js.

### 4.1 Headless Execution Feasibility

The core geometric and math libraries of Three.js do not rely on WebGL [cite: 1, 2]. `WebGLRenderer` requires a canvas, but evaluating `createScene()`, manipulating `Vector3`, applying matrices, and generating string exports via `OBJExporter` functions purely in V8/Node CPU memory space without windowing libraries like `puppeteer` or `jsdom`.

### 4.2 Handling ESM and "exports" Maps

Three.js v0.170.0 is packaged strictly as an ES Module. Its `package.json` includes `"type": "module"` and utilizes an `"exports"` field to enforce module resolution [cite: 29]. 

In legacy Node/Three environments, one could arbitrarily import deep file paths. In v0.170.0, the `exports` map defines exactly what can be imported.
```json
"exports": {
    ".": { "import": "./build/three.module.js", "require": "./build/three.cjs" },
    "./examples/jsm/*": "./examples/jsm/*",
    "./addons/*": "./examples/jsm/*"
}
```
Consequently, in a Node.js script, imports must match these constraints:
```javascript
import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
```

### 4.3 Polyfills for Browser Globals

Some of the legacy add-ons in `examples/jsm` reference browser-specific globals implicitly. To safeguard the headless script, inject lightweight polyfills at the absolute top of the Node entry file:
```javascript
if (typeof global.self === 'undefined') {
    global.self = global;
}
if (typeof global.window === 'undefined') {
    global.window = global;
}
```
If using older Node versions (pre-Node 18), importing `TextEncoder` and `TextDecoder` from the `util` module to the global scope might be necessary, though modern Node 20/22 natively includes them.

### 4.4 Evaluating the Target `object.js`

To evaluate the dynamic file produced by the AI, use the dynamic `import()` function.
```javascript
const targetModulePath = path.resolve(process.argv[cite: 24]);
// Convert to file:// URL to ensure Node ESM correctly resolves absolute Windows/Linux paths
const fileUrl = pathToFileURL(targetModulePath).href; 
const userModule = await import(fileUrl);
const scene = userModule.createScene();
```

---

## 5. Parsing Strategy for Extracting Part Structure

When the `createScene()` function returns a root `THREE.Group` or `THREE.Scene`, the utility must isolate the distinct assemblies.

### 5.1 Heuristics for Part Identification

In mechanical or hierarchical 3D object representation, assemblies are defined using `THREE.Group`. 

**The Parsing Rule Set:**
1.  **Iterate the Top Level**: Traverse the immediate children of the root (`root.children`).
2.  **Groups are Assemblies**: If a child is a `THREE.Group` (i.e., `child.isGroup`), it represents a complex part composed of multiple sub-meshes. Its entire descendant tree of meshes should be collected, matrices resolved, geometries merged, and exported as a single `[part_name].obj`.
3.  **Standalone Meshes are Parts**: If a top-level child is a `THREE.Mesh` (i.e., `child.isMesh`), it is an individual, distinct part. It should be exported as its own `[part_name].obj`.
4.  **Ignore Non-Geometry Nodes**: Nodes such as `THREE.Camera`, `THREE.Light`, or helpers are ignored.
5.  **Naming Fallback**: If a part lacks a `.name` property, generate a deterministic name: `UnnamedGroup_${index}` or `UnnamedMesh_${index}`.

### 5.2 Nested Hierarchies

If a `Group` contains nested `Group`s, deciding whether to flatten or recurse depends on the export requirement. For exporting "parts", the most standard approach is to treat the top-level semantic `Group` as the boundary. Any deeper meshes and subgroups are simply visual components that constitute that single top-level "Part". Thus, utilizing `BufferGeometryUtils.mergeGeometries` to collapse the entire nested tree of a top-level Group into one solid Mesh prior to `OBJExporter` is the optimal strategy.

---

## 6. Recommended Implementation Approach for the Skill

Because the Python AI skill operates outside of V8, establishing Inter-Process Communication (IPC) is required.

### 6.1 The Invocation Pattern

1.  **Python Preparation**: The Python skill dynamically authors a Node.js harness script (e.g., `headless_parser.mjs`) to disk.
2.  **Execution**: Python uses `subprocess.run` to spawn Node.js.
    ```python
    import subprocess, json
    
    cmd = ['node', 'headless_parser.mjs', 'user_scene.js', './output_dir']
    result = subprocess.run(cmd, capture_output=True, text=True)
    ```
3.  **Data Exchange**: The Node.js script outputs standard console warnings to `stderr`, but reserves `stdout` exclusively for a final JSON payload.
    ```javascript
    // At the end of the Node script
    const metadata = { status: "success", parts: exportedPartsList };
    console.log(JSON.stringify(metadata));
    ```
4.  **Python Harvesting**: Python reads `result.stdout`, parses the JSON, and acknowledges the successful disk writes of the OBJ files to the AI agent.

### 6.2 Error Interception

Because the target `createScene()` script is AI-generated, it may contain syntax errors or invalid API calls (e.g., passing a string to `applyMatrix4`). The Node script must wrap the `import()` and parsing logic in a `try...catch` block. If an error is caught, the Node script outputs `{"status": "error", "message": e.message}` to stdout and exits with code 1, allowing Python to gracefully alert the agent.

---

## 7. OBJ File Format Specifics

When validating the outputs generated by `OBJExporter` or a custom parser, the Wavefront OBJ specification must be strictly understood.

### 7.1 Format Architecture

*   **`v x y z`**: Defines a geometric vertex in space.
*   **`vn i j k`**: Defines a vertex normal vector.
*   **`vt u v`**: Defines a vertex texture coordinate.
*   **`f v1/vt1/vn1 v2/vt2/vn2 v3/vt3/vn3`**: Defines a polygonal face. The indices point to the order the `v`, `vt`, and `vn` definitions appeared in the file. **Indices start at 1, not 0.**

### 7.2 World vs. Local Space coordinates

When exporting a decomposed hierarchy, exporting local-space parts implies that their coordinates are centered at the origin, and re-assembly would require an accompanying metadata JSON specifying the translations and rotations.

Conversely, exporting **world-space** parts (by invoking `updateMatrixWorld(true)`) bakes the transforms into the vertices. If the generated OBJ files are loaded together in an external CAD software or viewer, they will immediately snap into the correct assembled position. This is the overwhelmingly preferred behavior for modular extraction. `OBJExporter` accomplishes this naturally when `.parse()` is used on properly updated objects.

### 7.3 Pitfalls in Serialization

*   **Missing trailing newline**: Some strict external parsers fail to read the last face if the file does not end with `\n`. `OBJExporter` appends this correctly.
*   **Indices Mismatch**: Mixing lines with `f v1 v2 v3` and `f v1//vn1 v2//vn2 v3//vn3` can break some engines.

---

## 8. Known Pitfalls and Version-Specific Notes for Three.js 0.170.0

A skill designed for Three.js v0.170.0 must account for recent breaking changes within the library's evolution [cite: 3, 8].

1.  **`Geometry` Class Removal**: Historically, developers utilized `THREE.Geometry` (which allowed arbitrary pushing to `.vertices` arrays). This was entirely removed around r125. Agents attempting to instantiate `new THREE.Geometry()` or `new THREE.Face3()` will cause fatal errors [cite: 3]. The skill must enforce `BufferGeometry`.
2.  **`mergeBufferGeometries` Renaming**: In r150, `mergeBufferGeometries` was renamed to `mergeGeometries` [cite: 3, 8]. AI agents trained on older data frequently hallucinate the old import path and function name. 
3.  **Color Space Revisions**: In r150+, `THREE.ColorManagement.enabled` defaults to `true`, and `sRGBEncoding` has transitioned to `SRGBColorSpace` [cite: 8]. While purely visual, if the skill attempts to extract color parameters, this shift is pertinent.
4.  **Implicit World Updates**: `WebGLRenderer` traditionally calls `scene.updateMatrixWorld()` before rendering. Because the headless utility omits the renderer entirely, the script *must* explicitly call `updateMatrixWorld(true)` on the root object before traversal or export [cite: 5].

---

## 9. Comprehensive Node.js Code Snippets

Below is the complete, robust Node.js implementation script tailored for the Python orchestration model. It dynamically loads a scene, categorizes parts, forces world matrix calculations, homogenizes and merges buffer geometries, and exports Wavefront OBJs.

**File: `three_parser_utils.mjs`**

```javascript
// Polyfills for Headless Node.js execution of Three.js Addons
if (typeof global.self === 'undefined') global.self = global;
if (typeof global.window === 'undefined') global.window = global;
if (typeof global.document === 'undefined') global.document = { createElement: () => ({}) };

import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import fs from 'fs/promises';
import path from 'path';
import { pathToFileURL } from 'url';

/**
 * Ensures all geometries in an array are non-indexed.
 * This is critical because mergeGeometries will fail if mixing indexed/non-indexed.
 */
function standardizeGeometries(geometries) {
    return geometries.map(geom => {
        // Clone to prevent mutating original scene assets
        let processed = geom.clone();
        if (processed.index !== null) {
            processed = processed.toNonIndexed();
        }
        return processed;
    });
}

/**
 * Extracts distinct "parts" from the scene root and serializes them to OBJ.
 */
async function extractAndExport(targetScriptPath, outputDirectory) {
    try {
        // Ensure output directory exists
        await fs.mkdir(outputDirectory, { recursive: true });

        // 1. Load the AI-generated User Module
        const scriptUrl = pathToFileURL(path.resolve(targetScriptPath)).href;
        const userModule = await import(scriptUrl);
        
        if (typeof userModule.createScene !== 'function') {
            throw new Error("Target file does not export a 'createScene' function.");
        }

        const rootObject = userModule.createScene();
        
        // 2. Force evaluate all global transforms locally (Mandatory in Headless)
        rootObject.updateMatrixWorld(true);

        const exportedParts = [];
        const exporter = new OBJExporter();

        // 3. Traverse immediate children to classify parts
        const topLevelChildren = [...rootObject.children];

        for (let i = 0; i < topLevelChildren.length; i++) {
            const node = topLevelChildren[i];
            const partName = node.name || `${node.type}_Part_${i}`;
            const fileName = `${partName.replace(/\s+/g, '_')}.obj`;
            const filePath = path.join(outputDirectory, fileName);

            let objData = "";

            if (node.isGroup) {
                // PART CATEGORY A: Group Assemblies
                // We want to combine all nested meshes into a single solid part geometry.
                const geometriesToMerge = [];
                
                node.traverseVisible((child) => {
                    if (child.isMesh && child.geometry) {
                        // Apply world matrix directly to geometry to freeze global position
                        const clonedGeom = child.geometry.clone();
                        clonedGeom.applyMatrix4(child.matrixWorld);
                        geometriesToMerge.push(clonedGeom);
                    }
                });

                if (geometriesToMerge.length > 0) {
                    const standardized = standardizeGeometries(geometriesToMerge);
                    const mergedGeom = mergeGeometries(standardized, false);
                    
                    if (!mergedGeom) {
                        throw new Error(`mergeGeometries failed for Group: ${partName}. Check attribute compatibility.`);
                    }

                    // Create a dummy mesh for the exporter
                    const mergedMesh = new THREE.Mesh(mergedGeom, new THREE.MeshBasicMaterial());
                    // Since vertices are already mapped to world space, prevent double-transform
                    mergedMesh.position.set(0, 0, 0);
                    mergedMesh.rotation.set(0, 0, 0);
                    mergedMesh.scale.set(1, 1, 1);
                    mergedMesh.updateMatrixWorld(true);

                    objData = exporter.parse(mergedMesh);
                }
                
            } else if (node.isMesh) {
                // PART CATEGORY B: Standalone Meshes
                // Export it directly since OBJExporter factors in mesh.matrixWorld
                objData = exporter.parse(node);
            }

            if (objData) {
                await fs.writeFile(filePath, objData, 'utf-8');
                exportedParts.push({
                    name: partName,
                    type: node.type,
                    file: filePath
                });
            }
        }

        // 4. Output structured metadata as JSON to stdout for Python consumption
        console.log(JSON.stringify({
            status: "success",
            extractedCount: exportedParts.length,
            parts: exportedParts
        }));

    } catch (error) {
        // Output deterministic error JSON for Python to catch
        console.log(JSON.stringify({
            status: "error",
            message: error.message,
            stack: error.stack
        }));
        process.exit(1);
    }
}

// CLI Execution entry point: node three_parser_utils.mjs <target_script> <output_dir>
const args = process.argv.slice(2);
if (args.length < 2) {
    console.error("Usage: node three_parser_utils.mjs <scene_script.js> <output_dir>");
    process.exit(1);
}

extractAndExport(args, args[cite: 6]);
```

**Sources:**
1. [infoq.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5ilEWBvv7otynpJVloUBF4H0rTr0vG5mWeWd9Brh8HXGUUen_WIfSnYDGwL1EgEVOcvjqCsN032gG4e0o9JEFMq5fhqe5j8bm9w9EXIIQliIWXhEd5nTFWGFVf7FIzif6Hjtqh6HNvUP1w_lUwYln1ZwSZJ3osQ==)
2. [npmjs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBXDj7pJ1tlQT42DuYs28dEn-1UGg7QWpG8F8vSGKBHyfSVLwaVnHbMGMrVrlxYyZqZrCNnvFRzKI7OcjmqAn4j8BTwh6Ra2Nhf6MHwAsa8fJ9_8lToAzYBW9CYU09gIExXOhMeCX0_Zul5A==)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6NRzCkl6UwK4yUG4HrdEhQZjqS61Pv_vMODu6htHgiBy0CDVIM_DMGlK87LJCgG0wWd5lQ9SHSc-UjQVsMjOXNb8-m0Ffe9Uy67cxBIhbunzLBq33cecohDz91OZXN0zt_jNYjVN_JmjXbJvETKb72QbzjzTMASN2HLkbWGjdPeWPj8P0petWt63ImTPjAAii9W2sk28=)
4. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG879m3xsddSrwEkkPtjFYbHV-WNG3q-UjJlhqDQh1eAMkbgvSqAyYrtxUj9m5NGOXcWFs2xrfDPCk3-mBB8RVb6HIz0HhyhEujECn3Oc20kigrPvxBz1o-7j3xDB6_I9P6WCMug81GXuplpQ4U9K7OA2ZzZG0Q)
5. [jamesyap.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEkI39xLucPfaSiLolN6gkKy_CBW2Bo4rKa4sgE4MylQL2MAayvjXs9YO3jmZxA_wZx0ttQDJV8LOOLAevkuwZFpFqnuwy1iKpZW8uOJVL0z9RZPTCE4YrMGybQvwzHD9OQrJWWPDCX7GiJ-5XjwgGgYIcUlA==)
6. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEToDhIpOxeGhqzmZrZk_SyHmG9kTZARwehrSfx1FauYZf-GXaGRVGGkAiqI7p21SlldrFL6BT-YQvSprIa0U97Ytkp86pwu-txJlloPsky5FpLjWGErYGSwBBzKJCC6jnbJFEkkA==)
7. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFA6TC6lPWEQBaxobyVMqQ-EA_KfkQFOSEPWyl3WQmo3Icdb6EGs1q3dddPUnE40MvJpAdLwfZRN4kd6P36zACLrSUUCJvOSyElYs-bPy4JtVTZ4bBMzLmNM3QKDgVHFTE-viHRmiYuLgL4znHGGrfslEcb6w==)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXDaflHLaaZoEd1FAtbvYtKbcSp0TyPTswJo9P0_6Tlae8SWkV6nVA8GQAsiqu8RJ2PS1zmEfmhKAzVASBs3h5H2mgYjBPmm8o3coPDPn08e8QIjlyaak6jBAQ_VmfS5ScJQHb7WGFDlZmWzu4)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEn3F9m7KNk5X0CukLeB7DRhPjyZd6UhPYN0iPg5Uyxl1RG5CS-sqgQT9yWTWBtSYW0kK3J9wVS9Y69mzw6hgnGUmLkwz7TbD8Y6AM2VoOfwBdVt-sdwqcXCA6ms5VPR8-lplzXTlOoloKrx3EXlHAk)
10. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEu4QMmeGgd6H6aiMFRbv8DCLnHOPKEqACGeZItGr5lSbMao6X2ni0Juw4cOE3gEcBokZf04g2DbRLa2iF-38t59n-fGmNwRcbm9Jde6MJGVgKF4HksA7Lst8ruBwDL35xcyn1f3g==)
11. [documentation.help](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHtcJnPj5PHOz0KssPOvFN2nmTQD3NdjGy-q2bfdN7I_QKhkIWXHl1XfcZswOEqv7hP25XplPzhC9tzMWr_7bBhJ4y79zO5x4nHsdyiInXKBPQJJvRL4pV1hvCDPcAJpvR3J65MkYXkLwUFgg==)
12. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH5cxp33sDt82W9YzOm6l6FGZh0ifqBHStUh-dmquYHwDtDvpF91cL4EqfCC-yF7e1Szg8qdoYexY_I4e5WDOM0gMPeif6vBW1RtBXR8PEfmrtGnGi2i88lLWoi04oiohwxmVAveiWYDw==)
13. [soft8soft.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGZcHP7xK3w717mIXayzi4rK0GoVSESxB3ZS9m4eO0aKyS8EVISQZtDprkUh01OMX9TxvczqEQ-mxmi27gi_lSaxObXlRiTxaZjQFmcjVumjdPII8n4l_URJ6kyuEkPDC6rxhxGJJHvicF_zGktC8LOGjVPTjhys6LHAw==)
14. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEkqM_p8vzccbOZvqXtSEo18iTEJ_abV3Z2qUvWQfGsKeb5_3kPuK6GdtO2N2LKGNJI--a3pQ2CLysKHeQJ6JkNncCtHLC2fcozBeEzESAYW-sQk8_s_VALtaBhBUVvZfGZLhFoQKiHRL9f)
15. [soft8soft.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHY0PmpSsBbc_1CylnVFajzuDaYw2SvX_PUGMF-9vg7YmNTVqg1ZCTXs4J_tnPjNVUsrzcW0EFp67PtOAJUiyOT6DTPSxAASfg7Hdy4OnGGZ1NkCBS8KutpRBVHDbskgguq-c7_qP0DmCvbS-oZ2ZAqzaYnbQ8u_L0i9Zur)
16. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJZkpl12qDRzK3YSWm72wn4iHT1y7rDlzrlp-HquhwiVOYM8HwrThs57SZuDRvoES0su3dnscDvdKERlsnx5CoNbaE07HCwfPynjBrfNTIuCx5yp2CGboEcQaNF81CihwJomJzJ_Yx)
17. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAwAUS-gD4roJd2j7vU6YDxUwp7Jbkslus4Od_U-t9U3n0NM4yyoveCy2scz3Pc-BeUuGFIHvzLkQ3gj1BqjVdg1e6RvSjICdQEpaOLzFHbKvzLsE0ZJ62swRzyNstCBM4-AK7tyLYYJ4=)
18. [soft8soft.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHo31X2wa0GoPL-5oPnzqL9NZrqEvNcV8TYj6uiUQA4rSNFBnZQRTN_cPT7x1zsN9YTpjQvtFSJW1l72GA7hxEkDmeX2bpHlnBToER9Ir3Rc2F3-KRyZl84MLwz8FFPYcLvDDJuFQZkrzQRFMbZ1lYj2XsJCZG_okeXgaY=)
19. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5YlV9iRgcVzWncqO_9PANBq68pfyrpcY2T0IXrnJ5egV8SaM08JcBYNh-cgMRr2datsdPpXLVRzdY1A7TPPH-h1cUSngRjErmNOloPWjKi-ZPgAoesHtlzYbHiCRanrxYn9xvBx7ECYaw3w==)
20. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZvLnJ9W7MWz-tHJp72CPg6VFA6sQDRAP2WUF_tElgbxtcEFk0cgZ9TSwLjQo46Yzr5jgdAUZ2yga_I7nR8uoPXD_iJ3MgrfhlU6FEm2uJvC1wX131_L0QVAVoZRk-nGruLnHPoqA-mm4gSc59GVfAhLZVH9MLClRAjlA=)
21. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEk7lxyaVJGPq6pUrAIl5LxRBTL6bLTaborSiQnIVmzGx3QdFBRnR-BNDhu3X8CtF9W7Lgg6GxQ99FG2mxK-WTvdjPtKoac-Mz7SbMY3GhhsFg0xuN9roOfJL8_1tGzKYNgsAVzzN-ZWruzSD1-_Vc5)
22. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHb56Ck5NQ2MeAfdyS9_a6WCrf2BLJge1VVCTlm_5wb-opzV5-0jb23vP1PZtNw3ZXoUq7MbPk4f8E7RD0_W2bZm6YRCxPr6F7Ld-BTNzWcV9joN0R5uzYOJHS4mFQndeaz-Ydqisj6CSMY5oN9mKxu3DcWgOC2iGE4BxTAtbR7O5TA02E=)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTo_N4n_MnH-w4dXHaNTWNb7ZwzmR0QXTY8XoZplKX-BD4QY63-gOypew3xDxaUSoXFoH-ZNW8Ej7-_9rnlP04gNiwggNffbiOfgpQdITcpG-OAaM-8U4j03fnywn8a564AgH2Ow==)
24. [godotengine.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFv_64nvnJd8jI2bRkXBI3qJmeosSCyfH4lUSbv78zOUXyD-lQ82uh-MVkC07vbvsJTPyhg7fDbHlee1IoDoxFa1Spy_DWri25qCXEUzcztRT5onE-I9aSqAlsTJvK4Qtd7Jt_jJrQ=)
25. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFU98J-5CuYVcP4wEWrUv1E6eGHZqCoLTldSoo_oObNeR-3fRZjbMTMNg7Xka47goIXM7Lm6B98sfwxP15Loaa4Sl9b5zNHXZB-K9rclyi_Q10RpmFyp6NZDnoQ6MjZecPyFKoZPS6GTfxfjjRtvtRcLnNAUAmAb93qXEGltnuv6PmcGAH7UQM=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdfRc5uAct4-zXRnRQQw75jk1Z8SyIWmvexOppdiCYHduwptY7wEn9UyN-wnyOwa5tUUNzCV-jJ3mfoskNttC1yEKk9yZiL4y8W5eHGJICePVFPk3q9F6QJnYPgVhOmZuyZsm7lDtiCyEbMZSJNwqJ2Ce2w6KzXSU1kfCUnZw__wtLA0uiV2u17e79nWqt-v1PGnKhY_q1dRL2)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEIGY5o_DJXvRf1Ci7jz4v-PqxlgoGKQ17zOCGOq_aMRH_52SCVmvizRYVztzwzZ-gVdgdAkTTaKl1kyq-9UYAocBS5pW1JOBrK5rLNkXtEiZ9SuRoTcRT1RDX4sHbZWZVRN5mcFzRLSdvASjFQYEwNjVOMwSkgBS94o1oWQgmVCBj9hGLXvY0C8Q_iKQ==)
28. [juejin.cn](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwbCtOYnHWr8yLUog0iRHuhiDObiOSjsqal6pVotWm6tWQYADRUJ-o6WX2qS2kZKRfeei8SKSoOtYNREgP8G86Ik5glpUNVQKRN1NquHPyjVlgfAe81bqrManSiyjaNVw=)
29. [nearform.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE1Ztstdp4C56gpYCA5auv8u_ReK1wwYcA2xe7MS7rU16BJwDj9F06R0fHBBNeP2ZiC4KO-eUucCQOBG0QqMQTG_IAdCaVaiVW5f4v0xwFXpiPm8vZOGasZxnyIYH9Hb6WbHy4ycR2LEXStSW-7qjAExYE=)
