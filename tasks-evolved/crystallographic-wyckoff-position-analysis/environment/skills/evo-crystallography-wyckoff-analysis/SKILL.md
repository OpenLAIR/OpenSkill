---
name: evo-crystallography-wyckoff-analysis
description: Parses CIF files using pymatgen, performs space group symmetry analysis via SpacegroupAnalyzer, and extracts Wyckoff position letters, multiplicities, and representative atom fractional coordinates from the symmetrized structure.
---

# evo-crystallography-wyckoff-analysis

Analyzes CIF files for Wyckoff position multiplicities and coordinates.

## Dependencies
- evo-crystallography-fraction-format (for coordinate rationalization)
- pymatgen >= 2025.10.7
- sympy >= 1.14.0

## Key Functions

- `load_structure_from_cif(filepath, primitive=False)` - Load CIF file to Structure
- `get_symmetrized_structure(structure, symprec=0.1)` - Get symmetrized structure
- `extract_wyckoff_multiplicities(sym_struct)` - Get {letter: multiplicity} dict
- `extract_representative_coordinates(sym_struct, max_den=12)` - Get {letter: [x,y,z]} dict
- `analyze_wyckoff_position_multiplicities_and_coordinates(filepath, symprec=0.1, max_den=12)` - Main entry function

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-crystallography-wyckoff-analysis/scripts')
from utils import analyze_wyckoff_position_multiplicities_and_coordinates

result = analyze_wyckoff_position_multiplicities_and_coordinates('/path/to/file.cif')
# Returns:
# {
#     "wyckoff_multiplicity_dict": {"a": 4, "c": 8},
#     "wyckoff_coordinates_dict": {
#         "a": ["0", "1/2", "1/2"],
#         "c": ["3/8", "1/9", "8/9"]
#     }
# }
```

## Key Details

1. Uses `CifParser.parse_structures(primitive=False)` (not deprecated get_structures)
2. Uses `SpacegroupAnalyzer(symprec=0.1)` for Materials Project DFT-relaxed structures
3. wyckoff_symbols from pymatgen include multiplicity prefix (e.g., '4a') - strip digits to get letter
4. First site in each equivalent_sites group is the representative coordinate
5. Coordinates wrapped to [0,1) and converted to fractions with denominator <= 12
