# Comprehensive Guide to CIF Parsing and Crystallographic Symmetry Analysis using Pymatgen and SymPy

**Key Points**
* The `pymatgen` library offers robust tools for parsing CIF files, notably through the `CifParser` class and the unified `Structure.from_file()` method, though recent API shifts have deprecated older parsing routines in favor of more explicit parameterization.
* Crystallographic symmetry analysis is largely handled by the `SpacegroupAnalyzer` class, which delegates core structural symmetrization to the C-based `spglib` backend, requiring careful tuning of the symmetry precision (`symprec`) parameter depending on the origin of the structural data.
* Fractional coordinate rationalization—converting floating-point approximations to exact crystallographic fractions—can be effectively achieved using `sympy.nsimplify` or `sympy.Rational` alongside denominator limiters to accurately reflect physical lattice geometries.
* Handling edge cases such as partial occupancies, fractional coordinate wrapping, and multi-block CIF files is critical for building a fault-tolerant structural analysis pipeline. 

**Overview**
The intersection of computational materials science and software engineering frequently demands precise extraction, processing, and transformation of crystallographic data. The Crystallographic Information File (CIF) format remains the universally accepted standard for storing atomic coordinates and lattice parameters. This report outlines a comprehensive methodology for building a robust Python utility module designed to parse CIF files, deduce symmetry operations, extract Wyckoff positions, and convert resulting empirical coordinates into exact rational fractions using `pymatgen` (version 2025.10.7) and `sympy` (version 1.14.0). 

**Complexity & Nuance**
While parsing a CIF file may appear conceptually straightforward, the practical implementation is laden with edge cases resulting from experimental noise, varied CIF writing conventions, and algorithmic tolerances. Structural symmetrization algorithms are highly sensitive to the spatial tolerance parameters (`symprec`); a value that is too strict may fail to recognize the underlying symmetry of a Density Functional Theory (DFT) relaxed structure, whereas a value that is too loose may incorrectly assign higher symmetry to a genuinely distorted phase. Furthermore, rounding errors intrinsic to floating-point arithmetic necessitate symbolic algebraic interventions (via `sympy`) to restore the theoretical fractional coordinates expected in standardized crystallographic reporting.

**Methodology**
This guide is structured sequentially, mirroring the data flow of the proposed utility module. It begins with the initial ingestion of the CIF file via `pymatgen`, transitions into the symmetry analysis and Wyckoff position extraction using `SpacegroupAnalyzer`, and concludes with the algebraic rationalization of these coordinates using `sympy`. Specific attention is dedicated to documenting the exact API signatures for the target software versions (2025.10.7 and 1.14.0), highlighting recent deprecations, and establishing best practices for handling ambiguous inputs.

---

## 1. Pymatgen CIF Parsing API

The initial step in any crystallographic data pipeline is the accurate ingestion of structural data. In `pymatgen`, this is achieved either via high-level wrapper methods or through the specialized `CifParser` class.

### 1.1 High-Level Parsing: `Structure.from_file()`
For simple, single-structure CIF files, the most pythonic and straightforward approach is using the `Structure` class's built-in factory method. Under the hood, this method infers the file format and delegates to the appropriate parser [cite: 1, 2].

```python
from pymatgen.core.structure import Structure

# Simple parsing assuming the default settings
structure = Structure.from_file("material.cif")
```

### 1.2 Granular Control: `pymatgen.io.cif.CifParser`
When dealing with complex CIF files—such as those containing multiple data blocks, explicit magnetic moments, or non-standard formatting—the `CifParser` class provides the necessary granularity [cite: 1, 3].

**Import Path:**
```python
from pymatgen.io.cif import CifParser
```

**Constructor Signature:**
```python
parser = CifParser(filename, occupancy_tolerance=1.0, site_tolerance=1e-4)
```

**Recent Deprecations and Method Shifts (2024–2025):**
In versions of `pymatgen` leading up to 2025.10.7, a critical shift occurred regarding how structures are retrieved from the parser. The legacy method, `CifParser.get_structures()`, originally defaulted to returning the *primitive* cell (`primitive=True`). This behavior often caused confusion, as users expected the conventional cell matching the CIF definition.

