import sys
import math
sys.path.insert(0, '/app/environment/skills/evo-civ6-map-parser/scripts')
from utils import get_hex_neighbors, hex_distance, is_land_tile, is_mountain, is_tile_river_adjacent

# Specialty districts that count against population cap
SPECIALTY_DISTRICTS = {
    'CAMPUS', 'COMMERCIAL_HUB', 'INDUSTRIAL_ZONE', 'HOLY_SITE',
    'THEATER_SQUARE', 'HARBOR', 'ENCAMPMENT', 'AERODROME',
    'ENTERTAINMENT_COMPLEX', 'WATER_PARK'
}

# Non-specialty districts (don't count against pop cap)
NON_SPECIALTY_DISTRICTS = {
    'CITY_CENTER', 'AQUEDUCT', 'DAM', 'CANAL', 'NEIGHBORHOOD', 'SPACEPORT',
    'GOVERNMENT_PLAZA', 'DIPLOMATIC_QUARTER'
}

# Districts that receive adjacency bonuses
ADJACENCY_RECEIVING_DISTRICTS = {
    'CAMPUS', 'COMMERCIAL_HUB', 'INDUSTRIAL_ZONE', 'HOLY_SITE',
    'THEATER_SQUARE', 'HARBOR'
}

def max_specialty_districts(population):
    """Calculate max specialty districts from population.
    Formula: 1 + floor((pop - 1) / 3)
    Pop 1-3: 1, Pop 4-6: 2, Pop 7-9: 3, Pop 10-12: 4
    """
    return 1 + (population - 1) // 3

def is_specialty_district(district_type):
    """Check if a district type is a specialty district."""
    return district_type in SPECIALTY_DISTRICTS

def get_available_district_types():
    """Get list of placeable specialty district types."""
    return list(ADJACENCY_RECEIVING_DISTRICTS)

def is_valid_district_placement(map_data, x, y, district_type, city_center, placed_tiles):
    """Check if a district can be placed at (x, y).
    
    Args:
        map_data: parsed map data from parse_civ6map
        x, y: target tile coordinates
        district_type: e.g. 'CAMPUS', 'HARBOR'
        city_center: (cx, cy) tuple of city center location
        placed_tiles: set of (x, y) already occupied by city center or other districts
    
    Returns:
        bool
    """
    tiles = map_data['tiles']
    
    # Must be on map
    if (x, y) not in tiles:
        return False
    
    tile = tiles[(x, y)]
    
    # Can't overlap with existing placements
    if (x, y) in placed_tiles:
        return False
    
    # Distance check: must be within 3 tiles of city center, not on city center
    cx, cy = city_center
    dist = hex_distance(x, y, cx, cy)
    if dist == 0 or dist > 3:
        return False
    
    terrain = tile['terrain']
    feature = tile.get('feature')
    resource = tile.get('resource')
    
    # Harbor special case: must be on coast
    if district_type == 'HARBOR':
        if terrain != 'TERRAIN_COAST':
            return False
        # Harbor must be adjacent to city center's land
        # Actually harbor just needs to be on coast within range
        return True
    
    # All other districts: must be on land
    if terrain in ('TERRAIN_OCEAN', 'TERRAIN_COAST'):
        return False
    
    # Mountains are impassable - can't place districts
    if 'MOUNTAIN' in terrain:
        return False
    
    # Natural wonders block placement
    if feature and 'NATURAL_WONDER' in feature:
        return False
    
    # Resources block placement (strategic and luxury)
    if resource:
        return False
    
    return True

def is_valid_city_center(map_data, x, y):
    """Check if a city center can be placed at (x, y).
    City center must be on land, not mountain, not ocean/coast.
    """
    tiles = map_data['tiles']
    if (x, y) not in tiles:
        return False
    tile = tiles[(x, y)]
    terrain = tile['terrain']
    if terrain in ('TERRAIN_OCEAN', 'TERRAIN_COAST'):
        return False
    if 'MOUNTAIN' in terrain:
        return False
    return True

