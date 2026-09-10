"""Wyckoff position analysis utilities for CIF files.

Parses CIF files using pymatgen, performs space group symmetry analysis,
and extracts Wyckoff position letters, multiplicities, and representative
atom fractional coordinates from the symmetrized structure.
"""

import warnings
import sys
from typing import Any, Dict, List, Tuple

# Import fraction formatting from sibling skill
sys.path.insert(0, '/app/environment/skills/evo-crystallography-fraction-format/scripts')
from fraction_utils import float_to_fraction_string, rationalize_coordinate_vector


def load_structure_from_cif(filepath: str, primitive: bool = False):
    """Load a structure from a CIF file using pymatgen's CifParser.
    
    Uses parse_structures() (not deprecated get_structures()).
    
    Args:
        filepath: path to CIF file
        primitive: if True, return primitive cell
    
    Returns:
        pymatgen Structure object
    """
    from pymatgen.io.cif import CifParser
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = CifParser(filepath)
        structures = parser.parse_structures(primitive=primitive, check_occu=True)
        if not structures:
            raise ValueError(f"No structures found in {filepath}")
        return structures[0]


def get_symmetrized_structure(structure, symprec: float = 0.1):
    """Get symmetrized structure using SpacegroupAnalyzer.
    
    Args:
        structure: pymatgen Structure object
        symprec: symmetry precision in Angstroms (default 0.1 for MP)
    
    Returns:
        Tuple of (SpacegroupAnalyzer, SymmetrizedStructure)
    """
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    
    sga = SpacegroupAnalyzer(structure, symprec=symprec)
    sym_struct = sga.get_symmetrized_structure()
    return sga, sym_struct


def extract_wyckoff_multiplicities(sym_struct) -> Dict[str, int]:
    """Extract Wyckoff position multiplicities from symmetrized structure.
    
    Returns dict mapping Wyckoff letter -> multiplicity.
    pymatgen returns wyckoff_symbols like '4a', '8c' - strip digits to get letter.
    
    Args:
        sym_struct: SymmetrizedStructure from SpacegroupAnalyzer
    
    Returns:
        Dict mapping Wyckoff letter to multiplicity
    """
    result = {}
    for ws, es in zip(sym_struct.wyckoff_symbols, sym_struct.equivalent_sites):
        letter = ws.lstrip('0123456789')
        multiplicity = len(es)
        result[letter] = multiplicity
    return result


def extract_representative_coordinates(sym_struct, max_den: int = 12) -> Dict[str, List[str]]:
    """Extract representative (first atom) coordinates for each Wyckoff position.
    
    Takes the first site in each equivalent_sites group and converts
    its fractional coordinates to rationalized fraction strings.
    
    Args:
        sym_struct: SymmetrizedStructure from SpacegroupAnalyzer
        max_den: maximum denominator for fraction conversion
    
    Returns:
        Dict mapping Wyckoff letter to list of 3 fraction strings
    """
    result = {}
    for ws, es in zip(sym_struct.wyckoff_symbols, sym_struct.equivalent_sites):
        letter = ws.lstrip('0123456789')
        first_site = es[0]
        frac_coords = first_site.frac_coords
        coord_strings = rationalize_coordinate_vector(frac_coords, max_den)
        result[letter] = coord_strings
    return result


def analyze_wyckoff_position_multiplicities_and_coordinates(
    filepath: str,
    symprec: float = 0.1,
    max_den: int = 12
) -> Dict[str, Any]:
    """Main entry function: analyze CIF file for Wyckoff positions.
    
    Args:
        filepath: path to CIF file
        symprec: symmetry precision (default 0.1 for Materials Project files)
        max_den: maximum fraction denominator (default 12)
    
    Returns:
        Dict with keys:
            - "wyckoff_multiplicity_dict": {letter: multiplicity}
            - "wyckoff_coordinates_dict": {letter: [x_str, y_str, z_str]}
    """
    structure = load_structure_from_cif(filepath, primitive=False)
    sga, sym_struct = get_symmetrized_structure(structure, symprec=symprec)
    mult_dict = extract_wyckoff_multiplicities(sym_struct)
    coord_dict = extract_representative_coordinates(sym_struct, max_den=max_den)
    
    return {
        "wyckoff_multiplicity_dict": mult_dict,
        "wyckoff_coordinates_dict": coord_dict
    }
