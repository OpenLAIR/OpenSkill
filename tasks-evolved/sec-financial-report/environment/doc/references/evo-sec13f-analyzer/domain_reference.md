# Domain Reference for evo-sec13f-analyzer

**Responsibility**: Provide all data loading, entity resolution, and holdings analytics utilities for SEC 13F datasets.

**Key functions to implement**: load_coverpage, load_infotable, load_summarypage, fuzzy_find_manager, get_fund_aum, get_fund_holdings, compare_holdings, top_holders_of_cusip

---

## 2. Dataset Architecture and File Structure


The SEC provides the 13F data as bulk ZIP archives (e.g., `01dec2025-28feb2026_form13f.zip`) containing multiple flat TSV (Tab-Separated Values) files [cite: 4, 5]. The delimiter used across all files is the tab character (`\t`) [cite: 6]. The files are standard UTF-8 encoded, and quoting issues are generally minimal, though stray tabs in text fields occasionally cause parsing misalignments.

### 2.2 Schema Definitions for Core Tables



## 3. The Critical 2023 SEC Value Reporting Rule Change


Any longitudinal programmatic analysis of Form 13F datasets must account for EDGAR Release 22.4.1, which went into effect on January 3, 2023 [cite: 9]. This SEC rule amendment fundamentally altered the unit of measurement in the `VALUE` column.

**Prior to January 3, 2023:** 
Filers were required to round all dollar values in the Information Table to the nearest one thousand dollars (e.g., omitting the "000" suffix) [cite: 2, 10]. A value of `$150,000,000` was reported as `150000`.

**After January 3, 2023:** 
The SEC simplified the rounding conventions, mandating that the `VALUE` column (and `TABLEVALUETOTAL`) reflect the exact market value rounded to the nearest U.S. dollar [cite: 10, 12]. Therefore, an entry of `150000000` now directly represents `$150,000,000` [cite: 12]. This impacts all filings for the period ending December 31, 2022, submitted in February 2023, as well as subsequent amendments to prior reports filed after the implementation date [cite: 9, 10].

## 4. Data Processing and Loading with Pandas


