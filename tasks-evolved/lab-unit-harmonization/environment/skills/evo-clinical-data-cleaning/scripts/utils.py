import pandas as pd
import numpy as np
import re


def load_clinical_csv(filepath):
    """
    Load clinical CSV data as strings to preserve all formatting for manual cleaning.
    We read as strings because using decimal=',' would break the CSV delimiter.
    """
    df = pd.read_csv(filepath, dtype=str, low_memory=False)
    return df


def replace_decimal_commas(value):
    """
    Replace decimal commas in a string value.
    '12,34' -> '12.34'
    '1,030' -> '1.030' (specific gravity)
    Only replaces comma when it's used as decimal separator (not thousands).
    Pattern: digits,digits where the part after comma is NOT exactly 3 digits
    followed by end or another separator (which would indicate thousands).
    
    Simple rule: if string contains exactly one comma and no dots, 
    the comma is a decimal separator.
    """
    if pd.isna(value) or not isinstance(value, str):
        return value
    value = value.strip()
    if value == '':
        return np.nan
    # If there's exactly one comma and no dots, treat comma as decimal
    if ',' in value and '.' not in value:
        value = value.replace(',', '.')
    return value


def replace_decimal_commas_df(df, skip_cols=None):
    """
    Apply decimal comma replacement to all columns in a DataFrame.
    skip_cols: list of column names to skip (e.g., patient_id)
    """
    if skip_cols is None:
        skip_cols = []
    for col in df.columns:
        if col in skip_cols:
            continue
        if df[col].dtype == object:
            df[col] = df[col].apply(replace_decimal_commas)
    return df


def coerce_to_numeric(df, skip_cols=None):
    """
    Convert all columns (except skip_cols) to numeric float64.
    Handles scientific notation natively via pd.to_numeric.
    Values that cannot be converted become NaN.
    """
    if skip_cols is None:
        skip_cols = []
    for col in df.columns:
        if col in skip_cols:
            continue
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def drop_incomplete_rows(df):
    """
    Drop rows that have any missing (NaN) values.
    Returns the cleaned DataFrame.
    """
    df_clean = df.dropna(how='any').reset_index(drop=True)
    return df_clean


def format_output_csv(df, output_filepath, skip_cols=None):
    """
    Format all numeric columns to 2 decimal places (X.XX format)
    and write to CSV without scientific notation.
    skip_cols: columns to keep as-is (e.g., patient_id)
    """
    if skip_cols is None:
        skip_cols = []
    
    # Round numeric columns to 2 decimal places
    for col in df.columns:
        if col in skip_cols:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].round(2)
    
    # Write CSV with float_format to prevent scientific notation
    df.to_csv(output_filepath, index=False, float_format='%.2f')
    return df
