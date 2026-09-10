import json
import os
import sys
import itertools

# Import search functions explicitly
sys.path.insert(0, '/app/environment/skills/evo-travel-data-search/scripts')
import importlib
_search = importlib.import_module('utils')

def optimize_route(origin, destinations):
    best_route = None
    min_dist = float('inf')
    for perm in itertools.permutations(destinations):
        total = 0
        curr = origin
        for nxt in perm:
            info = _search.search_distance(curr, nxt)
            d = info.get('distance')
            if d and isinstance(d, str):
                d = int(d.replace(',','').replace(' km','').strip())
            else:
                d = 999999
            total += d
            curr = nxt
        if total < min_dist:
            min_dist = total
            best_route = list(perm)
    return best_route

def allocate_days_to_cities(route):
    return [
        {'day':1,'city':route[0],'from':'Minneapolis','to':route[0]},
        {'day':2,'city':route[0],'from':None,'to':None},
        {'day':3,'city':route[1],'from':route[0],'to':route[1]},
        {'day':4,'city':route[1],'from':None,'to':None},
        {'day':5,'city':route[2],'from':route[1],'to':route[2]},
        {'day':6,'city':route[2],'from':None,'to':None},
        {'day':7,'city':route[2],'from':None,'to':None},
    ]

def build_daily_plan(allocation, cuisines):
    tool_called = {'search_cities'}
    cuisine_idx = 0
    used_rests = {}
    used_attrs = {}
    plan = []
    for di in allocation:
        day_num = di['day']
        city = di['city']
        tf, tt = di['from'], di['to']
        if city not in used_rests: used_rests[city] = set()
        if city not in used_attrs: used_attrs[city] = 0
        if tf and tt:
            transport = f"Self-driving: from {tf} to {tt}"
            current_city = f"from {tf} to {tt}"
            tool_called.add('search_transportation')
        else:
            transport = "-"
            current_city = city
        tool_called.add('search_restaurants')
        meals = []
        for i in range(3):
            c = cuisines[cuisine_idx % len(cuisines)]
            cuisine_idx += 1
            rests = _search.search_restaurants(city, cuisine=c)
            if rests.empty:
                rests = _search.search_restaurants(city)
            if not rests.empty:
                chosen = None
                for _, row in rests.iterrows():
                    if row['Name'] not in used_rests[city]:
                        chosen = row; break
                if chosen is None: chosen = rests.iloc[0]
                used_rests[city].add(chosen['Name'])
                meals.append(f"{chosen['Name']}, {city}")
            else:
                meals.append('-')
        tool_called.add('search_attractions')
        attr_df = _search.search_attractions(city)
        attr_names = []
        if not attr_df.empty:
            st = used_attrs[city]
            for j in range(2):
                idx = (st + j) % len(attr_df)
                attr_names.append(attr_df.iloc[idx]['Name'])
            used_attrs[city] = st + 2
        attraction_str = ';'.join(attr_names) + ';' if attr_names else '-'
        tool_called.add('search_accommodations')
        if day_num < 7:
            acc = _search.search_accommodations(city, pet_friendly=True)
            acc_name = acc.iloc[0]['NAME'] if not acc.empty else '-'
        else:
            acc_name = '-'
        plan.append({'day':day_num,'current_city':current_city,'transportation':transport,
            'breakfast':meals[0],'lunch':meals[1],'dinner':meals[2],
            'attraction':attraction_str,'accommodation':acc_name})
    return plan, sorted(list(tool_called))

def generate_itinerary_json(plan, tool_called, path='/app/output/itinerary.json'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {'plan': plan, 'tool_called': tool_called}
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    return path
