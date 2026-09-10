import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { pathToFileURL } from 'url';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import path from 'path';

/**
 * Convert a Three.js scene module to OBJ format for Blender (Z-up).
 *
 * Pipeline (per the domain research):
 * 1. Load the scene module and call the exported scene-creation function
 * 2. Update world matrices on the entire scene tree (CRITICAL in headless Node.js
 *    since there is no WebGLRenderer to auto-update matrices — DR cite 17, 18)
 * 3. Traverse the scene graph depth-first:
 *    - For InstancedMesh: for each instance, compose world matrix * instance matrix,
 *      clone geometry, apply composed matrix, apply axis rotation
 *    - For regular Mesh: clone geometry, apply world matrix, apply axis rotation
 *    - Skip non-mesh nodes (Groups, Lights, etc.)
 * 4. Ensure all geometries have consistent attributes (compute normals if missing)
 * 5. Convert all to non-indexed
 * 6. Merge all geometries into one
 * 7. Wrap in a single Mesh and export via OBJExporter
 *
 * Coordinate conversion: -90° X rotation converts Three.js Y-up to Blender Z-up
 * Math: Rx(-π/2) = [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]] (DR cite 12-16)
 */

/**
 * Attempt to extract a root Object3D from the loaded module.
 * Handles multiple common export patterns from object.js files:
 * - module.createScene() (named export)
 * - module.default() (default export function)
 * - module.default (default export that is already an Object3D)
 * - module.createObject(), module.create(), module.init(), module.build() etc.
 * - module.scene (named export that is already an Object3D)
 */
function extractSceneFromModule(mod) {
  // Common function names to try, in priority order
  const functionNames = [
    'createScene',
    'default',
    'createObject',
    'create',
    'init',
    'build',
    'getScene',
    'scene',
    'main',
    'getObject',
    'object',
  ];

  // First pass: try calling known function names
  for (const name of functionNames) {
    if (typeof mod[name] === 'function') {
      try {
        const result = mod[name]();
        if (result && result.isObject3D) {
          console.log(`Scene extracted via mod.${name}()`);
          return result;
        }
      } catch (e) {
        // Some functions might need arguments or fail — skip
        console.warn(`mod.${name}() threw: ${e.message}`);
      }
    }
  }

  // Second pass: check if any export is already an Object3D instance
  for (const name of functionNames) {
    if (mod[name] && mod[name].isObject3D) {
      console.log(`Scene extracted as mod.${name} (Object3D instance)`);
      return mod[name];
    }
  }

  // Third pass: scan all exports for Object3D instances or callable functions
  for (const key of Object.keys(mod)) {
    if (mod[key] && mod[key].isObject3D) {
      console.log(`Scene extracted as mod.${key} (Object3D instance)`);
      return mod[key];
    }
  }

  for (const key of Object.keys(mod)) {
    if (typeof mod[key] === 'function' && !functionNames.includes(key)) {
      try {
        const result = mod[key]();
        if (result && result.isObject3D) {
          console.log(`Scene extracted via mod.${key}()`);
          return result;
        }
      } catch (e) {
        // Skip
      }
    }
  }

  return null;
}

