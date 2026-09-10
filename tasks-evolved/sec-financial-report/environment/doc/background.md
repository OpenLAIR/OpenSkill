# Comprehensive Methodological Guide to Programmatic Analysis of SEC Form 13F-HR Datasets

**Key Points:**
*   **Dataset Structure:** The SEC Form 13F dataset consists of structured tab-separated value (TSV) files extracted quarterly from EDGAR XML filings. Key files include `COVERPAGE.tsv`, `INFOTABLE.tsv`, and `SUMMARYPAGE.tsv`.
*   **Critical Regulatory Shift:** A major SEC rule change implemented on January 3, 2023, altered the `VALUE` column reporting standard from *thousands of dollars* to *exact dollars* (rounded to the nearest dollar). Analysts must programmatically detect and normalize this structural break to prevent massive calculation errors in time-series analyses.
*   **Data Processing:** Reading these datasets via the `pandas` library requires strict type enforcement (e.g., `dtype=str`) to prevent the truncation of critical leading zeros in identifiers like CUSIP numbers.
*   **Entity Resolution:** Fund manager names frequently vary due to legal entity structuring or data entry inconsistencies. The `rapidfuzz` library (specifically v3.x and above) provides optimal, C++ optimized fuzzy matching algorithms to resolve these entities longitudinally. 
*   **Holdings Filtering:** Accurately calculating equity positions requires explicitly filtering out derivative contracts documented in the `PUTCALL` column and appropriately handling amended filings (Form 13F-HR/A).

The U.S. Securities and Exchange Commission (SEC) mandates that institutional investment managers exercising investment discretion over $100 million or more in qualifying equity assets file a Form 13F quarterly [cite: 1, 2]. These filings provide the public with a longitudinal view of institutional asset allocation. However, parsing the bulk structured datasets requires nuanced handling of file schemas, regulatory rule changes, financial identifier normalizations, and entity resolution methodologies. This report provides an exhaustive technical roadmap for building robust, reusable Python pipelines to analyze Form 13F datasets.

## 1. Introduction to SEC Form 13F Structured Datasets

Form 13F was adopted pursuant to a statutory directive under Section 13(f) of the Securities Exchange Act of 1934, designed to increase public transparency regarding the securities holdings of large institutional investors [cite: 1, 3]. The SEC releases this data via EDGAR in eXtensible Markup Language (XML) format, which is subsequently flattened and published quarterly as zipped datasets [cite: 1, 4]. 

These structured datasets, which include submissions like the initial holdings report (13F-HR) and its amendments (13F-HR/A), provide raw, "as-filed" representations of the XML data [cite: 4]. Because the SEC derives this data directly from registrant submissions without altering the fundamental values, the dataset is susceptible to data entry anomalies, missing values, and variations in entity naming conventions [cite: 1, 4]. Consequently, any programmatic analysis must incorporate defensive programming paradigms, rigorous data type enforcement, and domain-specific heuristics.

## 2. Dataset Architecture and File Structure

The SEC provides the 13F data as bulk ZIP archives (e.g., `01dec2025-28feb2026_form13f.zip`) containing multiple flat TSV (Tab-Separated Values) files [cite: 4, 5]. The delimiter used across all files is the tab character (`\t`) [cite: 6]. The files are standard UTF-8 encoded, and quoting issues are generally minimal, though stray tabs in text fields occasionally cause parsing misalignments.

### 2.1 File Layout and Relationships

A standard quarterly ZIP archive contains the following interconnected files [cite: 4]:
*   **SUBMISSION.tsv**: Contains metadata about the submission itself.
*   **COVERPAGE.tsv**: Contains the primary details of the filing manager.
*   **SUMMARYPAGE.tsv**: Contains summary statistics of the portfolio.
*   **INFOTABLE.tsv**: The core relational table detailing individual security holdings.
*   **OTHERMANAGER.tsv** & **OTHERMANAGER2.tsv**: Details regarding other managers sharing investment discretion.
*   **SIGNATURE.tsv**: Signature metadata.
*   **FORM13FFILE.tsv**: File-level metadata.

