# evo-molecule-similarity

## Description
Find top-k similar chemicals from a PDF molecule pool using Morgan fingerprints
with Tanimoto similarity. Converts chemical names to SMILES via PubChemPy,
computes Morgan fingerprints (radius=2, chirality=True), and ranks by
Tanimoto similarity with alphabetical tie-breaking.

## Key Concepts
- **PDF Extraction**: Uses pdfplumber to extract chemical names (one per line)
- **Name-to-SMILES**: Uses PubChemPy (external resource, no manual mapping)
- **Morgan Fingerprints**: radius=2, useChirality=True, default 2048 bits
- **Tanimoto Similarity**: Standard similarity metric for molecular fingerprints
- **Sorting**: Descending by similarity, alphabetical for ties

## Dependencies
- pdfplumber (PDF text extraction)
- pubchempy (chemical name to SMILES conversion)
- rdkit (fingerprints and similarity)

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-molecule-similarity/scripts')
from utils import (
    topk_tanimoto_similarity_molecules,
    extract_molecule_names,
    name_to_smiles,
    smiles_to_fingerprint,
    compute_tanimoto_similarity
)

# Main function - find top k similar molecules
results = topk_tanimoto_similarity_molecules(
    target_molecule_name='Aspirin',
    molecule_pool_filepath='/root/molecules.pdf',
    top_k=5
)
print(results)
# ['Acetylsalicylic acid', 'Aspirin', 'Methyl 2-acetoxybenzoate', ...]
```

## Function Reference

### topk_tanimoto_similarity_molecules(target_molecule_name, molecule_pool_filepath, top_k) -> list
Main entry point. Returns list of top-k molecule names sorted by descending
Tanimoto similarity, alphabetical for ties.

### extract_molecule_names(filepath) -> list
Extract chemical names from PDF file (one per line).

### name_to_smiles(name) -> str or None
Convert chemical name to canonical SMILES via PubChemPy.

### smiles_to_fingerprint(smiles) -> fingerprint or None
Convert SMILES to Morgan fingerprint (radius=2, chirality=True).

### compute_tanimoto_similarity(fp1, fp2) -> float
Compute Tanimoto similarity between two fingerprints.

## Notes
- Aspirin and Acetylsalicylic acid are the same molecule (same SMILES)
- The target molecule is NOT excluded from results if it appears in the pool
- Molecules that cannot be resolved via PubChemPy are silently skipped
- PubChemPy requires internet access
