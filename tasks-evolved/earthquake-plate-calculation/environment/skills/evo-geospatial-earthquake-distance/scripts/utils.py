import json
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import transform, unary_union

# Import from sister skill
import sys
sys.path.insert(0, '/app/environment/skills/evo-geospatial-antimeridian-plates/scripts')
from utils import shift_antimeridian_coords


def parse_usgs_earthquakes(usgs_geojson_path: str) -> gpd.GeoDataFrame:
    """
    Parses a raw USGS Earthquake FeatureCollection into a GeoDataFrame.
    Extracts id, magnitude, place, time (ms), latitude, longitude.
    Shifts coordinates to 0-360 space and sets CRS to EPSG:4326.
    
    Args:
        usgs_geojson_path: Path to USGS earthquake GeoJSON file
    
    Returns:
        GeoDataFrame with earthquake points in 0-360 shifted coordinates
    """
    with open(usgs_geojson_path, 'r', encoding='utf-8') as f:
        raw_json = json.load(f)
    
    records = []
    features = raw_json.get('features', [])
    
    for feat in features:
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [None, None, None])
        
        eq_id = feat.get('id')
        mag = props.get('mag')
        place = props.get('place')
        time_ms = props.get('time')  # Epoch timestamp in milliseconds
        
        # USGS provides [longitude, latitude, depth]
        lon, lat = coords[0], coords[1]
        
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
    
    eq_gdf = gpd.GeoDataFrame(records, geometry='geometry')
    
    # Shift points to match the 0-360 normalized space
    eq_gdf.geometry = shapely.transform(eq_gdf.geometry, shift_antimeridian_coords)
    
    # Assign WGS84 CRS metadata
    eq_gdf.set_crs(epsg=4326, inplace=True)
    
    return eq_gdf


def filter_earthquakes_within_plate(earthquakes_gdf: gpd.GeoDataFrame,
                                     plate_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Spatially filters earthquakes that fall within the given plate polygon.
    Uses GeoPandas 1.0.1 'predicate' parameter (not deprecated 'op').
    
    Args:
        earthquakes_gdf: GeoDataFrame of earthquake points (0-360 shifted)
        plate_gdf: GeoDataFrame of plate polygon (0-360 shifted)
    
    Returns:
        GeoDataFrame of earthquakes within the plate
    """
    eq_within = gpd.sjoin(earthquakes_gdf, plate_gdf, how='inner', predicate='within')
    return eq_within


def compute_boundary_distances(earthquakes_within_gdf: gpd.GeoDataFrame,
                                boundary_geom: shapely.Geometry) -> pd.Series:
    """
    Computes distance in km from each earthquake to the plate boundary.
    Reprojects both to EPSG:3832 (PDC Mercator) for metric distance calculation.
    
    Args:
        earthquakes_within_gdf: GeoDataFrame of filtered earthquakes (CRS=EPSG:4326, 0-360 shifted)
        boundary_geom: Unified boundary geometry (0-360 shifted, unprojected)
    
    Returns:
        pandas Series of distances in kilometers, indexed same as input
    """
    # Reproject earthquakes to EPSG:3832
    eq_proj = earthquakes_within_gdf.to_crs(epsg=3832)
    
    # Reproject boundary geometry to EPSG:3832
    pa_bound_series = gpd.GeoSeries([boundary_geom], crs="EPSG:4326")
    pa_bound_proj = pa_bound_series.to_crs(epsg=3832).iloc[0]
    
    # Compute distances in meters using broadcast
    distances_meters = eq_proj.distance(pa_bound_proj)
    
    # Convert to kilometers and round to 2 decimal places
    distances_km = (distances_meters / 1000.0).round(2)
    
    return distances_km


def find_furthest_earthquake(earthquakes_within_gdf: gpd.GeoDataFrame,
                              distances_km: pd.Series) -> pd.Series:
    """
    Identifies the earthquake with the maximum distance from the plate boundary.
    
    Args:
        earthquakes_within_gdf: GeoDataFrame of filtered earthquakes
        distances_km: Series of distances in km
    
    Returns:
        pandas Series (row) of the furthest earthquake
    """
    earthquakes_within_gdf = earthquakes_within_gdf.copy()
    earthquakes_within_gdf['distance_km'] = distances_km.values
    
    # Find the earthquake with maximum distance
    max_idx = earthquakes_within_gdf['distance_km'].idxmax()
    furthest = earthquakes_within_gdf.loc[max_idx]
    
    return furthest


def format_and_export_result(earthquake_row: pd.Series, output_path: str) -> dict:
    """
    Formats the earthquake data into the required JSON schema and exports.
    
    Converts epoch milliseconds to ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
    Uses original (unshifted) latitude/longitude values stored in the row.
    
    Args:
        earthquake_row: pandas Series with earthquake data
        output_path: Path to write the JSON output
    
    Returns:
        dict of the formatted result
    """
    # Convert millisecond timestamp to ISO 8601
    time_dt = pd.to_datetime(earthquake_row['time_ms'], unit='ms', utc=True)
    time_iso = time_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    result = {
        "id": str(earthquake_row['id']),
        "place": str(earthquake_row['place']),
        "time": time_iso,
        "magnitude": round(float(earthquake_row['magnitude']), 2) if pd.notnull(earthquake_row['magnitude']) else None,
        "latitude": float(earthquake_row['latitude']),
        "longitude": float(earthquake_row['longitude']),
        "distance_km": float(earthquake_row['distance_km'])
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    return result