The primary key linking these tables is the **`ACCESSION_NUMBER`**, a unique 20-character string assigned by the SEC to each specific filing submission [cite: 7].

### 2.2 Schema Definitions for Core Tables

#### 2.2.1 COVERPAGE.tsv
This file identifies the institutional investment manager submitting the report. Important columns include:
*   `ACCESSION_NUMBER`: The universal primary key linking the submission [cite: 7].
*   `REPORTCALENDARORQUARTER`: The ending date of the calendar quarter for which the report is filed (e.g., `12-31-2022`).
*   `FILINGMANAGER_NAME`: The legal name of the institutional investment manager.
*   `FILINGMANAGER_STREET1`, `FILINGMANAGER_CITY`, `FILINGMANAGER_STATEORCOUNTRY`, `FILINGMANAGER_ZIPCODE`: Address fields.
*   `CIK`: The Central Index Key (CIK) of the filing manager. *Note: CIK is often derived or exposed in the SUBMISSION.tsv or via the SEC's cross-reference mappings, but may appear as an optional field depending on the exact dataset vintage.*

#### 2.2.2 INFOTABLE.tsv
This is the most critical file for holdings analysis, detailing line-by-line portfolio positions [cite: 6].
*   `ACCESSION_NUMBER`: Foreign key to `COVERPAGE.tsv`.
*   `NAMEOFISSUER`: The name of the company issuing the security (e.g., "PALANTIR TECHNOLOGIES INC").
*   `TITLEOFCLASS`: The specific class of the security (e.g., "COM", "CL A").
*   `CUSIP`: The 9-character Committee on Uniform Securities Identification Procedures number [cite: 8].
*   `FIGI`: The Financial Instrument Global Identifier, a 12-character alphanumeric code added as an optional field starting in 2023 [cite: 9, 10].
*   `VALUE`: The market value of the holding at the end of the reporting period. The unit of this column is subject to a massive regulatory change (discussed in Section 3).
*   `SSHPRNAMT`: The number of shares or principal amount of the security held [cite: 11].
*   `SSHPRNAMTTYPE`: Identifies the type of amount (typically "SH" for shares or "PRN" for principal amount).
*   `PUTCALL`: Indicates whether the holding is a Put or Call option. If left blank, it indicates a direct equity/bond holding [cite: 8].
*   `INVESTMENTDISCRETION`: Identifies the manager's level of control, containing values like "SOLE", "DFND" (Defined), or "OTR" (Other) [cite: 8, 12].
*   `OTHERMANAGER`: Identifies other managers sharing discretion.
*   `VOTING_SOLE`, `VOTING_SHARED`, `VOTING_NONE`: Breakdown of voting authority [cite: 8].

#### 2.2.3 SUMMARYPAGE.tsv
This file provides an aggregate overview of the manager's 13F portfolio [cite: 7].
*   `ACCESSION_NUMBER`: Foreign key.
*   `OTHERINCLUDEDMANAGERSCOUNT`: Count of other managers listed.
*   `TABLEENTRYTOTAL`: The total number of individual line entries in the `INFOTABLE.tsv` [cite: 7].
*   `TABLEVALUETOTAL`: The aggregate gross market value of all 13(f) securities in the portfolio [cite: 7]. 

## 3. The Critical 2023 SEC Value Reporting Rule Change

Any longitudinal programmatic analysis of Form 13F datasets must account for EDGAR Release 22.4.1, which went into effect on January 3, 2023 [cite: 9]. This SEC rule amendment fundamentally altered the unit of measurement in the `VALUE` column.

**Prior to January 3, 2023:** 
Filers were required to round all dollar values in the Information Table to the nearest one thousand dollars (e.g., omitting the "000" suffix) [cite: 2, 10]. A value of `$150,000,000` was reported as `150000`.

