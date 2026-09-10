# Domain Reference for evo-seismic-phase-picking

**Responsibility**: Loading pretrained SeisBench models, running classify() on per-station streams, extracting pick times/phases/probabilities into a structured DataFrame.

**Key functions to implement**: load_picker_model, pick_phases_for_stream, pick_all_stations, picks_to_dataframe

---

## 2. SeisBench v0.10.2: Deep Learning Phase Picking


SeisBench is an open-source framework designed to standardize machine learning in seismology [cite: 15, 16]. Version 0.10.2 introduced major backend overhauls, including C-compiled bottleneck functions for performance, async interfaces, and an updated PhaseNet implementation utilizing original model weights [cite: 17].

### 2.1 Available Models and Import Paths

The pre-trained models can be imported directly from the `seisbench.models` module [cite: 18].

**Exact Import Paths:**
```python
import seisbench.models as sbm

### 2.2 Model API: `classify()` vs `annotate()`


SeisBench provides two primary high-level methods that integrate directly with ObsPy `Stream` objects [cite: 13, 15].

### 2.3 Handling Components, Gaps, and Sampling Rates

*   **1C vs 3C Data**: Models like PhaseNet and EQTransformer expect 3-component data [cite: 21, 27]. If 1-component data is provided, SeisBench will often duplicate the trace or pad with zeros, but performance drops drastically. 
*   **ZNE Ordering**: SeisBench automatically handles channel ordering. If not explicitly specified, it defaults to identifying 'Z', 'N', and 'E' based on the last character of the channel code [cite: 22, 28]. You do not need to manually sort the `Stream` before passing it to `classify()`.
*   **Sampling Rate**: Deep learning models are trained at specific sample rates (almost universally 100 Hz) [cite: 15, 16]. **SeisBench automatically resamples** the input trace to the required sampling rate internally before passing it to the model [cite: 22]. You do not need to manually resample your `Stream` [cite: 22].
*   **Gaps**: SeisBench models convert the traces into PyTorch tensors. If there are minor gaps in the trace, SeisBench's internal conversion routines (e.g., `stream_to_array`) fill the missing remaining parts with zeros to maintain temporal alignment [cite: 23].

### 2.4 Working Code Example: Complete Picking Pipeline


```python
import obspy
import seisbench.models as sbm
import pandas as pd
import torch

def run_seisbench_picker(mseed_path):
    # 1. Load Data
    stream = obspy.read(mseed_path)
    
    # 2. Group by Station
    station_streams = {}
    for tr in stream:
        sta_key = f"{tr.stats.network}.{tr.stats.station}"
        if sta_key not in station_streams:
            station_streams[sta_key] = obspy.Stream()
        station_streams[sta_key].append(tr)
        
    # 3. Load Model and Move to GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = sbm.PhaseNet.from_pretrained("stead")
    model.to(device)
    
    all_picks = []
    
    # 4. Predict
    for sta_key, st3c in station_streams.items():
        # Ensure at least 3 components are present (or let SeisBench handle padding)
        try:
            # classify() handles resampling and ZNE ordering internally
            output = model.classify(
                st3c, 
                batch_size=256,
                P_threshold=0.3,
                S_threshold=0.3,
                overlap=1500  # 15 seconds overlap for PhaseNet
            )
            
            # 5. Extract Picks
            for pick in output.picks:
                all_picks.append({
                    "station": sta_key,
                    "phase": pick.phase,              # 'P' or 'S'
                    "time": pick.start_time,          # obspy.UTCDateTime
                    "probability": pick.peak_value    # Confidence [cite: 17]
                })
        except Exception as e:
            print(f"Failed to process {sta_key}: {e}")
            
    # Convert to DataFrame for downstream association
    return pd.DataFrame(all_picks)