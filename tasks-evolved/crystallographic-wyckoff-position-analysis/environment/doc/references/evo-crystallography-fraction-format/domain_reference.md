# Domain Reference for evo-crystallography-fraction-format

**Responsibility**: Floating-point to rational number conversion using sympy.Rational.limit_denominator, coordinate wrapping to [0,1), boundary snapping for near-0 and near-1 values, and string formatting of fractions.

**Key functions to implement**: float_to_fraction_string, rationalize_coordinate_vector

---

## 5. Converting Float Coordinates to Simple Fractions Using SymPy


Because DFT algorithms and generic CIF parsers represent coordinates as IEEE 754 floating-point numbers, an atom located precisely at a high-symmetry position (e.g., \( \frac{1}{3} \)) might be represented as `0.33333334` [cite: 5]. Displaying this float is unhelpful to crystallographers; thus, conversion back to a mathematically exact rational number is necessary. `SymPy` provides robust algebraic tools to perform this conversion.

## 6. Handling Edge Cases and Pitfalls

