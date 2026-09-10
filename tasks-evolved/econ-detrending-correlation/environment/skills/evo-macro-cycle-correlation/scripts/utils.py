"""
evo-macro-cycle-correlation: Utility functions for deflating nominal series,
applying HP filter to extract cyclical components, and computing Pearson correlation.
"""

import pandas as pd
import numpy as np
import scipy.stats
from statsmodels.tsa.filters.hp_filter import hpfilter


def deflate_nominal_to_real(nominal: pd.Series, cpi: pd.Series) -> pd.Series:
    """
    Converts nominal series to real values using CPI deflation.
    
    Formula: Real_t = (Nominal_t / CPI_t) * 100
    
    Args:
        nominal: pd.Series of nominal values indexed by year
        cpi: pd.Series of CPI values indexed by year
        
    Returns:
        pd.Series of real values indexed by year
    """
    # Align on common years
    common_years = nominal.index.intersection(cpi.index)
    real = (nominal.loc[common_years] / cpi.loc[common_years]) * 100
    real.name = 'Real'
    return real


def extract_hp_cycle(real_series: pd.Series, lamb: float = 100) -> pd.Series:
    """
    Applies natural log transformation and HP filter to extract cyclical component.
    
    Steps:
    1. Take natural logarithm (np.log, NOT np.log10)
    2. Apply HP filter with lamb parameter (100 for annual data)
    3. Return cyclical component
    
    The hpfilter function returns (cycle, trend) in that order.
    Parameter name is 'lamb' (not 'lambda' or 'lam').
    
    Args:
        real_series: pd.Series of real values (must have no NaNs)
        lamb: HP filter smoothing parameter (default 100 for annual data)
        
    Returns:
        pd.Series of cyclical component values
    """
    # Log transformation
    log_series = np.log(real_series)
    
    # HP filter - returns (cycle, trend)
    cycle, trend = hpfilter(log_series, lamb=lamb)
    
    return cycle


def compute_cycle_pearson_correlation(cycle1: pd.Series, cycle2: pd.Series) -> float:
    """
    Computes Pearson correlation between two cyclical components.
    
    Uses scipy.stats.pearsonr which returns a PearsonRResult object
    with .statistic and .pvalue attributes (scipy 1.14.1).
    
    Args:
        cycle1: pd.Series of cyclical component 1
        cycle2: pd.Series of cyclical component 2
        
    Returns:
        float: Pearson correlation coefficient
    """
    result = scipy.stats.pearsonr(cycle1, cycle2)
    return result.statistic


def run_full_pipeline(
    pce_file: str,
    pfi_file: str,
    cpi_file: str,
    start_year: int = 1973,
    end_year: int = 2024,
    target_year: int = 2024,
    hp_lambda: float = 100,
    output_file: str = None
) -> float:
    """
    Complete pipeline: parse data -> deflate -> HP filter -> correlate.
    
    Steps:
    1. Parse ERP tables for PCE and PFI nominal annual totals
    2. Parse CPI annual data
    3. Deflate nominal to real using CPI
    4. Filter to year range [start_year, end_year] inclusive
    5. Apply log + HP filter to extract cyclical components
    6. Compute Pearson correlation
    7. Optionally write result to file (rounded to 5 decimal places)
    
    Args:
        pce_file: Path to ERP table 10 .xls file
        pfi_file: Path to ERP table 12 .xls file  
        cpi_file: Path to CPI .xlsx file
        start_year: Start of analysis period (default 1973)
        end_year: End of analysis period (default 2024)
        target_year: Year with partial quarterly data (default 2024)
        hp_lambda: HP filter smoothing parameter (default 100)
        output_file: Path to write result (optional)
        
    Returns:
        float: Pearson correlation coefficient
    """
    import sys
    sys.path.insert(0, '/app/environment/skills/evo-macro-data-ingestion/scripts')
    from utils import parse_erp_annual_total, process_cpi_annual
    
    # 1. Parse nominal data
    pce_nominal = parse_erp_annual_total(pce_file, target_year=target_year)
    pfi_nominal = parse_erp_annual_total(pfi_file, target_year=target_year)
    cpi_annual = process_cpi_annual(cpi_file)
    
    # 2. Deflate to real values
    pce_real = deflate_nominal_to_real(pce_nominal, cpi_annual)
    pfi_real = deflate_nominal_to_real(pfi_nominal, cpi_annual)
    
    # 3. Align to year range (inclusive) using .loc
    # .loc is inclusive of both bounds in pandas
    pce_real = pce_real.loc[start_year:end_year]
    pfi_real = pfi_real.loc[start_year:end_year]
    
    # Ensure both series cover same years
    common_years = pce_real.index.intersection(pfi_real.index)
    pce_real = pce_real.loc[common_years]
    pfi_real = pfi_real.loc[common_years]
    
    # Drop any NaNs (HP filter cannot handle them)
    valid_mask = pce_real.notna() & pfi_real.notna()
    pce_real = pce_real[valid_mask]
    pfi_real = pfi_real[valid_mask]
    
    # 4. Extract cyclical components via HP filter
    pce_cycle = extract_hp_cycle(pce_real, lamb=hp_lambda)
    pfi_cycle = extract_hp_cycle(pfi_real, lamb=hp_lambda)
    
    # 5. Compute Pearson correlation
    correlation = compute_cycle_pearson_correlation(pce_cycle, pfi_cycle)
    
    # 6. Output
    print(f"=== Macroeconomic Cycle Correlation Analysis ===")
    print(f"Data Range: {common_years.min()} to {common_years.max()}")
    print(f"Number of observations: {len(common_years)}")
    print(f"Pearson Correlation (r): {correlation:.5f}")
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(f"{correlation:.5f}\n")
        print(f"Result written to {output_file}")
    
    return correlation
