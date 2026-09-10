import torch
import pandas as pd
import obspy

def load_picker_model(model_name="PhaseNet", weights="stead"):
    """Load a pretrained SeisBench model.
    Args:
        model_name: 'PhaseNet' or 'EQTransformer'
        weights: 'stead', 'original', 'instance', etc.
    Returns:
        SeisBench model ready for inference
    """
    import seisbench.models as sbm
    
    if model_name == "PhaseNet":
        model = sbm.PhaseNet.from_pretrained(weights)
    elif model_name == "EQTransformer":
        model = sbm.EQTransformer.from_pretrained(weights)
    else:
        raise ValueError(f"Unknown model: {model_name}")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    return model

def pick_phases_for_stream(model, stream_3c, p_threshold=0.3, s_threshold=0.3):
    """Run phase picking on a single station's 3C stream.
    Args:
        model: SeisBench model
        stream_3c: ObsPy Stream with 3 components for one station
        p_threshold: probability threshold for P picks
        s_threshold: probability threshold for S picks
    Returns:
        list of dicts with keys: phase, time (UTCDateTime), probability
    """
    picks_list = []
    try:
        output = model.classify(
            stream_3c,
            batch_size=256,
            P_threshold=p_threshold,
            S_threshold=s_threshold,
        )
        
        for pick in output.picks:
            picks_list.append({
                'phase': pick.phase,
                'time': pick.peak_time,
                'probability': pick.peak_value,
            })
    except Exception as e:
        print(f"Warning: Failed to pick phases: {e}")
    
    return picks_list

def pick_all_stations(model, station_streams, p_threshold=0.3, s_threshold=0.3):
    """Run phase picking on all stations.
    Args:
        model: SeisBench model
        station_streams: dict of {net.sta: Stream}
        p_threshold, s_threshold: probability thresholds
    Returns:
        list of dicts with keys: station, phase, time, probability
    """
    all_picks = []
    
    for sta_key, st3c in station_streams.items():
        print(f"Picking phases for {sta_key} ({len(st3c)} traces)...")
        picks = pick_phases_for_stream(model, st3c, p_threshold, s_threshold)
        for p in picks:
            p['station'] = sta_key
            all_picks.append(p)
    
    print(f"Total picks: {len(all_picks)}")
    return all_picks

def picks_to_dataframe(picks_list):
    """Convert list of pick dicts to a pandas DataFrame.
    Ensures 'time' column contains UTCDateTime objects and adds 'unix_time' column."""
    if not picks_list:
        return pd.DataFrame(columns=['station', 'phase', 'time', 'probability', 'unix_time'])
    
    df = pd.DataFrame(picks_list)
    # Add unix timestamp for numerical operations
    df['unix_time'] = df['time'].apply(lambda t: float(t.timestamp) if hasattr(t, 'timestamp') else float(t))
    return df
