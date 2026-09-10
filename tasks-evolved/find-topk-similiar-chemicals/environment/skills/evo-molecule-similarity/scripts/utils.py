"""Utility functions for molecule similarity computation.

Provides functions for:
- Extracting chemical names from PDF files
- Converting chemical names to SMILES via PubChemPy
- Computing Morgan fingerprints with Tanimoto similarity
- Finding top-k similar molecules
"""
import warnings
warnings.filterwarnings('ignore')

import pdfplumber
import pubchempy as pcp
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import DataStructs


def extract_molecule_names(filepath):
    """Extract chemical names from a PDF file, one per line.
    
    Args:
        filepath: Path to PDF file containing molecule names
    
    Returns:
        list: List of chemical name strings
    """
    names = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.strip().split('\n'):
                    line = line.strip()
                    if line:
                        names.append(line)
    return names


def name_to_smiles(name):
    """Convert a chemical name to canonical SMILES using PubChemPy.
    
    Uses PubChem's online database to look up the canonical SMILES
    representation of a chemical given its common name.
    
    Args:
        name: Chemical name string
    
    Returns:
        str or None: Canonical SMILES string, or None if not found
    """
    try:
        results = pcp.get_compounds(name, 'name')
        if results:
            return results[0].canonical_smiles
    except Exception:
        pass
    return None


def smiles_to_fingerprint(smiles):
    """Convert SMILES to Morgan fingerprint.
    
    Uses Morgan fingerprint with radius=2 and chirality=True
    as specified by the task requirements.
    
    Args:
        smiles: SMILES string
    
    Returns:
        DataStructs.ExplicitBitVect or None: Fingerprint, or None if invalid SMILES
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, useChirality=True)


def compute_tanimoto_similarity(fp1, fp2):
    """Compute Tanimoto similarity between two fingerprints.
    
    Args:
        fp1: First fingerprint
        fp2: Second fingerprint
    
    Returns:
        float: Tanimoto similarity score between 0 and 1
    """
    return DataStructs.TanimotoSimilarity(fp1, fp2)


def topk_tanimoto_similarity_molecules(target_molecule_name, molecule_pool_filepath, top_k):
    """Find the top k similar chemicals in the molecule pool to the target molecule.
    
    Uses Morgan fingerprints (radius=2, chirality=True) with Tanimoto similarity.
    Results are sorted in descending order of similarity, with alphabetical
    ordering when ties happen.
    
    Args:
        target_molecule_name: Name of the target molecule
        molecule_pool_filepath: Path to PDF file containing molecule names
        top_k: Number of top similar molecules to return
    
    Returns:
        list: Top k molecule names sorted by descending Tanimoto similarity,
              with alphabetical ordering for ties
    """
    # Get target molecule SMILES and fingerprint
    target_smiles = name_to_smiles(target_molecule_name)
    if target_smiles is None:
        raise ValueError(f"Could not find SMILES for target molecule: {target_molecule_name}")
    
    target_fp = smiles_to_fingerprint(target_smiles)
    if target_fp is None:
        raise ValueError(f"Could not generate fingerprint for target molecule: {target_molecule_name}")
    
    # Extract molecule names from PDF
    pool_names = extract_molecule_names(molecule_pool_filepath)
    
    # Compute similarities for all molecules in the pool
    similarities = []
    for name in pool_names:
        pool_smiles = name_to_smiles(name)
        if pool_smiles is None:
            continue
        
        pool_fp = smiles_to_fingerprint(pool_smiles)
        if pool_fp is None:
            continue
        
        sim = compute_tanimoto_similarity(target_fp, pool_fp)
        similarities.append((name, sim))
    
    # Sort by descending similarity, then alphabetical for ties
    similarities.sort(key=lambda x: (-x[1], x[0]))
    
    # Return top k names
    return [name for name, sim in similarities[:top_k]]
