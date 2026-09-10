# Building a Robust Python Pipeline for Flooding Detection at USGS Streamflow Stations

### Key Findings and Project Overview
*   **Methodological Viability:** Research suggests that utilizing the Python `dataretrieval` package (v1.0.10) combined with `pandas` 2.2.3 provides a highly effective, programmatically rigorous framework for ingesting, processing, and analyzing United States Geological Survey (USGS) streamflow data [cite: 1, 2].
*   **Threshold Definitions:** It seems likely that in the absence of direct National Weather Service (NWS) flood stage data within the National Water Information System (NWIS), utilizing statistical percentile thresholds (such as the historical 90th or 95th percentiles) offers the most robust operational alternative for flood event detection [cite: 3, 4].
*   **API Transitions:** The evidence leans toward a significant transitional period within the `dataretrieval` package; while the legacy `nwis` module is fully operational in v1.0.10, users should be aware of creeping deprecation warnings as the USGS transitions to the modernized `waterdata` module [cite: 5, 6].
*   **Data Integrity:** Maintaining data integrity—specifically preserving the leading zeros of USGS 8-digit station identifiers—is absolutely critical when transitioning data from flat files into `pandas` DataFrames, as coercion to integer types will precipitate systemic API query failures.

### Introduction to Automated Hydrologic Monitoring
The deployment of automated, programmatic pipelines for monitoring hydrometeorological events has become a cornerstone of modern computational hydrology. The USGS operates the largest continuous network of water monitoring sites in the United States, managing an immense repository of real-time and historical surface water data via the NWIS [cite: 7]. Historically, researchers and operational hydrologists relied heavily on the R programming language's `dataRetrieval` library to interface with this database. 

However, the growing ubiquity of Python in data science has necessitated a native equivalent. The Python `dataretrieval` package was explicitly designed to simplify the process of loading hydrologic data into the Python ecosystem, reproducing the core functionality of its R predecessor while conforming to object-oriented Pythonic paradigms [cite: 8, 9]. The integration of `dataretrieval` v1.0.10 with `pandas` 2.2.3 allows for high-performance vectorization, time-series manipulation, and automated analytical workflows. This document details the technical specifications, architectural patterns, and code implementations required to build a skill module capable of detecting flooding events across multiple USGS streamgages.

### Scope of the Technical Implementation
This report comprehensively addresses the programmatic retrieval of instantaneous and daily streamflow records, the calculation of historical daily statistical thresholds to define flood conditions, the robust parsing of station lists, and the mitigation of common pipeline pitfalls. We will construct a resilient architecture capable of identifying which stations exceeded statistical "flooding" thresholds within a designated temporal window (e.g., April 1–7, 2025) and generating an actionable summary output.

---

## USGS dataretrieval Python Package (v1.0.10) API

The `dataretrieval` package interfaces directly with USGS web services, formatting complex REST API queries, handling JSON or RDB (Relational Database) responses, and returning highly performant `pandas` DataFrames [cite: 2, 7]. Understanding the specific syntax, imports, and return types of the v1.0.10 API is fundamental to pipeline construction.

### Module Import Conventions

In version 1.0.10, the legacy NWIS functions are housed within the `dataretrieval.nwis` submodule. While future iterations (>v1.1) emphasize the `waterdata` module, the `nwis` module remains functional and widely used for legacy codebases [cite: 5, 10]. 

The two correct paradigms for importing the module are:
```python
# Paradigm A: Direct import (Common in USGS documentation)
import dataretrieval.nwis as nwis

# Paradigm B: From import
from dataretrieval import nwis
```
Paradigm A is generally preferred in the official literature and minimizes namespace pollution while keeping the code highly readable [cite: 9, 11].

### Core Function Signatures

The API exposes several functions mapped to different USGS web services. The distinction between the generic `get_record()` wrapper and the specific endpoint functions (`get_dv()`, `get_iv()`, `get_stats()`) is a critical source of confusion for developers.

