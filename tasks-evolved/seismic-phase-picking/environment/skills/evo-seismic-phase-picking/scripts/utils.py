import numpy as np
import pandas as pd
import os
import sys
import importlib.util
from obspy.core import UTCDateTime

def _load_preprocessing():
    spec = importlib.util.spec_from_file_location(
        "preprocess_utils",
        "/app/environment/skills/evo-seismic-data-preprocessing/scripts/utils.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_preprocess = _load_preprocessing()
load_and_prepare_stream = _preprocess.load_and_prepare_stream


def load_phasenet_model(pretrained="stead"):
    """Load a pretrained PhaseNet model from SeisBench."""
    import seisbench.models as sbm
    model = sbm.PhaseNet.from_pretrained(pretrained)
    model.to_preferred_device(verbose=True)
    return model


def run_phase_picking(model, stream, p_threshold=0.3, s_threshold=0.3):
    """Run PhaseNet classification on an ObsPy Stream."""
    classify_out = model.classify(
        stream,
        P_threshold=p_threshold,
        S_threshold=s_threshold,
        overlap=0.6,
        batch_size=128
    )
    return classify_out


def extract_picks_to_dataframe(classify_out):
    """Extract picks from ClassifyOutput to a pandas DataFrame."""
    pick_list = classify_out.picks
    if len(pick_list) == 0:
        return pd.DataFrame(columns=['station', 'time', 'start_time', 'phase', 'probability'])
    picks_df = pick_list.to_dataframe()
    return picks_df


def convert_pick_to_original_index(pick_time, stream_start_time, original_dt):
    """Convert a pick time to an index in the original data array."""
    original_rate = 1.0 / float(original_dt)
    
    # Convert to epoch timestamps for safe subtraction
    if isinstance(stream_start_time, UTCDateTime):
        start_epoch = stream_start_time.timestamp
    else:
        start_epoch = pd.Timestamp(stream_start_time).timestamp()
    
    if isinstance(pick_time, UTCDateTime):
        pick_epoch = pick_time.timestamp
    elif isinstance(pick_time, pd.Timestamp):
        pick_epoch = pick_time.timestamp()
    else:
        pick_epoch = pd.Timestamp(pick_time).timestamp()
    
    time_diff = pick_epoch - start_epoch
    idx = int(round(time_diff * original_rate))
    return idx


def process_single_trace(model, npz_path, file_name, p_threshold=0.3, s_threshold=0.3):
    """Process a single trace file and return picks as list of dicts."""
    try:
        stream, trace_info = load_and_prepare_stream(npz_path)
        classify_out = run_phase_picking(model, stream, p_threshold, s_threshold)
        picks_df = extract_picks_to_dataframe(classify_out)
        
        if len(picks_df) == 0:
            return []
        
        original_dt = float(trace_info['dt'])
        stream_start = stream[0].stats.starttime
        
        results = []
        for _, row in picks_df.iterrows():
            # Use 'start_time' or 'time' column for pick time
            pick_time = row.get('start_time', row.get('time', None))
            if pick_time is None:
                continue
            phase = row['phase']
            idx = convert_pick_to_original_index(pick_time, stream_start, original_dt)
            
            # Clamp to valid range
            n_samples = trace_info['data'].shape[0]
            idx = max(0, min(idx, n_samples - 1))
            
            results.append({
                'file_name': file_name,
                'phase': phase,
                'pick_idx': idx
            })
        
        return results
    except Exception as e:
        print(f"Error processing {file_name}: {e}")
        return []


def process_all_traces_to_csv(data_dir, output_csv, p_threshold=0.3, s_threshold=0.3):
    """Process all .npz files in a directory and write results to CSV."""
    model = load_phasenet_model("stead")
    
    files = sorted([f for f in os.listdir(data_dir) if f.endswith('.npz')])
    print(f"Processing {len(files)} trace files...")
    
    all_results = []
    for i, fn in enumerate(files):
        npz_path = os.path.join(data_dir, fn)
        picks = process_single_trace(model, npz_path, fn, p_threshold, s_threshold)
        all_results.extend(picks)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{len(files)} files, {len(all_results)} picks so far")
    
    df = pd.DataFrame(all_results, columns=['file_name', 'phase', 'pick_idx'])
    df['pick_idx'] = df['pick_idx'].astype(int)
    df.to_csv(output_csv, index=False)
    print(f"Done! Wrote {len(df)} picks to {output_csv}")
    print(f"  P picks: {len(df[df['phase']=='P'])}, S picks: {len(df[df['phase']=='S'])}")
    return df