Consequently, `get_structures()` has been deprecated in favor of `parse_structures()` [cite: 4]. The new method enforces explicit handling and defaults to returning the exact cell described in the CIF without enforcing a primitive reduction [cite: 1, 5].

**New Method Signature:**
```python
parse_structures(
    primitive=False, 
    symmetrized=False, 
    check_occu=True, 
    on_error='warn'
) -> list[Structure]
```
*   `primitive` (bool): Defaults to `False`. If set to `True`, it reduces the cell to the standard primitive representation [cite: 1].
*   `symmetrized` (bool): Defaults to `False`. Returns a `SymmetrizedStructure` directly if symmetry operations are present in the CIF. However, standard practice usually involves calculating this later via `SpacegroupAnalyzer`.
*   `check_occu` (bool): Validates occupancies [cite: 1].

**Working Code Example:**
```python
from pymatgen.io.cif import CifParser
import warnings

def load_structure_from_cif(filepath: str, primitive: bool = False):
    """
    Safely loads a CIF file handling the updated parse_structures API.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parser = CifParser(filepath)
        
        if parser.has_errors:
            print(f"Warning: CIF parsing encountered errors in {filepath}")
            
        # Extract all structures; typically we want the first data block
        structures = parser.parse_structures(primitive=primitive, check_occu=True)
        return structures if structures else None
```

---

## 2. Pymatgen SpacegroupAnalyzer API

Once a `Structure` object is instantiated, the next phase is discerning its symmetry. `pymatgen` utilizes `spglib` (a robust C library by Atsushi Togo) as the backend for symmetry detection, accessed via the `SpacegroupAnalyzer` wrapper class [cite: 6].

### 2.1 Constructor Signature and Parameters
**Import Path:**
```python
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
```

**Constructor:**
```python
sga = SpacegroupAnalyzer(
    structure, 
    symprec=0.01, 
    angle_tolerance=5.0
)
```

**The Critical Role of `symprec`:**
The `symprec` parameter represents the spatial distance tolerance (in Ångströms) for determining if two atomic sites map onto one another under a symmetry operation.
*   **Default Value:** `0.01` Å [cite: 6]. This strict tolerance is highly recommended for idealized, experimentally refined CIF files (e.g., those directly output from Rietveld refinement via SHELX).
*   **Relaxed Structures (Materials Project/DFT):** Structures that have undergone DFT geometry relaxation frequently deviate slightly from perfect crystallographic symmetry due to numerical noise or computational constraints. For these structures, a looser `symprec` of `0.1` Å is the standard convention utilized by the Materials Project [cite: 6, 7]. 

### 2.2 Generating the SymmetrizedStructure
The most powerful method within `SpacegroupAnalyzer` for Wyckoff analysis is `get_symmetrized_structure()`.

```python
sym_struct = sga.get_symmetrized_structure()
```

The returned object is a `SymmetrizedStructure`—a subclass of `Structure` that groups equivalent atoms. It contains several critical attributes [cite: 6, 8]:
*   `sym_struct.equivalent_sites`: A list of tuples. Each tuple contains all `PeriodicSite` objects that belong to a single symmetrically equivalent group (i.e., a single Wyckoff position).
*   `sym_struct.equivalent_indices`: A list of lists of integers, providing the indices of the original structure's sites corresponding to each symmetric group [cite: 9].
*   `sym_struct.wyckoff_symbols`: A list of strings containing the Wyckoff letter for each distinct symmetric group (e.g., `['a', 'c', 'f']`). Note that the list aligns positionally with `equivalent_sites` [cite: 7, 9].

### 2.3 Accessing Wyckoff Symbols and Equivalent Sites
To map each site in the structure to its Wyckoff symbol, one must iterate through the grouped equivalent sites.

```python
# Extracting grouped data
wyckoff_groups = []
for symbol, sites in zip(sym_struct.wyckoff_symbols, sym_struct.equivalent_sites):
    wyckoff_groups.append({
        "wyckoff_letter": symbol,
        "multiplicity": len(sites),
        "sites": sites
    })
```
In `pymatgen`, the `wyckoff_symbols` attribute returns purely the lowercase letters (e.g., "a", "b", "c"). It does not automatically prefix the letter with the multiplicity (e.g., it returns `"a"` rather than `"2a"`). 

