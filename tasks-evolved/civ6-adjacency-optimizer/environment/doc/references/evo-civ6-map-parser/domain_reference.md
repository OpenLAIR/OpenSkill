# Domain Reference for evo-civ6-map-parser

**Responsibility**: All SQLite I/O, map data extraction (Plots, PlotRivers, PlotFeatures, PlotResources, MapAttributes), coordinate system math (odd-r offset to cube and back), and neighbor computation. Does NOT compute game rules or adjacency bonuses.

**Key functions to implement**: parse_civ6map, get_map_dimensions, offset_to_cube, cube_to_offset, get_hex_neighbors, is_tile_river_adjacent, get_tile_terrain, get_tile_feature, get_tile_resource

---

## Part I: Hexagonal Grid Coordinate System in Civilization VI


To parse map files and compute adjacencies, one must first understand the topological framework of the game board.

## Part II: The `.Civ6Map` Binary File Format Specification


Contrary to some assumptions that the `.Civ6Map` file is a proprietary, compressed binary blob, it is actually a standard **SQLite 3 database** file [cite: 1, 17]. No custom decompression or binary unpacking tools (like `zlib` or `struct`) are required; the standard Python `sqlite3` library can query the map directly [cite: 18].

### 5.2 Hexagonal Coordinate Math (Offset to Cube)

To navigate the map flawlessly regardless of staggered rows, we convert the Odd-R offset coordinates into 3D Cube coordinates \((q, r, s)\).

```python
class Hex:
    def __init__(self, q, r, s):
        self.q = q
        self.r = r
        self.s = s
        assert round(q + r + s) == 0, "Cube coordinates must sum to 0"

    def get_neighbors(self):
        # The 6 directional vectors in cube coordinates
        directions = [
            Hex(1, -1, 0), Hex(1, 0, -1), Hex(0, 1, -1),
            Hex(-1, 1, 0), Hex(-1, 0, 1), Hex(0, -1, 1)
        ]
        return [Hex(self.q + d.q, self.r + d.r, self.s + d.s) for d in directions]

def offset_to_cube(col, row):
    # Odd-R offset to Cube conversion
    q = col - (row - (row & 1)) // 2
    r = row
    s = -q - r
    return Hex(q, r, s)

def cube_to_offset(hex_obj):
    # Cube to Odd-R offset conversion
    col = hex_obj.q + (hex_obj.r - (hex_obj.r & 1)) // 2
    row = hex_obj.r
    return col, row
```

### 5.3 Parsing the SQLite Database

This function reads the SQLite `.Civ6Map` database, extracting relevant tables to reconstruct the map matrix in memory.

```python
TileData = namedtuple('TileData', ['x', 'y', 'terrain', 'feature', 'resource', 'is_river'])

def parse_civ6map(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Extract map dimensions
    cursor.execute("SELECT Value FROM MapAttributes WHERE Name='MapWidth'")
    width = int(cursor.fetchone())
    cursor.execute("SELECT Value FROM MapAttributes WHERE Name='MapHeight'")
    height = int(cursor.fetchone())
    
    # Extract tile data
    # Assuming PlotFeatures and PlotResources might be separate or left joined
    query = """
    SELECT 
        p.X, p.Y, p.TerrainType, 
        f.FeatureType, 
        r.ResourceType 
    FROM Plots p
    LEFT JOIN PlotFeatures f ON p.ID = f.PlotID
    LEFT JOIN PlotResources r ON p.ID = r.PlotID
    """
    cursor.execute(query)
    raw_plots = cursor.fetchall()
    
    # Extract River Edges (Simplified: tagging the tile if it touches any river)
    cursor.execute("SELECT PlotID FROM PlotRivers")
    river_plot_ids = set([row for row in cursor.fetchall()])
    
    map_grid = {}
    for row in raw_plots:
        x, y, terrain, feature, resource = row
        plot_id = y * width + x
        is_river = plot_id in river_plot_ids
        # In a real rigorous parser, you must also check neighbors' opposing river edges
        
        map_grid[(x, y)] = TileData(x, y, terrain, feature, resource, is_river)
        
    conn.close()
    return width, height, map_grid
```