When importing the TSV dumps using `pandas`, the single most catastrophic error is allowing pandas to infer data types automatically. CUSIPs often begin with leading zeros (e.g., Apple Inc.'s CUSIP is `037833100` [cite: 13]). If loaded as numeric, the CUSIP becomes `37833100`, rendering subsequent relational joins with market data providers impossible.

## 5. Advanced Analytical Patterns in Hedge Fund Analysis



## 6. Entity Resolution via RapidFuzz (v3.x)


A pervasive issue in 13F analytics is the slight alteration of fund manager names over time or across databases (e.g., "Renaissance Technologies LLC" vs. "RENAISSANCE TECHNOLOGIES, LLC"). This requires robust fuzzy matching text resolution [cite: 15].

The standard library for this in modern Python architectures is **RapidFuzz**, a C++ optimized library that operates as a high-performance drop-in replacement for the older `fuzzywuzzy` or `thefuzz` [cite: 15, 16]. RapidFuzz resolves licensing constraints (MIT licensed vs GPL) and provides massive execution speedups [cite: 16, 17].

## 7. Financial Identifier Normalization (CUSIP)


The CUSIP (Committee on Uniform Securities Identification Procedures) is a strictly 9-character alphanumeric identifier [cite: 8].

## 8. Methodological Pitfalls and Data Artifacts


Beyond data-type conversion and rule changes, the Form 13F dataset exhibits several domain-specific quirks that can severely compromise analytical integrity.

## 9. Reusable Python Utility Skill Module


Synthesizing the methodologies above, the following is a comprehensive, production-ready Python class utilizing the pandas and RapidFuzz APIs.

```python
import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz, utils
from typing import Tuple

class SEC13FAnalyzer:
    """
    A comprehensive toolkit for parsing and analyzing SEC Form 13F structured TSV datasets.
    Handles SEC 2023 value rule changes, CUSIP normalization, and entity resolution.
    """
    
    def __init__(self, value_multiplier: int = 1):
        """
        Args:
            value_multiplier: Use 1000 for datasets prior to Q4 2022 (where SEC 
                              mandated rounding to nearest thousand). Use 1 for Q4 2022 
                              and later (exact dollar reporting).
        """
        self.value_multiplier = value_multiplier

    def load_coverpage(self, filepath: str) -> pd.DataFrame:
        """Loads COVERPAGE.tsv preserving string datatypes."""
        df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
        df.columns = [col.upper().strip() for col in df.columns]
        return df

    def load_infotable(self, filepath: str) -> pd.DataFrame:
        """Loads INFOTABLE.tsv, applies type safety, and standardizes CUSIPs."""
        df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
        df.columns = [col.upper().strip() for col in df.columns]
        
        # Standardize CUSIP: uppercase, strip whitespace, pad to 9 chars
        if 'CUSIP' in df.columns:
            df['CUSIP'] = df['CUSIP'].fillna('').str.strip().str.upper().str.zfill(9)
            
        # Standardize PUTCALL flag
        if 'PUTCALL' in df.columns:
            df['PUTCALL'] = df['PUTCALL'].fillna('').str.strip().str.upper()
        else:
            df['PUTCALL'] = ''
            
        # Typecasting values
        df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce').fillna(0) * self.value_multiplier
        df['SSHPRNAMT'] = pd.to_numeric(df['SSHPRNAMT'], errors='coerce').fillna(0)
        
        return df

    def load_summarypage(self, filepath: str) -> pd.DataFrame:
        """Loads SUMMARYPAGE.tsv for aggregate AUM derivation."""
        df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
        df.columns = [col.upper().strip() for col in df.columns]
        df['TABLEVALUETOTAL'] = pd.to_numeric(df['TABLEVALUETOTAL'], errors='coerce').fillna(0) * self.value_multiplier
        return df

    def fuzzy_find_manager(self, coverpage_df: pd.DataFrame, query: str, top_n: int = 5) -> pd.DataFrame:
        """
        Performs entity resolution to find fund managers by name using RapidFuzz v3.x.
        """
        choices = coverpage_df['FILINGMANAGER_NAME'].fillna('').tolist()
        
        # Using WRatio with default_process for robust text matching [cite: 20, 21]
        results = process.extract(
            query,
            choices,
            scorer=fuzz.WRatio,
            limit=top_n,
            processor=utils.default_process
        )
        
        indices = [res[cite: 6] for res in results]
        scores = [res[cite: 1] for res in results]
        
        res_df = coverpage_df.iloc[indices].copy()
        res_df['MATCH_SCORE'] = scores
        return res_df[['ACCESSION_NUMBER', 'FILINGMANAGER_NAME', 'MATCH_SCORE']]

    def get_fund_holdings(self, infotable_df: pd.DataFrame, accession_number: str) -> pd.DataFrame:
        """
        Deduplicates and extracts pure equity holdings for a single fund submission.
        """
        fund_df = infotable_df[infotable_df['ACCESSION_NUMBER'] == accession_number]
        
        # Exclude options [cite: 8]
        equity_df = fund_df[fund_df['PUTCALL'] == '']
        
        # Deduplicate CUSIPs
        agg_dict = {
            'NAMEOFISSUER': 'first',
            'TITLEOFCLASS': 'first',
            'VALUE': 'sum',
            'SSHPRNAMT': 'sum'
        }
        return equity_df.groupby('CUSIP', as_index=False).agg(agg_dict).sort_values('VALUE', ascending=False)

    def get_fund_aum(self, summarypage_df: pd.DataFrame, accession_number: str) -> float:
        """
        Extracts the official gross portfolio AUM from the summary page.
        """
        fund = summarypage_df[summarypage_df['ACCESSION_NUMBER'] == accession_number]
        if fund.empty:
            return 0.0
        return fund['TABLEVALUETOTAL'].iloc

    def compare_holdings(self, holdings_q1: pd.DataFrame, holdings_q2: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates longitudinal delta between two processed holdings dataframes.
        Expects dataframes generated by `get_fund_holdings`.
        """
        # Outer merge on CUSIP
        merged = pd.merge(
            holdings_q1[['CUSIP', 'NAMEOFISSUER', 'VALUE', 'SSHPRNAMT']],
            holdings_q2[['CUSIP', 'VALUE', 'SSHPRNAMT']],
            on='CUSIP',
            how='outer',
            suffixes=('_Q1', '_Q2')
        ).fillna(0)
        
        # Calculate Deltas
        merged['VALUE_DELTA'] = merged['VALUE_Q2'] - merged['VALUE_Q1']
        merged['SHARES_DELTA'] = merged['SSHPRNAMT_Q2'] - merged['SSHPRNAMT_Q1']
        
        return merged.sort_values('VALUE_DELTA', ascending=False)

    def top_holders_of_cusip(self, infotable_df: pd.DataFrame, coverpage_df: pd.DataFrame, 
                             cusip: str, n: int = 3) -> pd.DataFrame:
        """
        Ranks top institutional owners of a target CUSIP.
        """
        target = infotable_df[(infotable_df['CUSIP'] == cusip) & (infotable_df['PUTCALL'] == '')]
        totals = target.groupby('ACCESSION_NUMBER', as_index=False)['VALUE'].sum()
        
        merged = pd.merge(totals, coverpage_df[['ACCESSION_NUMBER', 'FILINGMANAGER_NAME']], 
                          on='ACCESSION_NUMBER', how='left')
                          
        return merged.sort_values('VALUE', ascending=False).head(n)
```