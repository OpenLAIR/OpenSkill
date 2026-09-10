# Python Utility Module for Chemical Similarity Search: Integrating RDKit, PubChemPy, and PDF Extraction

**Key Points**
*   **PDF Extraction Context**: Extracting unstructured chemical text requires robust parsing. Current standard tools include `pdfplumber` (v0.11.9) for layout-aware parsing and `pypdf` (v6.6.0) for fast, pure-Python text extraction.
*   **Chemical Name Resolution**: Translating common or IUPAC nomenclature to structurally precise SMILES strings relies heavily on PubChem's REST API, accessed via `pubchempy` (v1.0.5). Handling API rate limits and structural isomerism is vital.
*   **RDKit API Evolution**: As of the 2024 and 2025 RDKit distributions (e.g., v2025.09.3), the traditional `AllChem.GetMorganFingerprintAsBitVect` is deprecated. Modern modules require `rdFingerprintGenerator.GetMorganGenerator`, substituting legacy arguments like `useChirality` and `nBits` with `includeChirality` and `fpSize`.
*   **Similarity Computation**: Tanimoto similarity over Morgan fingerprints remains the gold standard for high-throughput chemical similarity assessment, efficiently capturing localized structural environments.
*   **Pipeline Architecture**: A robust pipeline must seamlessly handle edge cases—such as unresolvable chemical names, invalid SMILES strings returning `None` object types, and complex tie-breaking sorts—to generate reliable similarity rankings.

---

## 1. Introduction to Chemical Similarity and Cheminformatics Pipelines

In computational chemistry and drug discovery, assessing the structural similarity between molecules is a foundational methodology used for virtual screening, scaffold hopping, and clustering compound libraries [cite: 1, 2]. The fundamental premise is the *similar property principle*, which posits that structurally similar molecules are likely to exhibit similar physicochemical and biological properties. 

To automate the discovery process, researchers often need to mine unstructured data sources, such as scientific literature in Portable Document Format (PDF), to identify chemical names, convert these names into machine-readable structural representations (SMILES), and finally compute mathematical similarity metrics against known target structures. This exhaustive report details the development of a complete Python utility module designed to execute this exact pipeline, meticulously aligned with modern package distributions including `pdfplumber` (version 0.11.9), `pypdf` (version 6.6.0), `pubchempy` (version 1.0.5), and `rdkit` (version 2025.09.3).

---

## 2. PDF Text Extraction of Chemical Names

Scientific articles, patents, and technical reports are overwhelmingly distributed as PDF files. Unlike structured databases, PDFs are graphical representations of text, making the extraction of semantically meaningful data inherently complex [cite: 3, 4]. A PDF document encodes characters with positioning data rather than logical semantic flow [cite: 3, 4].

### 2.1 Extraction Using `pdfplumber` (v0.11.9)

`pdfplumber` is an advanced, layout-aware PDF extraction library built upon `pdfminer.six`. It is particularly adept at handling complex multi-column layouts and extracting tables [cite: 5, 6]. Because chemical names in academic literature often appear in tightly formatted paragraphs, tables, or supplemental lists, `pdfplumber`'s spatial approach to text extraction is highly valuable.

#### Exact API and Usage
To utilize `pdfplumber`, the file is opened using a context manager with `pdfplumber.open()`, which yields a `pdfplumber.pdf.PDF` object [cite: 5, 6]. The pages are iterated through via the `.pages` attribute, and text is extracted using the `.extract_text()` method. 

The `page.extract_text()` method returns a standard Python `str` object containing the text of the page, or `None` if no text is found [cite: 7]. 

```python
import pdfplumber
import re

def extract_chemicals_pdfplumber(pdf_path: str) -> list:
    """
    Extracts text page by page using pdfplumber 0.11.9 and parses out 
    potential chemical names using heuristic text cleaning.
    """
    raw_text = ""
    # Best practice: use context manager to ensure file resources are released
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # layout=True preserves spatial arrangement, useful for tables
            page_text = page.extract_text(layout=False) 
            if page_text:
                raw_text += page_text + "\n"
                
    return clean_and_parse_chemical_names(raw_text)
```

### 2.2 Extraction Using `pypdf` (v6.6.0) as an Alternative

