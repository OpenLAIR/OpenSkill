"""SEC 13F Analyzer utility functions.

Provides loading, entity resolution, holdings analytics for 13F TSV datasets.
"""
import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz, utils as rf_utils

# For 2023+ data, VALUE column is in exact dollars (multiplier=1)
DEFAULT_VALUE_MULTIPLIER = 1


def load_coverpage(filepath: str) -> pd.DataFrame:
    """Load COVERPAGE.tsv preserving string datatypes."""
    df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
    df.columns = [col.upper().strip() for col in df.columns]
    return df


def load_infotable(filepath: str, value_multiplier: int = DEFAULT_VALUE_MULTIPLIER) -> pd.DataFrame:
    """Load INFOTABLE.tsv with type safety and standardized CUSIPs."""
    df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
    df.columns = [col.upper().strip() for col in df.columns]

    if 'CUSIP' in df.columns:
        df['CUSIP'] = df['CUSIP'].fillna('').str.strip().str.upper().str.zfill(9)

    if 'PUTCALL' in df.columns:
        df['PUTCALL'] = df['PUTCALL'].fillna('').str.strip().str.upper()
    else:
        df['PUTCALL'] = ''

    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce').fillna(0) * value_multiplier
    df['SSHPRNAMT'] = pd.to_numeric(df['SSHPRNAMT'], errors='coerce').fillna(0)
    return df


def load_summarypage(filepath: str, value_multiplier: int = DEFAULT_VALUE_MULTIPLIER) -> pd.DataFrame:
    """Load SUMMARYPAGE.tsv for aggregate AUM derivation."""
    df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
    df.columns = [col.upper().strip() for col in df.columns]
    df['TABLEVALUETOTAL'] = pd.to_numeric(df['TABLEVALUETOTAL'], errors='coerce').fillna(0) * value_multiplier
    if 'TABLEENTRYTOTAL' in df.columns:
        df['TABLEENTRYTOTAL'] = pd.to_numeric(df['TABLEENTRYTOTAL'], errors='coerce').fillna(0).astype(int)
    return df


def fuzzy_find_manager(coverpage_df: pd.DataFrame, query: str, top_n: int = 5) -> pd.DataFrame:
    """Fuzzy match fund manager names using RapidFuzz WRatio."""
    choices = coverpage_df['FILINGMANAGER_NAME'].fillna('').tolist()
    results = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=top_n,
        processor=rf_utils.default_process,
    )
    # results entries are (choice, score, index)
    indices = [r[2] for r in results]
    scores = [r[1] for r in results]
    res_df = coverpage_df.iloc[indices].copy()
    res_df['MATCH_SCORE'] = scores
    cols = ['ACCESSION_NUMBER', 'FILINGMANAGER_NAME', 'MATCH_SCORE']
    return res_df[cols].reset_index(drop=True)


def get_fund_holdings(infotable_df: pd.DataFrame, accession_number: str,
                     exclude_options: bool = True) -> pd.DataFrame:
    """Get deduplicated equity holdings for a given accession number."""
    fund_df = infotable_df[infotable_df['ACCESSION_NUMBER'] == accession_number]
    if exclude_options:
        fund_df = fund_df[fund_df['PUTCALL'] == '']
    agg_dict = {
        'NAMEOFISSUER': 'first',
        'TITLEOFCLASS': 'first',
        'VALUE': 'sum',
        'SSHPRNAMT': 'sum',
    }
    return fund_df.groupby('CUSIP', as_index=False).agg(agg_dict).sort_values('VALUE', ascending=False)


def get_fund_aum(summarypage_df: pd.DataFrame, accession_number: str) -> float:
    """Get gross AUM (TABLEVALUETOTAL) from summary page."""
    fund = summarypage_df[summarypage_df['ACCESSION_NUMBER'] == accession_number]
    if fund.empty:
        return 0.0
    return float(fund['TABLEVALUETOTAL'].iloc[0])


def compare_holdings(holdings_q1: pd.DataFrame, holdings_q2: pd.DataFrame) -> pd.DataFrame:
    """Compute longitudinal delta between two holdings dataframes."""
    merged = pd.merge(
        holdings_q1[['CUSIP', 'NAMEOFISSUER', 'VALUE', 'SSHPRNAMT']],
        holdings_q2[['CUSIP', 'VALUE', 'SSHPRNAMT']],
        on='CUSIP', how='outer', suffixes=('_Q1', '_Q2'),
    ).fillna({'VALUE_Q1': 0, 'VALUE_Q2': 0, 'SSHPRNAMT_Q1': 0, 'SSHPRNAMT_Q2': 0, 'NAMEOFISSUER': ''})
    merged['VALUE_DELTA'] = merged['VALUE_Q2'] - merged['VALUE_Q1']
    merged['SHARES_DELTA'] = merged['SSHPRNAMT_Q2'] - merged['SSHPRNAMT_Q1']
    return merged.sort_values('VALUE_DELTA', ascending=False)


def top_holders_of_cusip(infotable_df: pd.DataFrame, coverpage_df: pd.DataFrame,
                         cusip: str, n: int = 3) -> pd.DataFrame:
    """Rank top institutional holders of a CUSIP by aggregate VALUE."""
    cusip = cusip.strip().upper().zfill(9)
    target = infotable_df[(infotable_df['CUSIP'] == cusip) & (infotable_df['PUTCALL'] == '')]
    totals = target.groupby('ACCESSION_NUMBER', as_index=False)['VALUE'].sum()
    merged = pd.merge(totals, coverpage_df[['ACCESSION_NUMBER', 'FILINGMANAGER_NAME']],
                      on='ACCESSION_NUMBER', how='left')
    return merged.sort_values('VALUE', ascending=False).head(n).reset_index(drop=True)


def find_cusip_for_issuer(infotable_df: pd.DataFrame, issuer_substr: str) -> pd.DataFrame:
    """Find CUSIPs whose issuer name matches a substring (case-insensitive)."""
    mask = infotable_df['NAMEOFISSUER'].fillna('').str.upper().str.contains(issuer_substr.upper())
    sub = infotable_df[mask]
    grp = sub.groupby(['CUSIP', 'NAMEOFISSUER'], as_index=False).agg(VALUE=('VALUE', 'sum'),
                                                                      COUNT=('ACCESSION_NUMBER', 'nunique'))
    return grp.sort_values('VALUE', ascending=False).reset_index(drop=True)
