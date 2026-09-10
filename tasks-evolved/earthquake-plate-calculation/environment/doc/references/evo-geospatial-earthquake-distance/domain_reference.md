# Domain Reference for evo-geospatial-earthquake-distance

**Responsibility**: Parse earthquake data, shift earthquake coordinates to 0-360 space, perform spatial join to filter earthquakes within the Pacific plate, reproject to EPSG:3832 for metric distance calculation, identify the earthquake with maximum distance from the plate boundary, format timestamps to ISO 8601, and serialize result to JSON.

**Key functions to implement**: parse_usgs_earthquakes, filter_earthquakes_within_plate, compute_boundary_distances, find_furthest_earthquake, format_and_export_result

---

### 1.2 USGS Earthquake GeoJSON Specification

The USGS provides earthquake catalog data through a well-documented GeoJSON web service API [cite: 4, 16]. The output conforms strictly to the RFC 7946 GeoJSON standard, structured primarily as a `FeatureCollection` [cite: 4].

To build a robust parser, it is necessary to understand the exact JSON hierarchy of the USGS feed:
*   **Root Level:** Contains `type` ("FeatureCollection"), `metadata`, `bbox`, and `features` (an array of earthquake events) [cite: 4].
*   **Feature Level:** Each object within the `features` array possesses an `id` string (e.g., "nc72914101"), a `type` ("Feature"), a `properties` dictionary, and a `geometry` dictionary [cite: 4, 17].
*   **Properties Block:** The critical fields include `mag` (Decimal, representing the magnitude), `place` (String, textual location description), and `time` (Long Integer, representing milliseconds since the Unix epoch) [cite: 4, 5].
*   **Geometry Block:** Defined as a `Point` geometry, with a `coordinates` array structured strictly as `[longitude, latitude, depth]` [cite: 4].

When loading this into GeoPandas, `gpd.read_file()` natively flattens the `properties` dictionary into DataFrame columns, though manual extraction from a raw JSON payload using Python's `json` module is often preferred for rigorous schema validation and cleaning prior to DataFrame construction.

---

### 3.1 Deprecation of the `op` Parameter

In prior versions of GeoPandas, performing a spatial join (`gpd.sjoin`) utilized the `op` argument to specify the topological DE-9IM relationship (e.g., `op='within'`). In GeoPandas 1.0.1, the `op` parameter has been strictly removed and replaced by the `predicate` argument [cite: 9, 10]. 

To determine which earthquake points fall within the Pacific Plate polygon, the spatial join is executed via:
`gpd.sjoin(earthquakes_gdf, pacific_plate_gdf, how='inner', predicate='within')` [cite: 23, 24].

### 3.3 Broadcast Distance Computation

To calculate the distance from each filtered earthquake to the nearest point on the Pacific Plate boundary, we rely on `GeoSeries.distance()`. 

The `distance` method in GeoPandas measures Cartesian proximity. If two GeoSeries of equal length are passed, it computes row-wise distances. However, if a single singular geometric object (like our unioned `MultiLineString` Pacific boundary) is passed, GeoPandas 1.0.1 intelligently **broadcasts** this single geometry across the entire earthquake array, performing element-wise nearest-distance checks in a highly optimized vector space [cite: 32, 33]. 

This directly negates the need for manual loops or older tools like `shapely.ops.nearest_points()`. By projecting both the earthquake points and the plate boundaries into EPSG:3832, `earthquakes.distance(pacific_boundary_geom)` will instantly yield accurate proximity values in meters [cite: 34].

---

### 4.2 Python Source Code