def calculate_adjacency_bonus(map_data, x, y, district_type, placements, civ='GENERIC'):
    """Calculate the adjacency bonus for a district at (x, y).
    
    Args:
        map_data: parsed map data
        x, y: district location
        district_type: e.g. 'CAMPUS', 'COMMERCIAL_HUB'
        placements: dict mapping (x,y) -> district_type_string for all placed districts/city center
                    e.g. {(5,3): 'CITY_CENTER', (6,3): 'CAMPUS', ...}
        civ: civilization string
    
    Returns:
        int: total adjacency bonus (after floor for minor bonuses)
    """
    tiles = map_data['tiles']
    neighbors = get_hex_neighbors(x, y)
    
    yield_total = 0
    minor_district_count = 0
    minor_rainforest_count = 0
    minor_woods_count = 0
    
    for nx, ny in neighbors:
        if (nx, ny) not in tiles:
            continue
        
        ntile = tiles[(nx, ny)]
        n_terrain = ntile['terrain']
        n_feature = ntile.get('feature')
        n_resource = ntile.get('resource')
        
        # Check if neighbor has a placed district
        neighbor_district = placements.get((nx, ny))
        
        if neighbor_district:
            # Government Plaza gives +1 standard to all adjacent specialty districts
            if neighbor_district == 'GOVERNMENT_PLAZA':
                yield_total += 1
            
            # Special major bonuses from specific district adjacencies
            if district_type == 'COMMERCIAL_HUB' and neighbor_district in ('HARBOR',):
                yield_total += 2
            elif district_type == 'HARBOR' and neighbor_district == 'CITY_CENTER':
                yield_total += 2
            elif district_type == 'INDUSTRIAL_ZONE' and neighbor_district in ('AQUEDUCT', 'DAM', 'CANAL'):
                yield_total += 2
            elif district_type == 'THEATER_SQUARE' and neighbor_district in ('ENTERTAINMENT_COMPLEX', 'WATER_PARK'):
                yield_total += 2
            
            # Minor district bonus (+0.5 per adjacent district)
            # Japan gets +1 instead of +0.5
            if civ == 'JAPAN':
                yield_total += 1
            else:
                minor_district_count += 1
        
        # Terrain/feature-based bonuses per district type
        if district_type == 'CAMPUS':
            if n_feature == 'FEATURE_GEOTHERMAL_FISSURE':
                yield_total += 2
            if n_feature == 'FEATURE_REEF':
                yield_total += 2
            if 'MOUNTAIN' in n_terrain:
                yield_total += 1
            if n_feature == 'FEATURE_JUNGLE':  # Rainforest
                if civ == 'BRAZIL':
                    yield_total += 1
                else:
                    minor_rainforest_count += 1
        
        elif district_type == 'HOLY_SITE':
            if n_feature and 'NATURAL_WONDER' in str(n_feature):
                yield_total += 2
            if 'MOUNTAIN' in n_terrain:
                yield_total += 1
            if n_feature == 'FEATURE_FOREST':
                minor_woods_count += 1
        
        elif district_type == 'INDUSTRIAL_ZONE':
            # Strategic resources give +1
            # Quarry gives +1 (improvement - not on map)
            # Mine gives +0.5 (improvement - not on map)
            pass
        
        elif district_type == 'THEATER_SQUARE':
            # World wonders give +2 (not on this map)
            pass
        
        elif district_type == 'HARBOR':
            # Coastal resources give +1
            if n_resource and n_terrain == 'TERRAIN_COAST':
                yield_total += 1
    
    # Commercial Hub river bonus: +2 if on a river (binary, not per-edge)
    if district_type == 'COMMERCIAL_HUB':
        if is_tile_river_adjacent(map_data, x, y):
            yield_total += 2
    
    # Netherlands: Campus, Theater Square, IZ get +2 if adjacent to river
    if civ == 'NETHERLANDS' and district_type in ('CAMPUS', 'THEATER_SQUARE', 'INDUSTRIAL_ZONE'):
        if is_tile_river_adjacent(map_data, x, y):
            yield_total += 2
    
    # Tally minor bonuses (floor of count * 0.5)
    yield_total += math.floor(minor_district_count * 0.5)
    yield_total += math.floor(minor_rainforest_count * 0.5)
    yield_total += math.floor(minor_woods_count * 0.5)
    
    return yield_total