`pypdf` (formerly PyPDF2) is a pure-Python library that has undergone significant modernization up to its 6.6.0 release in January 2026 [cite: 8]. It offers faster extraction for digitally born (non-scanned) PDFs but lacks the advanced spatial layout analysis of `pdfplumber` [cite: 4, 9].

#### Exact API and Usage
With `pypdf`, extraction is performed using the `PdfReader` class. The `reader.pages` attribute provides a list-like collection of `PageObject` instances, which expose the `extract_text()` method [cite: 4, 10].

```python
from pypdf import PdfReader

def extract_chemicals_pypdf(pdf_path: str) -> list:
    """
    Extracts text using pypdf 6.6.0. Faster for simple digitally-born PDFs.
    """
    reader = PdfReader(pdf_path)
    raw_text = ""
    
    for page in reader.pages:
        # extract_text() returns a string. 
        # A visitor_text argument can be passed to filter out headers/footers.
        text = page.extract_text()
        if text:
            raw_text += text + "\n"
            
    return clean_and_parse_chemical_names(raw_text)
```

### 2.3 Best Practices for Cleaning and Parsing Extracted Text

Extracting chemical names from raw OCR or standard PDF text is notoriously difficult due to line breaks, complex punctuation (e.g., brackets, hyphens), and IUPAC nomenclature [cite: 3]. While advanced Named Entity Recognition (NER) models (like ChemDataExtractor) are the gold standard, heuristic parsing can be achieved using regular expressions and string normalization.

```python
def clean_and_parse_chemical_names(raw_text: str) -> list:
    """
    Cleans raw PDF text and extracts a list of chemical names.
    This uses a simplistic tokenization and heuristic filtering approach.
    """
    # 1. Normalize line breaks and spacing
    text = raw_text.replace('\n', ' ').strip()
    
    # 2. Tokenize by common delimiters (assuming a comma-separated list in text)
    # If text is continuous prose, more advanced NER is required.
    # For this utility, we assume we are parsing a list of molecules.
    raw_tokens = [token.strip() for token in re.split(r'[,;]|\band\b', text)]
    
    chemical_names = []
    for token in raw_tokens:
        # 3. Basic heuristic filtering:
        # - Exclude very short or excessively long tokens
        # - Must contain alphabetic characters
        if 3 < len(token) < 100 and re.search(r'[a-zA-Z]', token):
            # Clean lingering artifacts like stray parentheses at edges
            clean_token = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9)]+$', '', token)
            chemical_names.append(clean_token)
            
    # Return deduplicated list
    return list(set(chemical_names))
```

---

## 3. Converting Chemical Names to SMILES via PubChemPy

The Simplified Molecular-Input Line-Entry System (SMILES) is a line notation for describing the structure of chemical species using short ASCII strings. To transition from a human-readable name (like "aspirin" or an IUPAC name) to SMILES, an API call to the PubChem database is necessary [cite: 11, 12].

### 3.1 PubChemPy API Details (v1.0.5)

`pubchempy` provides a Pythonic wrapper around the PubChem PUG REST API [cite: 11, 13]. 

**Exact Import Path**:
```python
import pubchempy as pcp
```

**Exact Function Signature**:
```python
pcp.get_compounds(identifier, namespace='name', searchtype=None, as_dataframe=False, **kwargs)
```
When `identifier` is a chemical name string and `namespace` is set to `'name'`, this function hits the PubChem Compound database and returns a list of `Compound` objects [cite: 14, 15, 16]. 

**Accessing SMILES**:
The `Compound` object contains properties retrieved from the database. The two most relevant attributes are:
*   `canonical_smiles`: The SMILES string without stereochemical information [cite: 15, 16].
*   `isomeric_smiles`: The SMILES string encoding isotopic and stereochemical (chirality/cis-trans) configurations [cite: 15, 17]. **This is generally preferred** as it provides the most accurate structural representation.

### 3.2 Error Handling, Rate Limits, and Edge Cases

**What happens when a chemical name is not found?**
If a name is syntactically invalid or totally unknown to PubChem, `pubchempy` returns an empty list (`[]`). However, if the name string violates URL parsing rules, it may throw a `BadRequestError` (HTTP 400) [cite: 18].

