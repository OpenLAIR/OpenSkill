"""
DOTS Powerlifting Formula Utilities

Provides the exact DOTS scoring formula, sex-specific polynomial coefficients,
TotalKg computation rules, edge case handling, and Excel formula string builders.
"""

# DOTS Coefficients - 4th degree polynomial
# DOTS Score = TotalKg * (500 / (A*BW^4 + B*BW^3 + C*BW^2 + D*BW + E))

MALE_COEFFICIENTS = {
    'A': -0.000001093,
    'B': 0.0007391293,
    'C': -0.1918759221,
    'D': 24.0900756,
    'E': -307.75076
}

FEMALE_COEFFICIENTS = {
    'A': -0.0000010706,
    'B': 0.0005158568,
    'C': -0.1126655495,
    'D': 13.6175032,
    'E': -57.96288
}

# Required columns from Data sheet for DOTS calculation
REQUIRED_COLUMNS = ['Name', 'Sex', 'BodyweightKg', 'Best3SquatKg', 'Best3BenchKg', 'Best3DeadliftKg']


def get_dots_coefficients(sex='M'):
    """Return DOTS polynomial coefficients for given sex.
    Mx uses male coefficients.
    """
    if sex in ('M', 'Mx'):
        return MALE_COEFFICIENTS.copy()
    else:
        return FEMALE_COEFFICIENTS.copy()


def get_required_columns():
    """Return list of column names needed from Data sheet for DOTS calculation."""
    return REQUIRED_COLUMNS.copy()


def build_totalkg_excel_formula(row, squat_col='D', bench_col='E', deadlift_col='F'):
    """Build Excel formula string for TotalKg calculation.
    
    If any lift is blank or <= 0 (negative = failed attempt), return "".
    Otherwise return sum of three lifts.
    """
    s = f'{squat_col}{row}'
    b = f'{bench_col}{row}'
    d = f'{deadlift_col}{row}'
    
    formula = (
        f'=IF(OR(ISBLANK({s}), ISBLANK({b}), ISBLANK({d}), '
        f'{s}<=0, {b}<=0, {d}<=0), "", {s}+{b}+{d})'
    )
    return formula


def build_dots_excel_formula(row, sex_col='B', bw_col='C', total_col='G'):
    """Build Excel formula string for DOTS score calculation.
    
    Uses exact decimal notation for coefficients (no scientific notation).
    Mx uses male coefficients. Result rounded to 3 decimal places.
    """
    sx = f'{sex_col}{row}'
    bw = f'{bw_col}{row}'
    tot = f'{total_col}{row}'
    
    # Build polynomial strings with exact decimal coefficients
    # Male: A*BW^4 + B*BW^3 + C*BW^2 + D*BW + E
    male_poly = (
        f'-0.000001093*{bw}^4+0.0007391293*{bw}^3'
        f'-0.1918759221*{bw}^2+24.0900756*{bw}-307.75076'
    )
    
    female_poly = (
        f'-0.0000010706*{bw}^4+0.0005158568*{bw}^3'
        f'-0.1126655495*{bw}^2+13.6175032*{bw}-57.96288'
    )
    
    formula = (
        f'=IF(OR({tot}="",{bw}=""),"",'
        f'ROUND({tot}*500/'
        f'IF(OR({sx}="M",{sx}="Mx"),'
        f'{male_poly},'
        f'{female_poly}),3))'
    )
    return formula


def compute_dots_score(total_kg, bodyweight_kg, sex='M'):
    """Compute DOTS score numerically (for validation purposes)."""
    if total_kg is None or bodyweight_kg is None:
        return None
    if total_kg <= 0 or bodyweight_kg <= 0:
        return None
    
    coeffs = get_dots_coefficients(sex)
    bw = bodyweight_kg
    
    denominator = (
        coeffs['A'] * bw**4 +
        coeffs['B'] * bw**3 +
        coeffs['C'] * bw**2 +
        coeffs['D'] * bw +
        coeffs['E']
    )
    
    if denominator == 0:
        return None
    
    dots = total_kg * (500.0 / denominator)
    return round(dots, 3)
