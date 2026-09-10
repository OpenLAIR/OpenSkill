// Headless Three.js scene parser. Polyfills first.
if (typeof global.self === 'undefined') global.self = global;
if (typeof global.window === 'undefined') global.window = global;
if (typeof global.document === 'undefined') global.document = { createElement: () => ({}) };

import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';

function sanitize(name) {
    return String(name).replace(/[^A-Za-z0-9_.-]+/g, '_');
}

async function main() {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.error('Usage: node parser.mjs <scene.js> <output_dir>');
        process.exit(1);
    }
    const scenePath = path.resolve(args[0]);
    const outDir = path.resolve(args[1]);
    const partMeshesDir = path.join(outDir, 'part_meshes');
    const linksDir = path.join(outDir, 'links');
    fs.mkdirSync(partMeshesDir, { recursive: true });
    fs.mkdirSync(linksDir, { recursive: true });

    const url = pathToFileURL(scenePath).href;
    const mod = await import(url);
    if (typeof mod.createScene !== 'function') {
        throw new Error('No createScene() exported');
    }
    const root = mod.createScene();
    root.updateMatrixWorld(true);

    const exporter = new OBJExporter();
    const summary = { parts: [], standaloneMeshes: [] };

    // Collect ALL groups in the tree (excluding the root itself).
    const groups = [];
    const standaloneMeshes = [];

    root.traverse((node) => {
        if (node === root) return;
        if (node.isGroup) groups.push(node);
    });

    // Standalone meshes: top-level children of root that are Mesh
    for (const child of root.children) {
        if (child.isMesh) standaloneMeshes.push(child);
    }

    let unnamedGroupIdx = 0;
    let unnamedMeshIdx = 0;

    // Process each group as a part.
    for (const group of groups) {
        const partName = group.name || `UnnamedGroup_${unnamedGroupIdx++}`;
        const safePart = sanitize(partName);

        // Direct child meshes of this group (NOT meshes inside nested sub-groups)
        const directMeshes = group.children.filter(c => c.isMesh);

        // Create part_meshes/<part>/
        const partDir = path.join(partMeshesDir, safePart);
        fs.mkdirSync(partDir, { recursive: true });
        const usedNames = new Set();
        for (let j = 0; j < directMeshes.length; j++) {
            const m = directMeshes[j];
            let mname = m.name || `mesh_${j}`;
            let safe = sanitize(mname);
            let final = safe;
            let k = 1;
            while (usedNames.has(final)) {
                final = `${safe}_${k++}`;
            }
            usedNames.add(final);
            m.updateMatrixWorld(true);
            const objStr = exporter.parse(m);
            const fp = path.join(partDir, `${final}.obj`);
            fs.writeFileSync(fp, objStr, 'utf-8');
        }

        // For links/<part>.obj: merge ONLY direct child meshes (not nested group descendants)
        // This ensures wheel_structure link contains hub+rim+spokes but NOT cabin meshes
        if (directMeshes.length > 0) {
            const geometriesToMerge = [];
            for (const m of directMeshes) {
                m.updateMatrixWorld(true);
                const clonedGeom = m.geometry.clone();
                clonedGeom.applyMatrix4(m.matrixWorld);
                // Standardize: convert indexed to non-indexed
                let processed = clonedGeom;
                if (processed.index !== null) {
                    processed = processed.toNonIndexed();
                }
                // Remove attributes that might not be present in all geometries
                // Keep only position and normal for safe merging
                const attrs = Object.keys(processed.attributes);
                for (const attr of attrs) {
                    if (attr !== 'position' && attr !== 'normal') {
                        processed.deleteAttribute(attr);
                    }
                }
                geometriesToMerge.push(processed);
            }

            const mergedGeom = mergeGeometries(geometriesToMerge, false);
            if (mergedGeom) {
                const mergedMesh = new THREE.Mesh(mergedGeom, new THREE.MeshBasicMaterial());
                mergedMesh.position.set(0, 0, 0);
                mergedMesh.rotation.set(0, 0, 0);
                mergedMesh.scale.set(1, 1, 1);
                mergedMesh.updateMatrixWorld(true);
                const objStr = exporter.parse(mergedMesh);
                const linkPath = path.join(linksDir, `${safePart}.obj`);
                fs.writeFileSync(linkPath, objStr, 'utf-8');
            }
        }

        summary.parts.push({ name: partName, safe: safePart, directMeshCount: directMeshes.length });
    }

    // Process standalone top-level meshes
    for (let i = 0; i < standaloneMeshes.length; i++) {
        const m = standaloneMeshes[i];
        const partName = m.name || `UnnamedMesh_${unnamedMeshIdx++}`;
        const safePart = sanitize(partName);

        const partDir = path.join(partMeshesDir, safePart);
        fs.mkdirSync(partDir, { recursive: true });
        m.updateMatrixWorld(true);
        const objStr = exporter.parse(m);
        fs.writeFileSync(path.join(partDir, `${safePart}.obj`), objStr, 'utf-8');
        fs.writeFileSync(path.join(linksDir, `${safePart}.obj`), objStr, 'utf-8');
        summary.standaloneMeshes.push({ name: partName });
    }

    console.log(JSON.stringify({ status: 'success', summary }));
}

main().catch(err => {
    console.log(JSON.stringify({ status: 'error', message: err.message, stack: err.stack }));
    process.exit(1);
});
