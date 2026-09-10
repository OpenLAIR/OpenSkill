import obspy
import pandas as pd
from collections import defaultdict

def load_waveforms(mseed_path):
    """Load MiniSEED waveform data and return an ObsPy Stream."""
    stream = obspy.read(mseed_path)
    return stream

def load_stations(csv_path):
    """Load station CSV and return a pandas DataFrame."""
    df = pd.read_csv(csv_path)
    return df

def group_traces_by_station(stream):
    """Group a flat ObsPy Stream into dict of {net.sta: Stream} for 3C processing.
    For stations with mixed channel types (HH vs HN/EH), prefer HH channels.
    If no HH channels, use HN channels (treating EH as Z component)."""
    station_streams = defaultdict(obspy.Stream)
    
    for trace in stream:
        net = trace.stats.network
        sta = trace.stats.station
        key = f"{net}.{sta}"
        station_streams[key].append(trace)
    
    # For each station, if there are mixed channel types, prefer HH* or select best 3C set
    result = {}
    for key, st in station_streams.items():
        # Get unique channel prefixes (first 2 chars)
        prefixes = set(tr.stats.channel[:2] for tr in st)
        
        if 'HH' in prefixes:
            # Prefer HH channels (broadband seismometer)
            filtered = obspy.Stream([tr for tr in st if tr.stats.channel[:2] == 'HH'])
            result[key] = filtered
        elif 'HN' in prefixes:
            # Strong motion + possibly EH
            # Combine HN (E,N,Z) channels
            filtered = obspy.Stream([tr for tr in st if tr.stats.channel[:2] == 'HN'])
            result[key] = filtered
        else:
            result[key] = st
    
    return result

def get_station_dict(stations_df):
    """Build a dict mapping 'net.sta' -> {latitude, longitude, elevation} from stations DataFrame.
    Deduplicates by taking first row per station."""
    station_dict = {}
    for (net, sta), group in stations_df.groupby(['network', 'station']):
        row = group.iloc[0]
        sta_key = f"{net}.{sta}"
        station_dict[sta_key] = {
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'elevation': row.get('elevation_m', row.get('elevation', 0.0))
        }
    return station_dict
