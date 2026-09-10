"""
evo-dataframe-diff-report utility functions
Compares two pandas DataFrames (old vs new) by a key column to identify
deleted rows and modified fields, then exports results as JSON.
"""

import pandas as pd
import numpy as np
import json
from typing import List, Dict, Any, Optional


class NumpyTypeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles NumPy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
        return super().default(obj)


def find_deleted_employees(df_old: pd.DataFrame, df_new: pd.DataFrame,
                           id_column: str = 'ID') -> List[str]:
    """
    Find employee IDs that exist in df_old but not in df_new (deleted).
    
    Args:
        df_old: Old/backup DataFrame (from PDF)
        df_new: Current DataFrame (from Excel)
        id_column: Name of the ID column
    
    Returns:
        Sorted list of deleted employee ID strings
    """
    old_ids = set(df_old[id_column].dropna().unique())
    new_ids = set(df_new[id_column].dropna().unique())
    deleted = sorted(list(old_ids - new_ids))
    return deleted


def find_modified_employees(df_old: pd.DataFrame, df_new: pd.DataFrame,
                            id_column: str = 'ID',
                            numeric_columns: List[str] = None,
                            float_tolerance: float = 1e-4) -> List[Dict[str, Any]]:
    """
    Find employees that exist in both DataFrames but have modified fields.
    
    Returns one entry per changed field (not per employee), matching the
    required output format:
    {"id": "EMP00003", "field": "Salary", "old_value": 50020, "new_value": 55010}
    
    Args:
        df_old: Old/backup DataFrame
        df_new: Current DataFrame  
        id_column: Name of the ID column
        numeric_columns: List of numeric column names for tolerance comparison
        float_tolerance: Absolute tolerance for float comparisons
    
    Returns:
        List of modification dicts, sorted by ID then field
    """
    if numeric_columns is None:
        numeric_columns = []
    
    # Find common IDs
    old_ids = set(df_old[id_column].dropna().unique())
    new_ids = set(df_new[id_column].dropna().unique())
    common_ids = old_ids & new_ids
    
    # Index both DataFrames by ID for fast lookup
    df_old_indexed = df_old.set_index(id_column)
    df_new_indexed = df_new.set_index(id_column)
    
    # Get columns to compare (all shared columns except ID)
    compare_cols = [c for c in df_old_indexed.columns if c in df_new_indexed.columns]
    
    modifications = []
    
    for emp_id in sorted(common_ids):
        old_row = df_old_indexed.loc[emp_id]
        new_row = df_new_indexed.loc[emp_id]
        
        # Handle case where ID is duplicated (take first)
        if isinstance(old_row, pd.DataFrame):
            old_row = old_row.iloc[0]
        if isinstance(new_row, pd.DataFrame):
            new_row = new_row.iloc[0]
        
        for col in compare_cols:
            v_old = old_row[col]
            v_new = new_row[col]
            
            # Both NaN -> equal
            old_is_nan = pd.isna(v_old)
            new_is_nan = pd.isna(v_new)
            
            if old_is_nan and new_is_nan:
                continue
            
            if old_is_nan or new_is_nan:
                # One is NaN, the other isn't -> modified
                modifications.append({
                    "id": emp_id,
                    "field": col,
                    "old_value": _convert_value(v_old, col, numeric_columns),
                    "new_value": _convert_value(v_new, col, numeric_columns)
                })
                continue
            
            # Numeric comparison with tolerance
            if col in numeric_columns:
                try:
                    f_old = float(v_old)
                    f_new = float(v_new)
                    if not np.isclose(f_old, f_new, atol=float_tolerance):
                        modifications.append({
                            "id": emp_id,
                            "field": col,
                            "old_value": _convert_value(v_old, col, numeric_columns),
                            "new_value": _convert_value(v_new, col, numeric_columns)
                        })
                except (ValueError, TypeError):
                    if str(v_old).strip() != str(v_new).strip():
                        modifications.append({
                            "id": emp_id,
                            "field": col,
                            "old_value": _convert_value(v_old, col, numeric_columns),
                            "new_value": _convert_value(v_new, col, numeric_columns)
                        })
            else:
                # String comparison
                if str(v_old).strip() != str(v_new).strip():
                    modifications.append({
                        "id": emp_id,
                        "field": col,
                        "old_value": _convert_value(v_old, col, numeric_columns),
                        "new_value": _convert_value(v_new, col, numeric_columns)
                    })
    
    return modifications


def _convert_value(value, field: str, numeric_columns: List[str]):
    """
    Convert a value to the appropriate Python native type for JSON output.
    
    - Numeric fields (Salary, Years, Score): output as numbers
      - Salary and Years: integers
      - Score: float
    - Text fields: output as strings
    - NaN: output as None
    """
    if pd.isna(value):
        return None
    
    if field in numeric_columns:
        try:
            f_val = float(value)
            # If value is effectively an integer (Salary, Years), return int
            if field in ('Salary', 'Years'):
                return int(round(f_val))
            else:
                # Score - return as float
                # Check if it's a whole number
                if f_val == int(f_val) and '.' not in str(value):
                    return int(f_val)
                return float(f_val)
        except (ValueError, TypeError):
            return str(value)
    else:
        return str(value)


def build_diff_report(deleted: List[str], modified: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the final diff report dictionary.
    
    Args:
        deleted: Sorted list of deleted employee IDs
        modified: Sorted list of modification dicts
    
    Returns:
        Dict with 'deleted_employees' and 'modified_employees' keys
    """
    return {
        "deleted_employees": sorted(deleted),
        "modified_employees": sorted(modified, key=lambda x: (x["id"], x["field"]))
    }


def export_diff_to_json(report: Dict[str, Any], output_path: str, indent: int = 2):
    """
    Export the diff report to a JSON file with proper NumPy type handling.
    
    Args:
        report: The diff report dictionary
        output_path: Path to write the JSON file
        indent: JSON indentation level
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, cls=NumpyTypeEncoder, indent=indent, ensure_ascii=False)
