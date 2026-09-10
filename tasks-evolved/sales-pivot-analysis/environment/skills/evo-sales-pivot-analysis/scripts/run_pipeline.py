#!/usr/bin/env python3
"""
Complete demographic analysis pipeline.
Extracts population from PDF, loads income from Excel, merges, computes quartiles,
creates native openpyxl pivot tables, and exports multi-sheet workbook.
"""

import sys
import os
import re
import warnings
import pdfplumber
import pandas as pd
import numpy as np
from copy import copy

from openpyxl import Workbook
from openpyxl.pivot.table import (
    TableDefinition,
    PivotField,
    Reference,
    DataField,
    Location,
)
from openpyxl.pivot.fields import FieldList, Field, RowColField, RowColFieldList
from openpyxl.pivot.cache import (
    CacheDefinition,
    CacheField,
    CacheSource,
    WorksheetSource,
    SharedItems,
    String,
    Number,
)
from openpyxl.utils import get_column_letter


# ============================================================================
# 1. PDF EXTRACTION - Line-by-line text parsing for robustness
# ============================================================================

VALID_STATES = {
    "New South Wales",
    "Victoria",
    "Queensland",
    "South Australia",
    "Western Australia",
    "Tasmania",
    "Northern Territory",
    "Australian Capital Territory",
}


def extract_population_from_pdf(pdf_path):
    """
    Extract population data from multi-page PDF using multiple strategies.
    Strategy 1: pdfplumber table extraction
    Strategy 2: Line-by-line text parsing with regex
    Returns the strategy that yields more rows.
    """
    df_table = _extract_via_table(pdf_path)
    df_text = _extract_via_text(pdf_path)

    print(f"  Table extraction: {len(df_table)} rows")
    print(f"  Text extraction:  {len(df_text)} rows")

    # Use whichever yields more rows
    if len(df_text) >= len(df_table):
        print("  → Using text-based extraction")
        return df_text
    else:
        print("  → Using table-based extraction")
        return df_table


def _extract_via_table(pdf_path):
    """Extract using pdfplumber's table extraction with multiple configs."""
    all_rows = []
    header = None

    extraction_configs = [
        {},
        {"vertical_strategy": "text", "horizontal_strategy": "text",
         "snap_tolerance": 5, "intersection_x_tolerance": 15},
        {"vertical_strategy": "text", "horizontal_strategy": "lines",
         "snap_tolerance": 5, "intersection_x_tolerance": 10},
    ]

    with pdfplumber.open(pdf_path) as pdf:
        best_config = extraction_configs[0]
        for config in extraction_configs:
            test_table = pdf.pages[0].extract_table(table_settings=config) if pdf.pages else None
            if test_table and len(test_table) > 1 and len(test_table[0]) >= 4:
                best_config = config
                break

        for page in pdf.pages:
            table = page.extract_table(table_settings=best_config)
            if table is None:
                continue
            for row in table:
                if row is None:
                    continue
                cleaned = []
                for cell in row:
                    if cell is not None:
                        cleaned.append(str(cell).replace('\n', ' ').strip())
                    else:
                        cleaned.append('')
                first = cleaned[0] if cleaned else ''
                if 'SA2' in first.upper() and 'CODE' in first.upper():
                    if header is None:
                        header = cleaned
                    continue
                if all(c == '' for c in cleaned):
                    continue
                all_rows.append(cleaned)

    if not all_rows or header is None:
        return pd.DataFrame(columns=['SA2_CODE', 'SA2_NAME', 'STATE', 'POPULATION_2023'])

    fixed_header = []
    for h in header:
        h_str = str(h).strip()
        if 'POPULATION' in h_str.upper():
            fixed_header.append('POPULATION_2023')
        else:
            fixed_header.append(h_str)

    expected_cols = len(fixed_header)
    cleaned_rows = []
    for row in all_rows:
        if len(row) < expected_cols:
            row = row + [''] * (expected_cols - len(row))
        elif len(row) > expected_cols:
            row = row[:expected_cols]
        cleaned_rows.append(row)

    df = pd.DataFrame(cleaned_rows, columns=fixed_header)
    df = _clean_population_df(df)
    return df