#### The `nwis.get_record()` Function
`get_record()` acts as a universal wrapper that routes queries to the appropriate endpoint based on the `service` parameter.
*   **Signature:** `nwis.get_record(sites, service='iv', start=None, end=None, **kwargs)` [cite: 12]
*   **Return Type:** Returns a **single `pandas.DataFrame`** containing the requested data [cite: 12].
*   **Use Case:** Ideal for highly generalized pipelines where the service type might be passed as a variable.

#### The Specific Getters: `get_dv()`, `get_iv()`, and `get_stats()`
Unlike `get_record()`, the specific functions return a **Tuple** consisting of `(DataFrame, Metadata)`. The metadata object contains useful attributes such as the original URL, query execution time, and site information [cite: 7, 12].

*   **`nwis.get_dv(sites, parameterCd, start, end, **kwargs)`**: Queries the Daily Values (dv) service for mean daily data.
*   **`nwis.get_iv(sites, parameterCd, start, end, **kwargs)`**: Queries the Instantaneous Values (iv) service for high-resolution unit data (usually 15-minute intervals) [cite: 2, 12].
*   **`nwis.get_stats(sites, statReportType, statYearType, **kwargs)`**: Queries the NWIS statistics service to retrieve historical percentiles, means, and extrema [cite: 12].

### Required and Optional Parameters

To query these services effectively, the following parameters are heavily utilized [cite: 7]:

| Parameter | Type | Description | Common Values |
| :--- | :--- | :--- | :--- |
| `sites` | `str` or `list` | A single 8-digit USGS site code or a list/comma-separated string of site codes. | `'04193500'`, `['04193500', '04195500']` |
| `service` | `str` | (Used in `get_record`) Defines the NWIS service to query. | `'dv'`, `'iv'`, `'site'`, `'stat'`, `'peaks'` [cite: 9, 10] |
| `start` / `end` | `str` | Bounding dates for the time-series query in `YYYY-MM-DD` format. | `'2025-04-01'`, `'2025-04-07'` [cite: 7, 12] |
| `parameterCd` | `str` | USGS 5-digit parameter code indicating the physical property measured. | `'00060'` (Discharge), `'00065'` (Gage height) [cite: 7] |
| `statCd` | `str` | USGS 5-digit statistical code indicating how continuous data is aggregated. | `'00003'` (Mean) [cite: 13] |
| `statReportType` | `str` | Defines the aggregation level for the statistics endpoint. | `'daily'`, `'monthly'`, `'annual'` [cite: 12, 14] |

**Crucial Domain Knowledge:** The USGS parameter code for streamflow/discharge is universally **`00060`** (measured in cubic feet per second, cfs) [cite: 7]. The statistic code for a daily mean is **`00003`** [cite: 13].

### Data Structures and Return Types

When data is retrieved via `get_dv()` or `get_record(service='dv')`, the resulting `pandas` DataFrame is structured for time-series analysis:
1.  **Index Type:** The dataframe features a `DatetimeIndex`. The API automatically parses the ISO 8601 timestamps and localizes them to UTC (`00:00:00+00:00`) [cite: 7, 15].
2.  **Column Naming Conventions:** Columns are programmatically named based on the parameter code.
    *   `00060_Mean`: The numeric value of the streamflow [cite: 7].
    *   `00060_Mean_cd`: The data qualification code (e.g., `'A'` for Approved, `'P'` for Provisional, `'e'` for Estimated) [cite: 7, 15].
    *   `site_no`: The string representation of the USGS site ID [cite: 7, 15].

### Working Code Example: Fetching Daily Streamflow

```python
import pandas as pd
from dataretrieval import nwis

# Define targets
target_sites = ['04193500', '04195500', '04198000']
start_date = '2025-04-01'
end_date = '2025-04-07'

# Fetch Daily Values (dv). Notice we unpack the tuple.
df_dv, metadata_dv = nwis.get_dv(
    sites=target_sites, 
    parameterCd='00060', # Discharge
    start=start_date, 
    end=end_date
)

if not df_dv.empty:
    # Display the first few records
    print(df_dv[['site_no', '00060_Mean', '00060_Mean_cd']].head())
else:
    print("No data retrieved for the specified timeframe.")
```

---

## Defining "Flooding" from Streamflow Data

Detecting a "flood" programmatically requires defining what constitutes flood-level flow. In operational hydrology, this definition varies based on available data and the specific requirements of the forecasting agency.

