"""
evo-macro-data-ingestion: Utility functions for parsing ERP .xls tables
and FRED CPI .xlsx files into clean pandas Series indexed by integer year.
"""

import pandas as pd
import numpy as np
import re


def parse_erp_annual_total(filepath: str, target_year: int = 2024) -> pd.Series:
    """
    Parses an ERP .xls file to extract the annual "Total" column (column 1).
    
    Handles:
    - Multi-row headers (skipped)
    - Year formatting with trailing periods (e.g., '1973.')
    - Quarterly data at bottom of table
    - Partial year data (e.g., 2024 with only Q1-Q3)
    
    Args:
        filepath: Path to the ERP .xls file
        target_year: Final year to handle partial quarterly integration (default 2024)
        
    Returns:
        pd.Series of annual totals indexed by integer years
    """
    # Read entire file with no header to handle multi-row headers
    df = pd.read_excel(filepath, engine="xlrd", header=None)
    
    # Use only first two columns: Period and Total
    df = df.iloc[:, :2].copy()
    df.columns = ['Period', 'Total']
    
    # Drop rows where both are NaN
    df = df.dropna(subset=['Period', 'Total'], how='all')
    
    # Convert Period to string and strip whitespace
    df['Period'] = df['Period'].astype(str).str.strip()
    
    # Identify annual rows: match patterns like '1973.' or '1973'
    # ERP years have trailing periods like '1973.'
    annual_mask = df['Period'].str.match(r'^\d{4}\.?$')
    df_annual = df[annual_mask].copy()
    
    # Extract year as integer (remove trailing period)
    df_annual['Year'] = df_annual['Period'].str.replace('.', '', regex=False).astype(int)
    
    # Convert Total to numeric
    df_annual['Total'] = pd.to_numeric(df_annual['Total'], errors='coerce')
    
    # Create annual series
    annual_series = pd.Series(
        data=df_annual['Total'].values,
        index=df_annual['Year'].values,
        name='Total'
    )
    
    # Handle partial year data if target_year is not in annual data
    if target_year not in annual_series.index:
        partial_avg = compute_partial_year_average(df, target_year)
        if partial_avg is not None:
            annual_series.loc[target_year] = partial_avg
    
    # Sort and drop NaNs
    annual_series = annual_series.sort_index().dropna()
    return annual_series


def compute_partial_year_average(df: pd.DataFrame, target_year: int = 2024) -> float:
    """
    Computes the average of available quarterly data for a partial year.
    
    ERP quarterly format (actual observed):
    - First quarter of a year block: '2024: I.' (year prefix with colon)
    - Subsequent quarters: 'II.', 'III.', 'III p.', 'IV.' (no year prefix, no indentation)
    
    Strategy: Find the row with 'YYYY: I.' then collect subsequent rows
    that match Roman numeral patterns until we hit another year block or non-quarter row.
    
    Args:
        df: DataFrame with 'Period' and 'Total' columns (full raw data)
        target_year: Year to compute partial average for
        
    Returns:
        Float average of available quarters, or None if no data found
    """
    target_str = str(target_year)
    quarterly_values = []
    in_target_year_block = False
    
    for idx in range(len(df)):
        row = df.iloc[idx]
        period = str(row['Period']).strip()
        
        # Check if this row starts the target year's quarterly block
        # Pattern: '2024: I.' or '2024:I.'
        if re.match(r'^' + target_str + r'\s*:', period):
            in_target_year_block = True
            val = pd.to_numeric(row['Total'], errors='coerce')
            if not np.isnan(val):
                quarterly_values.append(val)
            continue
        
        if in_target_year_block:
            # Check if this is a continuation quarter
            # Patterns: 'II.', 'III.', 'IV.', 'III p.', 'II p.'
            # Remove 'p' and extra spaces, then check for Roman numeral
            cleaned = re.sub(r'\s*p\s*', '', period).strip()
            if re.match(r'^(I{1,3}V?|IV|V?I{0,3})\.?$', cleaned) and cleaned not in ('', '.'):
                val = pd.to_numeric(row['Total'], errors='coerce')
                if not np.isnan(val):
                    quarterly_values.append(val)
            else:
                # Check if it's another year's quarterly block starting
                if re.match(r'^\d{4}\s*:', period):
                    in_target_year_block = False
                else:
                    # Non-quarter row (footnote, etc.) - stop
                    in_target_year_block = False
    
    if quarterly_values:
        return np.mean(quarterly_values)
    return None


def process_cpi_annual(filepath: str) -> pd.Series:
    """
    Reads CPI data from xlsx file and returns annual CPI series.
    
    The CPI file may be:
    - Raw FRED monthly CPIAUCSL data (columns: observation_date, CPIAUCSL)
    - Pre-processed annual data (columns: Year, CPI_2024 or similar)
    
    Handles both formats automatically.
    
    Args:
        filepath: Path to CPI .xlsx file
        
    Returns:
        pd.Series of annual CPI values indexed by integer year
    """
    cpi_df = pd.read_excel(filepath, engine="openpyxl")
    
    cols = [c.lower() for c in cpi_df.columns]
    
    # Check if it's already annual data with Year column
    if 'year' in cols:
        year_col = cpi_df.columns[cols.index('year')]
        # Find the CPI value column (the non-year column)
        cpi_col = [c for c in cpi_df.columns if c != year_col][0]
        cpi_annual = pd.Series(
            data=cpi_df[cpi_col].values,
            index=cpi_df[year_col].astype(int).values,
            name='CPI'
        )
        return cpi_annual
    
    # Handle raw FRED monthly data
    if 'observation_date' in cols:
        date_col = cpi_df.columns[cols.index('observation_date')]
        cpi_col = cpi_df.columns[cols.index('cpiaucsl')] if 'cpiaucsl' in cols else cpi_df.columns[1]
        
        cpi_df[date_col] = pd.to_datetime(cpi_df[date_col])
        cpi_df['Year'] = cpi_df[date_col].dt.year
        cpi_annual = cpi_df.groupby('Year')[cpi_col].mean()
        cpi_annual.name = 'CPI'
        return cpi_annual
    
    # Fallback: assume first column is date/year, second is CPI
    cpi_df.columns = ['Date', 'CPI']
    try:
        cpi_df['Date'] = pd.to_datetime(cpi_df['Date'])
        cpi_df['Year'] = cpi_df['Date'].dt.year
        cpi_annual = cpi_df.groupby('Year')['CPI'].mean()
    except Exception:
        cpi_df['Year'] = cpi_df['Date'].astype(int)
        cpi_annual = cpi_df.set_index('Year')['CPI']
    
    return cpi_annual