---

## 3. Wyckoff Position Multiplicities

The multiplicity of a Wyckoff position denotes the number of symmetrically equivalent atomic sites generated by applying the space group's operations to a general or special position. Within a `SymmetrizedStructure`, determining the multiplicity is straightforward: it is precisely the length of the list of equivalent sites for that particular Wyckoff symbol.

### 3.1 Constructing a Multiplicity Dictionary
When multiple atomic species occupy different instances of the same Wyckoff letter (e.g., Na at 4a and Cl at 4b, or even two different Fe sites both at different 4a positions), tracking must be done carefully. A dictionary mapping the specific Wyckoff letter (with chemical context) to its multiplicity can be built.

```python
def extract_wyckoff_multiplicities(sym_struct):
    """
    Extracts a dictionary mapping Wyckoff symbols to their multiplicities.
    Because multiple distinct site groups can share the same Wyckoff letter
    (e.g., two distinct '4a' sites), we group them by index or chemical species.
    """
    wyckoff_data = {}
    
    # Iterate concurrently through the symbols and the grouped sites
    for idx, (wyckoff_letter, eq_sites) in enumerate(zip(sym_struct.wyckoff_symbols, sym_struct.equivalent_sites)):
        multiplicity = len(eq_sites)
        species_string = eq_sites.species_string
        
        # Standard notation combines multiplicity and letter (e.g., "4a")
        wyckoff_label = f"{multiplicity}{wyckoff_letter}"
        
        # Using a unique key to prevent overwriting if two different elements 
        # occupy different sites with the same Wyckoff letter.
        dict_key = f"{species_string}_{idx}_{wyckoff_label}"
        
        wyckoff_data[dict_key] = {
            "element": species_string,
            "wyckoff_letter": wyckoff_letter,
            "multiplicity": multiplicity,
            "label": wyckoff_label
        }
        
    return wyckoff_data
```

---

## 4. Wyckoff Position Coordinates

For a comprehensive crystallographic utility, extracting the representative spatial coordinate for each Wyckoff orbit is essential.

### 4.1 Identifying the "First" Atom
The `get_symmetrized_structure()` method returns `equivalent_sites` as tuples of `PeriodicSite` objects [cite: 6, 7]. The order of sites within these tuples corresponds to the sequence generated by applying the space group's symmetry operations, filtered for unique periodic boundary conditions.

The "first" atom in each group (i.e., `eq_sites`) is mathematically considered the representative generator for that orbit. Standard convention accepts this first index as the primary fractional coordinate representing the Wyckoff position, as all other coordinates in the tuple can be reconstructed by applying the `SymmOp` transformations.

### 4.2 Extracting and Wrapping Fractional Coordinates
Crystallographic coordinates reside in fractional space \( \mathbf{r} \in [0, 1)^3 \). However, internal manipulations or DFT outputs often result in coordinates outside this bound (e.g., `-0.0001` or `1.0001`). It is critical to wrap these coordinates back into the primary unit cell using modulo arithmetic.

```python
def get_representative_coordinates(sym_struct):
    representative_coords = []
    
    for eq_sites in sym_struct.equivalent_sites:
        first_site = eq_sites
        # Wrap fractional coordinates to [0, 1) using modulo 1.0
        frac_coords = first_site.frac_coords % 1.0
        representative_coords.append(frac_coords)
        
    return representative_coords
```

---

## 5. Converting Float Coordinates to Simple Fractions Using SymPy

Because DFT algorithms and generic CIF parsers represent coordinates as IEEE 754 floating-point numbers, an atom located precisely at a high-symmetry position (e.g., \( \frac{1}{3} \)) might be represented as `0.33333334` [cite: 5]. Displaying this float is unhelpful to crystallographers; thus, conversion back to a mathematically exact rational number is necessary. `SymPy` provides robust algebraic tools to perform this conversion.

