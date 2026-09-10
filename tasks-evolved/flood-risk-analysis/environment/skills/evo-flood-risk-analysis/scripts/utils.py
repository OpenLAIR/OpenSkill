"""
Flood detection pipeline: identifies flood days at USGS streamgages
by comparing daily max gage height (from instantaneous 15-min data)
against NWS flood stage thresholds.
"""

import os
import re
import time
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')


def extract_station_ids(stations_file):
    """Extract USGS station IDs from a michigan_stations.txt file.
    
    The file may be an RDB file with comment lines starting with '#',
    or a simple list. We look for 8-digit numeric station IDs.
    """
    station_ids = set()
    with open(stations_file, 'r') as f:
        content = f.read()
    
    # Try to find station IDs - they are typically 8-digit numbers starting with 0
    # Look in the entire file content for patterns like USGS\t04031000 or just 8-digit numbers
    # USGS RDB format: lines like "USGS\t04031000\t..."
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        parts = line.split('\t')
        for part in parts:
            part = part.strip()
            # Match 8-15 digit numbers that look like USGS station IDs
            if re.match(r'^0\d{7,14}$', part):
                station_ids.add(part)
            # Also try matching after "USGS" agency code
        if len(parts) >= 2 and parts[0].strip() == 'USGS':
            sid = parts[1].strip()
            if re.match(r'^\d{8,15}$', sid):
                station_ids.add(sid)
    
    return sorted(station_ids)


def download_nws_flood_thresholds():
    """Download NWS flood stage thresholds from the All Gauges Report.
    
    Returns dict: {usgs_station_id: flood_stage_ft}
    """
    url = 'https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv'
    
    try:
        df = pd.read_csv(url, dtype=str)
    except Exception as e:
        print(f"Error downloading NWS data: {e}")
        # Try alternative approach
        try:
            import urllib.request
            import io
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=60)
            content = response.read().decode('utf-8', errors='replace')
            df = pd.read_csv(io.StringIO(content), dtype=str)
        except Exception as e2:
            print(f"Alternative download also failed: {e2}")
            return {}
    
    # Find the USGS ID column
    usgs_col = None
    for col in df.columns:
        col_lower = col.lower().strip()
        if 'usgs' in col_lower and ('id' in col_lower or 'lid' in col_lower or 'site' in col_lower):
            usgs_col = col
            break
    if usgs_col is None:
        for col in df.columns:
            if 'gaugelid' in col.lower().strip():
                usgs_col = col
                break
    if usgs_col is None:
        for col in df.columns:
            if 'usgs' in col.lower():
                usgs_col = col
                break
    
    # Find the flood stage column
    flood_col = None
    for col in df.columns:
        col_lower = col.lower().strip()
        if 'flood' in col_lower and 'stage' in col_lower:
            flood_col = col
            break
    if flood_col is None:
        for col in df.columns:
            col_lower = col.lower().replace('.', ' ').replace('_', ' ').strip()
            if 'flood' in col_lower and ('stage' in col_lower or 'stg' in col_lower):
                flood_col = col
                break
    # Try sigstages patterns
    if flood_col is None:
        for col in df.columns:
            if 'sigstages' in col.lower() and 'flood' in col.lower():
                flood_col = col
                break
    
    if usgs_col is None or flood_col is None:
        print(f"Could not find required columns. Available: {list(df.columns)}")
        print(f"Found usgs_col={usgs_col}, flood_col={flood_col}")
        return {}
    
    print(f"NWS CSV: using usgs_col='{usgs_col}', flood_col='{flood_col}'")
    
    thresholds = {}
    for _, row in df.iterrows():
        sid = str(row[usgs_col]).strip()
        stage_str = str(row[flood_col]).strip()
        try:
            stage = float(stage_str)
            if not np.isnan(stage) and stage > 0:
                # Normalize station ID - remove leading/trailing whitespace
                # USGS IDs should be zero-padded
                thresholds[sid] = stage
        except (ValueError, TypeError):
            continue
    
    print(f"Found {len(thresholds)} stations with valid NWS flood stages")
    return thresholds


