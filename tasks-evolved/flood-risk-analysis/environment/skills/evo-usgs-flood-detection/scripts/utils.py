import pandas as pd
from dataretrieval import nwis
import logging
import time
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def load_stations(filepath: str) -> List[str]:
    """
    Reads a station list file, preserving leading zeros.
    Handles both CSV with 'station_id' header and flat text (one ID per line).
    """
    try:
        with open(filepath, 'r') as f:
            first_line = f.readline().strip()
        
        if first_line.lower() == 'station_id':
            # CSV with header
            df = pd.read_csv(filepath, dtype={'station_id': str})
            return df['station_id'].str.strip().tolist()
        else:
            # Flat text file, one station per line, no header
            with open(filepath, 'r') as f:
                stations = [line.strip() for line in f if line.strip()]
            return stations
    except Exception as e:
        logging.error(f"Failed to read stations file: {e}")
        return []


def get_station_flood_thresholds(site_id: str) -> pd.DataFrame:
    """
    Retrieves the 90th percentile historical daily streamflow thresholds
    using nwis.get_stats() with statReportType='daily'.
    
    Returns DataFrame with columns: month_nu, day_nu, p90_va
    """
    try:
        stats_df, _ = nwis.get_stats(
            sites=site_id,
            statReportType='daily',
            parameterCd='00060'
        )
        
        if stats_df.empty:
            logging.warning(f"No statistical data available for site {site_id}.")
            return pd.DataFrame()
        
        # Select necessary columns for threshold join
        required_cols = ['month_nu', 'day_nu', 'p90_va']
        for col in required_cols:
            if col not in stats_df.columns:
                logging.warning(f"Missing column {col} in stats for site {site_id}.")
                return pd.DataFrame()
        
        stats_subset = stats_df[required_cols].copy()
        
        # Ensure numeric types for merging
        stats_subset['month_nu'] = pd.to_numeric(stats_subset['month_nu'], errors='coerce')
        stats_subset['day_nu'] = pd.to_numeric(stats_subset['day_nu'], errors='coerce')
        stats_subset['p90_va'] = pd.to_numeric(stats_subset['p90_va'], errors='coerce')
        
        # Drop rows where p90_va is NaN
        stats_subset.dropna(subset=['p90_va'], inplace=True)
        
        return stats_subset
    except Exception as e:
        logging.error(f"Failed to fetch stats for {site_id}: {e}")
        return pd.DataFrame()


def detect_floods_for_site(site_id: str, start_date: str, end_date: str) -> int:
    """
    Fetches daily values for a site, joins with historical 90th percentile
    thresholds, and counts the number of days where observed flow > p90.
    
    A flood day is defined as: daily mean streamflow > 90th percentile
    historical flow for that calendar day.
    
    Returns the number of flood days (integer).
    """
    # 1. Fetch historical thresholds
    thresholds_df = get_station_flood_thresholds(site_id)
    if thresholds_df.empty:
        return 0
    
    # 2. Fetch daily streamflow observations
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
        logging.warning(f"No daily values retrieved for {site_id} in date range.")
        return 0
    
    # 3. Check for the expected column
    val_col = '00060_Mean'
    if val_col not in dv_df.columns:
        logging.warning(f"Expected column {val_col} missing for site {site_id}. Columns: {list(dv_df.columns)}")
        return 0
    
    # 4. Extract month and day from DatetimeIndex for merging
    dv_df = dv_df.reset_index()
    if 'datetime' in dv_df.columns:
        dv_df['month_nu'] = pd.to_datetime(dv_df['datetime']).dt.month
        dv_df['day_nu'] = pd.to_datetime(dv_df['datetime']).dt.day
    elif 'datetimeUTC' in dv_df.columns:
        dv_df['month_nu'] = pd.to_datetime(dv_df['datetimeUTC']).dt.month
        dv_df['day_nu'] = pd.to_datetime(dv_df['datetimeUTC']).dt.day
    else:
        # Try the index directly
        try:
            idx = pd.to_datetime(dv_df.iloc[:, 0])
            dv_df['month_nu'] = idx.dt.month
            dv_df['day_nu'] = idx.dt.day
        except Exception:
            logging.warning(f"Cannot extract date components for site {site_id}.")
            return 0
    
    # Ensure numeric type for the value column
    dv_df[val_col] = pd.to_numeric(dv_df[val_col], errors='coerce')
    
    # 5. Merge observations with thresholds on month and day
    merged = pd.merge(
        dv_df,
        thresholds_df,
        on=['month_nu', 'day_nu'],
        how='left'
    )
    
    # Drop rows where either value is NaN
    merged.dropna(subset=['p90_va', val_col], inplace=True)
    
    # 6. Count exceedances: flood day = observed > p90
    flood_mask = merged[val_col] > merged['p90_va']
    flood_days_count = int(flood_mask.sum())
    
    return flood_days_count


def run_flood_detection_pipeline(
    stations_file: str,
    out_file: str,
    start: str = '2025-04-01',
    end: str = '2025-04-07'
) -> pd.DataFrame:
    """
    Main pipeline orchestrator.
    
    1. Loads stations from file
    2. For each station, detects flood days
    3. Filters to stations with >= 1 flood day
    4. Writes CSV with station_id, flood_days columns
    
    Returns the results DataFrame.
    """
    logging.info("Initializing Flood Detection Pipeline...")
    sites = load_stations(stations_file)
    logging.info(f"Loaded {len(sites)} stations from {stations_file}.")
    
    results = []
    
    for i, site in enumerate(sites):
        logging.info(f"Processing site {site} ({i+1}/{len(sites)})...")
        flood_days = detect_floods_for_site(site, start, end)
        
        if flood_days > 0:
            results.append({
                'station_id': site,
                'flood_days': flood_days
            })
            logging.info(f"  -> {site}: {flood_days} flood days detected")
        else:
            logging.info(f"  -> {site}: no flooding")
        
        # Brief pause to avoid API rate limiting
        time.sleep(0.3)
    
    # Create results DataFrame
    df_results = pd.DataFrame(results)
    
    if not df_results.empty:
        # Ensure station_id is string with leading zeros preserved
        df_results['station_id'] = df_results['station_id'].astype(str)
        df_results.to_csv(out_file, index=False)
        logging.info(f"Pipeline complete. {len(df_results)} stations with flooding. Saved to {out_file}.")
    else:
        # Write empty CSV with headers
        pd.DataFrame(columns=['station_id', 'flood_days']).to_csv(out_file, index=False)
        logging.info("Pipeline complete. No flooding events detected.")
    
    return df_results
