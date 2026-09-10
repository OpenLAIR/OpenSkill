import sys
import json
import math
import os
from itertools import combinations, permutations

sys.path.insert(0, '/app/environment/skills/evo-civ6-map-parser/scripts')
import utils as map_utils

sys.path.insert(0, '/app/environment/skills/evo-civ6-adjacency-rules/scripts')
import importlib
import utils as adj_utils
importlib.reload(adj_utils)

# Re-export needed functions
parse_civ6map = map_utils.parse_civ6map
get_hex_neighbors = map_utils.get_hex_neighbors
hex_distance = map_utils.hex_distance
is_land_tile = map_utils.is_land_tile
is_mountain = map_utils.is_mountain
get_land_tiles = map_utils.get_land_tiles

calculate_adjacency_bonus = adj_utils.calculate_adjacency_bonus
is_valid_district_placement = adj_utils.is_valid_district_placement
is_valid_city_center = adj_utils.is_valid_city_center
max_specialty_districts = adj_utils.max_specialty_districts
get_available_district_types = adj_utils.get_available_district_types
ADJACENCY_RECEIVING_DISTRICTS = adj_utils.ADJACENCY_RECEIVING_DISTRICTS

def load_scenario(scenario_path):
    """Load scenario JSON configuration."""
    with open(scenario_path, 'r') as f:
        return json.load(f)

def enumerate_city_center_candidates(map_data):
    """Find all valid city center locations (land, non-mountain)."""
    candidates = []
    for (x, y) in get_land_tiles(map_data):
        if is_valid_city_center(map_data, x, y):
            candidates.append((x, y))
    return candidates

def get_tiles_in_range(map_data, cx, cy, max_range=3):
    """Get all tiles within hex distance max_range of (cx, cy)."""
    tiles = []
    for (x, y) in map_data['tiles']:
        if hex_distance(x, y, cx, cy) <= max_range and (x, y) != (cx, cy):
            tiles.append((x, y))
    return tiles

def evaluate_placement(map_data, city_center, district_assignments, civ='GENERIC'):
    """Evaluate total adjacency bonus for a set of district placements."""
    placements = {city_center: 'CITY_CENTER'}
    for dtype, dx, dy in district_assignments:
        placements[(dx, dy)] = dtype
    
    adjacency_bonuses = {}
    total = 0
    for dtype, dx, dy in district_assignments:
        if dtype in ADJACENCY_RECEIVING_DISTRICTS:
            bonus = calculate_adjacency_bonus(map_data, dx, dy, dtype, placements, civ)
            adjacency_bonuses[dtype] = bonus
            total += bonus
    
    return {
        'adjacency_bonuses': adjacency_bonuses,
        'total_adjacency': total
    }

def find_optimal_placements(map_data, scenario):
    """Find optimal city center and district placements."""
    num_cities = scenario['num_cities']
    population = scenario['population']
    civ = scenario.get('civilization', 'GENERIC')
    max_districts = max_specialty_districts(population)
    
    cc_candidates = enumerate_city_center_candidates(map_data)
    if not cc_candidates:
        return None
    
    district_types = list(ADJACENCY_RECEIVING_DISTRICTS)
    
    best_solution = None
    best_total = -1
    
    for cc in cc_candidates:
        cx, cy = cc
        
        # Get valid placement tiles within range for any district
        valid_tiles_by_type = {}
        all_valid_tiles = set()
        for dtype in district_types:
            valid_for_type = []
            for (x, y) in get_tiles_in_range(map_data, cx, cy, 3):
                if is_valid_district_placement(map_data, x, y, dtype, cc, {cc}):
                    valid_for_type.append((x, y))
                    all_valid_tiles.add((x, y))
            valid_tiles_by_type[dtype] = valid_for_type
        
        valid_tiles = list(all_valid_tiles)
        
        if len(valid_tiles) < 1:
            continue
        
        n_to_place = min(max_districts, len(valid_tiles))
        
        # Try all combinations of tiles
        for tile_combo in combinations(valid_tiles, n_to_place):
            # Try different district type assignments
            for dtype_perm in permutations(district_types, n_to_place):
                assignments = []
                placed = {cc}
                valid = True
                for i, (tx, ty) in enumerate(tile_combo):
                    dtype = dtype_perm[i]
                    if not is_valid_district_placement(map_data, tx, ty, dtype, cc, placed):
                        valid = False
                        break
                    assignments.append((dtype, tx, ty))
                    placed.add((tx, ty))
                
                if not valid:
                    continue
                
                result = evaluate_placement(map_data, cc, assignments, civ)
                if result['total_adjacency'] > best_total:
                    best_total = result['total_adjacency']
                    best_solution = {
                        'city_center': list(cc),
                        'assignments': assignments,
                        'adjacency_bonuses': result['adjacency_bonuses'],
                        'total_adjacency': result['total_adjacency']
                    }
    
    return best_solution

def write_solution_json(solution, output_path, num_cities=1):
    """Write solution to JSON file in required format."""
    if num_cities == 1:
        output = {
            'city_center': solution['city_center'],
            'placements': {},
            'adjacency_bonuses': solution['adjacency_bonuses'],
            'total_adjacency': solution['total_adjacency']
        }
        for dtype, dx, dy in solution['assignments']:
            output['placements'][dtype] = [dx, dy]
    else:
        output = {
            'cities': [{'center': solution['city_center']}],
            'placements': {},
            'adjacency_bonuses': solution['adjacency_bonuses'],
            'total_adjacency': solution['total_adjacency']
        }
        for dtype, dx, dy in solution['assignments']:
            output['placements'][dtype] = [dx, dy]
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    return output