def _extract_via_text(pdf_path):
    """Extract using line-by-line text parsing with regex."""
    # Pattern: 9-digit SA2 code at start of line
    sa2_pattern = re.compile(r'^(\d{9})\s+(.+)$')
    records = []
    current_state = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text is None:
                continue
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check if line is a state name
                for state in VALID_STATES:
                    if line.strip() == state or line.strip().startswith(state):
                        current_state = state
                        break

                # Check for header row - skip it
                if 'SA2_CODE' in line.upper() or 'SA2 CODE' in line.upper():
                    continue

                # Try to match SA2 data row
                m = sa2_pattern.match(line)
                if m:
                    sa2_code = m.group(1)
                    rest = m.group(2).strip()
                    # Parse the rest: SA2_NAME STATE POPULATION
                    # Try to find state name in the rest
                    found_state = None
                    for state in VALID_STATES:
                        if state in rest:
                            found_state = state
                            break

                    if found_state:
                        # Split around state name
                        parts = rest.split(found_state)
                        sa2_name = parts[0].strip()
                        pop_str = parts[1].strip() if len(parts) > 1 else ''
                        records.append({
                            'SA2_CODE': sa2_code,
                            'SA2_NAME': sa2_name,
                            'STATE': found_state,
                            'POPULATION_2023': pop_str
                        })
                    elif current_state:
                        # State not in line, use current_state context
                        # The population number is likely at the end
                        # Try to split: everything before last number group is name
                        pop_match = re.search(r'([\d,]+)\s*$', rest)
                        if pop_match:
                            pop_str = pop_match.group(1)
                            sa2_name = rest[:pop_match.start()].strip()
                        else:
                            sa2_name = rest
                            pop_str = ''
                        records.append({
                            'SA2_CODE': sa2_code,
                            'SA2_NAME': sa2_name,
                            'STATE': current_state,
                            'POPULATION_2023': pop_str
                        })

    if not records:
        return pd.DataFrame(columns=['SA2_CODE', 'SA2_NAME', 'STATE', 'POPULATION_2023'])

    df = pd.DataFrame(records)
    df = _clean_population_df(df)
    return df


def _clean_population_df(df):
    """Clean and type-coerce population DataFrame."""
    if df.empty:
        return df

    # Ensure required columns exist
    for col in ['SA2_CODE', 'SA2_NAME', 'STATE', 'POPULATION_2023']:
        if col not in df.columns:
            df[col] = ''

    # SA2_CODE
    df['SA2_CODE'] = (
        df['SA2_CODE'].astype(str)
        .str.replace(',', '', regex=False)
        .str.replace(r'[^\d]', '', regex=True)
        .str.strip()
    )
    df['SA2_CODE'] = pd.to_numeric(df['SA2_CODE'], errors='coerce')

    # SA2_NAME and STATE
    df['SA2_NAME'] = df['SA2_NAME'].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    df['STATE'] = df['STATE'].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)

    # POPULATION_2023
    df['POPULATION_2023'] = (
        df['POPULATION_2023'].astype(str)
        .str.replace(',', '', regex=False)
        .str.replace(r'[^\d.]', '', regex=True)
        .str.strip()
    )
    df['POPULATION_2023'] = pd.to_numeric(df['POPULATION_2023'], errors='coerce')

    # Drop invalid rows
    df = df.dropna(subset=['SA2_CODE'])
    df['SA2_CODE'] = df['SA2_CODE'].astype(int)

    # Filter to valid states only
    df = df[df['STATE'].isin(VALID_STATES)].copy()

    # Deduplicate by SA2_CODE
    df = df.drop_duplicates(subset=['SA2_CODE'], keep='first')

    return df


# ============================================================================
# 2. EXCEL INGESTION
# ============================================================================