async function main() {
  const inputPath = process.argv[2] || '/root/data/object.js';
  const outputPath = process.argv[3] || '/root/output/object.obj';

  console.log(`Input:  ${inputPath}`);
  console.log(`Output: ${outputPath}`);

  // Verify input file exists
  if (!existsSync(inputPath)) {
    console.error(`Input file not found: ${inputPath}`);
    process.exit(1);
  }

  // Dynamically import the scene module
  const fileUrl = pathToFileURL(path.resolve(inputPath)).href;
  let mod;
  try {
    mod = await import(fileUrl);
  } catch (err) {
    console.error(`Failed to import scene module: ${err.message}`);
    console.error('Ensure the file is valid ES module JavaScript and three.js is installed.');
    process.exit(1);
  }

  // Extract the root Object3D from the module
  const root = extractSceneFromModule(mod);
  if (!root) {
    console.error('Could not extract a valid Object3D from the module.');
    console.error('Available exports:', Object.keys(mod));
    process.exit(1);
  }

  console.log(`Root object type: ${root.constructor.name}, name: "${root.name || '(unnamed)'}"`);

  // Step 1: Force update all world matrices from the root down.
  // CRITICAL in headless Node.js — no WebGLRenderer to auto-update (DR cite 17, 18, 20, 21)
  root.updateMatrixWorld(true);

  // Step 2: Build the -90 degree X rotation matrix for Y-up -> Z-up conversion
  // Rx(-π/2): maps (x,y,z) → (x, z, -y) which converts Y-up to Z-up (DR cite 12-16)
  const axisRotation = new THREE.Matrix4().makeRotationX(-Math.PI / 2);

  // Step 3: Traverse and collect geometries
  const geometries = [];

  root.traverse((node) => {
    // Skip invisible nodes — OBJExporter may not respect .visible flag (DR cite 7, 22, 23)
    if (!node.visible) {
      return;
    }

    if (node.isInstancedMesh) {
      // Handle InstancedMesh: export each instance separately
      // Standard OBJExporter does NOT handle InstancedMesh — manual traversal required
      const count = node.count;
      const instanceMatrix = new THREE.Matrix4();

      for (let i = 0; i < count; i++) {
        // Get per-instance matrix from the instanceMatrix attribute
        instanceMatrix.fromArray(node.instanceMatrix.array, i * 16);

        // Compose: final = axisRotation * worldMatrix * instanceMatrix
        // This bakes world transform + instance transform + coordinate conversion
        const finalMatrix = new THREE.Matrix4();
        finalMatrix.multiplyMatrices(node.matrixWorld, instanceMatrix);
        finalMatrix.premultiply(axisRotation);

        // Clone geometry and apply the full transform
        const geom = node.geometry.clone();
        geom.applyMatrix4(finalMatrix);

        geometries.push(geom);
      }
    } else if (node.isMesh) {
      // Regular Mesh: clone geometry, apply world matrix, then axis rotation
      const geom = node.geometry.clone();

      // Check that geometry has position attribute (DR cite 11 — missing position = empty output)
      if (!geom.attributes.position) {
        console.warn(`Mesh "${node.name}" has no position attribute, skipping.`);
        return;
      }

      // Compose: final = axisRotation * worldMatrix
      const finalMatrix = new THREE.Matrix4();
      finalMatrix.multiplyMatrices(axisRotation, node.matrixWorld);

      geom.applyMatrix4(finalMatrix);

      geometries.push(geom);
    }
  });

  console.log(`Collected ${geometries.length} geometries`);

  if (geometries.length === 0) {
    console.error('No geometries found in the scene. The output OBJ will be empty.');
    // Still write an empty OBJ rather than crashing — some scenes may legitimately be empty
    mkdirSync(path.dirname(outputPath), { recursive: true });
    writeFileSync(outputPath, '# Empty scene - no geometries found\n');
    process.exit(0);
  }

  // Step 4: Prepare geometries for merging
  // - Convert indexed to non-indexed (required for consistent merging)
  // - Ensure all have normals
  // - Make attributes consistent by keeping only position and normal
  const preparedGeometries = geometries.map((geom, idx) => {
    // Convert indexed to non-indexed
    let g = geom.index ? geom.toNonIndexed() : geom.clone();

    // Compute normals if missing (DR cite 11 — OBJ spec benefits from normals)
    if (!g.attributes.normal) {
      g.computeVertexNormals();
    }

    // Remove UV and other extra attributes to ensure homogeneity for mergeGeometries
    // Keep only position and normal — OBJExporter doesn't export materials anyway (DR cite 6)
    const attribNames = Object.keys(g.attributes);
    for (const name of attribNames) {
      if (name !== 'position' && name !== 'normal') {
        g.deleteAttribute(name);
      }
    }

    return g;
  });

  // Step 5: Merge all geometries into one
  // mergeGeometries returns null on failure (e.g., attribute mismatch)
  let merged = mergeGeometries(preparedGeometries, false);

  if (!merged) {
    // Fallback: try merging with only position attributes (drop normals too)
    console.warn('Initial merge failed. Retrying with position-only attributes...');
    const positionOnlyGeometries = preparedGeometries.map((g) => {
      const stripped = g.clone();
      const attribNames = Object.keys(stripped.attributes);
      for (const name of attribNames) {
        if (name !== 'position') {
          stripped.deleteAttribute(name);
        }
      }
      return stripped;
    });

    merged = mergeGeometries(positionOnlyGeometries, false);

    if (!merged) {
      console.error('Failed to merge geometries even with position-only fallback.');
      // Last resort: export geometries individually without merging
      console.log('Falling back to individual geometry export...');
      const scene = new THREE.Scene();
      preparedGeometries.forEach((g, i) => {
        const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial());
        m.name = `part_${i}`;
        scene.add(m);
      });
      // No need for updateMatrixWorld since transforms are already baked into vertices
      const exporter = new OBJExporter();
      const objString = exporter.parse(scene);
      mkdirSync(path.dirname(outputPath), { recursive: true });
      writeFileSync(outputPath, objString);
      console.log(`OBJ written to ${outputPath} (individual parts, no merge)`);
      console.log(`File size: ${objString.length} bytes`);
      return;
    }

    // Compute normals for the merged position-only geometry
    merged.computeVertexNormals();
  }

  const vertexCount = merged.attributes.position.count;
  const normalCount = merged.attributes.normal ? merged.attributes.normal.count : 0;
  console.log(`Merged geometry: ${vertexCount} vertices, ${normalCount} normals`);

  // Step 6: Wrap in a single Mesh and export via OBJExporter
  // Using a single mesh avoids OBJExporter's limited scene traversal (DR cite 7, 10)
  const exportMesh = new THREE.Mesh(merged, new THREE.MeshBasicMaterial());
  exportMesh.name = 'exported_object';

  const exporter = new OBJExporter();
  const objString = exporter.parse(exportMesh);

  // Validate output is non-trivial
  if (!objString || objString.trim().length === 0) {
    console.error('OBJExporter produced empty output.');
    process.exit(1);
  }

  // Count faces for diagnostic output
  const faceCount = (objString.match(/^f /gm) || []).length;
  console.log(`OBJ contains ${faceCount} faces`);

  // Ensure output directory exists
  mkdirSync(path.dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, objString);

  console.log(`OBJ written to ${outputPath}`);
  console.log(`File size: ${objString.length} bytes`);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  console.error(err.stack);
  process.exit(1);
});