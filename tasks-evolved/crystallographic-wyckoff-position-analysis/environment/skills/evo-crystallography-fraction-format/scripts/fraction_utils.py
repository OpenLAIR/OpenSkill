"""Fraction formatting utilities for crystallographic coordinates.

Converts floating-point fractional coordinates to clean rational fraction
strings with bounded denominators (<=12), handling edge cases like
near-zero/near-one wrapping and integer values.
"""

from fractions import Fraction
from typing import List


def float_to_fraction_string(val: float, max_den: int = 12) -> str:
    """Convert a floating point coordinate to a clean string fraction.
    
    Steps:
    1. Wrap coordinate to [0, 1) using modulo 1.0
    2. Snap near-0 and near-1 values to 0
    3. Use Fraction.limit_denominator to get clean rational
    4. If result is >= 1, return "0" (wrapping)
    5. Format as string: integers as "0", fractions as "p/q"
    
    Args:
        val: floating point coordinate value
        max_den: maximum denominator (default 12)
    
    Returns:
        String representation of the fraction
    """
    # Wrap to [0, 1)
    val = val % 1.0
    
    # Snap boundary conditions: near 0 or near 1
    if abs(val) < 1e-3 or abs(val - 1.0) < 1e-3:
        return "0"
    
    # Convert to fraction with bounded denominator
    frac = Fraction(val).limit_denominator(max_den)
    
    # If fraction rounds to 1 or 0, return "0"
    if frac >= 1 or frac <= 0:
        return "0"
    
    # Format output
    if frac.denominator == 1:
        return str(frac.numerator)
    else:
        return f"{frac.numerator}/{frac.denominator}"


def rationalize_coordinate_vector(coords: list, max_den: int = 12) -> List[str]:
    """Convert a list of 3 float coordinates to fraction strings.
    
    Args:
        coords: list/array of 3 float values (fractional coordinates)
        max_den: maximum denominator (default 12)
    
    Returns:
        List of 3 string fractions
    """
    return [float_to_fraction_string(float(c), max_den) for c in coords]
