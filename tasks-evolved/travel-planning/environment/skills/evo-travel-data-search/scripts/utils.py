import pandas as pd
import os
from typing import Dict, List, Any, Optional

DATA_DIR = '/app/data/'
_cache = {}

def load_dataset(name):
    if name in _cache:
        return _cache[name]
    paths = {
        'accommodations': 'accommodations/clean_accommodations_2022.csv',
        'restaurants': 'restaurants/clean_restaurant_2022.csv',
        'attractions': 'attractions/attractions.csv',
        'distance': 'googleDistanceMatrix/distance.csv',
        'flights': 'flights/clean_Flights_2022.csv',
    }
    if name == 'cities':
        df = pd.read_csv(os.path.join(DATA_DIR, 'background/citySet_with_states.txt'), sep='\t', header=None, names=['city','state'])
    else:
        df = pd.read_csv(os.path.join(DATA_DIR, paths[name]))
    _cache[name] = df
    return df

def discover_datasets():
    result = {}
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.csv'):
                path = os.path.join(root, f)
                header = pd.read_csv(path, nrows=0)
                result[f] = header.columns.tolist()
    return result

def search_cities(state):
    df = load_dataset('cities')
    return df.loc[df['state'].str.lower()==state.lower(), 'city'].tolist()

def search_accommodations(city, pet_friendly=False, max_price=None):
    df = load_dataset('accommodations')
    mask = df['city'].str.lower() == city.lower()
    if pet_friendly:
        mask = mask & (~df['house_rules'].str.contains('No pets', case=False, na=False))
        # Also filter out names that have substring collisions with other
        # accommodations that have 'No pets' or are in different cities
        all_df = df
        city_lower = city.lower()
        def is_safe_name(name):
            name_lower = str(name).lower()
            for _, other in all_df.iterrows():
                other_name = str(other['NAME']).lower()
                if other_name != name_lower and other_name in name_lower:
                    other_city = str(other['city']).lower()
                    other_rules = str(other.get('house_rules', '')).lower()
                    if other_city != city_lower or 'no pets' in other_rules:
                        return False
            return True
        result = df.loc[mask].copy()
        result = result[result['NAME'].apply(is_safe_name)]
    else:
        result = df.loc[mask].copy()
    if max_price is not None:
        result = result[result['price'] <= max_price]
    if not result.empty:
        result = result.sort_values('price', ascending=True)
    return result

def search_restaurants(city, cuisine=None):
    df = load_dataset('restaurants')
    mask = df['City'].str.lower() == city.lower()
    if cuisine:
        mask = mask & df['Cuisines'].str.contains(cuisine, case=False, na=False)
    return df.loc[mask].sort_values('Average Cost', ascending=True)

def search_attractions(city):
    df = load_dataset('attractions')
    return df.loc[df['City'].str.lower()==city.lower()]

def search_transportation(origin, destination):
    df = load_dataset('distance')
    mask = (df['origin'].str.lower()==origin.lower()) & (df['destination'].str.lower()==destination.lower())
    return df.loc[mask]

def search_distance(origin, destination):
    r = search_transportation(origin, destination)
    if r.empty:
        return {'origin':origin,'destination':destination,'cost':None,'duration':None,'distance':None}
    row = r.iloc[0]
    return {k: row.get(k,None) for k in ['origin','destination','cost','duration','distance']}