### Limitations of NWIS and the NWS AHPS
A frequent point of confusion is the search for "Flood Stage" within USGS NWIS data. Flood stages are defined and maintained by the National Weather Service (NWS) through the Advanced Hydrologic Prediction Service (AHPS), not the USGS [cite: 3, 16]. While USGS WaterWatch maps overlay NWS flood stages where available [cite: 3, 17], the NWIS REST API does not directly serve a parameter code for "NWS Flood Stage."

If exact NWS flood stages are required, a secondary API or web-scraping script targeting the NWS AHPS must be engineered. However, this is brittle and scales poorly across thousands of ungauged or unforecasted sites.

### Percentile-Based Flood Definition (USGS WaterWatch Methodology)
Because NWS flood stages are not established for all USGS streamgages [cite: 16, 17], the most robust alternative is the percentile-based methodology pioneered by USGS WaterWatch. WaterWatch evaluates current streamflow against the historical period of record for that exact day of the year (requiring at least 30 years of continuous data for statistical stability) [cite: 3, 17].

WaterWatch classifications define flow severity mathematically:
*   **Normal:** 25th – 74th percentile [cite: 3, 16]
*   **Above Normal:** 75th – 89th percentile [cite: 3, 16]
*   **Much Above Normal:** \(\ge\) 90th percentile (Dark Blue) [cite: 3, 17]
*   **Highest on Record:** 100th percentile (Black) [cite: 3, 16]

For a programmatic flooding detection skill, the **90th percentile** (`p90_va`) or **95th percentile** (`p95_va`) of the historical daily mean serves as an excellent surrogate for a flooding or extreme high-flow event [cite: 3, 4, 18]. 

### Computing Per-Station Flood Thresholds using `get_stats`
To implement this, we must fetch the historical daily statistics for each site using `nwis.get_stats()`. When `statReportType='daily'` is invoked, the API returns a DataFrame detailing the historical statistics for each of the 365 days of the year [cite: 7, 12, 19].

The resulting DataFrame schema includes:
*   `month_nu`: The month of the year (1-12) [cite: 14, 18].
*   `day_nu`: The day of the month (1-31) [cite: 14, 18].
*   `count_nu`: The number of historical observations used in the calculation.
*   `p75_va`: 75th percentile flow value [cite: 18, 20].
*   `p90_va`: 90th percentile flow value [cite: 18, 20].
*   `p95_va`: 95th percentile flow value [cite: 18, 20].
*   `max_va`: Maximum historical value for this calendar day [cite: 18, 20].

#### Methodological Step: Joining Statistics to Observations
Because the daily statistics DataFrame is indexed by generic days of the year, and the daily values DataFrame is indexed by specific chronological dates (e.g., April 1, 2025), we must extract the `month` and `day` from the `DatetimeIndex` of our observations to execute a `pandas` left join.

Let \( Q_{obs}(t) \) be the observed daily mean flow on day \( t \). Let \( Q_{90}(m, d) \) be the 90th percentile historical flow for month \( m \) and day \( d \). The threshold condition for a flood event is:
\[ \text{Flood Event} \iff Q_{obs}(t) > Q_{90}(\text{month}(t), \text{day}(t)) \]

---

## Reading a Stations List File

In operational pipelines, target stations are rarely hardcoded. They are read from external configuration files, such as `michigan_stations.txt`.

### Formatting and Parsing the Identifiers
USGS site numbers are hierarchical, region-encoded identifiers that contain leading zeros (e.g., `04193500`). A critical failure point in Python pipelines is allowing `pandas.read_csv()` to infer the data type of this column. If inferred as a numeric type, `04193500` is truncated to `4193500`, which will cause HTTP 400 Bad Request errors when passed to the NWIS API [cite: 7].

To robustly parse a delimited text file containing a column of station IDs, you must explicitly enforce string typing utilizing the `dtype` parameter.

