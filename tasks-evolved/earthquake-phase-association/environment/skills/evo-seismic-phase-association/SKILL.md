---
name: evo-seismic-phase-association
description: Associates phase picks from multiple stations into earthquake events using temporal clustering (DBSCAN) and travel-time validation with a uniform velocity model, then outputs event catalog as CSV.
---

# evo-seismic-phase-association

Associates P/S picks into earthquake events using DBSCAN clustering and moveout validation.

## Functions

- `associate_picks(picks_df, station_dict, vp, vs, eps_sec, min_picks)` - Main association
- `validate_cluster(cluster_df, station_dict, source_lat, source_lon, t0, vp, vs, tolerance)` - Validate picks
- `estimate_origin_time(valid_picks, station_dict, source_lat, source_lon, vp, vs)` - Estimate t0
- `deduplicate_events(events, time_threshold)` - Remove duplicate events
- `write_event_catalog(events, output_path)` - Write CSV with ISO timestamps

## Usage

```python
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

assoc_utils = load_module('assoc_utils', '/app/environment/skills/evo-seismic-phase-association/scripts/utils.py')

events = assoc_utils.associate_picks(picks_df, station_dict, vp=6.0, vs=6.0/1.75, eps_sec=15.0, min_picks=4)
assoc_utils.write_event_catalog(events, '/root/results.csv')
```
