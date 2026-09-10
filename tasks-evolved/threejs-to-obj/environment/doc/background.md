# Programmatic Execution and Export of Three.js Geometry to Wavefront OBJ in Node.js Environments

*   Research suggests that Three.js can be effectively utilized in headless Node.js environments for programmatic 3D geometry generation and processing.
*   The `OBJExporter` addon facilitates the translation of hierarchical scene graphs into the standardized Wavefront OBJ string format.
*   Coordinate system alignments are necessary to bridge the gap between rendering frameworks (which typically utilize a Y-up axis) and digital content creation tools (which often rely on a Z-up axis).
*   It seems highly probable that world matrix recalculations must be explicitly triggered prior to export to ensure that all spatial transformations are accurately baked into the resulting output.

The programmatic generation and manipulation of 3D geometry outside of traditional browser-based rendering environments represents a highly efficient computational paradigm. By leveraging Node.js, developers can batch-process, procedurally generate, and translate 3D data without the overhead of a graphical user interface or a WebGL context. While the Three.js library was principally architected for browser-based rendering, its core mathematical modules and geometry constructors operate independently of the Document Object Model (DOM), making it highly suitable for server-side execution. 

This document explores the methodologies required to execute Three.js (specifically version 0.175.0) within a Node.js environment. The report delineates the process of importing the core library and its supplementary exporter modules, constructing complex scene hierarchies, mitigating coordinate system discrepancies, dynamically evaluating geometry modules, and finally persisting the data to the file system as a Wavefront OBJ file. Through an analysis of the underlying API mechanics and affine matrix transformations, this report provides a comprehensive blueprint for headless 3D data pipelines.

## 1. Architectural Paradigms: Three.js within Node.js (v0.175.0)

The integration of Three.js within a Node.js environment requires a robust understanding of modern ECMAScript module (ESM) resolution. Historically, executing front-end JavaScript libraries on the server presented numerous friction points, primarily due to global variable assumptions (such as `window` or `document`) and differing module formats (CommonJS versus UMD). As of Three.js version 0.175.0, the library is strictly distributed as an ES Module, which optimally aligns with modern Node.js configurations [cite: 1, 2].

To correctly initialize a project, the `package.json` file must include the `"type": "module"` directive. This ensures that Node.js interprets all `.js` files as ES Modules, enabling the native use of `import` and `export` syntax without requiring a transpilation step or a bundler. 

When importing the primary namespace of the library, the optimal syntax is:
```javascript
import * as THREE from 'three';
```
While destructuring imports (e.g., `import { Scene, Mesh, BoxGeometry } from 'three';`) is technically valid and heavily utilized in front-end applications paired with tree-shaking bundlers, importing the entire namespace via `* as THREE` is frequently preferred in scripting contexts to ensure parity with external examples and to mitigate the overhead of maintaining long import lists [cite: 1, 3]. 

**Node.js-Specific Constraints and Missing Contexts**
While the core mathematical classes (`Vector3`, `Matrix4`, `Quaternion`), geometric constructors (`BufferGeometry`, `BoxGeometry`), and structural entities (`Scene`, `Group`, `Mesh`) are entirely independent of the browser environment, certain elements of the Three.js ecosystem implicitly expect a DOM. The most prominent instances occur within specific loaders (e.g., `TextureLoader`, `GLTFLoader`), which rely on the `HTMLImageElement`, `Canvas`, or the `window.fetch` API. Furthermore, attempting to instantiate a `WebGLRenderer` in a headless Node.js context will predictably fail, as Node.js lacks an underlying WebGL context and a `document.createElement('canvas')` implementation by default [cite: 4, 5].

However, when the objective is strictly programmatic geometry generation and export via `OBJExporter`, these DOM dependencies are largely bypassed. The exporter relies exclusively on mathematical matrix traversal and string concatenation, neither of which invokes the rendering pipeline or requires the DOM [cite: 6, 7].

## 2. The OBJExporter Module: API and Internal Mechanics

The `OBJExporter` is an auxiliary module that does not reside within the core `three` package entry point. Instead, it is distributed as part of the examples/addons directory. Understanding the correct import path is paramount for successful Node.js execution.

