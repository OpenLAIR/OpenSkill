---
name: evo-geospatial-earthquake-distance
description: Parse USGS earthquake GeoJSON, spatially filter earthquakes within a tectonic plate, compute projected distances to plate boundaries using EPSG:3832, and output the furthest earthquake as formatted JSON.
---

# evo-geospatial-earthquake-distance

Complete pipeline for finding the earthquake furthest from a tectonic plate boundary within the plate.

## Key Concepts

### USGS GeoJSON Format
- Root: FeatureCollection with `features` array
- Each feature: `id` (string), `properties` (mag, place, time in ms epoch), `geometry` (Point with [lon, lat, depth])
- Time is milliseconds since Unix epoch, convert with `pd.to_datetime(ms, unit='ms', utc=True)`
- ISO 8601 format: `strftime('%Y-%m-%dT%H:%M:%SZ')`

### Pipeline Steps
1. Parse earthquakes, store original lat/lon, shift geometry to 0-360
2. Spatial join with plate polygon using `predicate='within'` (not `op`)
3. Reproject to EPSG:3832 (PDC Mercator) for metric distances
4. Compute distances via `GeoSeries.distance(boundary_geom)` broadcast
5. Find max distance earthquake, format and export

### Output Format
```json
{
  "id": "earthquake_id",
  "place": "location description",
  "time": "YYYY-MM-DDTHH:MM:SSZ",
  "magnitude": 5.88,
  "latitude": 19.1868,
  "longitude": -155.4932,
  "distance_km": 4143.49
}
```

## Functions

### `parse_usgs_earthquakes(path)` -> GeoDataFrame
Parses USGS GeoJSON. Stores original lat/lon columns. Shifts geometry to 0-360.

### `filter_earthquakes_within_plate(eq_gdf, plate_gdf)` -> GeoDataFrame
Spatial join with `predicate='within'`.

### `compute_boundary_distances(eq_gdf, boundary_geom)` -> Series
Reprojects to EPSG:3832, computes distances in km.

### `find_furthest_earthquake(eq_gdf, distances_km)` -> Series
Finds earthquake with maximum distance.

### `format_and_export_result(row, output_path)` -> dict
Formats to JSON with ISO 8601 time, original coordinates.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-geospatial-antimeridian-plates/scripts')
sys.path.insert(0, '/app/environment/skills/evo-geospatial-earthquake-distance/scripts')

from utils import load_plate_polygon, load_plate_boundaries
# Rename to avoid conflict
import importlib
import utils as eq_utils

# Or more explicitly:
from utils import parse_usgs_earthquakes, filter_earthquakes_within_plate
from utils import compute_boundary_distances, find_furthest_earthquake, format_and_export_result
```
