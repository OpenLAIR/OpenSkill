---
name: evo-seismic-data-preprocessing
description: Loads seismic waveform data from .npz files and converts them into ObsPy Stream objects ready for SeisBench model inference. Handles channel identification, reordering to Z/N/E convention, float32 conversion, detrending, and resampling to 100 Hz.
---

# evo-seismic-data-preprocessing

## Overview
This skill handles all data I/O from .npz seismic trace files and transforms them into properly formatted ObsPy Stream objects with correct channel ordering (Z, N, E), sampling rate (100 Hz), and data types (float32).

## Key Knowledge
- NPZ files contain: data (12000x3), dt (sampling interval), channels (comma-separated like "DPE,DPN,DPZ")
- SeisBench models expect Z, N, E channel order - must reorder from whatever order is in the file
- Channel codes ending in Z=Vertical, N=North, E=East
- Data must be float32 for PyTorch models
- Detrend (demean) before inference
- Resample to 100 Hz if not already at that rate

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-seismic-data-preprocessing/scripts')
from utils import load_and_prepare_stream, load_npz_trace, build_obspy_stream, preprocess_stream, identify_channel_order

# Full pipeline
stream, trace_info = load_and_prepare_stream('/root/data/somefile.npz')

# Or step by step
trace_info = load_npz_trace('/root/data/somefile.npz')
z_idx, n_idx, e_idx = identify_channel_order(trace_info['channels'])
stream = build_obspy_stream(trace_info['data'], trace_info['dt'], trace_info['channels'])
stream = preprocess_stream(stream)
```

## Functions
- `load_npz_trace(npz_path)` - Load npz file, return dict of all fields
- `identify_channel_order(channels_str)` - Parse channel string, return (z_idx, n_idx, e_idx)
- `build_obspy_stream(trace_data, dt, channels_str, ...)` - Build ObsPy Stream in ZNE order
- `preprocess_stream(stream, target_rate=100.0)` - Detrend and resample
- `load_and_prepare_stream(npz_path)` - Full pipeline convenience function