**Import Path Resolution**
In recent iterations of Three.js (including v0.175.0), the library relies on the `three/addons/` alias to expose its supplementary modules. While older documentation might reference `three/examples/jsm/exporters/OBJExporter.js`, the standardized, modern import path defined by the package's internal resolution logic is:
```javascript
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';
```
Node.js correctly resolves this path by inspecting the `"exports"` map within the `three` package's `package.json`, securely routing the alias to the underlying `examples/jsm/` file structure without requiring browser-based import maps [cite: 8, 9].

**API Signature and Return Typology**
The `OBJExporter` class exposes a highly streamlined API interface. The primary mechanism of execution is the `parse()` method, which accepts a singular argument: an `Object3D` instance (typically a `Scene` or a `Group`). 

```javascript
const exporter = new OBJExporter();
const objDataString = exporter.parse(scene);
```
The `parse()` method operates synchronously and strictly returns a `String` containing the fully serialized Wavefront OBJ file data [cite: 6]. It is critical to note that the exporter outputs geometry data exclusively; it is incapable of exporting material properties to a supplementary `.mtl` file, nor does it support exporting vertex colors or skeletal rigging architectures [cite: 6].

**BufferGeometry and Indexing Mechanisms**
Under the hood, `OBJExporter` iteratively traverses the provided `Object3D` hierarchy. When it encounters a node where the internal boolean flag `.isMesh` is evaluated to `true`, it extracts the underlying `BufferGeometry` [cite: 7, 10]. The exporter intrinsically handles both indexed and non-indexed `BufferGeometry` instances [cite: 11]. For non-indexed geometries, it reads the sequential flat array of the `position` attribute. For indexed geometries, it references the `index` array to construct the polygonal faces, ensuring that shared vertices are appropriately mapped to the OBJ `f` (face) declarations. The exporter seamlessly handles UV coordinates (`vt` declarations) and vertex normals (`vn` declarations) if those specific attributes exist within the geometry payload [cite: 7, 11].

## 3. Geometry Instantiation and Export Compatibility

Three.js v0.175.0 supports a vast taxonomy of parametric geometric constructors, all of which are fundamentally subclasses of the base `BufferGeometry` class. The legacy `Geometry` class—which utilized array-based `Vector3` and `Face3` instances—has been entirely deprecated and removed from the core library to ensure strict adherence to modern, performant, typed-array memory architectures [cite: 2].

**Standard Constructor Compatibility**
Common parametric constructors—including `BoxGeometry`, `SphereGeometry`, `CylinderGeometry`, `TorusGeometry`, `PlaneGeometry`, `ExtrudeGeometry`, `LatheGeometry`, `TubeGeometry`, and `ShapeGeometry`—are natively compatible with `OBJExporter`. Because they instantly formulate the required `position` Float32Array attributes upon instantiation, the exporter requires no intermediate translation layers to parse them. 

**Custom BufferGeometry**
When constructing custom topological shapes by directly instantiating a raw `BufferGeometry`, the user must explicitly set the `position` attribute using a `BufferAttribute`. 
```javascript
const geometry = new THREE.BufferGeometry();
const vertices = new Float32Array([
    0.0, 0.0, 0.0,
    1.0, 0.0, 0.0,
    1.0, 1.0, 0.0
]);
geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
```
If the `position` attribute is omitted, the `OBJExporter` will silently fail to output any vertex declarations for that specific mesh, resulting in a topologically empty object within the output string [cite: 11].

**Scene Graph Traversal**
The exporter leverages the native `.traverse()` method of the `Object3D` base class. This means that arbitrary hierarchical nesting—such as a `Mesh` placed inside a `Group`, which is in turn placed inside another `Object3D` within the `Scene`—is flawlessly resolved [cite: 7]. The exporter processes every child node recursively, identifying printable geometry regardless of its depth in the scene graph.

## 4. Coordinate System Transformations: Aligning Y-Up with Z-Up