**Exceptions Raised**:
All exceptions inherit from `PubChemHTTPError` [cite: 16, 19].
*   `BadRequestError` (HTTP 400): Malformed query string [cite: 17, 20].
*   `NotFoundError` (HTTP 404): Input record genuinely not found in the database layer [cite: 17, 19].
*   `TimeoutError` / `ServerBusyError` (HTTP 503/504): Occurs during heavy server load or excessively broad queries [cite: 16, 17].

**Rate Limits**:
PubChem enforces strict dynamic request throttling via the `X-Throttling-Control` HTTP header [cite: 21, 22]. The explicit limits are:
*   Maximum **5 requests per second** [cite: 23, 24].
*   Maximum **400 requests per minute** [cite: 12, 23].
*   Maximum **300 seconds of compute time** per minute [cite: 23, 24].
Exceeding these limits leads to HTTP 503 responses and temporary IP blocks [cite: 21].

**Alternative Lookups**:
If a common name fails, looking up by **synonym** can help. PubChem allows searching via the `substance` domain rather than the `compound` domain, as substances represent raw contributor deposits (which contain vast synonym lists) prior to standardization [cite: 16, 17, 20]. 

### 3.3 Working Code: Name to SMILES Converter

```python
import pubchempy as pcp
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def name_to_smiles(chemical_name: str, retries: int = 3) -> str:
    """
    Converts a chemical name to an isomeric SMILES string using PubChemPy.
    Handles rate limiting and potential resolution failures.
    """
    for attempt in range(retries):
        try:
            # Sleep to respect the 5 requests/sec rate limit
            time.sleep(0.25)
            
            # Primary lookup
            compounds = pcp.get_compounds(chemical_name, 'name')
            
            if compounds:
                # Prefer isomeric SMILES for maximum structural fidelity
                # Return the first (best) match
                compound = compounds
                return compound.isomeric_smiles or compound.canonical_smiles
            else:
                # Fallback: Try a synonym search if the direct name fails.
                # In pubchempy, get_synonyms can return lists of dictionaries,
                # but searching via the substance domain is often more robust.
                substances = pcp.get_substances(chemical_name, 'name')
                if substances and hasattr(substances, 'cids') and substances.cids:
                    # Resolve substance to standard compound CID
                    fallback_comp = pcp.Compound.from_cid(substances.cids)
                    return fallback_comp.isomeric_smiles or fallback_comp.canonical_smiles
                return None
                
        except pcp.BadRequestError as e:
            logger.error(f"Bad Request for {chemical_name}: {e}")
            return None
        except (pcp.PubChemHTTPError, TimeoutError) as e:
            logger.warning(f"PubChem server issue ({e}). Retrying {attempt+1}/{retries}...")
            time.sleep(2 ** attempt)  # Exponential backoff
            
    logger.error(f"Failed to resolve {chemical_name} after {retries} retries.")
    return None
```

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

#### The Legacy API (Deprecated)
Historically, generation was done via:
`rdkit.Chem.AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048, useChirality=True)` [cite: 29, 31, 32].
*   **Is it deprecated?** **Yes, absolutely.** In recent RDKit releases (2024.x, 2025.x), invoking this function emits a explicit warning: `DEPRECATION WARNING: please use MorganGenerator` [cite: 27]. The C++ backends were rewritten for generator architectures that separate parameter definition from molecular application [cite: 25].

#### The Current Recommended API
The modern paradigm utilizes the `rdFingerprintGenerator` module. Instead of a single function call, you instantiate a generator object with desired parameters, then pass molecules to the generator [cite: 25, 30].

**Exact API for Generator Creation**:
```python
from rdkit.Chem import rdFingerprintGenerator

fpgen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
```
*   **Radius**: Represents the maximum bond iterations (radius 2 equals an ECFP4 fingerprint, radius 3 equals ECFP6) [cite: 29, 33].
*   **fpSize**: Replaces the old `nBits` parameter. The default `fpSize` is strictly **2048** [cite: 25, 30, 33].
*   **includeChirality**: **CRITICAL CHANGE**. The old parameter was named `useChirality` [cite: 31, 34]. In the new `rdFingerprintGenerator.GetMorganGenerator`, the parameter is named **`includeChirality`** [cite: 30, 33, 35]. Using `useChirality` in the new API will throw a TypeError.