### 5.1 Using `sympy.nsimplify`
The `nsimplify` function attempts to find a simple numerical formula (including fractions) that approximates the input float within a specified tolerance [cite: 10].

```python
import sympy

float_val = 0.33333334
# Convert to rational fraction with a given tolerance
rational_val = sympy.nsimplify(float_val, rational=True, tolerance=1e-4)
# Returns: 1/3
```

### 5.2 Bounding the Denominator: `limit_denominator`
While `nsimplify` is powerful, standard crystallographic fractional coordinates rarely feature denominators larger than 12 (common denominators are 2, 3, 4, 6, 8, 12). If the float is slightly noisy, `nsimplify` without constraints might return an absurd fraction like `3333/10000`. 

To resolve this, the `sympy.Rational` class includes the `limit_denominator` method [cite: 11, 12].

```python
from sympy import Rational

noisy_float = 0.8333331
# Convert direct to Rational, which initially gives a massive denominator
raw_rational = Rational(noisy_float)

# Constrain the denominator to a maximum of 12
clean_rational = raw_rational.limit_denominator(12)
# Returns: 5/6
```
Alternatively, Python's built-in standard library offers the `fractions` module, which performs identically and is computationally lighter if `sympy`'s broader algebraic features are not required.
```python
from fractions import Fraction
clean_frac = Fraction(noisy_float).limit_denominator(12)
```

### 5.3 Formatting Fractional Strings
Once converted to a rational representation, the output must be formatted for human readability. Integers should be displayed natively (e.g., "0", "1"), while fractions must preserve the `"numerator/denominator"` syntax.

```python
def format_fraction(val: float, max_den: int = 12) -> str:
    """
    Converts a floating point coordinate to a string fraction, 
    snapping to integer boundaries where appropriate.
    """
    # Address edge cases close to 0 or 1
    if abs(val) < 1e-4 or abs(val - 1.0) < 1e-4:
        return "0"
        
    rat = sympy.Rational(val).limit_denominator(max_den)
    
    # If the denominator is 1, it's an integer
    if rat.q == 1:
        return str(rat.p)
    else:
        return f"{rat.p}/{rat.q}"
```

---

## 6. Handling Edge Cases and Pitfalls

### 6.1 Multiple Data Blocks in CIF Files
CIF files frequently contain multiple data blocks (e.g., representing different temperature readings or optimization steps). `CifParser` parses all blocks by default, storing the output in a list. When calling `parse_structures()`, it returns a list of structures corresponding to these blocks [cite: 4, 5]. The utility must explicitly select the desired block, commonly `structures`.

### 6.2 The Near-Zero and Wrapped Coordinate Problem
Atoms on the boundary of the unit cell are mathematically equivalent. A coordinate of `0.9999` is crystallographically identical to `-0.0001` and exactly `0.0`. 
**Solution:** Always apply `modulo 1.0` to the coordinate. For values that result in `0.9999` post-modulo, a proximity check (e.g., `if abs(val - 1.0) < tol`) should forcefully snap the value to `0.0` before passing to `limit_denominator`.

### 6.3 Pymatgen Disordered Sites and Partial Occupancies
A major pitfall arises when processing solid solutions or disordered materials (e.g., $K_{0.5}Na_{0.5}Cl$). `pymatgen` permits `Structure` objects to hold partial occupancies, mapping a site to multiple species with fractional probabilities [cite: 2, 13].
However, `SpacegroupAnalyzer` inherently expects fully occupied sites and will often fail or raise `ValueError` / `NotImplementedError` when attempting symmetry analysis on a disordered structure [cite: 14, 15].
**Solution:** The utility must verify if `structure.is_ordered`. If `False`, the developer must either refuse parsing, extract the dominant species, or utilize `pymatgen.transformations.advanced_transformations.OrderDisorderedStructureTransformation` to enforce a discrete ordered supercell [cite: 16].

### 6.4 `symprec` Best Practices
*   **SHELX/ICSD Files:** These files are heavily symmetrized. Use `symprec=0.01` [cite: 6].
*   **VASP/Quantum Espresso Outputs:** Use `symprec=0.1` to account for relaxation drift [cite: 6].