A critical disparity exists between the coordinate system utilized by WebGL/Three.js and the coordinate systems standard to many Digital Content Creation (DCC) applications, most notably Blender. Three.js adheres to a right-handed Cartesian coordinate system where the Y-axis designates vertical elevation (Y-up), the X-axis represents horizontal translation, and the negative Z-axis extends forward into the frustum [cite: 12, 13]. Conversely, Blender operates on a right-handed Cartesian system where the Z-axis designates vertical elevation (Z-up), the X-axis represents horizontal width, and the Y-axis extends longitudinally (Y-forward) [cite: 12, 14]. 

Failure to reconcile this discrepancy prior to export will result in models appearing rotationally offset (typically rotated 90 degrees face-down) upon subsequent importation into Blender or other Z-up environments [cite: 15, 16].

**Mathematical Matrix Alignment**
To map a Y-up system into a Z-up system while preserving right-handedness, the entire coordinate space must be rotated by \(-90^\circ\) (or \(-\frac{\pi}{2}\) radians) around the global X-axis. 

The rotation matrix \( R_x \) for an angle \(\theta = -\frac{\pi}{2}\) is mathematically defined as:
\[
R_x(-\pi/2) = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & \cos(-\pi/2) & -\sin(-\pi/2) & 0 \\ 0 & \sin(-\pi/2) & \cos(-\pi/2) & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix} = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 0 & 1 & 0 \\ 0 & -1 & 0 & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix}
\]
When this affine transformation is applied to a coordinate vector \([x, y, z, 1]^T\), the resulting vector transforms the former $+Y$ elevation into the new $+Z$ elevation, and the former $+Z$ depth into the new $-Y$ depth.

**Implementation Modalities**
There are two primary methodologies for applying this transformation within the Three.js ecosystem prior to export:

1.  **Geometric Modification (`geometry.applyMatrix4`)**: The transformation matrix can be applied directly to the underlying `Float32Array` buffers of the `BufferGeometry`. 
    ```javascript
    const matrix = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
    geometry.applyMatrix4(matrix);
    ```
    While computationally efficient, this approach destructively alters the fundamental vertex data. If a geometry is shared across multiple meshes, all instances are irreparably altered.

2.  **Object Rotation and Matrix Baking (Recommended)**: A more non-destructive, scalable approach involves applying the rotation to a high-level `Object3D` or `Group` that contains the scene payload.
    ```javascript
    const rootGroup = new THREE.Group();
    rootGroup.add(mesh);
    rootGroup.rotation.x = -Math.PI / 2;
    scene.add(rootGroup);
    ```
    However, setting the rotation property alone is insufficient for the `OBJExporter`. The exporter does not read the `.rotation` or `.position` Euler/Vector properties directly; instead, it bakes the absolute spatial data by calling `vertex.applyMatrix4( mesh.matrixWorld )` during string construction [cite: 7, 11].

**The Necessity of `updateMatrixWorld(true)`**
In a standard Three.js render loop, the `matrixWorld` property of every object is automatically recalculated by the `WebGLRenderer` prior to rasterization. In a headless Node.js environment without a renderer, these world matrices remain stale (defaulting to the identity matrix) regardless of how the `.position`, `.rotation`, or `.scale` properties are manipulated [cite: 17, 18].

To ensure the exporter captures the \(-90^\circ\) rotational transformation, the developer must explicitly force a matrix synchronization by invoking:
```javascript
scene.updateMatrixWorld(true);
```
The boolean argument `true` ensures that the matrix recalculation aggressively traverses the entire descendant hierarchy [cite: 17, 19]. Without this critical function call, the output OBJ file will export the vertices at the origin with their native Y-up orientation, completely ignoring any applied object transformations [cite: 20, 21].

## 5. Dynamic Evaluation and Ingestion of Scene Files

In robust data pipelines, 3D definitions are frequently isolated in separate algorithmic files. Evaluating and ingesting these files programmatically in Node.js requires careful architectural planning. Assuming a user-defined file exists at `/root/data/object.js` utilizing Three.js constructors, modern Node.js environments can dynamically load this payload using the asynchronous `import()` API.

**Module Design Patterns**
For optimal ingestion, the external file should be structured as an ES module that exports a deterministic entity, such as a localized `Mesh` or `Group`, rather than globally polluting a scene.

