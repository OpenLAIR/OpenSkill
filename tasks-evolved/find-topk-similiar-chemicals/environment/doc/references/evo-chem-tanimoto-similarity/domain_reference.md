# Domain Reference for evo-chem-tanimoto-similarity

**Responsibility**: SMILES to RDKit Mol conversion, Morgan fingerprint generation using the modern rdFingerprintGenerator API (radius=2, fpSize=2048, includeChirality=True), Tanimoto similarity computation, top-k sorting with descending similarity and alphabetical tie-breaking, and the main `topk_tanimoto_similarity_molecules` function.

**Key functions to implement**: generate_fingerprint, compute_tanimoto_similarity, topk_tanimoto_similarity_molecules

---

## 4. RDKit Molecular Processing & Tanimoto Similarity (Version 2025.09.3)


RDKit is the premier open-source cheminformatics toolkit in Python. However, its API has undergone massive modernizations, significantly altering how fingerprints are generated in versions post-2023 [cite: 25].

### 4.1 Converting SMILES to Mol Objects


SMILES strings must be instantiated into topological graph objects (`rdkit.Chem.rdchem.Mol`). 
**API**: `Chem.MolFromSmiles(smiles)` [cite: 1, 26, 27].

**Handling Invalid SMILES**: 
When `MolFromSmiles` encounters an invalid SMILES string (e.g., broken valence, unclosed rings), it prints a warning to the console and crucially **returns the Python `None` object** [cite: 1, 27]. Any automated pipeline must check for `if mol is None:` before passing the object to feature generators, or else an `ArgumentError` (C++ signature mismatch) will crash the program.

### 4.2 Morgan Fingerprints: The Deprecation of `GetMorganFingerprintAsBitVect`


Morgan fingerprints are circular topological fingerprints analogous to the Extended Connectivity Fingerprints (ECFP) algorithm [cite: 26, 28, 29]. They iterate through atomic neighborhoods up to a specified radius, hashing local structural invariants into a fixed-length bit vector [cite: 28, 30, 31].

### 4.3 Computing Tanimoto Similarity


The Tanimoto coefficient (also known as the Jaccard index) is the ratio of intersecting set bits to the union of set bits: \( T(A, B) = \frac{|A \cap B|}{|A| + |B| - |A \cap B|} \) [cite: 31, 36]. It bounds between 0.0 (no shared substructures) and 1.0 (identical bit vector sets).

**Exact Import Path and Signature**:
```python
from rdkit import DataStructs

### 4.4 Complete Working Code: SMILES to Tanimoto


```python
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from rdkit import DataStructs

def compute_tanimoto_similarity(smiles1: str, smiles2: str) -> float:
    """
    Computes Tanimoto similarity between two SMILES strings using RDKit 2025+.
    Uses Morgan fingerprints (Radius=2, 2048 bits, chirality enabled).
    """
    # 1. Convert SMILES to Mol objects
    mol1 = Chem.MolFromSmiles(smiles1)
    mol2 = Chem.MolFromSmiles(smiles2)
    
    # Gracefully handle invalid SMILES
    if mol1 is None or mol2 is None:
        return 0.0
        
    # 2. Instantiate the CURRENT recommended Morgan generator
    # Note: Using fpSize (not nBits) and includeChirality (not useChirality)
    fpgen = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, 
        fpSize=2048, 
        includeChirality=True
    )
    
    # 3. Generate ExplicitBitVects
    fp1 = fpgen.GetFingerprint(mol1)
    fp2 = fpgen.GetFingerprint(mol2)
    
    # 4. Compute and return float Tanimoto score
    return DataStructs.TanimotoSimilarity(fp1, fp2)
```

---

## 5. Common Pitfalls and Edge Cases Summary


When deploying a cheminformatics utility module, robust handling of data inconsistencies is paramount. 

1.  **RDKit `MolFromSmiles()` Returning `None`**: SMILES strings scraped from the web or improperly parsed from PDFs may possess invalid valences or syntax errors. Attempting to generate a fingerprint on a `NoneType` throws fatal C++ argument errors. **Solution**: Always embed a `if mol is None:` check and skip/filter the molecule from downstream pipelines [cite: 1, 27].
2.  **PubChem Name Resolution Failures**: Chemical names extracted from text may be trade names, fragmented, or ambiguous. **Solution**: Rely on PubChemPy's error handling (`try/except`), utilize the exponential backoff pattern for rate limit (`HTTP 503`) protection [cite: 18, 39], and attempt synonym/substance fallback lookups [cite: 15, 17].
3.  **Parameter Name Drift (`useChirality` vs `includeChirality`)**: Upgrading codebases from pre-2023 RDKit to 2024/2025 breaks legacy arguments. The generator API (`GetMorganGenerator`) strictly utilizes `includeChirality` and `fpSize` [cite: 25, 30, 35].
4.  **Sorting Results with Tiebreakers**: In similarity searches, multiple molecules may share identical Tanimoto scores (ties). An unstable sort order creates non-deterministic pipeline outputs. **Solution**: Use Python's built-in tuple sorting logic in the `key` parameter of `sorted()`. By passing `lambda x: (-x['similarity'], x['name'])`, Python first sorts by the negative similarity (yielding descending numerical order) and ties are broken by the string name (yielding ascending alphabetical order).

---

## 6. The Unified Data Pipeline Pattern


Synthesizing all previous steps, the following code represents a complete, reusable, and production-ready utility pipeline. It executes the full sequence from PDF parsing to sorted similarity evaluation against a target query.

```python
import os
import time
import logging
import pdfplumber
import pubchempy as pcp
from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import rdFingerprintGenerator