**After January 3, 2023:** 
The SEC simplified the rounding conventions, mandating that the `VALUE` column (and `TABLEVALUETOTAL`) reflect the exact market value rounded to the nearest U.S. dollar [cite: 10, 12]. Therefore, an entry of `150000000` now directly represents `$150,000,000` [cite: 12]. This impacts all filings for the period ending December 31, 2022, submitted in February 2023, as well as subsequent amendments to prior reports filed after the implementation date [cite: 9, 10].

### 3.1 Detecting and Normalizing the Value Shift
To normalize AUM and holdings value across time periods, the programmatic utility must inspect the `REPORTCALENDARORQUARTER` column or the filing timestamp. A heuristic to normalize `VALUE` to exact dollars involves applying a multiplier of 1,000 to any filing corresponding to Q3 2022 or earlier. If analyzing a period straddling the rule change, failure to normalize will artificially indicate a 100,000% spike in fund AUMs between Q3 2022 and Q4 2022.

## 4. Data Processing and Loading with Pandas

When importing the TSV dumps using `pandas`, the single most catastrophic error is allowing pandas to infer data types automatically. CUSIPs often begin with leading zeros (e.g., Apple Inc.'s CUSIP is `037833100` [cite: 13]). If loaded as numeric, the CUSIP becomes `37833100`, rendering subsequent relational joins with market data providers impossible.

### 4.1 Loading Strategy
Files must be read with `dtype=str` to preserve textual integrity. Only strictly mathematical columns (`VALUE`, `SSHPRNAMT`, `TABLEVALUETOTAL`) should be cast to numeric types post-load. The separator is explicitly the tab character (`\t`) [cite: 6].

```python
import pandas as pd
import numpy as np

def load_coverpage(filepath: str) -> pd.DataFrame:
    """
    Loads the COVERPAGE.tsv file, preserving text formatting.
    """
    df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8')
    # Standardize column names to uppercase for consistency
    df.columns = [col.upper() for col in df.columns]
    return df

def load_infotable(filepath: str) -> pd.DataFrame:
    """
    Loads INFOTABLE.tsv, converting numerical fields and handling CUSIPs.
    """
    df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8', on_bad_lines='skip')
    df.columns = [col.upper() for col in df.columns]
    
    # Clean and cast numerical columns
    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce').fillna(0)
    df['SSHPRNAMT'] = pd.to_numeric(df['SSHPRNAMT'], errors='coerce').fillna(0)
    
    # Normalize PUTCALL to uppercase to ensure consistent filtering
    if 'PUTCALL' in df.columns:
        df['PUTCALL'] = df['PUTCALL'].fillna('').str.upper()
        
    return df

def load_summarypage(filepath: str) -> pd.DataFrame:
    """
    Loads SUMMARYPAGE.tsv and extracts aggregate AUM data.
    """
    df = pd.read_csv(filepath, sep='\t', dtype=str, encoding='utf-8')
    df.columns = [col.upper() for col in df.columns]
    
    df['TABLEVALUETOTAL'] = pd.to_numeric(df['TABLEVALUETOTAL'], errors='coerce').fillna(0)
    return df
```

## 5. Advanced Analytical Patterns in Hedge Fund Analysis

### 5.1 Computing Total AUM (Portfolio Value)
A fund's AUM can theoretically be derived in two ways:
1.  **Reading `TABLEVALUETOTAL` from SUMMARYPAGE**: This is the manager's officially reported gross asset value of 13(f) securities [cite: 7].
2.  **Summing `VALUE` in INFOTABLE**: Grouping by `ACCESSION_NUMBER` and summing the `VALUE` column.

While these should perfectly reconcile, discrepancies occur. Discrepancies are often caused by the manager requesting Confidential Treatment (13F-CTR) for specific holding rows [cite: 10, 14]. The SEC omits these confidential rows from the public `INFOTABLE.tsv` [cite: 3], meaning the sum of the visible `VALUE` rows will mathematically be lower than the true `TABLEVALUETOTAL`. Therefore, `TABLEVALUETOTAL` should be prioritized when establishing high-level fund size metrics.

### 5.2 Deduplicating and Counting Unique Stock Holdings
Hedge funds frequently report multiple rows for the same CUSIP. This occurs when a manager holds the same asset across different discretionary accounts (e.g., Sole, Shared-Defined, Shared-Other) [cite: 8]. To calculate the unique number of equity securities held:
1.  Filter out derivative contracts (Put/Call options).
2.  Group by `ACCESSION_NUMBER` and `CUSIP`.
3.  Sum the `VALUE` and `SSHPRNAMT`.

```python
def get_fund_holdings(infotable_df: pd.DataFrame, accession_number: str) -> pd.DataFrame:
    """
    Retrieves and aggregates unique equity positions for a specific fund submission.
    Filters out options (PUTCALL).
    """
    # Filter for specific fund
    fund_df = infotable_df[infotable_df['ACCESSION_NUMBER'] == accession_number].copy()
    
    # Pitfall avoidance: Exclude Puts and Calls [cite: 8]
    if 'PUTCALL' in fund_df.columns:
        fund_df = fund_df[fund_df['PUTCALL'] == '']
        
    # Aggregate duplicate CUSIP rows (e.g., different investment discretion accounts)
    agg_funcs = {
        'NAMEOFISSUER': 'first',
        'TITLEOFCLASS': 'first',
        'VALUE': 'sum',
        'SSHPRNAMT': 'sum'
    }
    
    deduped = fund_df.groupby('CUSIP', as_index=False).agg(agg_funcs)
    return deduped.sort_values(by='VALUE', ascending=False)
```

### 5.3 Comparing Holdings Across Quarters
Comparing a fund's portfolio longitudinally requires linking `ACCESSION_NUMBER`s across time. Because a new `ACCESSION_NUMBER` is generated every quarter for the same fund, the analyst must track the fund via an immutable identifier. The Central Registration Depository (CRD) number or SEC File Number (newly mandated in 2023 [cite: 12, 14]) are optimal, but traditionally, the manager's `CIK` or an exact text match on `FILINGMANAGER_NAME` are used as the primary linking keys.

### 5.4 Ranking Top Holders of a Specific CUSIP
To identify the largest institutional owners of a specific equity, the process involves querying the aggregated `INFOTABLE` for a target CUSIP across all valid accession numbers, then joining back to the `COVERPAGE` to resolve the fund manager's name.

```python
def top_holders_of_cusip(infotable_df: pd.DataFrame, coverpage_df: pd.DataFrame, cusip: str, n: int = 5) -> pd.DataFrame:
    """
    Finds the top N institutional holders of a specific CUSIP in a given quarter.
    """
    # Filter by CUSIP and exclude options
    target_holdings = infotable_df[(infotable_df['CUSIP'] == cusip) & (infotable_df['PUTCALL'] == '')]
    
    # Aggregate total value held by each accession number
    fund_totals = target_holdings.groupby('ACCESSION_NUMBER', as_index=False)['VALUE'].sum()
    
    # Join with cover page to get fund names
    merged = pd.merge(fund_totals, coverpage_df[['ACCESSION_NUMBER', 'FILINGMANAGER_NAME']], on='ACCESSION_NUMBER', how='left')
    
    # Rank and return
    ranked = merged.sort_values(by='VALUE', ascending=False).head(n)
    return ranked
```

## 6. Entity Resolution via RapidFuzz (v3.x)

A pervasive issue in 13F analytics is the slight alteration of fund manager names over time or across databases (e.g., "Renaissance Technologies LLC" vs. "RENAISSANCE TECHNOLOGIES, LLC"). This requires robust fuzzy matching text resolution [cite: 15].

The standard library for this in modern Python architectures is **RapidFuzz**, a C++ optimized library that operates as a high-performance drop-in replacement for the older `fuzzywuzzy` or `thefuzz` [cite: 15, 16]. RapidFuzz resolves licensing constraints (MIT licensed vs GPL) and provides massive execution speedups [cite: 16, 17].

### 6.1 RapidFuzz v3.14 API Updates and Quirks
A critical warning for developers updating legacy codebases: **RapidFuzz v3.0.0 fundamentally changed the API regarding text preprocessing** [cite: 18, 19]. In v2.x, setting `processor=True` was valid. In v3.x and above (e.g., 3.14.x), the `processor` argument must be either `None` or a callable function, and the default behavior was changed to `None` (meaning no preprocessing happens automatically) [cite: 18].

To achieve optimal, case-insensitive matching that strips non-alphanumeric characters, the developer must explicitly pass `rapidfuzz.utils.default_process` to the matching functions [cite: 16, 20].

### 6.2 Implementation of Entity Resolution
For matching a query like "berkshire hathaway" against the `FILINGMANAGER_NAME` column:

```python
from rapidfuzz import process, fuzz, utils

def fuzzy_find_manager(coverpage_df: pd.DataFrame, query: str, top_n: int = 5) -> pd.DataFrame:
    """
    Utilizes RapidFuzz to find the closest matches for a fund manager name.
    Requires rapidfuzz v3.x API constructs.
    """
    # Ensure no NaN names
    choices = coverpage_df['FILINGMANAGER_NAME'].fillna('').tolist()
    
    # rapidfuzz.process.extract returns a list of tuples: (match_string, score, index)
    # fuzz.WRatio is optimal for general text comparing with length variations [cite: 16, 21]
    # processor=utils.default_process forces lowercase and non-alphanumeric stripping [cite: 20]
    results = process.extract(
        query, 
        choices, 
        scorer=fuzz.WRatio, 
        limit=top_n, 
        processor=utils.default_process
    )
    
    # Map back to the dataframe
    indices = [res[cite: 6] for res in results]
    scores = [res[cite: 1] for res in results]
    
    matched_df = coverpage_df.iloc[indices].copy()
    matched_df['FUZZY_SCORE'] = scores
    
    return matched_df[['ACCESSION_NUMBER', 'FILINGMANAGER_NAME', 'FUZZY_SCORE']]
```

Using `fuzz.token_set_ratio` is also highly recommended when entity names contain extra repetitive boilerplate words (e.g., "Management", "LLC", "LP") as it computes intersections of word tokens, ignoring word order [cite: 15, 16, 21].

## 7. Financial Identifier Normalization (CUSIP)

The CUSIP (Committee on Uniform Securities Identification Procedures) is a strictly 9-character alphanumeric identifier [cite: 8]. 

### 7.1 Palantir Technologies Case Study
The query addresses Palantir Technologies Class A common stock. Based on SEC Schedule 13G filings and ETF fund data, **Palantir's official CUSIP is indeed `69608A108`** [cite: 13, 22, 23]. 

### 7.2 Normalization Pitfalls
When parsing the `INFOTABLE.tsv`, the CUSIP must be meticulously standardized. Common pitfalls include:
1.  **Trailing whitespace**: Sometimes introduced during XML-to-TSV flattening. (Fix: `.str.strip()`).
2.  **Lowercase letters**: CUSIP alphabetic characters must be uppercase. (Fix: `.str.upper()`).
3.  **Missing leading zeros**: The most devastating error. If pandas strips a leading zero from a CUSIP (e.g., Apple's `037833100`), it becomes an 8-character string, breaking database joins. (Fix: `dtype=str` on import, or `.str.zfill(9)`).

## 8. Methodological Pitfalls and Data Artifacts

Beyond data-type conversion and rule changes, the Form 13F dataset exhibits several domain-specific quirks that can severely compromise analytical integrity.

### 8.1 The PUTCALL Filter
The SEC requires managers to report both direct equity holdings and options positions on those equities. The `PUTCALL` column will contain the text `Put` or `Call` (capitalized first letter) if the position is an option [cite: 8]. 

If an analyst calculates the aggregate ownership percentage of a company by summing all `SSHPRNAMT` shares without filtering `PUTCALL`, they will erroneously double-count the notional exposure of the options as actual voting shares. Options **must be explicitly filtered out** (`df['PUTCALL'] == ''` or `.isna()`) for pure stock holding analyses.

### 8.2 Amendment Handling (13F-HR/A)
Managers frequently file restatements due to calculation errors or the expiration of confidential treatment periods [cite: 3, 4]. These are filed under the form type `13F-HR/A` (Amendment) [cite: 4]. 
*   **Pitfall**: A naive aggregation of the dataset by calendar quarter might ingest both the original `13F-HR` and the `13F-HR/A`, resulting in a duplicate portfolio size.
*   **Resolution**: Analysts must group the dataset by the manager's identifier (e.g., `CIK`) and the `REPORTCALENDARORQUARTER`. By sorting on the filing date or `ACCESSION_NUMBER` descending, the pipeline can execute a `drop_duplicates(subset=['CIK', 'REPORTCALENDARORQUARTER'], keep='last')` command, ensuring only the finalized, amended portfolio is processed.

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

## Conclusion

Analyzing the SEC's Form 13F-HR quarterly TSV dumps presents tremendous opportunities for reverse-engineering the capital allocation strategies of major institutional actors. However, success dictates strict adherence to data governance protocols. As outlined in this report, the analyst must meticulously enforce `pandas` text schemas to preserve CUSIP identifiers, algorithmically address the January 2023 SEC exact-dollar value reporting transition, explicitly filter out derivative contracts from equity calculations, and leverage high-performance C++ string matching via `rapidfuzz` v3.x to maintain historical continuity across diverse fund entities. By standardizing these patterns into a reusable Python utility, institutional holdings can be parsed with academic rigor and deterministic accuracy.

**Sources:**
1. [sec.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH6RIMUl4Z-eCy0bZ9omuzm0o1i5fIQiwfaccSpH9MaFxuF99MSo_akGPBH9g4dp2806EuHIt1_uTVWC1g2l0C62Wdmk0ND0-b6SbqWDrcmSi-BU2Jp6Qeja0w-6tWBoGhm6yqgc7xZDJwq13psgH3EEl1CaB-4JvQARbo=)
2. [btlaw.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGnDXWpAVbYyH2lBUSsF_FRLAV0CFZZRty5AdN7GanlT0LMIeq48gCUZ4pE_32LlH33XcigRCvohdtSp90cQwqsKMzNSJQtmY0NWY2Vwm5f4-tUof7grGIuwyTy1Rv3En9kmQHT_ZFSwE-stTZIb7kmWTDMY1dz-t-PYmy8KOXL-naGTVb1nk7SJIuI2QPRhYcIbdIXBgAfX0spzy9YB5THk2nh-zNY6MJsV-Z2e__Q)
3. [natlawreview.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFIGm0SXBqXkKEY2oEQQB5wSA64zJsYKvUqzAu1ER2C4wX6u9IyHVSfWEYBVn73zKMv9N2cQghd4npz-0GqM6fVdDhN6wKp_NJSid3zGhMoxGH9zgDJCXvSK7n_pLyzNaVeiuuvi1R72rdFmw0q2Uthh_alf4e_hFRV69WuAU4AVU5LizlkFMfqr5o57aAHVCwU4qKkSHhoIQeRZwZoEtU=)
4. [sec.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjjRdh6Cm40NkORlxIYxXLXUAtzhb5pS9kLgJNTFxZQr4afIktHd79UMaEAgDi26lKgoZZ5_ZU8fwnJG2wJoJKcPdrTGew8m6wGdK0Hts9pcX4yo4surHdTIZ7wg==)
5. [usa.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYb_BzVMDghjRfHuMXcSPfDt6P8FTlSdKbReGESU86Pip0bsQWRU-3QGLl6mvrNpQQQmvt0ejJCL_EtVKjMmIHN7owFtos4aAkLNxRgpxOR--HP0O1j4JlYqFSCkU5cfMZmO3Yq5wQp8As4UeQoLGsKMSYLWyxVjXFu5I5CIBW0EYwSGHwO_xvM6y0ew==)
6. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-kp8FP6hD4wO4IpCP6eRDDJPZyK8cphLj52MneLbWPN6pjOVMVkXw0VsoSVk6xS5ww4NdrDobfiDzK4_SQCUDnVNZBN9cl0hd4oT7-bSdQScRyaVfT0W3SvQkhTNyjSVyQGoGWVASCZ9jB6ucQsUVfoIfumJYDLIwXh9zGq7hMAQ2gz7l2wgnOKBH75alIK-z3NHg1ecMJAy_wsY=)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7nL9W3fRmJZra7gHA-F-8-U8j0Q7ImDEB4Ru4t1YKIrIcTKYokqOeg4TCoO7rdHvfqW0XsggrgImqriwLV42Mmxu0TTt990iWju5QqblhBRh1ud_oyp9Ldja0mtzU_SC_og==)
8. [sec.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEn5t6YAdJhlR31D8SR308t5hgRpvgmRu60GtJlHXwaUThJxSM5dlg-eN5KN_Lr6wjw4-aX-usn7X5pHdv1i08ItB2UgEHu5Y-5k-pcz3wh_49dAN7NLgZJ2txExUOCWaD3H_Z0rmp5wJ3rYG2ue9pRNa2dAbXuiuGxp0EEcj65JemWjd3WZI7BrQSteoQZMJN04CqKBg6m40OKymnAglH9BBj5NT2hlQhItum077CR7lq-)
9. [workiva.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGByUgA1qeL980z2Aw07_Osdm3o6d5G7XUk8V_fYjldfRT1Ir5snGL9efQDOCv-AN9lVyQKrKa5ENQtKPj0u-tJ_3ffWyula7sqkJxRcW0nZ5vPrR7D41NhF_VvDF_rBSMaIlX4pqe5NKrdVuSdAKJjyBCpdYSPccvCtdt0hWpNPsb7bWxmyFmb9A==)
10. [vigilantllc.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhcVvBDOdUGp02OEeqsNkBsFwndGVAgOEm-BE9wsqmyQKiy9Y6PPw-wJolJF9B2PTQJSideLngaY5Xgs1wsYH10OeiU_vSp_4iTeMJ15T-8IWT9QDDGvjNpamdzt1lnnGVA402NkUD5UQJs0xCk7tc1i8NGextaASbBIg=)
11. [sec-api.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEybzEE7kaaHL-YF5t9EUgfyH9ywl5nHJ4K2cpqHXw365bgYUCz8Yo67zVnNNFWhNkisjfg45G1eDZUzvVEsZULtNar3iBGg2qjkLbaziS3vI1CqTMlk1Vcuk-Oo3SGTLReoAwe5538RweBBAp4YVWwdW_xbrSU-A==)
12. [sec.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGi9hJgDKGSyOy-nGQc3ADy0gI8SVBWz9P3qqZCTIsIn8o31NoNmJGuhE-DHboELFxXlL_S0Jn_pLeohv_ML_v1IjGAhnee1I6P29z4Q1_8uLNxJE25J70UTTSa4zD3VvCM6Gm8OPKr0xS1kf5pJo2Qy2WZsuZ5W76YIQ7WM-M9xdKgRZk7mPT98fSWduK7HCsOGSyqCPebhl-Ka7xxzzoNWodssrdXNBSTcZbHYj9kSdbZpDUWz86WkGR4l69vBpAJauhAXmydpLSnekBZuZE=)
13. [schwabassetmanagement.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGN90yNlYdOVrCManl6MhniN1pWDpf2cCuuiM1mz7dBbW8T5aJ9C4OoxMLVKjQnOAfBpxdUwy3Btt5nXiPSGe4Jf2t1ZmZlZmANv-t5s_axX5MECKyGrGMu6SCPYcxbAwTL-yNgmdeN9xtkR2s=)
14. [filepoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_2qfI4jXA4kjHR7i-ziPxl2jD6JS3oZKkP5hh0NJ1BzDVBuwtkgneEa6GDGDUsjEb2778y9rmZRoCgIpLpaTr78U9X1ZWxjm9goqmMFwuHy_54uefteF-_9AOU060V8NPnCPSkLZYeDRXc29iUryg--8=)
15. [letsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqCWNEpTQIJ-HuNgb-lu9C5FmsGXwCS-5UhtAEwexX9zGhRzKn9l5yngH0vuuXc3PpLOwqeawQ9Ak_S-y_wdRDn_9P6vqklVkVu3epTpT_qvTRgSw9WhNr5RJvj-XNQlc13fwbU54dsEXPBXs-TW7s_QzYjyYJVTi8F-chQnwAOniGfpFrCU8GhUnt4AciIVK3ikeDubGj)
16. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFt4RYsraFYMI7AaWnv1UzWvN3jE4D2SKfpoBFXmWlmfDHBrAh5uVIT1j4BbUH44hQ076fLn880V6UAeUPlT42YQJ9A8BhOF3TSCuvGCpCwmBZsCrz6nUyqmSMDA0_BxhtLBe-sdMwBj2YeXw==)
17. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmqVymYcgmjgaVy-GbNp7DWf6_OhiRCwJNWx95X2rhMY5pZei6q6vsBUeq0PhdKxWhtsSh9queL_y3XnKyL8uFU1NdRxpYCas9y3xJ0CshYZq8w9FLkWDLsA==)
18. [newreleases.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF0m_SsrEbiOlI3ckb34nSIYLfSjJnNaAGkG1FE4wHKAAMZKlLTaFplWMIiqV5O56U64d9FDQjlvTXIWnjBN9WaWVbxtvObIIzlIcFM4sNqK6bm8oh1uGQyfUySmKC8Fo_07V5YB6BS2_EZXaAbOMi4LrQen6b4Ech_9nnc7_Q=)
19. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHtJrvE0yQVc4XOKRXeKVL7FzAXU3Ujjr_ziR6mLlLJStL4l3aBPpubeMDRLuzw-W_6nfsH-UX-Iq2GNOALGmIjfmo5JzOizCrLgzWYyxD8V36wPczc1Z8Dz9n3Fz-HRur3OxeT8chKd4o74l93MY1rPcWnew==)
20. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNWblgShPQcrTdBz6ZiCPfCmPwTH2lzI4IHLABTdmyWMS2kzg1cRd4dxSI6edOTKEQWT59wR78yVqnuKdlW7muHgxwct5T-MKQwyVGfXs6RzhpedD8LtVT4sjucTne98ZP8bV7ipizNCmlMNo=)
21. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHj4CYaWs5sdnWULI0OLJa4K5M5TzKodrKcOZhDlJmLzY-kUHCa7vGhcKpU1gvfm9fAbaCflUQOcOp6f1ObB7jI5pFPwqAVLw-eYJkF6_Wd5hiaXZasEDtEJZI2ZwcM3tgc_7yeiOzdKNsIPg==)
22. [roic.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaDx2zkBo1RQcZOyFAp3MfeOqu9O6xa1680lFUCy1f1HRCJ6V-a0Av-PWKAXd03s1RNo2zcqqADZiJX2V1wqZuZ7Y0XdGGK26vclPo-B4pLtF6LtE=)
23. [nasdaqtrader.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGXHWXTChhwKG1lSEVn6XpEAiB4KYcVFKWC2W7xE3iFW8kdsWRL5Q_Qo4BgepX2OH6S98lQYh44dKbqqVnkw0WyVuEkmfNKQHApst70xWlc7YkjiTZSfr87A1E6X67ScaHklgQqd7LQUN6KI3XVPv0d)