*External File (`object.js`):*
```javascript
import * as THREE from 'three';

export default function createGeometryPayload() {
    const geo = new THREE.TorusGeometry(10, 3, 16, 100);
    const mat = new THREE.MeshBasicMaterial();
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = "Torus_Payload";
    return mesh;
}
```

*Main Ingestion Script:*
```javascript
async function loadAndExport(filePath) {
    // Dynamically resolve the external ES module
    const module = await import(filePath);
    
    // Invoke the default export to instantiate the 3D hierarchy
    const externalObject = module.default();
    
    const exportScene = new THREE.Scene();
    exportScene.add(externalObject);
    
    // Proceed with transformation and export...
}
```
This pattern allows arbitrary computational geometry code to be dynamically wrapped, sandboxed, and instantiated into a standardized pipeline without the security implications or scope pollution of legacy `eval()` invocations.

## 6. File System I/O and Output Generation

Once the `OBJExporter` has synchronously parsed the scene and returned a monolithic string, the data must be persisted to the disk. In Node.js, this is accomplished efficiently using the native `fs` (File System) module.

```javascript
import fs from 'fs';
import path from 'path';

// ... exporter logic

const outputPath = path.resolve('./exports/output.obj');
// Write the string to disk using strict UTF-8 encoding
fs.writeFileSync(outputPath, objDataString, 'utf-8');
```
The `utf-8` encoding specification is standard for plaintext format descriptors like Wavefront OBJ. Due to the potentially massive string length generated by high-density `BufferGeometry` models, using `writeFileSync` ensures the execution thread blocks until the entire payload is securely written, preventing race conditions in automated build environments.

## 7. Diagnostics, Limitations, and Common Pitfalls

When architecting a headless programmatic pipeline, developers frequently encounter several deterministic pitfalls specific to the Node.js and Three.js environments:

1.  **Invisible Objects (`visible: false`)**: The standard `OBJExporter` operates through the `.traverse()` method and checks specifically for `child.isMesh`. Depending on the exact iteration and minor version optimizations, it may not explicitly respect the `.visible` boolean flag of the `Object3D` class [cite: 7, 10]. If a developer intends to exclude specific meshes from the export, best practice dictates physically removing the object from the scene hierarchy (`scene.remove(mesh)`) prior to parsing, rather than relying on rendering-specific visibility flags [cite: 22, 23].
2.  **Unapplied Transformation Matrices**: As extensively noted, failing to invoke `object.updateMatrixWorld(true)` is the primary cause of exported geometries appearing stubbornly at the coordinate origin with zero rotation [cite: 20, 21]. The exporter strictly parses `.matrixWorld` [cite: 7].
3.  **Missing Position Attributes**: Procedural geometries that fail to define a `position` `BufferAttribute` will yield empty outputs [cite: 11]. The Wavefront OBJ spec mandates vertex coordinate definitions.
4.  **Deprecated API Invocations**: Code snippets sourced from older literature frequently reference `new THREE.Geometry()` or `new THREE.Face3()`. In Three.js v0.175.0, these classes will instantly throw an `undefined` fatal error, as they have been fully deprecated and removed. All geometry must strictly utilize `THREE.BufferGeometry` [cite: 2].
5.  **Window / Document Undefined Errors**: These errors do not stem from the `OBJExporter` or the geometry primitives, but rather if the dynamic script inadvertently imports a UI dependency (e.g., `OrbitControls`) or attempts to instantiate an image-based `TextureLoader` which attempts to read the DOM `document.createElement('img')` [cite: 5, 24]. Scripts meant for headless export must be rigorously stripped of frontend rendering logic.

## 8. Comprehensive End-to-End Algorithmic Implementation

The following code block represents a fully functional, end-to-end Node.js ES module script. It demonstrates the seamless instantiation of the environment, the creation of a scene graph, the critical coordinate transformation for Blender Z-up compatibility, the forced matrix recalculation, the execution of the exporter, and the localized file persistence.

