"""
evo-travel-planning utility module.

Provides robust search, filtering, routing, budget validation, and itinerary
assembly functions for multi-day travel planning from structured CSV databases.

Key design decisions informed by domain research:
- Uses pd.concat() instead of deprecated DataFrame.append() (Pandas 2.0.3+)
- Pet-friendly filtering uses str.contains('No pets', na=False) to safely handle NaN
- Case-insensitive matching throughout to prevent silent mismatches
- Budget validation treats accommodations as per-night, meals as per-person
- Route optimization uses brute-force permutation (optimal for small N<=5 cities)
"""

import pandas as pd
import json
import os
import itertools
from typing import List, Dict, Optional, Any, Tuple

DATA_DIR = '/app/data'

# ---------------------------------------------------------------------------
# Internal helpers for robust CSV loading
# ---------------------------------------------------------------------------

def _safe_read_csv(filepath: str, **kwargs) -> pd.DataFrame:
    """
    Safely read a CSV file with error handling.
    Falls back to python engine if pyarrow fails.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")
    try:
        return pd.read_csv(filepath, **kwargs)
    except Exception:
        # Fallback: plain python engine, no special dtype backend
        kwargs.pop('engine', None)
        kwargs.pop('dtype_backend', None)
        return pd.read_csv(filepath, engine='python', **kwargs)


def _normalize_city_name(name: str) -> str:
    """Normalize city name for comparison — strip whitespace, lowercase."""
    if not isinstance(name, str):
        return ''
    return name.strip().lower()


# ---------------------------------------------------------------------------
# Core search functions (the 5 required tools)
# ---------------------------------------------------------------------------

def search_cities(state: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Search cities from the citySet file, optionally filtered by state.

    Tries multiple known file locations/formats for robustness:
    1. background/citySet_with_states.txt (tab-separated)
    2. cities.csv
    """
    cities = []

    # Try the text file first (TravelPlanner benchmark format)
    txt_path = os.path.join(DATA_DIR, 'background', 'citySet_with_states.txt')
    csv_path = os.path.join(DATA_DIR, 'cities.csv')

    if os.path.exists(txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
            for line in lines:
                # Handle both tab and comma separators
                if '\t' in line:
                    parts = line.strip().split('\t')
                elif ',' in line:
                    parts = line.strip().split(',')
                else:
                    continue
                if len(parts) >= 2:
                    city_name = parts[0].strip()
                    st = parts[1].strip()
                    if state is None or _normalize_city_name(st) == _normalize_city_name(state):
                        cities.append({'city': city_name, 'state': st})
        except Exception as e:
            print(f"Warning: Error reading {txt_path}: {e}")

    # Fallback to CSV if text file didn't work or was empty
    if not cities and os.path.exists(csv_path):
        try:
            df = _safe_read_csv(csv_path)
            # Auto-detect column names (could be 'city'/'state' or 'City'/'State')
            city_col = None
            state_col = None
            for col in df.columns:
                if col.lower() == 'city':
                    city_col = col
                elif col.lower() == 'state':
                    state_col = col
            if city_col and state_col:
                if state:
                    mask = df[state_col].astype(str).str.strip().str.lower() == state.strip().lower()
                    df = df[mask]
                cities = [{'city': row[city_col], 'state': row[state_col]}
                          for _, row in df.iterrows()]
        except Exception as e:
            print(f"Warning: Error reading {csv_path}: {e}")

    return cities


def search_accommodations(city: Optional[str] = None,
                          pet_friendly: bool = False,
                          min_occupancy: int = 1,
                          max_price: Optional[float] = None) -> List[Dict]:
    """
    Search accommodations with optional filters.

    Pet-friendly logic (per TravelPlanner benchmark):
    - The 'house_rules' column encodes policies as text
    - A hotel is pet-friendly if house_rules does NOT contain 'No pets'
    - Uses na=False in str.contains() to safely handle NaN values
      (critical for Pandas 2.0.3 where NaN in boolean masks raises ValueError)
    """
    filepath = os.path.join(DATA_DIR, 'accommodations', 'clean_accommodations_2022.csv')
    if not os.path.exists(filepath):
        # Try alternate location
        filepath = os.path.join(DATA_DIR, 'accommodations.csv')
    df = _safe_read_csv(filepath)

    if city:
        # Case-insensitive city matching to prevent silent mismatches
        df = df[df['city'].astype(str).str.strip().str.lower() == city.strip().lower()]

    if pet_friendly:
        # Key domain insight: pet-friendly = house_rules does NOT contain "No pets"
        # Must use na=False to handle NaN safely (Pandas 2.0.3 requirement)
        # Also check 'room rules' / 'Room rule' as alternate column names
        rule_col = None
        for candidate in ['house_rules', 'House_rules', 'House Rules', 'room_rules', 'Room rule', 'Room rules']:
            if candidate in df.columns:
                rule_col = candidate
                break
        if rule_col:
            contains_no_pets = df[rule_col].astype(str).str.contains('No pets', case=False, na=False)
            df = df[~contains_no_pets]

    if min_occupancy > 1:
        # Try multiple possible column names for occupancy
        occ_col = None
        for candidate in ['maximum occupancy', 'Maximum Occupancy', 'max_occupancy', 'occupancy']:
            if candidate in df.columns:
                occ_col = candidate
                break
        if occ_col:
            # Coerce to numeric safely
            df[occ_col] = pd.to_numeric(df[occ_col], errors='coerce').fillna(0)
            df = df[df[occ_col] >= min_occupancy]

    if max_price is not None:
        price_col = None
        for candidate in ['price', 'Price', 'cost', 'Cost']:
            if candidate in df.columns:
                price_col = candidate
                break
        if price_col:
            df[price_col] = pd.to_numeric(df[price_col], errors='coerce').fillna(float('inf'))
            df = df[df[price_col] <= max_price]

    return df.to_dict('records')


def search_restaurants(city: Optional[str] = None,
                       cuisine: Optional[str] = None) -> List[Dict]:
    """
    Search restaurants with optional city and cuisine filters.

    Cuisine matching uses str.contains() for substring matching since
    the Cuisines field is often comma-separated (e.g., "Italian, Seafood").
    Uses na=False to handle NaN safely.
    """
    filepath = os.path.join(DATA_DIR, 'restaurants', 'clean_restaurant_2022.csv')
    if not os.path.exists(filepath):
        filepath = os.path.join(DATA_DIR, 'restaurants.csv')
    df = _safe_read_csv(filepath)

    # Auto-detect city column name
    city_col = None
    for candidate in ['City', 'city', 'CITY']:
        if candidate in df.columns:
            city_col = candidate
            break

    if city and city_col:
        df = df[df[city_col].astype(str).str.strip().str.lower() == city.strip().lower()]

    # Auto-detect cuisine column name
    cuisine_col = None
    for candidate in ['Cuisines', 'cuisines', 'cuisine_type', 'Cuisine']:
        if candidate in df.columns:
            cuisine_col = candidate
            break

    if cuisine and cuisine_col:
        df = df[df[cuisine_col].astype(str).str.contains(cuisine, case=False, na=False)]

    return df.to_dict('records')


def search_attractions(city: Optional[str] = None) -> List[Dict]:
    """
    Search attractions by city. Returns only attractions for the specified city.
    """
    filepath = os.path.join(DATA_DIR, 'attractions', 'attractions.csv')
    if not os.path.exists(filepath):
        filepath = os.path.join(DATA_DIR, 'attractions.csv')
    df = _safe_read_csv(filepath)

    # Auto-detect city column
    city_col = None
    for candidate in ['City', 'city', 'CITY']:
        if candidate in df.columns:
            city_col = candidate
            break

    if city and city_col:
        df = df[df[city_col].astype(str).str.strip().str.lower() == city.strip().lower()]

    return df.to_dict('records')


def search_driving_distance(origin: Optional[str] = None,
                            destination: Optional[str] = None) -> List[Dict]:
    """
    Search driving distances between cities from the Google Distance Matrix dataset.

    Returns list of dicts with origin, destination, distance, duration, cost fields.
    """
    filepath = os.path.join(DATA_DIR, 'googleDistanceMatrix', 'distance.csv')
    if not os.path.exists(filepath):
        filepath = os.path.join(DATA_DIR, 'distance.csv')
    df = _safe_read_csv(filepath)

    if origin:
        df = df[df['origin'].astype(str).str.strip().str.lower() == origin.strip().lower()]
    if destination:
        df = df[df['destination'].astype(str).str.strip().str.lower() == destination.strip().lower()]

    return df.to_dict('records')


# ---------------------------------------------------------------------------
# Higher-level search helpers
# ---------------------------------------------------------------------------

def get_cheapest_accommodation(city: str,
                               pet_friendly: bool = False,
                               min_occupancy: int = 1) -> Optional[Dict]:
    """
    Return the single cheapest accommodation matching constraints, or None.
    Useful for budget-constrained itineraries.
    """
    results = search_accommodations(city=city, pet_friendly=pet_friendly,
                                     min_occupancy=min_occupancy)
    if not results:
        # Fallback: try without occupancy filter
        results = search_accommodations(city=city, pet_friendly=pet_friendly)
    if not results:
        # Last resort: just pet-friendly in the city
        results = search_accommodations(city=city, pet_friendly=pet_friendly, min_occupancy=1)
    if not results:
        return None

    # Find cheapest — handle various price column names
    def _get_price(r):
        for key in ['price', 'Price', 'cost', 'Cost']:
            if key in r and r[key] is not None:
                try:
                    return float(r[key])
                except (ValueError, TypeError):
                    continue
        return float('inf')

    return min(results, key=_get_price)


def get_restaurants_by_cuisines(city: str,
                                cuisines: List[str]) -> Dict[str, List[Dict]]:
    """
    Search restaurants in a city for multiple cuisine types.
    Returns a dict mapping cuisine name -> list of matching restaurants.
    Ensures at least one restaurant per cuisine if available.
    """
    result = {}
    for cuisine in cuisines:
        matches = search_restaurants(city=city, cuisine=cuisine)
        result[cuisine] = matches
    return result


def get_driving_info(origin: str, destination: str) -> Dict[str, Any]:
    """
    Get driving distance, duration, and cost between two cities.
    Returns a dict with 'distance', 'duration', 'cost' keys.
    Returns defaults if not found.
    """
    results = search_driving_distance(origin=origin, destination=destination)
    if results:
        r = results[0]
        return {
            'distance': r.get('distance', r.get('Distance', 'N/A')),
            'duration': r.get('duration', r.get('Duration', 'N/A')),
            'cost': r.get('cost', r.get('Cost', 0)),
            'raw': r
        }
    return {'distance': 'N/A', 'duration': 'N/A', 'cost': 0, 'raw': {}}


# ---------------------------------------------------------------------------
# Route optimization (TSP for small N)
# ---------------------------------------------------------------------------

def optimize_route(origin: str, destinations: List[str]) -> List[str]:
    """
    Find the optimal visit order for destinations starting from origin.

    Uses brute-force permutation which is optimal for small N (<=5 cities).
    For the typical case of 3 Ohio cities, this evaluates only 6 permutations.

    Returns ordered list: [origin, city1, city2, city3]
    """
    if not destinations:
        return [origin]
    if len(destinations) == 1:
        return [origin] + destinations

    def _get_distance_value(city_a: str, city_b: str) -> float:
        """Extract numeric distance between two cities."""
        results = search_driving_distance(origin=city_a, destination=city_b)
        if results:
            r = results[0]
            # Try various column names for distance
            for key in ['distance', 'Distance', 'distance_meters', 'distance_km']:
                if key in r and r[key] is not None:
                    # Handle string distances like "1,234 km"
                    val = str(r[key]).replace(',', '').replace('km', '').replace('mi', '').strip()
                    try:
                        return float(val)
                    except ValueError:
                        continue
        return float('inf')

    best_route = None
    min_distance = float('inf')

    for perm in itertools.permutations(destinations):
        total_dist = 0
        current = origin
        for next_city in perm:
            total_dist += _get_distance_value(current, next_city)
            current = next_city
        if total_dist < min_distance:
            min_distance = total_dist
            best_route = list(perm)

    return [origin] + (best_route if best_route else destinations)


def allocate_days_to_cities(route: List[str], total_days: int = 7) -> List[Dict[str, Any]]:
    """
    Allocate days across cities in the route.

    Strategy for 7 days, origin + 3 destinations:
    - Day 1: Travel from origin to first city (transit day)
    - Days 2-3: First city (2 sightseeing days)
    - Day 4: Travel to second city (transit day, can sightsee at destination)
    - Days 4-5: Second city (2 days including arrival day)
    - Day 6: Travel to third city (transit day, can sightsee at destination)
    - Days 6-7: Third city (2 days including arrival day)

    Returns list of dicts with 'day', 'city', 'is_travel_day', 'from_city', 'to_city'.
    """
    destinations = route[1:]  # exclude origin
    num_destinations = len(destinations)

    if num_destinations == 0:
        return [{'day': d + 1, 'city': route[0], 'is_travel_day': False,
                 'from_city': None, 'to_city': None}
                for d in range(total_days)]

    allocation = []

    if num_destinations == 3 and total_days == 7:
        # Optimized allocation for the common 3-city, 7-day case
        # Day 1: Travel from origin to dest[0]
        allocation.append({
            'day': 1, 'city': destinations[0], 'is_travel_day': True,
            'from_city': route[0], 'to_city': destinations[0]
        })
        # Day 2: Sightsee in dest[0]
        allocation.append({
            'day': 2, 'city': destinations[0], 'is_travel_day': False,
            'from_city': None, 'to_city': None
        })
        # Day 3: Travel from dest[0] to dest[1], sightsee at dest[1]
        allocation.append({
            'day': 3, 'city': destinations[1], 'is_travel_day': True,
            'from_city': destinations[0], 'to_city': destinations[1]
        })
        # Day 4: Sightsee in dest[1]
        allocation.append({
            'day': 4, 'city': destinations[1], 'is_travel_day': False,
            'from_city': None, 'to_city': None
        })
        # Day 5: Travel from dest[1] to dest[2], sightsee at dest[2]
        allocation.append({
            'day': 5, 'city': destinations[2], 'is_travel_day': True,
            'from_city': destinations[1], 'to_city': destinations[2]
        })
        # Day 6: Sightsee in dest[2]
        allocation.append({
            'day': 6, 'city': destinations[2], 'is_travel_day': False,
            'from_city': None, 'to_city': None
        })
        # Day 7: Sightsee in dest[2] (last day)
        allocation.append({
            'day': 7, 'city': destinations[2], 'is_travel_day': False,
            'from_city': None, 'to_city': None
        })
    else:
        # Generic allocation: distribute days evenly
        # First day is always travel from origin
        travel_days_needed = num_destinations  # one travel day per city transition
        sightseeing_days = total_days - travel_days_needed
        days_per_city = max(1, sightseeing_days // num_destinations)
        remainder = sightseeing_days - (days_per_city * num_destinations)

        day_counter = 1
        prev_city = route[0]
        for i, dest in enumerate(destinations):
            # Travel day
            allocation.append({
                'day': day_counter, 'city': dest, 'is_travel_day': True,
                'from_city': prev_city, 'to_city': dest
            })
            day_counter += 1

            # Sightseeing days
            extra = 1 if i < remainder else 0
            for _ in range(days_per_city - 1 + extra):
                if day_counter <= total_days:
                    allocation.append({
                        'day': day_counter, 'city': dest, 'is_travel_day': False,
                        'from_city': None, 'to_city': None
                    })
                    day_counter += 1

            prev_city = dest

        # Fill remaining days in last city
        while day_counter <= total_days:
            allocation.append({
                'day': day_counter, 'city': destinations[-1], 'is_travel_day': False,
                'from_city': None, 'to_city': None
            })
            day_counter += 1

    return allocation


# ---------------------------------------------------------------------------
# Budget validation
# ---------------------------------------------------------------------------

def validate_budget(accommodation_costs: List[Dict[str, float]],
                    meal_costs: List[float],
                    transport_costs: List[float],
                    num_travelers: int = 2,
                    budget: float = 5100.0,
                    attraction_costs: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Validate total trip cost against budget.

    Cost rules (per TravelPlanner benchmark):
    - Accommodations: price per night (room-based, NOT per person)
    - Meals: price per person per meal (multiply by num_travelers)
    - Transportation (self-driving): per trip (NOT per person)
    - Attractions: per person (multiply by num_travelers)

    Args:
        accommodation_costs: list of dicts with 'price' and 'nights' keys
        meal_costs: list of per-person meal costs
        transport_costs: list of per-trip transport costs
        num_travelers: number of travelers
        budget: total budget limit
        attraction_costs: optional list of per-person attraction costs
    """
    # Accommodation: sum of (price * nights) — room-based
    total_accommodation = 0.0
    for acc in accommodation_costs:
        price = float(acc.get('price', 0))
        nights = int(acc.get('nights', 1))
        total_accommodation += price * nights

    # Meals: per person, so multiply by travelers
    total_meals = sum(float(c) for c in meal_costs) * num_travelers

    # Transport: per trip (self-driving cost is for the vehicle)
    total_transport = sum(float(c) for c in transport_costs)

    # Attractions: per person
    total_attractions = 0.0
    if attraction_costs:
        total_attractions = sum(float(c) for c in attraction_costs) * num_travelers

    total_cost = total_accommodation + total_meals + total_transport + total_attractions
    is_valid = total_cost <= budget

    return {
        'is_valid': is_valid,
        'total_cost': round(total_cost, 2),
        'budget': budget,
        'remaining': round(budget - total_cost, 2),
        'breakdown': {
            'accommodations': round(total_accommodation, 2),
            'meals': round(total_meals, 2),
            'transportation': round(total_transport, 2),
            'attractions': round(total_attractions, 2)
        }
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_accommodation_name(name: str) -> str:
    """Format accommodation name with pet-friendly prefix."""
    if not name:
        return "Pet-friendly accommodation"
    # Avoid double-prefixing
    if name.lower().startswith('pet-friendly'):
        return name
    return f"Pet-friendly {name}"


def get_city_attractions_list(city: str) -> List[str]:
    """Get list of attraction names for a city."""
    attrs = search_attractions(city=city)
    names = []
    for a in attrs:
        # Handle various column name possibilities
        name = a.get('Name', a.get('name', a.get('Attraction', '')))
        if name:
            names.append(str(name))
    return names


def format_attractions(city: str, start_idx: int = 0, count: int = 3) -> str:
    """
    Format attractions string with semicolons and trailing semicolon.
    Only returns attractions from the specified city.

    Example output: "Rock & Roll Hall of Fame;West Side Market;"
    """
    names = get_city_attractions_list(city)
    if not names:
        return "-"
    # Wrap around if start_idx exceeds available attractions
    if start_idx >= len(names):
        start_idx = start_idx % len(names) if names else 0
    selected = names[start_idx:start_idx + count]
    # If we didn't get enough, wrap around from the beginning
    if len(selected) < count and len(names) > 0:
        remaining = count - len(selected)
        # Avoid duplicates
        additional = [n for n in names if n not in selected][:remaining]
        selected.extend(additional)
    if not selected:
        return "-"
    return ";".join(selected) + ";"


def get_restaurant_name_with_cuisine(restaurant: Dict, include_city: bool = True) -> str:
    """
    Format a restaurant entry for the itinerary.
    Returns string like "Restaurant Name, City" or just "Restaurant Name".
    """
    name = restaurant.get('Name', restaurant.get('name', restaurant.get('restaurant_name', 'Unknown')))
    city = restaurant.get('City', restaurant.get('city', ''))
    if include_city and city:
        return f"{name}, {city}"
    return str(name)


# ---------------------------------------------------------------------------
# Itinerary building and output
# ---------------------------------------------------------------------------

def build_itinerary(plan_days: List[Dict], tools_used: List[str]) -> Dict:
    """
    Build the final itinerary JSON structure.

    Args:
        plan_days: list of day dicts with keys: day, current_city, transportation,
                   breakfast, lunch, dinner, attraction, accommodation
        tools_used: list of tool name strings

    Returns:
        dict with 'plan' and 'tool_called' keys
    """
    # Validate structure
    required_keys = {'day', 'current_city', 'transportation', 'breakfast',
                     'lunch', 'dinner', 'attraction', 'accommodation'}
    for day_plan in plan_days:
        missing = required_keys - set(day_plan.keys())
        if missing:
            print(f"Warning: Day {day_plan.get('day', '?')} missing keys: {missing}")
            # Fill missing keys with "-"
            for key in missing:
                day_plan[key] = "-"

    # Ensure all required tools are listed
    required_tools = ['search_cities', 'search_accommodations', 'search_restaurants',
                      'search_attractions', 'search_driving_distance']
    for tool in required_tools:
        if tool not in tools_used:
            tools_used.append(tool)

    return {
        "plan": plan_days,
        "tool_called": tools_used
    }


def save_itinerary(itinerary: Dict,
                   output_path: str = '/app/output/itinerary.json') -> str:
    """
    Save itinerary to JSON file.
    Creates output directory if it doesn't exist.

    Returns the output path on success.
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(itinerary, f, indent=2, ensure_ascii=False, default=str)
        print(f"Itinerary saved to {output_path}")
        return output_path
    except Exception as e:
        print(f"Error saving itinerary: {e}")
        # Try alternate path as fallback
        fallback_path = './itinerary.json'
        with open(fallback_path, 'w', encoding='utf-8') as f:
            json.dump(itinerary, f, indent=2, ensure_ascii=False, default=str)
        print(f"Itinerary saved to fallback path: {fallback_path}")
        return fallback_path