```python
import pandas as pd

# Assuming a CSV/TXT format:
# station_id,station_name
# 04193500,HURON RIVER AT ANN ARBOR, MI
# 04195500,HURON RIVER AT MILFORD, MI

def load_target_stations(filepath: str) -> list:
    """Reads a delimited file and extracts USGS site numbers as strings."""
    try:
        # Enforce string evaluation to preserve leading zeros
        df_sites = pd.read_csv(filepath, sep=',', dtype={'station_id': str})
        
        # Strip potential whitespace and return as list
        site_list = df_sites['station_id'].str.strip().tolist()
        return site_list
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
        return []
    except KeyError:
        # Fallback if it's a flat text file (one ID per line, no header)
        df_sites = pd.read_csv(filepath, header=None, dtype=str)
        return df_sites.str.strip().tolist()
```

---

## Pipeline Development and Automation Patterns

To transition from abstract definitions to a resilient data processing pipeline, the code must handle scale, network volatility, index alignment, and output generation. 

### Iteration and Exception Handling
When requesting data for dozens or hundreds of stations, querying them iteratively or in highly massive chunks can lead to missing data anomalies (stations that have no data for the requested period) or API rate-limiting errors. A robust pattern wraps the retrieval block in a `try/except` loop, specifically trapping empty dataframes and connection timeouts.

### Handling Timezone-Aware Datetimes
NWIS returns time-series data with a timezone-aware DatetimeIndex (specifically UTC, formatted like `1971-01-01 00:00:00+00:00`) [cite: 7, 15]. If your pipeline attempts to slice, filter, or compare this index against naive string dates (`'2025-04-01'`), `pandas` may raise a `TypeError` or `ValueError` regarding timezone mismatches. The safest approach is to ensure any manual date filtering uses timezone-aware timestamps localized to UTC, or utilizing the inherently filtered return of the `get_dv` function based on the API parameters.

### Counting Exceedances and Grouping
By executing a `merge` between the daily observations and the daily statistics, we align the `00060_Mean` and `p90_va` columns. Using vectorized `pandas` logic, we can create a boolean mask for flood events, group by the station ID, and aggregate the true counts.

### Writing Results to CSV
The final output must be highly sanitized. The goal is to generate a two-column CSV (`station_id`, `flood_days`), excluding stations that recorded 0 flood days.

---

## Comprehensive Code Implementation

Below is the complete, modular, and copy-pasteable Python script integrating all theoretical concepts discussed thus far.

