# Skill Creation Plan

**Task**: Build a Python function that parses CIF files, extracts Wyckoff position multiplicities and representative fractional coordinates (as rationalized fractions), and returns them in a specified dictionary format.

**Rationale**: The task has three clear concerns: (1) CIF file parsing and structure loading, (2) symmetry analysis to extract Wyckoff positions with multiplicities and coordinates, and (3) floating-point to rational fraction conversion. However, these are tightly coupled in a single pipeline with a single entry function, so two skills suffice: one for CIF parsing + symmetry/Wyckoff extraction (the core crystallography pipeline), and one for coordinate rationalization (the numerical formatting concern).

**Number of skills**: 2

---

## Skill 1: evo-crystallography-wyckoff-analysis

**Description**: Parses CIF files using pymatgen, performs space group symmetry analysis via SpacegroupAnalyzer, and extracts Wyckoff position letters, multiplicities, and representative atom fractional coordinates from the symmetrized structure.

**Responsibility**: CIF file loading (via CifParser/parse_structures), structure symmetry analysis (SpacegroupAnalyzer with appropriate symprec), extraction of wyckoff_symbols, equivalent_sites, multiplicities, and the first atom's fractional coordinates for each unique Wyckoff position.

**Key functions**: `load_structure_from_cif`, `get_symmetrized_structure`, `extract_wyckoff_multiplicities`, `extract_representative_coordinates`, `analyze_wyckoff_position_multiplicities_and_coordinates`

**Depends on**: evo-crystallography-fraction-format


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-crystallography-wyckoff-analysis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-crystallography-fraction-format

**Description**: Converts floating-point fractional coordinates to clean rational fraction strings with bounded denominators (≤12), handling edge cases like near-zero/near-one wrapping and integer values.

**Responsibility**: Floating-point to rational number conversion using sympy.Rational.limit_denominator, coordinate wrapping to [0,1), boundary snapping for near-0 and near-1 values, and string formatting of fractions.

**Key functions**: `float_to_fraction_string`, `rationalize_coordinate_vector`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-crystallography-fraction-format/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