def load_income_from_excel(excel_path):
    """Load income data from Excel."""
    df = pd.read_excel(
        excel_path, engine='openpyxl', sheet_name=0, header=0,
        na_values=['-', '...', 'null', 'N/A', 'n/a', '']
    )
    df.columns = [str(c).strip().upper().replace(' ', '_') for c in df.columns]

    df['SA2_CODE'] = pd.to_numeric(df['SA2_CODE'], errors='coerce')
    df = df.dropna(subset=['SA2_CODE'])
    df['SA2_CODE'] = df['SA2_CODE'].astype(int)

    if 'SA2_NAME' in df.columns:
        df['SA2_NAME'] = df['SA2_NAME'].astype(str).str.strip()

    for col in ['EARNERS', 'MEDIAN_INCOME', 'MEAN_INCOME']:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(',', '', regex=False)
                .str.replace('$', '', regex=False)
                .str.replace(' ', '', regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


# ============================================================================
# 3. MERGE
# ============================================================================

def merge_data(df_pop, df_income):
    """Merge population and income on SA2_CODE (inner join)."""
    for df in [df_pop, df_income]:
        df['SA2_CODE'] = pd.to_numeric(df['SA2_CODE'], errors='coerce')
        df.dropna(subset=['SA2_CODE'], inplace=True)
        df['SA2_CODE'] = df['SA2_CODE'].astype(int)

    pop_cols = [c for c in ['SA2_CODE', 'SA2_NAME', 'STATE', 'POPULATION_2023'] if c in df_pop.columns]
    income_cols = [c for c in ['SA2_CODE', 'EARNERS', 'MEDIAN_INCOME', 'MEAN_INCOME'] if c in df_income.columns]

    df = pd.merge(df_pop[pop_cols], df_income[income_cols], on='SA2_CODE', how='inner')

    if df.empty:
        warnings.warn("Merge produced zero rows!")

    return df


# ============================================================================
# 4. RANGE-BASED QUARTILES
# ============================================================================

def assign_range_quartiles(df):
    """
    Assign quartiles based on equal-width range bins of MEDIAN_INCOME.
    Q1 = lowest range, Q4 = highest range.
    bin_width = (max - min) / 4
    """
    df = df.copy()
    df['MEDIAN_INCOME'] = pd.to_numeric(df['MEDIAN_INCOME'], errors='coerce')

    valid = df['MEDIAN_INCOME'].notna()
    if valid.sum() == 0:
        df['Quarter'] = np.nan
        return df

    min_val = df.loc[valid, 'MEDIAN_INCOME'].min()
    max_val = df.loc[valid, 'MEDIAN_INCOME'].max()
    step = (max_val - min_val) / 4.0

    boundaries = [
        min_val,
        min_val + step,
        min_val + 2 * step,
        min_val + 3 * step,
        max_val,
    ]

    def _assign(val):
        if pd.isna(val):
            return np.nan
        if val <= boundaries[1]:
            return 'Q1'
        elif val <= boundaries[2]:
            return 'Q2'
        elif val <= boundaries[3]:
            return 'Q3'
        else:
            return 'Q4'

    df['Quarter'] = df['MEDIAN_INCOME'].apply(_assign)
    return df


# ============================================================================
# 5. DERIVED COLUMNS
# ============================================================================

def compute_derived(df):
    """Compute Total = EARNERS * MEDIAN_INCOME."""
    df = df.copy()
    df['EARNERS'] = pd.to_numeric(df['EARNERS'], errors='coerce')
    df['MEDIAN_INCOME'] = pd.to_numeric(df['MEDIAN_INCOME'], errors='coerce')
    df['Total'] = df['EARNERS'] * df['MEDIAN_INCOME']
    return df


# ============================================================================
# 6. NATIVE OPENPYXL PIVOT TABLE CREATION
# ============================================================================

def _write_source_data(wb, df, sheet_name='SourceData'):
    """Write source data to a worksheet and return (ws, cell_range_string)."""
    ws = wb.create_sheet(title=sheet_name)
    headers = list(df.columns)

    # Write headers
    for c_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=c_idx, value=header)

    # Write data
    for r_idx, row in enumerate(df.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            if pd.isna(val) if isinstance(val, (float, np.floating)) else False:
                ws.cell(row=r_idx, column=c_idx, value=None)
            else:
                ws.cell(row=r_idx, column=c_idx, value=val)

    n_rows = len(df) + 1  # +1 for header
    n_cols = len(headers)
    cell_range = f"{sheet_name}!$A$1:${get_column_letter(n_cols)}${n_rows}"

    return ws, cell_range, headers, n_rows, n_cols


def _build_cache_fields(df, headers):
    """Build CacheField objects from DataFrame columns."""
    cache_fields = []
    for col_name in headers:
        series = df[col_name]

        if series.dtype == object or col_name in ('SA2_NAME', 'STATE', 'Quarter'):
            # String/categorical field
            unique_vals = sorted(series.dropna().unique().astype(str).tolist())
            shared = SharedItems(s=[String(v=v) for v in unique_vals])
            cf = CacheField(name=col_name, sharedItems=shared)
        else:
            # Numeric field
            vals = series.dropna()
            if len(vals) > 0:
                min_v = float(vals.min())
                max_v = float(vals.max())
                shared = SharedItems(
                    containsSemiMixedTypes=False,
                    containsString=False,
                    containsNumber=True,
                    minValue=min_v,
                    maxValue=max_v,
                )
            else:
                shared = SharedItems(
                    containsSemiMixedTypes=False,
                    containsString=False,
                    containsNumber=True,
                )
            cf = CacheField(name=col_name, sharedItems=shared)

        cache_fields.append(cf)

    return cache_fields


def _create_pivot_table(wb, source_ws, source_range, target_sheet_name,
                        df, headers, n_rows, n_cols,
                        row_field_name, data_field_name, agg_type,
                        col_field_name=None):
    """
    Create a native openpyxl pivot table on a new sheet.

    Parameters:
        row_field_name: column name for row labels (e.g., 'STATE')
        data_field_name: column name for values (e.g., 'POPULATION_2023')
        agg_type: 'sum' or 'count'
        col_field_name: column name for column labels (e.g., 'Quarter'), or None
    """
    target_ws = wb.create_sheet(title=target_sheet_name)

    # Build cache
    cache_fields = _build_cache_fields(df, headers)

    ws_source = WorksheetSource(sheet=source_ws.title, ref=f"A1:{get_column_letter(n_cols)}{n_rows}")
    cache_source = CacheSource(type='worksheet', worksheetSource=ws_source)

    cache_def = CacheDefinition(
        cacheSource=cache_source,
        cacheFields=cache_fields,
        recordCount=n_rows - 1,
    )

    # Find field indices
    row_idx = headers.index(row_field_name)
    data_idx = headers.index(data_field_name)
    col_idx = headers.index(col_field_name) if col_field_name else None

    # Build pivot fields - one per cache field
    pivot_fields = []
    for i, col_name in enumerate(headers):
        if i == row_idx:
            # Row field: axis=1 means row axis
            # Get unique values for item references
            unique_vals = sorted(df[col_name].dropna().unique().astype(str).tolist())
            items = [Field(x=j) for j in range(len(unique_vals))]
            items.append(Field(t='default'))  # default/total item
            pf = PivotField(axis=1, items=items, showAll=False)
        elif col_idx is not None and i == col_idx:
            # Column field: axis=2 means column axis
            unique_vals = sorted(df[col_name].dropna().unique().astype(str).tolist())
            items = [Field(x=j) for j in range(len(unique_vals))]
            items.append(Field(t='default'))
            pf = PivotField(axis=2, items=items, showAll=False)
        elif i == data_idx:
            pf = PivotField(dataField=True, showAll=False)
        else:
            pf = PivotField(showAll=False)
        pivot_fields.append(pf)

    # Row fields
    row_fields = RowColFieldList()
    row_fields.append(RowColField(x=row_idx))

    # Column fields
    col_fields = None
    if col_idx is not None:
        col_fields = RowColFieldList()
        col_fields.append(RowColField(x=col_idx))

    # Data field
    data_field = DataField(
        name=f"{'Sum' if agg_type == 'sum' else 'Count'} of {data_field_name}",
        fld=data_idx,
        subtotal=agg_type,
    )

    # Determine pivot table location on target sheet
    pivot_location = Location(ref="A1:Z50", firstHeaderRow=1, firstDataRow=2, firstDataCol=1)

    # Create pivot table definition
    pivot_table = TableDefinition(
        name=target_sheet_name.replace(' ', '_'),
        cacheId=0,
        dataFields=[data_field],
        pivotFields=pivot_fields,
        rowFields=row_fields,
        colFields=col_fields,
        location=pivot_location,
    )

    pivot_table.cache = cache_def
    target_ws._pivots.append(pivot_table)

    return target_ws


# ============================================================================
# 7. MAIN PIPELINE
# ============================================================================

def main(pdf_path='/root/population.pdf',
         excel_path='/root/income.xlsx',
         output_path='/root/demographic_analysis.xlsx'):
    """Run the complete pipeline."""

    print("[1/8] Extracting population data from PDF...")
    df_pop = extract_population_from_pdf(pdf_path)
    print(f"       → {len(df_pop)} rows extracted")

    print("[2/8] Loading income data from Excel...")
    df_income = load_income_from_excel(excel_path)
    print(f"       → {len(df_income)} rows loaded")

    print("[3/8] Merging data on SA2_CODE...")
    df = merge_data(df_pop, df_income)
    print(f"       → {len(df)} rows after merge")

    print("[4/8] Assigning range-based income quartiles...")
    df = assign_range_quartiles(df)

    print("[5/8] Computing derived columns...")
    df = compute_derived(df)

    # Ensure column order for SourceData
    desired_cols = ['SA2_CODE', 'SA2_NAME', 'STATE', 'POPULATION_2023',
                    'EARNERS', 'MEDIAN_INCOME', 'MEAN_INCOME', 'Quarter', 'Total']
    cols = [c for c in desired_cols if c in df.columns]
    # Add any extra columns not in desired list
    for c in df.columns:
        if c not in cols:
            cols.append(c)
    df = df[cols]

    print("[6/8] Creating workbook with native pivot tables...")
    wb = Workbook()
    # Remove default sheet
    default_sheet = wb.active
    wb.remove(default_sheet)

    # Write source data first (pivot tables reference it)
    source_ws, source_range, headers, n_rows, n_cols = _write_source_data(wb, df, 'SourceData')

    print("  Creating 'Population by State' pivot...")
    _create_pivot_table(
        wb, source_ws, source_range, 'Population by State',
        df, headers, n_rows, n_cols,
        row_field_name='STATE',
        data_field_name='POPULATION_2023',
        agg_type='sum',
    )

    print("  Creating 'Earners by State' pivot...")
    _create_pivot_table(
        wb, source_ws, source_range, 'Earners by State',
        df, headers, n_rows, n_cols,
        row_field_name='STATE',
        data_field_name='EARNERS',
        agg_type='sum',
    )

    print("  Creating 'Regions by State' pivot...")
    _create_pivot_table(
        wb, source_ws, source_range, 'Regions by State',
        df, headers, n_rows, n_cols,
        row_field_name='STATE',
        data_field_name='SA2_CODE',
        agg_type='count',
    )

    print("  Creating 'State Income Quartile' pivot...")
    _create_pivot_table(
        wb, source_ws, source_range, 'State Income Quartile',
        df, headers, n_rows, n_cols,
        row_field_name='STATE',
        data_field_name='EARNERS',
        agg_type='sum',
        col_field_name='Quarter',
    )

    # Reorder sheets: pivot sheets first, then SourceData
    sheet_order = [
        'Population by State',
        'Earners by State',
        'Regions by State',
        'State Income Quartile',
        'SourceData',
    ]
    for i, name in enumerate(sheet_order):
        idx = wb.sheetnames.index(name)
        wb.move_sheet(name, offset=i - idx)

    print(f"[7/8] Saving to {output_path}...")
    wb.save(output_path)
    print("[8/8] ✓ Done!")

    # Print summary
    print(f"\nSummary:")
    print(f"  Total rows: {len(df)}")
    print(f"  States: {sorted(df['STATE'].unique())}")
    print(f"  Quarters: {sorted(df['Quarter'].dropna().unique())}")


if __name__ == '__main__':
    main()