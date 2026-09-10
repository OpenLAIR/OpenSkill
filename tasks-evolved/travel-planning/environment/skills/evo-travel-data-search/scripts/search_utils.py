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
    if max_price is not None:
        mask = mask & (df['price'] <= max_price)
    return df.loc[mask].sort_values('price', ascending=True)

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
