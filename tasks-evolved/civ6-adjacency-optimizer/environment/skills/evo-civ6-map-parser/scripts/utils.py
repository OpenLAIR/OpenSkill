import sqlite3
import math

def offset_to_cube(col, row):
    """Convert odd-r offset coordinates to cube coordinates (q, r, s)."""
    q = col - (row - (row & 1)) // 2
    r = row
    s = -q - r
    return (q, r, s)

def cube_to_offset(q, r, s):
    """Convert cube coordinates back to odd-r offset (col, row)."""
    col = q + (r - (r & 1)) // 2
    row = r
    return (col, row)

def hex_distance(x1, y1, x2, y2):
    """Calculate hex distance between two offset coordinates."""
    q1, r1, s1 = offset_to_cube(x1, y1)
    q2, r2, s2 = offset_to_cube(x2, y2)
    return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))

def get_hex_neighbors(x, y):
    """Get the 6 hex neighbors of tile (x, y) in odd-r offset coordinates."""
    q, r, s = offset_to_cube(x, y)
    directions = [
        (1, -1, 0), (1, 0, -1), (0, 1, -1),
        (-1, 1, 0), (-1, 0, 1), (0, -1, 1)
    ]
    neighbors = []
    for dq, dr, ds in directions:
        nq, nr, ns = q + dq, r + dr, s + ds
        nc, nrow = cube_to_offset(nq, nr, ns)
        neighbors.append((nc, nrow))
    return neighbors

def parse_civ6map(db_path):
    """Parse a .Civ6Map SQLite database and return map data.
    
    Returns:
        dict with keys:
            'width': int
            'height': int
            'tiles': dict mapping (x, y) -> tile_info dict
            'rivers': dict mapping plot_id -> river edge data
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get dimensions from Map table
    cursor.execute("SELECT Width, Height FROM Map LIMIT 1")
    row = cursor.fetchone()
    width, height = row[0], row[1]
    
    # Parse all plots
    cursor.execute("SELECT ID, TerrainType, ContinentType, IsImpassable FROM Plots ORDER BY ID")
    plots_raw = cursor.fetchall()
    
    # Parse features
    features = {}
    cursor.execute("SELECT ID, FeatureType FROM PlotFeatures")
    for r in cursor.fetchall():
        features[r[0]] = r[1]
    
    # Parse resources
    resources = {}
    try:
        cursor.execute("SELECT ID, ResourceType FROM PlotResources")
        for r in cursor.fetchall():
            resources[r[0]] = r[1]
    except:
        pass
    
    # Parse rivers
    rivers = {}
    try:
        cursor.execute("SELECT ID, IsNEOfRiver, IsWOfRiver, IsNWOfRiver FROM PlotRivers")
        for r in cursor.fetchall():
            rivers[r[0]] = {
                'IsNEOfRiver': bool(r[1]),
                'IsWOfRiver': bool(r[2]),
                'IsNWOfRiver': bool(r[3])
            }
    except:
        pass
    
    # Build tile dictionary
    tiles = {}
    for plot in plots_raw:
        plot_id, terrain, continent, is_impassable = plot
        x = plot_id % width
        y = plot_id // width
        
        tile = {
            'id': plot_id,
            'x': x,
            'y': y,
            'terrain': terrain,
            'continent': continent,
            'is_impassable': bool(is_impassable),
            'feature': features.get(plot_id, None),
            'resource': resources.get(plot_id, None),
        }
        tiles[(x, y)] = tile
    
    conn.close()
    return {
        'width': width,
        'height': height,
        'tiles': tiles,
        'rivers': rivers,
    }

def is_tile_river_adjacent(map_data, x, y):
    """Check if a tile at (x,y) is adjacent to a river.
    
    A tile is river-adjacent if:
    - It has any river edge in its own PlotRivers entry, OR
    - Any of its neighbors has a river edge facing this tile
    
    PlotRivers stores 3 edges per tile: NE, W, NW (the edges owned by this tile).
    The opposing edges are owned by neighbors:
    - E neighbor's W edge
    - SE neighbor's NW edge  
    - SW neighbor's NE edge
    """
    width = map_data['width']
    rivers = map_data['rivers']
    plot_id = y * width + x
    
    # Check own edges
    if plot_id in rivers:
        r = rivers[plot_id]
        if r['IsNEOfRiver'] or r['IsWOfRiver'] or r['IsNWOfRiver']:
            return True
    
    # Check neighbors' opposing edges
    neighbors = get_hex_neighbors(x, y)
    # In odd-r hex grid, neighbor indices from get_hex_neighbors:
    # 0: E, 1: SE, 2: SW, 3: W, 4: NW, 5: NE
    # Actually let me use the cube direction mapping:
    # directions = [(1,-1,0), (1,0,-1), (0,1,-1), (-1,1,0), (-1,0,1), (0,-1,1)]
    # For odd-r pointy-top:
    # dir 0 (1,-1,0) = NE
    # dir 1 (1,0,-1) = E  
    # dir 2 (0,1,-1) = SE
    # dir 3 (-1,1,0) = SW
    # dir 4 (-1,0,1) = W
    # dir 5 (0,-1,1) = NW
    
    # E neighbor (index 1) has W edge facing us
    nx, ny = neighbors[1]  # E neighbor
    e_id = ny * width + nx
    if e_id in rivers and rivers[e_id]['IsWOfRiver']:
        return True
    
    # SE neighbor (index 2) has NW edge facing us
    nx, ny = neighbors[2]  # SE neighbor
    se_id = ny * width + nx
    if se_id in rivers and rivers[se_id]['IsNWOfRiver']:
        return True
    
    # SW neighbor (index 3) has NE edge facing us
    nx, ny = neighbors[3]  # SW neighbor
    sw_id = ny * width + nx
    if sw_id in rivers and rivers[sw_id]['IsNEOfRiver']:
        return True
    
    return True if plot_id in rivers else False

def get_tile_terrain(map_data, x, y):
    """Get terrain type of tile."""
    tile = map_data['tiles'].get((x, y))
    return tile['terrain'] if tile else None

def get_tile_feature(map_data, x, y):
    """Get feature type of tile."""
    tile = map_data['tiles'].get((x, y))
    return tile['feature'] if tile else None

def get_tile_resource(map_data, x, y):
    """Get resource type of tile."""
    tile = map_data['tiles'].get((x, y))
    return tile['resource'] if tile else None

def is_land_tile(map_data, x, y):
    """Check if tile is a land tile (not ocean/coast)."""
    tile = map_data['tiles'].get((x, y))
    if not tile:
        return False
    terrain = tile['terrain']
    return terrain not in ('TERRAIN_OCEAN', 'TERRAIN_COAST')

def is_mountain(map_data, x, y):
    """Check if tile is a mountain."""
    tile = map_data['tiles'].get((x, y))
    if not tile:
        return False
    return 'MOUNTAIN' in tile['terrain']

def get_land_tiles(map_data):
    """Get all land tile coordinates."""
    result = []
    for (x, y), tile in map_data['tiles'].items():
        if is_land_tile(map_data, x, y):
            result.append((x, y))
    return result