```javascript
/**
 * Headless Three.js (v0.175.0) to Wavefront OBJ Pipeline
 * Ensures package.json contains "type": "module".
 */

import fs from 'fs';
import path from 'path';
import * as THREE from 'three';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';

async function executeHeadlessExport() {
    console.log('Initializing Headless 3D Pipeline...');

    // 1. Initialize Root Scene Graph
    const scene = new THREE.Scene();

    // 2. Instantiate Geometry and Topology
    // Note: Utilizing BufferGeometry subclass per modern standard
    const geometry = new THREE.CylinderGeometry(5, 5, 20, 32);
    
    // The material is purely structural here; OBJExporter ignores materials, 
    // but the Mesh constructor requires it.
    const material = new THREE.MeshBasicMaterial({ color: 0x0055ff });
    
    const mesh = new THREE.Mesh(geometry, material);
    // Assigning a name explicitly sets the 'o <name>' parameter in the OBJ output
    mesh.name = "Cylinder_Payload"; 

    // 3. Construct Hierarchy
    const rootGroup = new THREE.Group();
    rootGroup.name = "Root_Transform_Group";
    rootGroup.add(mesh);
    scene.add(rootGroup);

    // 4. Coordinate System Conversion (Y-Up to Blender Z-Up)
    // Apply a -90 degree (-PI/2) rotation along the global X-axis
    rootGroup.rotation.x = -Math.PI / 2;

    // 5. Matrix Baking
    // CRITICAL STEP: The WebGLRenderer is absent in Node.js.
    // We must manually force the computation of the world matrices so the 
    // OBJExporter can bake the right-handed Z-up transformation into the vertices.
    scene.updateMatrixWorld(true);

    // 6. Serialized Parsing
    console.log('Parsing topology to Wavefront OBJ format...');
    const exporter = new OBJExporter();
    
    // parse() synchronously traverses the hierarchy evaluating matrixWorld
    const objDataString = exporter.parse(scene);

    // 7. File System I/O
    const outputDirectory = './output';
    if (!fs.existsSync(outputDirectory)){
        fs.mkdirSync(outputDirectory);
    }

    const outputPath = path.join(outputDirectory, 'model_z_up.obj');
    
    try {
        fs.writeFileSync(outputPath, objDataString, 'utf-8');
        console.log(`Export Successful. Payload written to: ${outputPath}`);
    } catch (error) {
        console.error(`I/O Error during export: ${error.message}`);
    }
}

// Execute the pipeline
executeHeadlessExport();
```

