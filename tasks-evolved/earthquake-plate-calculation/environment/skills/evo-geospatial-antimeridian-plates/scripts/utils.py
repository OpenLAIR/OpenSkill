import numpy as np
import geopandas as gpd
import shapely
from shapely import transform, unary_union


def shift_antimeridian_coords(coords: np.ndarray) -> np.ndarray:
    """
    Shapely 2.0.6 transform function.
    Takes an (N, 2) or (N, 3) ndarray of coordinates.
    Shifts longitudes < 0 to the 0-360 degree scale to avoid antimeridian artifacts.
    
    This is used as a callback for shapely.transform(geometry, func).
    The function receives an (N, 2) or (N, 3) array where column 0 is longitude.
    """
    shifted = np.copy(coords)
    shifted[:, 0] = np.where(shifted[:, 0] < 0, shifted[:, 0] + 360.0, shifted[:, 0])
    return shifted


def load_plate_polygon(plates_geojson_path: str, target_plate_code: str = 'PA') -> gpd.GeoDataFrame:
    """
    Loads PB2002_plates.json, extracts the target plate polygon, and normalizes
    its geometry to 0-360 longitude range to handle antimeridian crossing.
    
    Args:
        plates_geojson_path: Path to PB2002_plates.json
        target_plate_code: Plate code to filter (default 'PA' for Pacific)
    
    Returns:
        GeoDataFrame with the target plate polygon in 0-360 shifted coordinates,
        CRS set to EPSG:4326.
    """
    plates_gdf = gpd.read_file(plates_geojson_path)
    
    # Filter for the target plate using the 'Code' column
    target_plate = plates_gdf[plates_gdf['Code'] == target_plate_code].copy()
    
    if target_plate.empty:
        raise ValueError(f"Plate Code '{target_plate_code}' not found in the dataset.")
    
    # Shift plate geometry to 0-360 range using Shapely 2.0 array interface
    target_plate.geometry = shapely.transform(target_plate.geometry, shift_antimeridian_coords)
    
    # Assign CRS metadata as EPSG:4326 (coordinates are shifted but still in degree units)
    target_plate.set_crs(epsg=4326, inplace=True, allow_override=True)
    
    return target_plate


def load_plate_boundaries(boundaries_geojson_path: str, target_plate_code: str = 'PA') -> shapely.Geometry:
    """
    Loads PB2002_boundaries.json, isolates boundary segments involving the target plate,
    shifts longitudes to 0-360 range, and unions them into a single MultiLineString.
    
    Args:
        boundaries_geojson_path: Path to PB2002_boundaries.json
        target_plate_code: Plate code to filter (default 'PA' for Pacific)
    
    Returns:
        A unified Shapely geometry (MultiLineString) of all boundary segments
        for the target plate, in 0-360 shifted coordinates.
    """
    bounds_gdf = gpd.read_file(boundaries_geojson_path)
    
    # Filter boundary segments where PlateA OR PlateB equals the target code
    mask = (bounds_gdf['PlateA'] == target_plate_code) | (bounds_gdf['PlateB'] == target_plate_code)
    target_bounds = bounds_gdf[mask].copy()
    
    if target_bounds.empty:
        raise ValueError(f"No boundaries found for plate code '{target_plate_code}'.")
    
    # Shift boundary segment geometries to 0-360 range
    target_bounds.geometry = shapely.transform(target_bounds.geometry, shift_antimeridian_coords)
    
    # Union all segments into a single geometric object (MultiLineString)
    # unary_union replaces deprecated cascaded_union in Shapely 2.0
    merged_boundary = unary_union(target_bounds.geometry.values)
    
    return merged_boundary
