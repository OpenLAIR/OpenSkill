---
name: evo-seismic-phase-picking
description: Runs SeisBench deep learning models (PhaseNet/EQTransformer) on grouped station waveforms to produce P and S phase picks with timestamps and probabilities.
---

# evo-seismic-phase-picking

Uses SeisBench PhaseNet/EQTransformer for P/S wave picking.

## Functions

- `load_picker_model(model_name, weights)` - Load pretrained SeisBench model
- `pick_phases_for_stream(model, stream_3c, p_threshold, s_threshold)` - Pick one station
- `pick_all_stations(model, station_streams, p_threshold, s_threshold)` - Pick all stations
- `picks_to_dataframe(picks_list)` - Convert picks to DataFrame with unix_time column

## Usage

Note: Since all skills have utils.py, use importlib to avoid name collisions:

```python
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

pick_utils = load_module('pick_utils', '/app/environment/skills/evo-seismic-phase-picking/scripts/utils.py')

model = pick_utils.load_picker_model("PhaseNet", "stead")
all_picks = pick_utils.pick_all_stations(model, station_streams, p_threshold=0.3, s_threshold=0.3)
picks_df = pick_utils.picks_to_dataframe(all_picks)
```