**Sources:**
1. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE9mygU8Cy-Sjc0JcVhlEIVRCEWm7BoYs8-6DNsyzVw0nW0jrKt1uQQ_LCgmKMHe654_uSDzhPFr-vBZ6zGSc2fkKqndkGb7F3wfIm-Jy6eBRfU8JW7zlSPMqRVNa-QykfsBMeY7QDVq1ojKC45)
2. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHvZcyXXQubAnt2r5nX00RKFRkPJEom1eRBQm1hqZt4O4vJ1TLi5IcCrFwyyDGV-v_fPS7_fDgvo-V6DijnU3rHX_KQlMM17g28Mcj7cFaAUIlB3hjSmFQtu3woUCFbX4HG-Io1FdFwvp26c8zf)
3. [discoverthreejs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHrFmWxK1PdAq6LON_O_rBcEDuBOfjVxhcAVOVVz636Aq9oWFEoobdc-3pCnIr1HoQofN2xuXfUNjcZGlUN3UJ62i6PYq6MshGTn6XyNoZJoEx8pXcyU_C9xoOdVOlun6w44IA5ZAuevSZrXrRwRZi)
4. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdKuKeq4vfQYdB8QV53jKEtKKQUL5CsmSunGd89-HwcPj-6950uty865zsVwYEgxG4a0fQ_n1zqhHAYokQ4x4OdqFvCGCIOfAnmXWI8oJPXdwyUBLbtkkBwtJ1FvBJB0MxpCa0Vjwjd2kR0xEcQ87Xxyb6)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_9bPqUS91HFbfuL3PvwgY8bwc5XGuRQlcx5PsoIX5ZlwftZmdWGNypkwD4Ts3eWrrEVoRMF5JZZ7R5qt3e8ZIbBmAZIY_3OJP79qR621iixqkfREOZAZQYJL_fQc1kSf65zIHWQ==)
6. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHQqJ4B6PimCGZVRIHyQZiw0ClU8p3CdivBxCB4sZVeslfj7m1W97M93i8d8fb-GINK8Syq9Cqfwo0T75eoK3bRn3Axdnw7Xqh_H0WRJrrh1iDcFZVhzU-sEld0X8rew39k6IqkAg==)
7. [cnrs.fr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF6qpty_6_Y1DYyO3vd6BbBQxtGJ_NkBGochK_YojKqsF-rTwsXbl0mRv0ilb42Ilh_dD9s2kJXx3rMmH1NOw2aM7wA5m95tcmMckINWnJH-uvmiiFbCG7EV1TMY22B0Su_0XhrmRrk2lwVaJ-rW142AvuxxcKQwTUsfEZHaZuE9ccUeZmIzVXm2ve5WE-Fk0V8IIsC0DdFPIRdzF92hNJohc7q4zDqGlwGybk9Sv0iHV1LP1ff7gr9PRN6x_zI0A==)
8. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHU2ICV6Q1xxgrhUzRtFAzE8LZhxo3PieTz_l0RF-3oopxluU4oGBb3qyLnvZvD8lawXCWHNSJP8O3PHMRxAKBgBksRDPwvGAAZJyoKzOs1-OeggH1b6KRk2NxQv94ZssHnTnzxqemnEXxU_mqmh0OnopzFzUD_WxzDw7rd-4HJW47NVTn65O-zz6lZFuSk)
9. [sbcode.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFrEjIiKp2nKeJyWvZTLfkhxdtaVaBaAMMywyI81KWhI5VuTmode3DwCH38zPrfWbhYzbWbWalOCK0Fb0qFj6mdXJ-zOmD7VMrSj1TBW9nMTKtoQoE3kUTPMGkY)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVBucFTZbB1C4QdISN1bY8lV0cVFRrbw9wAEPXE84ZhGviUSysipVoWPhCQp2DUmBkDWcYrkQufa2RGR6hFBirK2-429byqUKNJ4-9PvRY8LoT99iPxplAMJtTYUbCMSdthpgxrg==)
11. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGmOXNxaStLonBEDALV2d0qWghNt8PB1fLGT8eX0J85iHbnK4QyvAaxpaEfRjmrkLCxLczT5xlsYp9nUI7Av9U_49Uu5WKWDuOEobIK2x7vnAGXfEHXmbk9NpTKd_aXpWGtUP7QNMFS-QKG2glJDtM9QqhbVPTCUiKFgQ==)
12. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHspxko56y08krjjy_RGfi1PZvUUetfONulEK7q0keJtAqN55zMwigeDqvZkGZ22-cRsWU8ZP2aeH9HNggpWGFq29YJZ7E9hQnO1xRrcofzGbDX5hCh9aOMbsI5u7jrqKQ-jf1fz2E1cqC_ytdHvLVi006YrkcHAfSHOtUEh4PrUzysNs-nzKhMgigQzsHfxoFZSUmT)
13. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH6q3xst_YE_u0D5KpSPo8Km1SX_I7VTsunZS4mtlg6c2cwX5xkw2oD57pH8bZQ-L2Ohrfm1vSyyDUiY9c2DLcOV5e9F-kdCW4V3TvrKBfadc7gmhUQQnyntNA5k1ELWkYMlHTAa-EqIie_hW6MW_deEgCGKIfRQaKaq-7aBTubMQDv7VOL1YvLHTUIJlSIRmoNlvB2NhDv8Kc8)
14. [blender.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0ik-11X3DiuDN0-nSKYh7TqqaboFEOBVx82SjqNZn3TdBS2_yQ4sKQMKwd8dGDwsjNISl61pvc8lAR5mULANOyQyNXsRxcP0xe8CafRWYGC0TmIPsYsXWh7gECSSaPyKfrt3F3-uS2IqpH3HyJPY0LMIIOS9IjkhSCq15)
15. [vectorworks.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEHiw4GTH-5PxcvxsPxOZMVhPRrIhFumvcmpclwIWJW3X-HZYH9JJpkOhqDVTFMU1tB4fAEndjIG1R_bXQFemMfolB7YTWFa1_gXKa4joyDxCkCV3p_bRQXzLuz2Y00K2aiu5AbKTuQHrPx7PZ82-OlCoVTyQoUO08UgVq57WNuNYwQ6hcCHBDwyDMDDa4zMbSB32u0vg==)
16. [blenderartists.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuz6X4TlL2pt_5ofH0wRveAbdkrKwhkAN67G2-HApQtLXNvMOA6gqTxfSI9jzXFc6kevWHjyADyOyhBzEQtQ50mzCn5LQ64bGMHWuA5BExdouPba6ycNDhN_y-JoUNv2vp6_8CVnCtFvL3yACFZnDPey765FwvxmSY)
17. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFGAQYLZq-d4PGHrZPiVUKRirZg5OR-2Bb_J8RcWFxCYz68t01zzCWrJO6Y4FLdyDPMhdAyLBzoaF9NIgrhzHiXaxzauGHPCgz8xNGEqyYNSzpOjKlpoFINLib4tZ0dZWDj9zqBMt5Em7W9SN3Sjw8L)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGEzk2mLn8noCo68xsO1igV4GrTRPgb2Iax84tG2lD5rKy66BrIhmzVbiUQDX2QiPU6DvQSXpqTa6KTfHT9_HXEBcM_md6nA-RiqsIxjnADg0p3TXv1N_PBCD1Dj2OhvDCJcyWrx2_vM-8bAyGxCxySQKFw1hm1HU4QVNhC-hp7-Jo_fwsuZf0sTQuCQz8Yad4oQxUX)
19. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEe1ZfUO4fJFPlrcia9zzrNArpOtOR-X1XAJdl00XSM9RVjtjQti2aAo0x7gVjDxzCoRNTnssVtWFAAfj4zIbu84s4c6E_Aa5ucNKq78B2DbspEQgzAlSvPqFmjf3Osnv6mZltZ38eBxCthf6dzQwgLLZPS--7F)
20. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwTT_8TdPrkYttTR8omyWPY8cVaQS2OAJiCOsoIV9TEE2N--yAfzrqQapuLv0MJw_zI84Jj9h4pSOQHpFuGC56y15F9_yO4ggxkKKfSEkfVZj5zlG0CStVS8Hd5VnnxLQAVXW2BE7OJM5sV3-PHUc7ISBU7BFcMRm1FX5OKU8K4ywRk-nzd5MMVmY=)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEs5gC_nbubIkPnCbhb_P4MHBvck0Qaz68fCNzK5hPClXTex-jrbK8LUaIr-coSSqRP9Cd6814x5T-f0t8F5283gyjIZiYuqufH5BNnrq9jpvSJPtBvNSTvTS7M10Nwp57c2gzm_gJREFxZWxImXe5fODjZhsrj)
22. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGKou16sRD1KqanmfLxZ0_kW-uSnedF3DpA44C0kEBxF-s7Yun_3dRomPzchlNSW_zKGnrtkTK1J2NN1usOqS0Rpv-Oib_i1pHl_pvL6oFoLk1DZuq-8EJYsXU7jWMRJy5q8ejWKImfbrh9AJo=)
23. [threejs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFjoGKYjTxpMZ4Je9iiPQcVxPiydLrqg9pDAvKRsU_-vwg_5cshWl5csdr3ow7auhE_DSX3cFhUcxJqQiUT-lg99EBJGk4Sl2q5FTWIzx8X-mNXaa9NK4ipbx1G_Rw6KS_f4Knt-yjzKb-tEqwEccSxY-4McoLSiBx5)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG33YlaFciXv0-qZMJ689KAbthLP1vGYjUphH8JwgUlRCEREATvlaBO_WVZv3Bj3cFWpc-tSe8JvtbktasaBCmQa52hzpSN0FCdZJTzC5eF-BCXl5__4ZgUOjY1surQ4u2KPUgd7KTDZTAJldate9Rz7oI0HDreZo-MeOjZCi7Ia9erliG5-AsahAkOui8l)
