import fs from 'fs';
import path from 'path';

/**
 * Generates the content of a Node.js ES module export script as a string.
 * The generated script will:
 * 1. Dynamically import the Three.js object definition
 * 2. Call the exported createScene() function
 * 3. Wrap in a Group with -90deg X rotation for Y-up to Z-up conversion
 * 4. Force updateMatrixWorld(true)
 * 5. Export via OBJExporter
 * 6. Write to output path
 */
export function generate_export_script(inputPath, outputPath) {
  const absInput = path.resolve(inputPath);
  const absOutput = path.resolve(outputPath);
  
  return `
import fs from 'fs';
import path from 'path';
import * as THREE from 'three';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';

async function main() {
  // 1. Dynamically import the object definition
  const module = await import('${absInput}');
  
  // 2. Find and call the export function
  let object3D;
  if (typeof module.createScene === 'function') {
    object3D = module.createScene();
  } else if (typeof module.default === 'function') {
    object3D = module.default();
  } else {
    // Try to find any exported function
    for (const key of Object.keys(module)) {
      if (typeof module[key] === 'function') {
        object3D = module[key]();
        break;
      }
    }
  }
  
  if (!object3D) {
    console.error('No valid 3D object found in module');
    process.exit(1);
  }
  
  // 3. Create scene and apply coordinate transform
  const scene = new THREE.Scene();
  const rootGroup = new THREE.Group();
  rootGroup.name = 'CoordinateTransform';
  rootGroup.rotation.x = Math.PI / 2;  // Y-up to Z-up
  rootGroup.add(object3D);
  scene.add(rootGroup);
  
  // 4. CRITICAL: Force world matrix update (no renderer in Node.js)
  scene.updateMatrixWorld(true);
  
  // 5. Export to OBJ
  const exporter = new OBJExporter();
  const objString = exporter.parse(scene);
  
  // 6. Write output
  const outputDir = path.dirname('${absOutput}');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  fs.writeFileSync('${absOutput}', objString, 'utf-8');
  console.log('Export complete: ${absOutput}');
}

main().catch(err => { console.error(err); process.exit(1); });
`;
}

/**
 * Generates the export script, writes it to disk, and optionally executes it.
 */
export async function create_obj_export_node_script(inputPath, outputPath, scriptOutputPath) {
  const scriptContent = generate_export_script(inputPath, outputPath);
  fs.writeFileSync(scriptOutputPath, scriptContent, 'utf-8');
  console.log(`Export script written to: ${scriptOutputPath}`);
  return scriptOutputPath;
}