```python
import pandas as pd
from dataretrieval import nwis
import logging
from typing import List

# Configure basic logging for pipeline observability
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def load_stations(filepath: str) -> List[str]:
    """Reads station list, preserving leading zeros."""
    try:
        # Assumes a flat text file or CSV with 'station_id' column
        try:
            df = pd.read_csv(filepath, dtype={'station_id': str})
            return df['station_id'].str.strip().tolist()
        except ValueError:
            # Fallback for flat file with no header
            df = pd.read_csv(filepath, header=None, dtype=str)
            return df.str.strip().tolist()
    except Exception as e:
        logging.error(f"Failed to read stations file: {e}")
        return []

def get_station_flood_thresholds(site_id: str) -> pd.DataFrame:
    """Retrieves the 90th percentile historical daily streamflow thresholds."""
    try:
        # Retrieve daily statistics (returns tuple: DataFrame, Metadata)
        stats_df, _ = nwis.get_stats(
            sites=site_id, 
            statReportType='daily', 
            parameterCd='00060'
        )
        
        if stats_df.empty:
            logging.warning(f"No statistical data available for site {site_id}.")
            return pd.DataFrame()
            
        # Select necessary columns for the threshold join
        stats_subset = stats_df[['month_nu', 'day_nu', 'p90_va']].copy()
        
        # Ensure data types are numeric for merging
        stats_subset['month_nu'] = pd.to_numeric(stats_subset['month_nu'])
        stats_subset['day_nu'] = pd.to_numeric(stats_subset['day_nu'])
        
        return stats_subset
        
    except Exception as e:
        logging.error(f"Failed to fetch stats for {site_id}: {e}")
        return pd.DataFrame()

def detect_floods_for_site(site_id: str, start_date: str, end_date: str) -> int:
    """
    Fetches daily values, joins with statistical thresholds, 
    and counts the number of days exceeding the 90th percentile.
    """
    # 1. Fetch Thresholds
    thresholds_df = get_station_flood_thresholds(site_id)
    if thresholds_df.empty:
        return 0
        
    # 2. Fetch Daily Streamflow Observations
    try:
        dv_df, _ = nwis.get_dv(
            sites=site_id,
            parameterCd='00060',
            start=start_date,
            end=end_date
        )
    except Exception as e:
        logging.error(f"API request failed for DV at {site_id}: {e}")
        return 0

    if dv_df.empty:
        logging.warning(f"No daily values retrieved for {site_id} in requested date range.")
        return 0

    # 3. Prepare the observation dataframe for merging
    # Ensure standard USGS column naming is present
    val_col = '00060_Mean'
    if val_col not in dv_df.columns:
        logging.warning(f"Expected column {val_col} missing for site {site_id}.")
        return 0
        
    # The index is a timezone-aware DatetimeIndex. Extract month and day.
    dv_df['month_nu'] = dv_df.index.month
    dv_df['day_nu'] = dv_df.index.day
    
    # 4. Merge observations with historical thresholds
    merged = pd.merge(
        dv_df, 
        thresholds_df, 
        on=['month_nu', 'day_nu'], 
        how='left'
    )
    
    # Drop rows where threshold data is NaN
    merged.dropna(subset=['p90_va', val_col], inplace=True)
    
    # 5. Count exceedances
    # A flood day is defined as a day where Mean Flow > 90th Percentile Flow
    flood_mask = merged[val_col] > merged['p90_va']
    flood_days_count = flood_mask.sum()
    
    return int(flood_days_count)

def run_flood_detection_pipeline(stations_file: str, out_file: str, start: str, end: str):
    """Main execution orchestrator."""
    logging.info("Initializing Flood Detection Pipeline...")
    sites = load_stations(stations_file)
    logging.info(f"Loaded {len(sites)} stations from {stations_file}.")
    
    results = []
    
    for site in sites:
        logging.info(f"Processing site {site}...")
        flood_days = detect_floods_for_site(site, start, end)
        
        # Only append stations that experienced at least 1 flood day
        if flood_days > 0:
            results.append({
                'station_id': site,
                'flood_days': flood_days
            })
            
    # 6. Formatting the Output
    df_results = pd.DataFrame(results)
    
    if not df_results.empty:
        # Write to CSV, omitting the index
        df_results.to_csv(out_file, index=False)
        logging.info(f"Pipeline complete. Detected flooding at {len(df_results)} stations. Results saved to {out_file}.")
    else:
        logging.info("Pipeline complete. No flooding events detected. No CSV generated.")

# Example execution block
if __name__ == "__main__":
    # Create a dummy file for the script to run standalone
    with open('michigan_stations.txt', 'w') as f:
        f.write("station_id\n04193500\n04195500\n04198000")
        
    run_flood_detection_pipeline(
        stations_file='michigan_stations.txt',
        out_file='flood_events_output.csv',
        start='2025-04-01',
        end='2025-04-07'
    )
```

---

## Common Pitfalls and Troubleshooting

Architecting highly dependable integrations with external APIs exposes developers to several recurring obstacles. Below are the most critical pitfalls specific to this stack and their respective mitigations.

### 1. Deprecated `dataretrieval` APIs in v1.0.10
While using version 1.0.10, developers will frequently encounter `DeprecationWarning`s when utilizing the `nwis` module. The USGS is actively decommissioning legacy NWIS endpoints in favor of OGC-compliant Water Data APIs [cite: 5, 6]. 
*   **The Pitfall:** Writing new infrastructure heavily reliant on `nwis.get_iv` or `nwis.get_gwlevels` exposes the codebase to sudden breakage if the USGS completes endpoint decommissioning. For example, the `nwis.get_discharge_measurements` and `nwis.get_gwlevels` functions are already considered defunct as of early 2026 updates, returning 503 errors if called [cite: 5, 6].
*   **The Solution:** For the scope of this project, `nwis.get_dv()` and `nwis.get_stats()` remain functional in v1.0.10. However, when migrating to `dataretrieval` > 1.1.x, developers must refactor imports to `from dataretrieval import waterdata` and utilize methods like `waterdata.get_daily()` [cite: 5, 6].