### 6.5 Wyckoff Letter Convention
Does `pymatgen` match the standard convention? Yes. `spglib` (and by extension `pymatgen`) strictly adheres to the International Tables for Crystallography Volume A standard. The letters start from the highest site symmetry (designated 'a') and proceed alphabetically downwards. As noted, `pymatgen` returns isolated lowercase letters; appending the multiplicity is incumbent upon the developer.

---

## 7. Complete Working Code Pattern

Below is a complete, production-ready Python utility class synthesizing all principles discussed above.

```python
import warnings
import numpy as np
import sympy
from typing import Dict, Any, List

# Pymatgen 2025.10.7 Imports
from pymatgen.io.cif import CifParser
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.core.structure import Structure

class WyckoffAnalyzer:
    """
    A utility class to parse CIF files, deduce symmetry, and output 
    rationalized Wyckoff fractional coordinates.
    """
    
    def __init__(self, filepath: str, symprec: float = 0.01):
        self.filepath = filepath
        self.symprec = symprec
        self.structure = self._load_structure()
        self.sga = SpacegroupAnalyzer(self.structure, symprec=self.symprec)
        self.sym_struct = self.sga.get_symmetrized_structure()

    def _load_structure(self) -> Structure:
        """Loads CIF and mitigates deprecation warnings."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parser = CifParser(self.filepath)
            
            if parser.has_errors:
                warnings.warn(f"CIF Parser encountered errors in {self.filepath}.")
                
            # Using the modern parse_structures API
            structures = parser.parse_structures(
                primitive=False, 
                symmetrized=False, 
                check_occu=True
            )
            
            if not structures:
                raise ValueError("No structures found in the provided CIF file.")
                
            structure = structures
            
            # Guard clause for disordered structures
            if not structure.is_ordered:
                raise NotImplementedError(
                    "Symmetry analysis for disordered structures is not natively supported. "
                    "Please order the structure prior to analysis."
                )
            return structure

    @staticmethod
    def _format_fraction(val: float, max_den: int = 12) -> str:
        """Converts floating point coordinate to a clean string fraction."""
        # Wrap coordinate inside [0, 1)
        val = val % 1.0
        
        # Snap boundary conditions
        if abs(val) < 1e-4 or abs(val - 1.0) < 1e-4:
            return "0"
            
        # Use SymPy to bound the denominator
        rat = sympy.Rational(val).limit_denominator(max_den)
        
        if rat.q == 1:
            return str(rat.p)
        return f"{rat.p}/{rat.q}"

    def analyze_wyckoff_positions(self) -> Dict[str, Any]:
        """
        Extracts unique Wyckoff positions, calculates multiplicities, 
        and rationalizes generator coordinates.
        """
        results = {
            "space_group_symbol": self.sga.get_space_group_symbol(),
            "space_group_number": self.sga.get_space_group_number(),
            "wyckoff_positions": []
        }
        
        # Iterate over the distinct symmetry orbits
        for idx, (wyckoff_letter, eq_sites) in enumerate(zip(
            self.sym_struct.wyckoff_symbols, 
            self.sym_struct.equivalent_sites
        )):
            multiplicity = len(eq_sites)
            label = f"{multiplicity}{wyckoff_letter}"
            species = eq_sites.species_string
            
            # The first site in the equivalent group is taken as the generator
            generator_site = eq_sites
            raw_coords = generator_site.frac_coords
            
            # Convert the x, y, z floats into string fractions
            fraction_coords = [self._format_fraction(c) for c in raw_coords]
            
            results["wyckoff_positions"].append({
                "species": species,
                "multiplicity": multiplicity,
                "wyckoff_letter": wyckoff_letter,
                "wyckoff_label": label,
                "raw_coordinates": raw_coords.tolist(),
                "fractional_coordinates": fraction_coords
            })
            
        return results

# Usage Example:
if __name__ == "__main__":
    # Ensure you have a valid CIF file path
    # analyzer = WyckoffAnalyzer("mp-1234.cif", symprec=0.1)
    # wyckoff_data = analyzer.analyze_wyckoff_positions()
    # import pprint; pprint.pprint(wyckoff_data)
    pass
```

