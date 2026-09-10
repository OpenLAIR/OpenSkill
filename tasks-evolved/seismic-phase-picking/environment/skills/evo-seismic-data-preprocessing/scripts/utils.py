import numpy as np
from obspy.core import Trace, Stream, UTCDateTime


def load_npz_trace(npz_path):
    """Load a seismic trace from an npz file."""
    f = np.load(npz_path, allow_pickle=True)
    result = {}
    for key in f.keys():
        val = f[key]
        if val.ndim == 0:
            result[key] = val.item()
        else:
            result[key] = val
    return result


def identify_channel_order(channels_str):
    """Parse channel string and return (z_idx, n_idx, e_idx, mapped_channels).
    
    Handles: ZNE standard, 123 numbering, single/partial components.
    """
    if isinstance(channels_str, np.ndarray):
        channels_str = str(channels_str)
    chan_list = [c.strip() for c in channels_str.split(',')]
    
    z_idx = n_idx = e_idx = None
    
    for i, ch in enumerate(chan_list):
        last_char = ch[-1] if ch else ''
        if last_char == 'Z':
            z_idx = i
        elif last_char in ('N', '1'):
            n_idx = i
        elif last_char in ('E', '2'):
            e_idx = i
        elif last_char == '3':
            z_idx = i
    
    # Get prefix for channel codes
    prefix = chan_list[0][:-1] if len(chan_list[0]) > 1 else 'BH'
    
    if len(chan_list) == 1:
        # Single channel name but 3 columns of data
        z_idx, n_idx, e_idx = 0, 1, 2
        return z_idx, n_idx, e_idx, [prefix + 'Z', prefix + 'N', prefix + 'E']
    
    if len(chan_list) == 2:
        # Two channels - assign the missing one
        used = {z_idx, n_idx, e_idx} - {None}
        remaining = [i for i in range(3) if i not in used]
        if z_idx is None and remaining:
            z_idx = remaining[0]
        elif n_idx is None and remaining:
            n_idx = remaining[0]
        elif e_idx is None and remaining:
            e_idx = remaining[0]
        # Ensure all are assigned
        if z_idx is None: z_idx = 2
        if n_idx is None: n_idx = 1  
        if e_idx is None: e_idx = 0
        return z_idx, n_idx, e_idx, [prefix + 'Z', prefix + 'N', prefix + 'E']
    
    # 3 channels
    if z_idx is None: z_idx = 0
    if n_idx is None: n_idx = 1
    if e_idx is None: e_idx = 2
    
    return z_idx, n_idx, e_idx, [prefix + 'Z', prefix + 'N', prefix + 'E']


def build_obspy_stream(trace_data, dt, channels_str, network='XX', station='STA',
                       location='', start_time_str=None):
    """Build an ObsPy Stream from numpy array data, reordered to ZNE.
    
    Normalizes data to have reasonable amplitudes for the model.
    """
    z_idx, n_idx, e_idx, mapped_channels = identify_channel_order(channels_str)
    
    sampling_rate = 1.0 / float(dt)
    
    if start_time_str and start_time_str not in ('--', 'None', ''):
        try:
            start_time = UTCDateTime(start_time_str)
        except:
            start_time = UTCDateTime("2023-01-01T00:00:00.000000Z")
    else:
        start_time = UTCDateTime("2023-01-01T00:00:00.000000Z")
    
    if location in ('--', 'None', None):
        location = ''
    
    zne_indices = [z_idx, n_idx, e_idx]
    
    # Normalize data to reasonable amplitudes
    # SeisBench does per-window normalization, but extremely small values
    # (1e-15) can underflow in float32. Scale to ~1.0 range.
    data_copy = trace_data.copy().astype(np.float64)
    max_abs = np.abs(data_copy).max()
    if max_abs > 0 and max_abs < 1e-3:
        # Scale up to reasonable range
        scale_factor = 1.0 / max_abs
        data_copy = data_copy * scale_factor
    data_copy = data_copy.astype(np.float32)
    
    traces = []
    for i, (orig_idx, chan_code) in enumerate(zip(zne_indices, mapped_channels)):
        stats = {
            "network": network,
            "station": station,
            "location": location,
            "channel": chan_code,
            "starttime": start_time,
            "sampling_rate": sampling_rate
        }
        tr = Trace(data=data_copy[:, orig_idx].copy(), header=stats)
        traces.append(tr)
    
    stream = Stream(traces=traces)
    return stream


def preprocess_stream(stream, target_rate=100.0):
    """Preprocess an ObsPy Stream: detrend and resample if needed."""
    stream.detrend("demean")
    
    current_rate = stream[0].stats.sampling_rate
    if abs(current_rate - target_rate) > 0.01:
        stream.resample(target_rate)
    
    return stream


def load_and_prepare_stream(npz_path):
    """Full pipeline: load npz -> build stream -> preprocess."""
    trace_info = load_npz_trace(npz_path)
    
    stream = build_obspy_stream(
        trace_data=trace_info['data'],
        dt=trace_info['dt'],
        channels_str=trace_info.get('channels', 'DPE,DPN,DPZ'),
        network=str(trace_info.get('network', 'XX')),
        station=str(trace_info.get('station', 'STA')),
        location=str(trace_info.get('location_code', '')),
        start_time_str=str(trace_info.get('start_time', None))
    )
    
    stream = preprocess_stream(stream)
    
    return stream, trace_info