### 2. Tuple vs. DataFrame Return Types
*   **The Pitfall:** The discrepancy in return types between `get_record()` and specific getters (`get_dv()`, `get_stats()`) frequently triggers `AttributeError: 'tuple' object has no attribute 'empty'`.
*   **The Solution:** Always explicitly unpack the tuple when using specific getters:
    `df, md = nwis.get_dv(...)` [cite: 2, 7]. If employing `get_record()`, remember it returns the DataFrame directly: `df = nwis.get_record(...)` [cite: 9, 12].

### 3. Missing Data and Qualifier Codes (`_cd`)
*   **The Pitfall:** NWIS is an operational database; sensors break, freeze, or experience transmission errors. Missing values are represented as `NaN`. Attempting to evaluate `NaN > p90_va` evaluates to `False`, which silently ignores data outages. Additionally, provisional data (flagged `'P'` in the `00060_Mean_cd` column) is subject to revision and may contain anomalous spikes [cite: 7, 15]. Ice-affected data often carries an `'e'` (estimated) flag.
*   **The Solution:** Use `dropna(subset=['00060_Mean'])` before executing logical operations. If high scientific rigor is required, filter out provisional data by querying the qualification string: `df = df[df['00060_Mean_cd'].str.contains('A', na=False)]` (where 'A' implies Approved).

### 4. Site Identifier Type Coercion
*   **The Pitfall:** As detailed previously, permitting `pandas` to infer data types when utilizing `read_csv()` destroys the leading zeros of USGS site numbers, mutating `04193500` into the integer `4193500`. The USGS API strictly requires the zero-padded string structure; numeric inputs will prompt HTTP 400 rejection codes [cite: 7].
*   **The Solution:** Mandate string evaluation via `dtype={'station_id': str}` during all read operations.

### 5. Timezone Dissonance and Index Alignments
*   **The Pitfall:** The `nwis` functions parse JSON/RDB responses and utilize ISO 8601 timestamps to define the DataFrame's index. These index values are rigorously localized to UTC (e.g., `2025-04-01 00:00:00+00:00`) [cite: 12, 15]. Conversely, filtering by naive strings natively invokes a mismatch.
*   **The Solution:** In pipeline patterns evaluating threshold exceedance chronologically, extracting integer equivalents representing the calendar month (`df.index.month`) and day (`df.index.day`) bypasses timezone mismatch issues completely and facilitates precise alignment with historical statistics mapped to the generalized day of the year [cite: 14, 18].

### 6. API Rate Limiting and Payload Chunking
*   **The Pitfall:** Requesting daily statistics for hundreds of sites in rapid succession utilizing individual `get_stats()` HTTP calls will eventually yield `HTTP 503 Service Unavailable` or `429 Too Many Requests` responses. 
*   **The Solution:** The `get_dv()` function accepts a comma-separated string or a list of multiple site IDs (e.g., `sites=['04193500', '04195500']`) [cite: 7]. While the daily values endpoint accommodates querying batches of sites simultaneously to mitigate network overhead, the `get_stats()` endpoint historically behaves more predictably when iterating singly or in small, discrete batches. Implementing brief programmatic pauses `time.sleep(0.5)` between successive `get_stats()` calls during the initialization phase ensures reliable metadata acquisition. Furthermore, obtaining and applying an API key as an environment variable (`os.environ["API_USGS_PAT"] = "your_api_key_here"`) will raise internal rate limits, though this feature is primarily enforced in the newer `waterdata` modules [cite: 5, 10].

