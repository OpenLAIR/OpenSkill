import fs from 'fs';
import path from 'path';
import * as THREE from 'three';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';

async function main() {
  const inputPath = process.argv[2] || '/root/data/object.js';
  const outputPath = process.argv[3] || '/root/output/object.obj';
  
  console.log(`Input: ${inputPath}`);
  console.log(`Output: ${outputPath}`);
  
  // 1. Dynamically import the object definition
  const absInput = path.resolve(inputPath);
  const module = await import(absInput);
  
  // 2. Find and call the export function
  let object3D;
  if (typeof module.createScene === 'function') {
    object3D = module.createScene();
  } else if (typeof module.default === 'function') {
    object3D = module.default();
  } else {
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
  
  console.log(`Loaded object: ${object3D.name}`);
  
  // 3. Create scene and apply coordinate transform (Y-up to Z-up)
  const scene = new THREE.Scene();
  const rootGroup = new THREE.Group();
  rootGroup.name = 'CoordinateTransform';
  rootGroup.rotation.x = Math.PI / 2;  // -90 degrees around X axis  // -90 degrees around X axis
  rootGroup.add(object3D);
  scene.add(rootGroup);
  
  // 4. CRITICAL: Force world matrix update (no renderer in headless Node.js)
  scene.updateMatrixWorld(true);
  
  // 5. Export to OBJ format
  const exporter = new OBJExporter();
  const objString = exporter.parse(scene);
  
  // 6. Write output file
  const outputDir = path.dirname(path.resolve(outputPath));
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  fs.writeFileSync(path.resolve(outputPath), objString, 'utf-8');
  
  // Diagnostics
  const lines = objString.split('\n');
  const vCount = lines.filter(l => l.startsWith('v ')).length;
  const fCount = lines.filter(l => l.startsWith('f ')).length;
  const vnCount = lines.filter(l => l.startsWith('vn ')).length;
  const oCount = lines.filter(l => l.startsWith('o ')).length;
  console.log(`Vertices: ${vCount}, Faces: ${fCount}, Normals: ${vnCount}, Objects: ${oCount}`);
  console.log(`Export complete: ${path.resolve(outputPath)}`);
}

main().catch(err => { console.error(err); process.exit(1); });