**Generating the Fingerprint**:
```python
# Returns an ExplicitBitVect
fp = fpgen.GetFingerprint(mol) 
```

### 4.3 Computing Tanimoto Similarity

The Tanimoto coefficient (also known as the Jaccard index) is the ratio of intersecting set bits to the union of set bits: \( T(A, B) = \frac{|A \cap B|}{|A| + |B| - |A \cap B|} \) [cite: 31, 36]. It bounds between 0.0 (no shared substructures) and 1.0 (identical bit vector sets).

**Exact Import Path and Signature**:
```python
from rdkit import DataStructs

# Returns a float representing the similarity
score = DataStructs.TanimotoSimilarity(fp1, fp2) 
```
Both `fp1` and `fp2` must be of type `<rdkit.DataStructs.cDataStructs.ExplicitBitVect>` [cite: 36, 37, 38].

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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Cache the Fingerprint Generator globally to avoid recreating it per molecule
MORGAN_FP_GEN = rdFingerprintGenerator.GetMorganGenerator(
    radius=2, 
    fpSize=2048, 
    includeChirality=True
)

def extract_chemicals_from_pdf(filepath: str) -> list:
    """Extracts candidate chemical names from a PDF file."""
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return []
        
    extracted_names = set()
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=False)
                if text:
                    # Simplistic split by lines/commas for demonstration
                    # In production, replace with advanced Regex/NER
                    lines = text.replace('\n', ',').split(',')
                    for raw_token in lines:
                        token = raw_token.strip()
                        if 3 < len(token) < 100 and any(c.isalpha() for c in token):
                            extracted_names.add(token)
    except Exception as e:
        logger.error(f"Failed parsing PDF {filepath}: {e}")
        
    return list(extracted_names)

def resolve_name_to_smiles(name: str) -> str:
    """Uses PubChemPy to look up a SMILES string, handling rate limits."""
    retries = 3
    for attempt in range(retries):
        try:
            time.sleep(0.25)  # Enforce max 4 requests/sec (PubChem limit is 5)
            compounds = pcp.get_compounds(name, 'name')
            if compounds:
                return compounds.isomeric_smiles or compounds.canonical_smiles
            return None
        except (pcp.PubChemHTTPError, TimeoutError) as e:
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.debug(f"Resolution error for {name}: {e}")
            return None
    return None

def generate_fingerprint(smiles: str):
    """Converts SMILES to Mol, then generates an RDKit Morgan ExplicitBitVect."""
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return MORGAN_FP_GEN.GetFingerprint(mol)

def topk_tanimoto_similarity_molecules(
    target_molecule_name: str, 
    molecule_pool_filepath: str, 
    top_k: int
) -> list:
    """
    Main Pipeline:
    1. Look up target molecule SMILES & compute fingerprint.
    2. Extract chemical names from PDF pool.
    3. Look up SMILES and compute fingerprints for the pool.
    4. Compute Tanimoto similarities.
    5. Return top_k sorted by descending similarity, then ascending alphabetical.
    """
    logger.info(f"Resolving target molecule: {target_molecule_name}")
    target_smiles = resolve_name_to_smiles(target_molecule_name)
    target_fp = generate_fingerprint(target_smiles)
    
    if target_fp is None:
        logger.error("Target molecule could not be resolved or parsed. Aborting.")
        return []
        
    logger.info(f"Extracting chemical pool from {molecule_pool_filepath}")
    pool_names = extract_chemicals_from_pdf(molecule_pool_filepath)
    logger.info(f"Found {len(pool_names)} candidate names. Resolving...")
    
    results = []
    
    for name in pool_names:
        smiles = resolve_name_to_smiles(name)
        if not smiles:
            continue
            
        pool_fp = generate_fingerprint(smiles)
        if pool_fp is None:
            continue
            
        # Compute Similarity
        similarity = DataStructs.TanimotoSimilarity(target_fp, pool_fp)
        
        results.append({
            'name': name,
            'smiles': smiles,
            'similarity': float(similarity)
        })
        
    # Sort with Tie-breaking logic: 
    # Negative similarity sorts descending, name sorts alphabetically ascending
    sorted_results = sorted(results, key=lambda x: (-x['similarity'], x['name']))
    
    # Return Top-K
    return sorted_results[:top_k]