def get_gage_height_data(station_id, start, end):
    """Fetch instantaneous (15-min) gage height data for a station.
    
    Returns a DataFrame with datetime index and gage height values.
    """
    import dataretrieval.nwis as nwis
    
    try:
        df, _ = nwis.get_iv(
            sites=station_id,
            parameterCd='00065',
            start=start,
            end=end
        )
        if df is None or df.empty:
            return None
        
        # Find the gage height column
        gh_col = None
        for col in df.columns:
            if '00065' in str(col):
                gh_col = col
                break
        
        if gh_col is None:
            return None
        
        series = pd.to_numeric(df[gh_col], errors='coerce').dropna()
        if series.empty:
            return None
        
        return series
        
    except Exception as e:
        print(f"  Error fetching IV data for {station_id}: {e}")
        return None


def compute_daily_max(series):
    """Compute daily maximum from instantaneous time series.
    
    Returns a Series with date index and daily max values.
    """
    if series is None or series.empty:
        return None
    
    # Ensure we have a datetime index
    if series.index.tz is not None:
        series = series.tz_convert('US/Eastern').tz_localize(None)
    
    daily_max = series.resample('D').max().dropna()
    return daily_max


def count_flood_days(daily_max, flood_stage):
    """Count days where daily max gage height >= flood stage.
    
    Returns integer count of flood days.
    """
    if daily_max is None or daily_max.empty:
        return 0
    
    flood_days = (daily_max >= flood_stage).sum()
    return int(flood_days)


def run_flood_analysis(stations_file, out_file, start='2025-04-01', end='2025-04-07'):
    """Main pipeline: detect flood days at USGS stations.
    
    Args:
        stations_file: Path to michigan_stations.txt
        out_file: Path to output CSV
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
    """
    # Ensure dataretrieval is installed
    try:
        import dataretrieval.nwis as nwis
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'dataretrieval', '-q'])
        import dataretrieval.nwis as nwis
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    # Step 1: Extract station IDs
    print(f"Reading stations from {stations_file}...")
    station_ids = extract_station_ids(stations_file)
    print(f"Found {len(station_ids)} stations")
    
    # Step 2: Download NWS flood thresholds
    print("Downloading NWS flood stage thresholds...")
    thresholds = download_nws_flood_thresholds()
    
    # Step 3: For each station, fetch IV data and compute flood days
    results = []
    
    for i, sid in enumerate(station_ids):
        if sid not in thresholds:
            continue
        
        flood_stage = thresholds[sid]
        print(f"[{i+1}/{len(station_ids)}] Station {sid}: flood stage = {flood_stage} ft")
        
        # Fetch instantaneous gage height data
        series = get_gage_height_data(sid, start, end)
        if series is None:
            print(f"  No gage height data available")
            time.sleep(0.3)
            continue
        
        # Compute daily max
        daily_max = compute_daily_max(series)
        if daily_max is None:
            print(f"  No daily max computed")
            time.sleep(0.3)
            continue
        
        # Count flood days
        n_flood = count_flood_days(daily_max, flood_stage)
        print(f"  Daily max values: {daily_max.values}")
        print(f"  Flood days: {n_flood}")
        
        if n_flood > 0:
            results.append({'station_id': sid, 'flood_days': n_flood})
        
        time.sleep(0.5)
    
    # Step 4: Create output DataFrame and save
    if results:
        out_df = pd.DataFrame(results)
        out_df = out_df.sort_values('flood_days', ascending=False).reset_index(drop=True)
    else:
        out_df = pd.DataFrame(columns=['station_id', 'flood_days'])
    
    out_df.to_csv(out_file, index=False)
    print(f"\nResults saved to {out_file}")
    print(f"Total stations with flooding: {len(out_df)}")
    print(out_df.to_string(index=False))
    
    return out_df


if __name__ == '__main__':
    run_flood_analysis(
        stations_file='/root/data/michigan_stations.txt',
        out_file='/root/output/flood_results.csv',
        start='2025-04-01',
        end='2025-04-07'
    )