---
name: evo-geospatial-antimeridian-plates
description: Load and process PB2002 tectonic plate boundaries and polygons with antimeridian-safe coordinate normalization (0-360 longitude shift) using Shapely 2.0 transform and GeoPandas 1.0 APIs.
---

# evo-geospatial-antimeridian-plates

Handles loading PB2002 tectonic plate polygon and boundary GeoJSON files, filtering by plate code, and normalizing coordinates across the antimeridian to 0-360 range.

## Key Concepts

### Antimeridian Problem
The Pacific plate spans the 180°/-180° antimeridian. Standard WGS84 coordinates wrap at this boundary, causing catastrophic topological artifacts when projecting. Solution: shift all negative longitudes by +360 to create a continuous 0°-360° space.

### PB2002 Data Model
- **Plates file** (`PB2002_plates.json`): Contains Polygon/MultiPolygon geometries. Pacific plate identified by `Code == 'PA'`.
- **Boundaries file** (`PB2002_boundaries.json`): Contains LineString geometries. Each segment has `PlateA` and `PlateB` properties. Pacific boundaries are where `PlateA == 'PA'` OR `PlateB == 'PA'`.

### Coordinate Handling
- Use `shapely.transform(geometry, func)` (Shapely 2.0 array interface) - NOT `shapely.ops.transform`
- Use `unary_union()` - NOT deprecated `cascaded_union`
- After shifting, use `set_crs(epsg=4326, allow_override=True)` to assign CRS metadata
- Use `to_crs(epsg=3832)` for Pacific-centric metric projection (PDC Mercator, central meridian 150°E)

## Functions

### `shift_antimeridian_coords(coords)`
Shapely 2.0 transform callback. Takes (N,2) or (N,3) ndarray, shifts longitude < 0 by +360.

### `load_plate_polygon(plates_geojson_path, target_plate_code='PA')`
Loads PB2002 plates, filters by code, shifts to 0-360, returns GeoDataFrame with CRS=EPSG:4326.

### `load_plate_boundaries(boundaries_geojson_path, target_plate_code='PA')`
Loads PB2002 boundaries, filters by PlateA/PlateB, shifts to 0-360, returns unified MultiLineString geometry.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-geospatial-antimeridian-plates/scripts')
from utils import shift_antimeridian_coords, load_plate_polygon, load_plate_boundaries

# Load Pacific plate polygon (shifted to 0-360)
pacific_plate_gdf = load_plate_polygon('/root/PB2002_plates.json', 'PA')

# Load Pacific plate boundary as unified geometry (shifted to 0-360)
pacific_boundary = load_plate_boundaries('/root/PB2002_boundaries.json', 'PA')
```