---

## 8. Version-Specific Concerns for Pymatgen 2025.10.7

When migrating or building code explicitly against `pymatgen` version 2025.10.7 (and generally navigating the 2024–2025 development branch), several API behaviors require strict adherence:

### 8.1 Deprecation of `get_structures()`
The most disruptive change to the I/O module in recent years is the transition away from `CifParser.get_structures()`. Code relying on `get_structures()` may suddenly output non-primitive standard unit cells, silently altering downstream defect calculations and density of state integrations [cite: 4]. In 2025.10.7, usage of `CifParser.parse_structures()` is fully enforced as the canonical standard.

### 8.2 Magnetic Structures and Symmetrization
Recent patches have explicitly restricted `SpacegroupAnalyzer` operations on structures containing complex collinear magnetic moments or disordered magnetic sites. Specifically, a `NotImplementedError` stating *"Disordered magnetic structures not currently supported"* will interrupt pipelines attempting to naively ingest spin-decorated CIF files without proper sanitization [cite: 14].

### 8.3 Preservation of `SymmetrizedStructure`
The underlying representation of `SymmetrizedStructure` has remained structurally stable concerning its core attribute names (`wyckoff_symbols`, `equivalent_sites`). However, internal type hints and return structures have been aggressively updated to leverage Python's type annotations. E.g., lists of symmetry operations are now typed as `list[SymmOp]` [cite: 1]. The behavior of `wyckoff_symbols`—returning a tuple/list of strings without integer multiplicities—remains unchanged [cite: 8]. 

### Summary
Building a successful, modern crystallographic parser requires deep integration between the structural abstraction capabilities of `pymatgen` and the exact numerical representations offered by `sympy`. By adhering to the `parse_structures` methodologies, dynamically tuning `symprec`, tracking partial occupancy boundaries, and constraining fractional denominators, developers can construct robust and reproducible materials science pipelines.