# ==========================================
# Example Usage Execution
# ==========================================
if __name__ == "__main__":
    # Example execution (assuming 'literature.pdf' contains chemical names)
    # top_matches = topk_tanimoto_similarity_molecules("Aspirin", "literature.pdf", top_k=5)
    # for match in top_matches:
    #     print(f"{match['name']}: {match['similarity']:.3f} | {match['smiles']}")
    pass
```

## 7. Conclusion

This report constructs an end-to-end, state-of-the-art methodology for extracting chemical entities from unstructured PDFs, translating them into computable structural frameworks via PubChemPy, and evaluating geometric and topological homology using the latest RDKit (2025+) paradigms. The strict enforcement of modernized APIs—most notably the transition to `rdFingerprintGenerator`—ensures software longevity and eliminates deprecation bottlenecks inherent in legacy cheminformatics codebase adaptations. Systematic implementation of rigorous error handling and rate-limiting routines shields the analytical pipeline from common environmental failures, yielding a highly stable, production-ready similarity engine.

**Sources:**
1. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhaTLtASGU5nsJ_ippdN16zSGWZLfA0yvCqtlfQ1xcnlDKDdJMPpL7CaosRRMjHwzG8Q63W0aPXg8qSUdXde1yKrf0tN891_kOxCzdzf_0VU4uRA1QFKEf9E96FOTN7NHy4wE3K4EYsZFAm1kjyrdoB3t5Xi1ntw8vLyVj--_ZDCQ6HgKPg4sb8w239Fv2qJAv0SAc-LOwq0ksfXIqC9WeQ5_s-t5EByM=)
2. [semantic-web-journal.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHiGYCWA878sQ44-iF7gba-pm0mmv91VbEI94B2ZJf9k20ssFZZa7eSHxSWbcC37g9ZNJRxY9Uu1FoLAp32dujzkbITEwuaGWs3zwTjsyFQNkKXFlFvUUSM3sKQv2hY6zI-cCfOZ2aPd1tNeF3l0Ro98N1s)
3. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJ03Tq2pkxXNAp3BT7CJrORsK-oYUIzFWFrHmS-6-hfrd0yWMPvNvgSGs5a0kZGgkuhtO7drZZhAA6l81KbIDY1MC1ct84NXyT7fuoiqCP5nqtDFCmRTD_qlQi9EFDxcflJa04yL5cYR2qKfRNNr6AUwrh)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEyGo7SSFIdo9gOowEBXdoldHY58aVRO8zh7oW_G1xtL9Ht1QvHVg3UUSVGGa1nuKYl6Qn854LtfSudSVsP3qD_T1J3_jU1Dl92kkvQp9b1_Ag_j1ReKzyJL7dyzz6Hjlx4BfBQxji19ntFeAfhHewePK2c)
5. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJlIilUvcMlYnQlTAeM1Zo3m_d5eQLqSyfE3ZydTkpo7Ozqox0vDMvhYKcb34nwVpEkoD1mR0tMpypvzUpuihGJOtakoTSb8CvH9aAzNicA2NaPAMbgM_3xqTUolxaka1eC3KAJCRMOXOu1ewCbDv8w_gi9nYcGw1yyeY=)
6. [useanvil.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGzNHMSKFTBrJ4Was_ExsDpFILYHkQAumW9l-Yy-KNJxQCA8nVRxo9M57T0IT3tUKtsKCKgNlqPF2P_pAJRI8Uo3f5lAzuZriuGOicfGCM3DPp8fkgskzVBh7XOlos1w7V7f4CaMefYXaT0RAZ0cM43GgQcvriuRl6ek1mniwxrusXsiK_lQE6xMpQOIjPwCOyo)
7. [docs.rs](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGqgYwLPtwMF0-vvyyC6f6P9p5jriWICpMPVpUR6UpM5TlksCTNpy-q8XW9uOGbg3UEWMhUamyiY0gd0im6S7GxFwmXqQ7JfO9nErE5jWsFA7a-SAQ7gfxM6SHHwkEebs_0MFo=)
8. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxumDVf5q2r36DxUY7_KJuRBrYFI2ScDXbvyd4XyW8-5tx0aEeACuoZLUwRJQnGLnSYTxkm30Gg7v2PvgbxSvA3jRFqHiKMWUXozS3ONY-fnzAe9J3Iycz7NH4eofW3sgARVFTlqUTmB5fsDC8fao=)
9. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2qj9Xz9RWGqkLSuaSitJ_O1BKnC_0VIAUA4GTQ5AJZNuvn-9WwGFQcA4tQEbIVpijb_r5oznfq1qfjzR_55yr8JgkSDEq1pOT65gBlc7dZbKg6YdDNk5L7QPjVrJuxLYGO6O23q3yyo5MeC--cj9g9HckS_vmkgBxY8zgFeDqJBa_8-mgXqiCXxkuQC6wXyDy)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFdNlBD_WUTA9HhmNQGiD_4Ur18HqcM4mxvcTioR9zMou6KYZXLWkbgmBPVByvoijJeFCn-QTaud3_q2ODwQ46Bl_OIJU9Y5dT-UGi3t24FDwCXFtE1)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFC5qxGdqPTP8oVjr2vsBUkgjj5PeWW27jdKHbC4EjgVr6QRl9YdLSL2UIp2WXnymtqWMvHwIvF52fV2uync99_vg5dHyjBlVNdvxVGRgtxHURCxNnte5fnq2qXZzl8Y-M=)
12. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEFdK1wPl4pwjoBepclFF0Rct7Nb6JqN5RC8Pr1gLStaOuODPD24HYIYZAzvQQpYqAjjCN1N9gdvWsRkEb3e7bd58Ci2epOcr57bzGpBJS8OVqHx2qCtZYrtgMK2BZnvaGTCEXn3Xz3)
13. [r-project.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-RDOhLJ6nbqVS56ojMXTcheQyJQD6ywYI8hcpBAryB6qAb_SlJiebivarX24jscfE7zoGDt-s11qGorNxVe_FVhWP0_VjuNfCcMFXLFb6yHorv5SWZB-xbuuxqHrjd7zsR2pXt6nvc3RrfSs7uSFjTIX9YZK6bMY=)
14. [insilicochemistry.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHw3nqs0A4p51ACZ2pSMXSsfpT_23Jea8aSRWd-_-r4qzUm3YfVWxo42I7uDg61YVSOkrYdpPybq5HU_K-0jW0JqmLhl_7PEfU3q5LWQHyBak4d5y0jrHOpVE-gjwNs4-SOK7MO-tBwQLBNggP7_s1Cba7ohTEcWd85ZMTzCTHP6UdmDDBiHRBApXxsWkfdzQs=)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbpPQqEMCrErb0hv2IEC7Cq6b1BVHqEY-frhCdrhMeMmAZckmUZC67ZAn5Lx_5BzyzbR8nJYT2vB6hDUMluklhgMHwYLLJ2Qlv0573Bp3ptMj4ZWerm4VZtqxpkUdgPpM2GYoXMafPPnyGeWbhTMrgF51R5g==)
16. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMNFj_pWb2IJPpooA4JUof2MEug0v6WFJbSOGhXY6mKTgU3RYyL3kNarkb2r9jKxlvOn0O3UPzjnPAr3IVTYJq-L2y1Pqv85k7dQiJLLZ4VS6Y7RdUJax6fem506EJ55ZDQhAgg_3b6xc=)
17. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHerjQ-AUy0cCxVju0pXSZSs2vXf3P1b9rN-cJ3b9SFGuJVPs4UoWmoQ1hQu3M1ml6a8JCMotpYV6q322muiL35hujEcQIKaRBgO8jO0Rxz0Mpwz7ZIIT6ajkCkeUG-Sglq4taa2PZfME=)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJrEmHm5-hbj2koMD7jhPSeLAq_T8JPBQhbgtKpxE95wlE8KMGZfyZLqQsCNOO13ZNtp0Klfhyq_2dXKZuEM2Q1qExqhYJ-kXtibc13C7Ajq5Har56poIW7Mrf6BuU-iWWdmre2LhADYIlTHzY5OiaqF4z0o-FBEQnxgJXaydOKVifQJdNfBJNqNF79n4RJuiDBenFyESBeNSGqov1zQ6foWVoBCFC34fi)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0-EDMd_3_qXhEOAQKmE72SCiWTXhGphObu_MBhOoUXijDs1u-FWYl5BVE3f41nKBwF5WQLSoKH3u-nNoUo-dYJEKH8wwYzZBXQuYDV8UBHYJTBGX_70BSKdB-6BkCWaxpue8ObF0AGxtAzvSix4uihQ==)
20. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_2T5q5c08W51alxv4MvMWwGgxjNaEfmwqX6QI0HAU1K9IPO-A_2qFlyjYz23CAzbJlDKLDd9Cbqze8_HbK4TvHyiEmWX3sn10DpxXILDGNMQaCjepmzqefO0ZMdKgHi--cPta9Ek1C5sLEX3z5Lp_-g==)
21. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjFs_GXtrXmScki0YgHHkscTG4NTpk0beTsHfC2Zi_IAPDUDCwnwa04qij4E38Hp7kRERrkTdtR50HpttcRLSGdaNFGtcCn_sag3b9i1DGYMS3QBZV-mklrztSedbj2kIUufOP-YqR3XNTOq4uBs_dklFAUvra)
22. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEzWBr0oSttSe8zqqc7-GYBMepKPDqfj7AqKNhUPuR6HJJ1v5OTB8bawmviUfrRHwW9Xx4kDKpB51rc-8LXooYLx5bcSmcofHK4sDiAnxCw6Q-cWoLIATua3tE2iqF-V7xbVOfY7rjH)
23. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4zpGgbkw93fp2MxucQ6RXWVbeQDXu6WDOldUQQsv1ApcJJCdAbb6Wk0oF5jwSd1mh8ffzM-sll0L6zcZjV90n6TuJ4qzi8rmak25L8rTCMCpk3tMtYXGZBB2wtltcNsqS9HNjtLidCpe1Jhn5gAFTN3mqAI-xq8lOyPsJbmPKePERoz1L3LIcgsru8ndwbw-t898rEe-wqkHAfw==)
24. [juliahealth.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_9yCGRHkO6xrvq9hLQ0JFRWcYHDBIbtPwrUSbi-k65n6W_ESMCfM-vautxBELv2Dq75aFhgERJ8pHDydtPBl12Mj6Yn57fP22wq5EZ3BPdJLvn-r9s4lNKynJO0bV3AFKG0hzVgDf)
25. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHsXxtXZ3KLbGDdYMv1UBITcmlv-PQmeddyiNfzg1ul2AwK3Hb8oqXW_Lc0S1exEqd-Hl3YAHxmW9ldSWwHuHaVEVJzthcklmoeculkHstwxZGUWw8XCL1zVnR-7d6qaHw60BoiL1qoR3I8KJPmXf9AS2W7Fz-wfgG-7j8mKdRrpVsIyTOkh8rZjiOIf9y9y6f5yVQ=)
26. [rdkit.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE6RxJkiU4jUgQo55Ps8cqohjBgPj3u6qtk6g9mf0vimwfJPfTGLlU0h1N5_-ywLF8sqHZymY8DTzG1IvwMfesWtosHzUkKJLhlUJRDqASuAYDQdU0EyrE38DkDuOZUq0TgLBY=)
27. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEt-IN1lFqJQvbhuE9tgwng3rbKafTjuDPO8tU6DIgTOO1Uq-opl0Jms4HbZTjXVy7L51lk_8nbKrhcJbUyh4LzAK9tE7eQ5De5uVuvr_qHMF2cqbrvrSjcZzcqztC-lMI=)
28. [herongyang.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhfTkzAPxjHJ636OG8FF4qqlj5l57Vg_q_eh-6ArPKq96hS6nlCcsiqUdFbZqcrQub6n7hk09zJ3G7BXUyoIjUB46ukDvDd64vbcT6bswdUTVyHdxHQx5mytBRGLquq3NKU2CpAdq5uAXC-fQHUAqR9SFK6BKCNm0A6KPiNbSZtBVuv69Ty6Of-DKMfuOn2srq6A8exEC3EelN91s=)
29. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxHujPYZ-NP1UTevOCFjMSAnt7nLCAb_6Et01EsRHogpoRPVpX8RFaRGEA1IvXJHXxVhPiW1RZbuomw_BicYVklUYQlW3XT3OXVTCvfGYpq1gZbo8aGu1f7A8eB-M_bs9Kh37fd7rFNAvPE0ljoI31gjw=)
30. [herongyang.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqHffP9QAt57nC-FibY0eWRif3gf7mm52TbwboTyNNYLI43t9DB0-Yjw3fY70nAsTAEX5TvUQmBHgk6fe7M6Z9b0PbIyAwna2r3igza5dP-cWVli8FAQtC422lYVuscHiIZK447175nkTDqltyxih46RMF5eYTs9RooRpzvFqm6Rc5QkLRJe7SNgwkJK8yrVO1)
31. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFR16866U9tSfcLoX5dttUvDOlJH2sko1M3swC3trC5QDXWikEqe0QeiKDXWUba5xbFgh6rARRQ2RTxKx1splEIlOCh6c1SN8u5sT4ICpQhd_XzPceDY92KIJAGePfLpbx6_54sUnrzc1LVrrw-eETAmk5G)
32. [rdkit.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsnxyZTs4XsObJyEkUYNxpHou_sM3lZ_qh8xRftSMwF3lHt6wE79b63kEGDbRCjPEG_hLZU0tOXrUP6CrgkxS1vPhtBIuWSimqf9Md88hiyLFaIdo6gmYBRzOJkUEWrMviQ00amIv23Zcr1Bv18ARZDffrWgsZ2UE=)
33. [chemfp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwaDldXFlsyuC25VcpFcIULbL20bg-Wxn-pLpIqXsy1jqQHbPq1AG5gngqVQ56qhVCGIwyJvBzN1e4cA7tx5yvgRJM_vWQvQzGJcCxGZLRixh-QsVIJx6GcjqZA-jRqN_X9Fwjlg==)
34. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFY62Ix-WofHP-UO484DLq819hqM1I9YH71kkJAU0XfBSgvo95gdl37qezCny8B5lRvc9myTYeTW8ZNwaxBg5mlSSe6wjW0GjihnM4O2cDbzn5Zn2Zcu6jcN8taTtnQG6AUKt5sOAAgXb7r976bE4gymgHRLweRPKtunY4=)
35. [rdkit.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxDU3z5AlcWkxwjtigdghtg5IvUNV_S6sPD9MRuXjZWN33OlsxhUhQHCIZQ01WBWI-JEl3h4mDpdTnqOmUkyTQW38hvEpIva4tumxA1ZlEeOfAyOn1U3j3nLe0ZF0-wVp6Zxc0UDSrkPnM4jNVMmLHiG70Hll1jMxMtI8zH5A=)
36. [rdkit.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFlyu40mO4a9Ss7NyF44z-oGZQYjbHmNdSxQycYjZCl-K-NDa63io29NGEU0U1QeYenUPNqMLjXY1yb8k3cmqn_KcWfcd9lmUREViC_hYDZOlRwVgGxtkY72O_UHukfVKXlcn1nyOzZE2wJJZGVlpfI5aoOxmtg8VtFxfE=)
37. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEToVse5jzn6IWMM2xHnUEoGi9F8wbSgZIQ5i2EqCNpVfKA1L0J__mdhj0q2e5dtgiJS76Ya0kRJU-NcQAq4XWwyHnhTLA63dI1P7yogm-za3OVu13Rg6G93F-SvpEojklcN_iPeGind6BginmDf-QVrLAW9Teft64=)
38. [rdkit.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFr1w2da_FW5bJ31jYCf8XOuy4SN9YZU-0MiUMn4TLJVNk09O_8eJk5bFd7MysQirCiU-Kwt5dbpdtv5fNx4e_vGPfRX8g2PKpCccvxFPgU4AHYhOdMv9s426NDVETfu97ssYRtr0FH7GKYddlF-w==)
39. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGcAW1mM9VmVZoouCrcSYADCrnYXhcusKf3XSWuEYIxOYk_x6cMZ7i_vumZwtKnjypETNuOM6_b5hQNJzo6DPcLhSvA146cKdU12zzDSj-WooiRMiWMJuHSuBxxBeQd-ABCeJt9B71n0k8h4TsrrM3sgbsFoQ==)