**Sources:**
1. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmoF-u9BqlRBnSZZ-Buuw4R_cL0o74U6QhAzmwsoncAXfNB5Z0d3oB_Tn6Z2elPhMhfWJFEdQ9UnJ5JE6mXTRTx-peduJdivtu9b4eksXUaSrMuc6RxexZwsP_B7vXE9sVjKQ5S6tilV-7KOLY1vbZsZXmIYwJojSWrxWFv2MEqVAtD5D0sS86dC_nsfiQyvNMZBicHtDVB1vamRxOU5WkYugPCLg2obQVGtkt0L21TAfS3s7bSqK9HBMYSzeTBBW_r4sQ1wkZ6Ra0aAmrDg==)
2. [usu.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGxNgGyH9cf0wCnGUpH3d2E4Qluj2DpcoKi5CYiZl5gJBe009FvYKCMxxdSnyHP1FMnZ-_c1H3fMX-sJOwaPHtCKsY6UE9bA0iLrBJj10kJBfBD-giL7bKl_CUQTtmb4Zstl8rAC72Tv09RndLwFDR8Ljka994fBICT19aUU4V397NWJG1tUAmg)
3. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpsE1Pc7KtBobNo4tNrEyZbTLiIrPJ7X6Rpv1o3zVN3aKcD8Cg3rvAvozBJGJkO9c5FikH5z6Cstp7JpeeeGsgNtlfTDbzbQy8t-kfOAQLn790sKQGKhqmwLXjD0l-X00OGQF_fSBUkBe74GnmJWyCh3Dv)
4. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFLiltfGjIAohL5pAl5wQYOp15qj8N-jHWF_8ddgOVN2fwLAkzyZmjcllvcK7HN_kscvatfvyLRfcF-y1JWgMGGKw4VZUkFSRe6_-2uTM3Z9a0_bHTtrI8I_HSRHAXD9pH96vRKTt0Y)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFis0o5mzoCGFYdQjIyqQvqlL9FEbRUlCDP6Wy8yyYUEIFT0PqsTEHP4GLL961iBQQJy2fhR1PCnJZRrDSXHdO-I5gnhMzkfCA5xxtTHqdCW3YD8NHSLiBl3UlyuAW2QfvJeShq3uI=)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAIGFD4k2mszrv-kE3q6AUH5AXO0LMbySTolq8et5l30La3epMKxrj9vZsU_13BuHdGvXYPxXmVaT1KRFnFUKyxy2sEvjsVVJWO1FYprzA5GpGO7NNHEGvCk1TRJ6e2pRz_dkNsZYbcvLsEGIRGW0-Pd86-oYAdZQ=)
7. [hydrolearn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGsVMkkuFQT3itIQebSMF7RYhyZsjKICvSz7dQHnOpTafopWT3_7A8MVa-E9gxECUBaoapuXptNTWs92GZMEHg8k0KNCzM_qp-PNaB1Ii38GFupDvWmAEoA7kM-sNV9SU5eIo3rPxV_1ljSml9H1LxLczhwB5ZLdIZ7gmBtS9sFLY1HtJH6TXBQ_uLHowyo-9Vi8IS2kIVwHCi0fXmVOSJczIdzSgV4_-L8jC_x4X08nF7AI1DHKwFIr_pFgdmN7jPy46O1tZrWX7qW7w==)
8. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVpj_w26I4OBKwdyALIJBeuTkiH04frQ1b--SV5oFh1RsHZaFZp1KsENGF2EKfAWQT4X6A6BudTEGd60KiTCNIDx76i990M5NbvrtTVJvmJD3LIQVmxchSyw2omcQ=)
9. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEcrLM07N0lOIX6noGMG7QGSscb1Ubw4ndb-HG5JyCOHK9DaFlwdDEwHe-25YPpEGq_ejBwlYOmV-YJPlftJWjU_SaSoxiPyErn_n8qgViuSkJ9YC56CJGaKhOQGqIVq7zn618=)
10. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGDtTryOeQ4nqpqWJXD7LRbRBItBpH879D00JV3BxaZLm4KSyu_7eDJRrmwCfFL2F3oiwfbLq1I4izBTQtst7jgzq48smlAxHxSWV2qibJtXxex93PP9rzrqt9QthsiI5gdUCGmpsnqeB2eU6nH0s32VgysAFzq_Ia-7Ygd)
11. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAaDa-5a1XzHYbNHG3z0kvX9h4lUWFniy3d4S-d3hvK71wa4q-tpoFmGZz2vMxoO_lGVV4Fc1rP5cu8U8dowvpfrcUMdUjnIptwcbUg-hOxp8xA-SQfLzZ2b5Asyh9HKsBPR2l7PTD_Hn-tdH-jCuW7jbC_Q==)
12. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHY4l4bL9KuEj5ljejy2uiOSv26FASjvEXW72qGxYLz_2F9GPRtOm8wasbL3CaDrKmnNuOpwgHMt4jGpTSYQP2VARU6EPcb2VF3SyLJ0re2gdO4DeZMBnRw4xCAWB85PoDbc8mwul3oJxIUR9O685u_uW9npzfwprQa)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGc8AVnnYRxtXiJwiNWbcO9pQTBWVhv5xpW62f_VWrck23Gz_IlpMnABZjSMjZi7y5DEoKu8LIkFXWVQSP8EuuDLTQ3YqNOPvjWr0OXUTiJ9sZYorm4bjlxE5Czi8J4uJBhtdxqvP-PamqdCgB1MzwiAu_CXDRE9eQp8dFA-xhyHRGAf2ezCofIq6VhASZ30ioWykKLjCxDlpzdpTUUCZdlKqJC169v12nF89EEW_vQzGdBgQ==)
14. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMpOJ9LuvwSEi4ZaFMbtqxJ-4I1RvKIE_ia3nYQgAwQ6ksJ2tOpg6ZSRAoACH2FVfzPHtLsfUFGyE4YxWiXfrlOUGSMaHiF9XSfgXmB5STHQ3GwwXgbnaodfGaH5lsnKY2HdvR_jDeMtSSx2EvOGwiWBcIt7jlGNbBTZ1rEChqzpC5xmZzeuXdmaBxpw==)
15. [earthdatascience.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGw41uH85hfaC6pYUhUkvdYakLT-5l7ybBOhylZZl_W0ZFmnVebQugqLjTY2kWksLPV-BRoDBc-UrHnCEkHKKw7TCxhs3Qrzu9-GgzxVWUH_cxKURWJkOhxDl3Dm0QksBVzDyug18xcSeIwQvBGGRAhEByWGYlqVz-xh3Hqwpjg)
16. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGW1IiwY7Ocm_dwtYNbLkVkMgZ5WB9sKBuK_kux6FXPO1_VGyz5J1aCebCesd2OVEhYwWgsOSX4is0tachZMVPI2CpQEybaBf8pKTCR07gKjlAr1LNYnb8ljvJw)
17. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGGF53dTYhZAjoLikTK6Y1Oku_sJBYkFco6VmEQnSCIYV453tX4mL5spMydky9M-853FoEv2N8lhBQLl8vSac9gmrx546kBGSxgz-XtaZxf-jFYCfC77ioyxQ==)
18. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFM4ac9awOBRAmBB-Qy1t3yoTjD3JBabJT1h8wWVsdWDAE0gdQy2GvpImXAnq2V1GLOXQOpzGck-hOSPbbPWoOMrdMNWT1Zqwlb_f98xuqj23kcyyoYO37qJ4YosFjjRlh9KEME-Vu4u5uB-Z-jrG81wQiKp97_8Zz-69z4oELgq6aoDp1xwf7s1-aXg_6L4vYSvvQVmss8OYt4MOX1T4-Up-QU7mlCw9I8lPENtGl3sMXFeizFAerEzUtkzyR)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtPkH0K_Z9mtn9SDo9tzvpaJOrhtXtjzHVHWrkF7HHkEzOGIb1tgqs25jGLv1S7CFktakfVwcffmqyUTWov8gyq_BGNVchDzcPHHt0hRb-odVPI5CejSytiaTgeSbnQ1_aXCOs-lEocIKYplHHY4-kGLv31Ltp)
20. [ca.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFjhAYIp_nBdXeOWxzjeGP3DT6BFyyElsMWACIYCMYtw6ZHOaCE1RPi_0rrJk5aeKYPtvt8TzitIuYcJxN6CliLf69cJ1h42Re0Ip0VfZvN77jvx-wfpWRhaRupUNGh4apK_hqtu3VSRLuOcEwEx0FwkFN5WlRGZg_v389kEeGHmiU4hHPMLOMZXj3e00o_rhDyKl4tU4ySlD3knQzcsUQJwxtdA6fh8MclGyhn4WKjCnmPsecb3BmhYeUfM_sjudSoyYpehyWAlV8nyQyZ9gs=)
