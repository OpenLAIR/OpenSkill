"""
evo-pdf-excel-extraction utility functions
Extracts tabular data from PDF files using pdfplumber and reads Excel files
using pandas/openpyxl, returning normalized pandas DataFrames.
"""

import pdfplumber
import pandas as pd
import numpy as np
from typing import List, Optional, Dict


def extract_table_from_pdf(pdf_path: str, table_settings: dict = None) -> pd.DataFrame:
    """
    Extract a multi-page table from a PDF file using pdfplumber.
    
    Iterates over all pages, extracts tables, detects headers from the first page,
    handles repeated headers on subsequent pages, and concatenates all rows.
    
    Args:
        pdf_path: Path to the PDF file
        table_settings: Optional pdfplumber table_settings dict. 
                       If None, uses default line-based strategy.
    
    Returns:
        pd.DataFrame with all extracted rows and cleaned headers
    """
    if table_settings is None:
        # Default settings - try lines first (works for most structured PDFs)
        table_settings = {}
    
    all_data = []
    headers = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Use extract_table for the largest table on each page
            table = page.extract_table(table_settings)
            
            if not table or len(table) < 1:
                continue
            
            if headers is None:
                # First page: first row is headers
                raw_headers = table[0]
                headers = [
                    str(h).replace('\n', ' ').strip() if h is not None else f"Col_{i}"
                    for i, h in enumerate(raw_headers)
                ]
                data_rows = table[1:]
            else:
                # Subsequent pages: check if first row is a repeated header
                first_row_cleaned = [
                    str(c).replace('\n', ' ').strip() if c is not None else ""
                    for c in table[0]
                ]
                if first_row_cleaned == headers:
                    data_rows = table[1:]
                else:
                    data_rows = table
            
            all_data.extend(data_rows)
    
    if not all_data or headers is None:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_data, columns=headers)
    
    # Clean string cells: strip whitespace and replace newlines
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: x.replace('\n', ' ').strip() if isinstance(x, str) else x
        )
    
    return df


def read_excel_file(excel_path: str, id_column: str = 'ID', 
                    sheet_name=0, dtype_map: dict = None) -> pd.DataFrame:
    """
    Read an Excel .xlsx file using pandas with openpyxl engine.
    
    Preserves string IDs by explicitly setting dtype for the ID column.
    
    Args:
        excel_path: Path to the .xlsx file
        id_column: Name of the ID column to preserve as string
        sheet_name: Sheet name or index (default 0)
        dtype_map: Optional explicit dtype mapping
    
    Returns:
        pd.DataFrame with data from the Excel file
    """
    if dtype_map is None:
        dtype_map = {id_column: str}
    
    df = pd.read_excel(
        excel_path,
        engine='openpyxl',
        sheet_name=sheet_name,
        dtype=dtype_map
    )
    return df


def normalize_dataframe(df: pd.DataFrame, id_column: str = 'ID',
                       numeric_columns: List[str] = None) -> pd.DataFrame:
    """
    Normalize a DataFrame for consistent comparison:
    - Strip whitespace from all string columns
    - Preserve ID column as string
    - Coerce numeric columns (handle commas, convert to numeric)
    - Replace empty strings and 'nan'/'None' with NaN
    
    Args:
        df: Input DataFrame
        id_column: Name of the ID/key column (preserved as string)
        numeric_columns: List of column names to coerce to numeric
    
    Returns:
        Normalized DataFrame
    """
    if numeric_columns is None:
        numeric_columns = []
    
    df_clean = df.copy()
    
    # 1. Ensure ID column is string and clean
    if id_column in df_clean.columns:
        df_clean[id_column] = df_clean[id_column].astype(str).str.strip()
        # Remove any .0 suffix from float conversion
        df_clean[id_column] = df_clean[id_column].str.replace(r'\.0$', '', regex=True)
    
    # 2. Clean string columns
    str_cols = [c for c in df_clean.columns if c != id_column and c not in numeric_columns]
    for col in str_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
            df_clean[col] = df_clean[col].replace(
                {'nan': np.nan, 'None': np.nan, '': np.nan}
            )
    
    # 3. Coerce numeric columns
    for col in numeric_columns:
        if col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                # Remove commas (e.g., "112,000" -> "112000")
                df_clean[col] = df_clean[col].astype(str).str.replace(',', '', regex=False)
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    # 4. Drop rows where ID is NaN or empty
    if id_column in df_clean.columns:
        df_clean = df_clean[df_clean[id_column].notna() & (df_clean[id_column] != '') & (df_clean[id_column] != 'nan')]
    
    return df_clean