```python
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import transform, unary_union

def shift_antimeridian_coords(coords: np.ndarray) -> np.ndarray:
    """
    Shapely 2.0.6 transform function.
    Takes an (N, 2) or (N, 3) ndarray of coordinates.
    Shifts longitudes < 0 to the 0-360 degree scale to avoid antimeridian artifacts.
    """
    shifted = np.copy(coords)
    # Longitude is the 0-th index in the coordinate array
    shifted[:, 0] = np.where(shifted[:, 0] < 0, shifted[:, 0] + 360.0, shifted[:, 0])
    return shifted

def load_and_filter_plate(plates_geojson_path: str, target_plate_code: str = 'PA') -> gpd.GeoDataFrame:
    """
    Loads PB2002_plates.json, extracts the target plate, and normalizes its geometry.
    """
    # Load raw PB2002 plates
    plates_gdf = gpd.read_file(plates_geojson_path)
    
    # Filter for the Pacific Plate. PB2002 plate identifier is in the 'Code' property
    target_plate = plates_gdf[plates_gdf['Code'] == target_plate_code].copy()
    
    if target_plate.empty:
        raise ValueError(f"Plate Code '{target_plate_code}' not found in the dataset.")
        
    # Shift plate geometry to 0-360 range using Shapely 2.0 array interface
    target_plate.geometry = shapely.transform(target_plate.geometry, shift_antimeridian_coords)
    
    # Define coordinate system explicitly as EPSG:4326 metadata
    target_plate.set_crs(epsg=4326, inplace=True, allow_override=True)
    return target_plate

def extract_plate_boundaries(boundaries_geojson_path: str, target_plate_code: str = 'PA') -> shapely.Geometry:
    """
    Loads PB2002_boundaries.json, isolates boundary segments involving the target plate,
    shifts longitudes, and unions them into a single MultiLineString.
    """
    bounds_gdf = gpd.read_file(boundaries_geojson_path)
    
    # Filter boundary segments where PlateA OR PlateB equals the target code
    mask = (bounds_gdf['PlateA'] == target_plate_code) | (bounds_gdf['PlateB'] == target_plate_code)
    target_bounds = bounds_gdf[mask].copy()
    
    # Shift boundary segment geometries to 0-360 range
    target_bounds.geometry = shapely.transform(target_bounds.geometry, shift_antimeridian_coords)
    
    # Union all segments into a single geometric object (MultiLineString)
    # Note: cascaded_union is deprecated; unary_union is the correct Shapely 2.0 standard
    merged_boundary = unary_union(target_bounds.geometry.values)
    
    return merged_boundary

def parse_usgs_earthquakes(usgs_geojson_path: str) -> gpd.GeoDataFrame:
    """
    Parses a raw USGS Earthquake FeatureCollection into a GeoDataFrame,
    extracting id, magnitude, place, and time metadata.
    """
    with open(usgs_geojson_path, 'r', encoding='utf-8') as f:
        raw_json = json.load(f)
        
    records = []
    features = raw_json.get('features', [])
    
    for feat in features:
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [None, None])
        
        # Extract features
        eq_id = feat.get('id')
        mag = props.get('mag')
        place = props.get('place')
        time_ms = props.get('time') # Epoch timestamp in milliseconds
        
        # USGS provides [lon, lat, depth]
        lon, lat = coords, coords[cite: 32]
        
        if lon is not None and lat is not None:
            records.append({
                'id': eq_id,
                'magnitude': mag,
                'place': place,
                'time_ms': time_ms,
                'latitude': lat,
                'longitude': lon,
                'geometry': shapely.Point(lon, lat)
            })
            
    # Create GeoDataFrame
    eq_gdf = gpd.GeoDataFrame(records, geometry='geometry')
    
    # Shift points to match the 0-360 normalized space
    eq_gdf.geometry = shapely.transform(eq_gdf.geometry, shift_antimeridian_coords)
    
    # Assign WGS84 CSR metadata
    eq_gdf.set_crs(epsg=4326, inplace=True)
    return eq_gdf

def run_geospatial_pipeline():
    # File Paths (Assuming existence in local directory)
    plates_file = 'PB2002_plates.json'
    bounds_file = 'PB2002_boundaries.json'
    earthquakes_file = 'earthquakes.json'
    
    # 1. Load Data and shift across Antimeridian
    pacific_plate_gdf = load_and_filter_plate(plates_file, 'PA')
    pacific_boundary_geom = extract_plate_boundaries(bounds_file, 'PA')
    earthquakes_gdf = parse_usgs_earthquakes(earthquakes_file)
    
    # 2. Filter Earthquakes that fall strictly within the Pacific Plate
    # Uses GeoPandas 1.0.1 predicate parameter (op is deprecated)
    eq_within_pacific = gpd.sjoin(earthquakes_gdf, pacific_plate_gdf, how='inner', predicate='within')
    
    # 3. Reproject geometries to EPSG:3832 (PDC Mercator) for accurate Pacific distance calculations
    eq_within_pacific_proj = eq_within_pacific.to_crs(epsg=3832)
    
    # Create a temporary GeoSeries for the boundary scalar to facilitate reprojection
    pa_bound_series = gpd.GeoSeries([pacific_boundary_geom], crs="EPSG:4326")
    pa_bound_proj = pa_bound_series.to_crs(epsg=3832).item()
    
    # 4. Compute shortest distance from each point to the MultiLineString boundary
    # GeoPandas 1.0+ natively broadcasts the singular geometry element-wise
    distances_meters = eq_within_pacific_proj.distance(pa_bound_proj)
    
    # 5. Format Data for Serialization
    # Convert meters to kilometers and round to 2 decimal places
    eq_within_pacific['distance_km'] = (distances_meters / 1000.0).round(2)
    
    # Convert long integer timestamps (ms) to ISO 8601 strings
    # UTC constraint applied for ISO ZULU ("Z") time formatting
    eq_within_pacific['time'] = pd.to_datetime(eq_within_pacific['time_ms'], unit='ms', utc=True)
    eq_within_pacific['time_iso'] = eq_within_pacific['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # 6. Export to Output JSON
    output_data = []
    for _, row in eq_within_pacific.iterrows():
        output_data.append({
            "id": row['id'],
            "place": row['place'],
            "time": row['time_iso'],
            "magnitude": round(float(row['magnitude']), 2) if pd.notnull(row['magnitude']) else None,
            "latitude": round(float(row['latitude']), 4),
            "longitude": round(float(row['longitude']), 4),
            "distance_km": float(row['distance_km'])
        })
        
    with open('pacific_earthquake_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)

if __name__ == '__main__':
    # Execute analytical pipeline
    run_geospatial_pipeline()
```

---

### 5.1 ISO 8601 DateTime Conversion

The standard format for the USGS earthquake `time` property is a Unix epoch timestamp captured in milliseconds (Long Integer type) [cite: 4, 5]. When processing this data into an ISO 8601 standardized format (e.g., `YYYY-MM-DDTHH:MM:SSZ`), utilizing Python's `pandas.to_datetime` yields excellent vectorization capabilities. 

Because the raw integer represents milliseconds, we must pass the parameter `unit='ms'`. Additionally, ensuring the timezone remains strictly UTC requires passing `utc=True`. The subsequent application of the `dt.strftime('%Y-%m-%dT%H:%M:%SZ')` string format yields the perfectly compliant ISO sequence string, complete with the `"Z"` trailing identifier denoting Zulu (UTC) time.

### 5.2 Python Float Normalization and Serialization

In geospatial distance tracking, highly volatile floats resulting from projection algorithms (e.g., Euclidean distance measurement derived from EPSG:3832 metric matrices) must be truncated or rounded. The Python built-in `round(float_value, 2)` functionality or Pandas' `.round(2)` applied to the respective Series ensures data remains interpretable. When preparing the ultimate export, standard dict conversion mapping scalar properties facilitates clean JSON serialization via `json.dump()`.