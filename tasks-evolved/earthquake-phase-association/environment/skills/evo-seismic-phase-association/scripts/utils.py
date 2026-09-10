import numpy as np
import pandas as pd
from obspy import UTCDateTime

def associate_picks(picks_df, station_dict, vp=6.0, vs=None, 
                    tolerance=1.5, n_picks=8, n_p_picks=3, n_s_picks=3,
                    min_interevent_time=3.0):
    """Associate phase picks into earthquake events using PyOcto.
    
    Args:
        picks_df: DataFrame with columns [station, phase, time, probability, unix_time]
        station_dict: dict of {net.sta: {latitude, longitude, elevation}}
        vp: P-wave velocity in km/s
        vs: S-wave velocity in km/s
    Returns:
        list of event dicts
    """
    import pyocto
    
    if vs is None:
        vs = vp / 1.75
    
    if len(picks_df) == 0:
        return []
    
    picks_df = picks_df.copy()
    
    # Build stations DataFrame for PyOcto
    sta_rows = []
    for sta_key, info in station_dict.items():
        sta_rows.append({
            'id': sta_key,
            'latitude': info['latitude'],
            'longitude': info['longitude'],
            'elevation': info['elevation'],
        })
    stations_pyocto = pd.DataFrame(sta_rows)
    
    # Build picks DataFrame for PyOcto
    # PyOcto expects 'time' as a timestamp (seconds since epoch)
    pick_rows = []
    for _, pick in picks_df.iterrows():
        t = pick['time']
        if hasattr(t, 'timestamp'):
            timestamp = float(t.timestamp)
        else:
            timestamp = float(t)
        pick_rows.append({
            'station': pick['station'],
            'phase': pick['phase'],
            'time': timestamp,
        })
    picks_pyocto = pd.DataFrame(pick_rows)
    
    # Create velocity model
    velocity_model = pyocto.VelocityModel0D(
        p_velocity=vp,
        s_velocity=vs,
        tolerance=tolerance,
    )
    
    # Compute coordinate bounds with padding
    lat_min = stations_pyocto['latitude'].min() - 0.5
    lat_max = stations_pyocto['latitude'].max() + 0.5
    lon_min = stations_pyocto['longitude'].min() - 0.5
    lon_max = stations_pyocto['longitude'].max() + 0.5
    
    # Create associator
    associator = pyocto.OctoAssociator(
        xlim=(lat_min, lat_max),  # Will be transformed by CRS
        ylim=(lon_min, lon_max),
        zlim=(0, 30),  # depth 0-30 km
        velocity_model=velocity_model,
        time_before=300.0,
        n_picks=n_picks,
        n_p_picks=n_p_picks,
        n_s_picks=n_s_picks,
        n_p_and_s_picks=n_p_picks,
        min_interevent_time=min_interevent_time,
        min_node_size=10.0,
        pick_match_tolerance=tolerance,
    )
    
    # Set CRS and transform stations
    associator.crs = associator.get_crs(stations_pyocto)
    stations_transformed = associator.transform_stations(stations_pyocto)
    
    # Update xlim/ylim based on transformed coordinates with padding
    x_pad = 50  # km padding
    y_pad = 50
    associator.xlim = (
        stations_transformed['x'].min() - x_pad,
        stations_transformed['x'].max() + x_pad
    )
    associator.ylim = (
        stations_transformed['y'].min() - y_pad,
        stations_transformed['y'].max() + y_pad
    )
    
    print(f"  PyOcto: {len(picks_pyocto)} picks, {len(stations_transformed)} stations")
    print(f"  X range: {associator.xlim}")
    print(f"  Y range: {associator.ylim}")
    
    # Run association
    events_df, assignments_df = associator.associate(picks_pyocto, stations_transformed)
    
    print(f"  PyOcto found {len(events_df)} events")
    
    # Convert to our event format
    events = []
    for _, evt in events_df.iterrows():
        events.append({
            'event_id': f"ev_{evt.name}",
            'time': UTCDateTime(evt['time']),
            'latitude': evt.get('latitude', 0.0) if 'latitude' in evt.index else 0.0,
            'longitude': evt.get('longitude', 0.0) if 'longitude' in evt.index else 0.0,
            'num_picks': int(evt.get('n_picks', 0)) if 'n_picks' in evt.index else 0,
        })
    
    # Deduplicate events within 5 seconds
    events = deduplicate_events(events, time_threshold=5.0)
    
    return events

def deduplicate_events(events, time_threshold=5.0):
    """Remove duplicate events within time_threshold seconds."""
    if len(events) <= 1:
        return events
    
    events.sort(key=lambda e: float(e['time'].timestamp))
    
    deduped = [events[0]]
    for evt in events[1:]:
        last = deduped[-1]
        time_diff = abs(float(evt['time'].timestamp) - float(last['time'].timestamp))
        if time_diff < time_threshold:
            if evt.get('num_picks', 0) > last.get('num_picks', 0):
                deduped[-1] = evt
        else:
            deduped.append(evt)
    
    return deduped

def write_event_catalog(events, output_path):
    """Write event catalog to CSV with ISO-formatted timestamps (no timezone)."""
    rows = []
    for evt in events:
        rows.append({
            'time': evt['time'].strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'latitude': evt.get('latitude', ''),
            'longitude': evt.get('longitude', ''),
            'num_picks': evt.get('num_picks', ''),
        })
    
    df = pd.DataFrame(rows)
    if len(df) == 0:
        df = pd.DataFrame(columns=['time'])
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} events to {output_path}")
    return df