**Sources:**
1. [pymatgen.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEq5f21YW9jml9K2z3VE7S345VEjfBMxisIE1FVxT_w7NU87Zgqo0xXQGWEw7LbhUldyYhrNUBNQTWgEInqtZwDpymeX7ZWojUD6mvbxgBZ9DCgzOtiV03_0pmx)
2. [pymatgen.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGC4JwlikgK7Kr-O2s7S4v7V8cXwKumtZ5-L6YdXmT9PKaAQDexhyaKQvKGildk1O9kdEQqGyyoL_ynI9PfAlOGEpVGmLznmsXbeQE=)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGj_1UNMHzbzZW-6qRnKOYSvT3m_xSr-WrROgk-wjLnt5HWxmyWoXY4ayAZhUDTCSGLC226WlDSt9cAwwJZ2R4A5mwqciBZTectHFQZdTeB09ODOjAuOWS6HgdeYX1oRBoZkUzzwNHFGESuWeMYqvuQmOwMG9E=)
4. [matsci.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFPZAKJratVFQoGA9E8Ul7jJFxALjThWxLDwizzSUQmIFAwUsimeP7YlUibTv4kMJW3lisiKXHFxCuswwQ61p6DoWsYJYg4jG4JVMrXCjscshFF5wgFtrVU5yGJSMJ0agGNYBlTEuBTIq-mG8sVsv0CZ5xtfsF9NC_NimQ7nupxReN4xuK7GLU=)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2HSJAYSmEera71cnjO3KMViFrg5t9XFRnNZzF2W99M2bCNOL5BjrshwqPnlj0zq4U0OubZKDDzM6Q95-l68OYihWveMqYcxAtUIU_RQGTIb686m1C-xRZaQvfBsNogeKTFA7z3hxDjm1-6RFsFQ==)
6. [pymatgen.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFB5nNLdoH6yzPwcRBH6fOSkBbYnn-1aXAS5H4ScTTHew_zuCVGCeiCn-FKD2aaAfbc1h5K2CIoNSbgS5GsOjS4ChVFnpZT67ajRSGZyCPL3QTEFCHdlzFZen_6jlHcMXgS)
7. [matsci.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFpFwKQvegupHEOkdvcXl8uQo_HiaZX3VKY7pFW2EbdVT2uMzvTrp8mwwqeC0EkK3SNRmwXak7o5Uw5mE2rNmlJ37Ks2E7FwhX8f7UIo6Rgtu4l4S9wDUXIBAdxXLbpAxBPx-n6UbWiVhsbfTMsLVsICCfx9eh-lHQqwiCBJNZOPLuhbZU215v_)
8. [janosh.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZShdMYEVMuMJQvZaJS0JX5s3tLWUnD-e8SSqQjE1A0W_lNmI4Coi5WN_eUGpj1-D55bQLwyciqA7EcGxtESVXBX1XlTKQsj5rNRckrn-UxG0Yypzn4K1UuB3dwa2D824raX5aZINEsGkcI5liydGonXlkwd_F0ZAs19rDn5AcTAQN)
9. [janosh.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5pZ-39sLdJmy-XCb7V_ql_3DTV8uRiZ4TovTB4zA19xBCyJfb3c-RME9ymeP_NF6QkYXSCppKkcbuA67Y8CeqPYt0qwcjNlxYQCJgBujeywFAHSqVB8TivVNzleGnZc4ByqAuyyLEKfJbwRA8_w5BfSaYyi5Ero15mJObkehXYPLXZm-nt1DAzamK8A==)
10. [sympy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGbt_FXfq-D7jZLgAKCiEFRUG-UmxTazH1ktZdIWFSqeEmCXDc-Wz2bBaMfjGo9lGAux72Pt79SkfQWgz2Vs8aiJ8QoFLpmmO4lcTFnefN1dDllaHVhpBx1eBMjLaPpd3g-Lwoc1cY=)
11. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFWzCWIZmKco5UggbsB_Y_uo9PGmkibbgDU2UnzCDoGGBoiM2MJ8C7zEn5Vkrr967pTFDJ70S6LFC0PhTCL1az2U_pU9pc8PoW1Yp2F_GWu2wrs1SBDp21XAYpoCrA9HP0Vt5V3--VfXB7DJUS3yabKSs-UNigolB6Nc2iCWQ==)
12. [sympy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFdMyH5Bgf7gLfmxF-x674mczwhfRJt9w5nY7A5ju014pD4VMeSk7DUHvAoUmNwjDnSpM6v3N4AT_hZAIrZ9N28qvge-L55OuzUkUAzse9gpI_gSGgD0FU8m7Wtu_euf4dGarSnDQ==)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHpTo9HJG-xvM8561L6crswBFhPrlWxKyegKvd7pHuMcgWtFRbyFdckyD4QLk3zqjBm3uowD-fRaR3bD76PIPmfOqo-TafNSiCrRw9U2iBoBgF6toj21NjFWFMGXd_52I9HaFgc_rh4-9JGKLzeUuAv3iOYMkxmw9RIxGwWx444dVT5giVtE31Y5kMFgPu1u_AQSod6aw==)
14. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpXaY5URYRIuQdXy4NGomn8X0MvAAo5lMm9Fn2dDSmmZecmck8xtGGRPH6qjrl9EnYWl3SZs6d_D3P59cViglmlSErU56KjqgRCOGBsToj0UaLUMue84yjwJvBOGILqKCRK3rwYefagibLp2ccCA==)
15. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVtJSXBNbEIYoK-M-n_slzFG6mi-BDWek-q9GI-wgr62dSfhmHteOKV-m9TndCjnhR_Fo6g1p-BAoXkixVbhEHYEycGTnhp679NeTgjbsz4VXEpRJAAbbC05ftxh81XVwm7EiEsfKV9Gqer2wCb8VXhwKFgYHkRQ==)
16. [pymatgen.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNokK9S6WkjYBLB0y8OoMKKN6hOR3WTknnBK-aPezFMN6wmun-jQJ48iKYZqDLYBrFL8L06y-3mU-LBHKFJOzmQ79oSBrXkMqfdi9ommnrCnmjrN5CpRVDYjX0YMp2v-daXyzsnPKXlw==)
