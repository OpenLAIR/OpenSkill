# Domain Reference for evo-chem-pdf-extraction

**Responsibility**: PDF text extraction, chemical name parsing/cleaning, and chemical name to SMILES resolution via PubChem API. Does NOT compute similarity.

**Key functions to implement**: extract_chemicals_from_pdf, resolve_name_to_smiles, clean_and_parse_chemical_names

---

## 2. PDF Text Extraction of Chemical Names


Scientific articles, patents, and technical reports are overwhelmingly distributed as PDF files. Unlike structured databases, PDFs are graphical representations of text, making the extraction of semantically meaningful data inherently complex [cite: 3, 4]. A PDF document encodes characters with positioning data rather than logical semantic flow [cite: 3, 4].

### 2.1 Extraction Using `pdfplumber` (v0.11.9)


`pdfplumber` is an advanced, layout-aware PDF extraction library built upon `pdfminer.six`. It is particularly adept at handling complex multi-column layouts and extracting tables [cite: 5, 6]. Because chemical names in academic literature often appear in tightly formatted paragraphs, tables, or supplemental lists, `pdfplumber`'s spatial approach to text extraction is highly valuable.

### 2.2 Extraction Using `pypdf` (v6.6.0) as an Alternative


`pypdf` (formerly PyPDF2) is a pure-Python library that has undergone significant modernization up to its 6.6.0 release in January 2026 [cite: 8]. It offers faster extraction for digitally born (non-scanned) PDFs but lacks the advanced spatial layout analysis of `pdfplumber` [cite: 4, 9].

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