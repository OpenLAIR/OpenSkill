import pandas as pd
import numpy as np

def load_all_datasets(data_dir='/root/data/'):
    """Load all four CSV datasets from the data directory."""
    water_temp = pd.read_csv(f'{data_dir}water_temperature.csv')
    climate = pd.read_csv(f'{data_dir}climate.csv')
    land_cover = pd.read_csv(f'{data_dir}land_cover.csv')
    hydrology = pd.read_csv(f'{data_dir}hydrology.csv')
    return water_temp, climate, land_cover, hydrology

def merge_datasets(water_temp, climate, land_cover, hydrology):
    """Merge all datasets on the Year column into a single DataFrame."""
    merged = water_temp.copy()
    merged = merged.merge(climate, on='Year', how='inner')
    merged = merged.merge(land_cover, on='Year', how='inner')
    merged = merged.merge(hydrology, on='Year', how='inner')
    return merged

def get_feature_columns():
    """Return list of all predictor feature column names."""
    return [
        'Precip', 'AirTempLake', 'Shortwave', 'Longwave', 'WindSpeedLake',
        'DevelopedArea', 'AgricultureArea', 'Outflow', 'Inflow'
    ]

def get_feature_columns_by_category():
    """Return a dictionary mapping category names to their feature columns.
    
    Categories:
    - Heat: Thermodynamic forcing (air temperature, radiation)
    - Flow: Hydrological forcing (precipitation, inflow, outflow)
    - Wind: Mechanical forcing (wind speed)
    - Human: Anthropogenic forcing (land cover changes)
    """
    return {
        'Heat': ['AirTempLake', 'Shortwave', 'Longwave'],
        'Flow': ['Precip', 'Outflow', 'Inflow'],
        'Wind': ['WindSpeedLake'],
        'Human': ['DevelopedArea', 'AgricultureArea']
    }

def get_category_map():
    """Return a flat dictionary mapping each feature to its category."""
    categories = get_feature_columns_by_category()
    cat_map = {}
    for cat, features in categories.items():
        for feat in features:
            cat_map[feat] = cat
    return cat_map
