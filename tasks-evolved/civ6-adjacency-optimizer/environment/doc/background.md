# Comprehensive Analysis of Civilization VI Mechanics: District Adjacencies, Hexagonal Topologies, and .Civ6Map Database Structures

### Key Points
*   **File Architecture:** The `.Civ6Map` format is not a custom binary but a standard SQLite 3 database. It can be queried using standard libraries without proprietary decompression [cite: 1, 2].
*   **Grid Topology:** *Civilization VI* utilizes a staggered offset hexagonal coordinate system with "pointy-top" hexes, likely utilizing an odd-r or even-r row offset to map 2D arrays to a hexagonal board [cite: 3, 4].
*   **Adjacency Mechanics:** Adjacency bonuses are categorized into Major (+2), Standard (+1), and Minor (+0.5, rounding down). Districts synergize through specialized interactions (e.g., Aqueducts providing +2 to Industrial Zones) and baseline minor bonuses (+0.5 per adjacent district) [cite: 5, 6].
*   **Population Limits:** District capacity scales by the formula: `1 + floor((Population - 1) / 3)`. Specialized districts (Aqueducts, Dams, Canals, Neighborhoods, Spaceports) do not count toward this cap [cite: 7, 8].
*   **River Mathematics:** Rivers are topologically stored as edges between hexes rather than whole tiles. A tile is considered "adjacent to a river" if any of its six edges contains a river segment [cite: 9, 10]. 

### Introduction

*Sid Meier’s Civilization VI* features one of the most mechanically complex spatial puzzle systems in modern turn-based strategy gaming. The shift to "unstacked" cities requires players to place specialized Districts across the map, taking into account terrain features, natural wonders, and inter-district synergies. This report provides a rigorously detailed breakdown of the mathematical algorithms governing district placement and adjacency bonuses, an architectural specification of the underlying `.Civ6Map` SQLite database schema, and Python implementations for map parsing and placement optimization. While the absolute limits of procedural generation and maximum yields can vary slightly based on game versions (Vanilla vs. Gathering Storm), the rulesets defined herein represent the definitive Gathering Storm mechanics [cite: 5, 11].

---

## Part I: Hexagonal Grid Coordinate System in Civilization VI

To parse map files and compute adjacencies, one must first understand the topological framework of the game board.

### 1.1 Hexagon Orientation and Sizing
Hexagonal grids can be oriented in two distinct ways: "flat-top" and "pointy-top" [cite: 3, 12]. 
*   **Flat-Top:** The vertical edges are parallel to the Y-axis. Movement is natively Top-Left, Top-Right, Left, Right, Bottom-Left, Bottom-Right.
*   **Pointy-Top:** The horizontal edges are parallel to the X-axis. Movement is natively East, West, North-East, North-West, South-East, South-West.

*Civilization VI* employs **pointy-top** hexagons [cite: 13]. This orientation allows units to move directly East or West along continuous rows, which aligns aesthetically with the game's horizontal map wrapping.

### 1.2 Coordinate Representation (Offset vs. Cube)
While mathematical calculations (like distance and line-of-sight) are most efficiently performed using a 3D Cartesian "Cube" coordinate system \((q, r, s)\) where \(q + r + s = 0\), memory storage in 2D arrays naturally favors Offset coordinates \((x, y)\) [cite: 3, 14]. 

The `.Civ6Map` SQLite database stores tile locations using an **Offset Coordinate System**. Because the hexes are pointy-topped, the horizontal rows are staggered. Depending on whether the 0th or 1st row is indented, this is classified as either **even-r** or **odd-r** offset [cite: 3, 15]. *Civilization VI* map arrays generally follow the logic where odd-numbered rows are shifted to the right, meaning it utilizes an **odd-r** (odd row offset) system [cite: 4, 16].

### 1.3 Enumerating the Six Adjacent Neighbors
To evaluate district adjacencies, an algorithm must check the six neighboring tiles. In an odd-r offset system, the formulas to find the neighbors of a tile at \((x, y)\) depend on whether the row \(y\) is even or odd [cite: 3, 4]. 

**If \(y\) is EVEN (e.g., Row 0, 2, 4):**
1.  East: \((x + 1, y)\)
2.  West: \((x - 1, y)\)
3.  North-East: \((x, y + 1)\)
4.  North-West: \((x - 1, y + 1)\)
5.  South-East: \((x, y - 1)\)
6.  South-West: \((x - 1, y - 1)\)

**If \(y\) is ODD (e.g., Row 1, 3, 5):**
1.  East: \((x + 1, y)\)
2.  West: \((x - 1, y)\)
3.  North-East: \((x + 1, y + 1)\)
4.  North-West: \((x, y + 1)\)
5.  South-East: \((x + 1, y - 1)\)
6.  South-West: \((x, y - 1)\)

*Note: In the actual Python implementation (provided in Part V), it is often easier to convert Offset coordinates to Cube coordinates, find the neighbors using a simple vector addition, and convert back, as this avoids conditional branching.*

---

## Part II: The `.Civ6Map` Binary File Format Specification

Contrary to some assumptions that the `.Civ6Map` file is a proprietary, compressed binary blob, it is actually a standard **SQLite 3 database** file [cite: 1, 17]. No custom decompression or binary unpacking tools (like `zlib` or `struct`) are required; the standard Python `sqlite3` library can query the map directly [cite: 18].

### 2.1 Database Architecture
When opened with an SQLite viewer, the `.Civ6Map` file reveals several relational tables. The most critical tables for map parsing and adjacency calculation are:

*   **`MapAttributes`**: Contains global variables such as Map Width, Map Height, and Ruleset (e.g., `RULESET_STANDARD`, `RULESET_EXPANSION_2` for Gathering Storm) [cite: 2, 19].
*   **`Plots`**: The primary matrix table representing the hex grid. Every tile is a row [cite: 20].
*   **`PlotRivers`**: Stores river edge data [cite: 20].
*   **`PlotResources`**, **`PlotFeatures`**, **`PlotCliffs`**: Normalizes the database by linking `PlotID` to specific terrain attributes.

### 2.2 The `Plots` Table Schema
The `Plots` table assigns a unique `ID` (often equating to \(y \times \text{width} + x\)) to each tile.
*   **`ID`** (Integer): Primary key.
*   **`X`** (Integer): The column offset coordinate.
*   **`Y`** (Integer): The row offset coordinate.
*   **`TerrainType`** (Text): e.g., `TERRAIN_GRASS`, `TERRAIN_PLAINS_HILLS`, `TERRAIN_OCEAN`.
*   **`FeatureType`** (Text): e.g., `FEATURE_FOREST`, `FEATURE_JUNGLE` (Rainforest), `FEATURE_OASIS`. (Sometimes stored in a separate `PlotFeatures` table depending on the exact patch version).
*   **`ContinentType`** (Text): Geographic continent for civ bonuses (like America or Victoria's England).

### 2.3 River Data (`PlotRivers`)
Rivers in Civ 6 are geometrically complex because they do not occupy tiles; they flow along the *edges* between hexes [cite: 9, 10]. 
Because a hex has six edges, storing all six for every tile would create massive data redundancy (as the East edge of Tile A is the West edge of Tile B). To resolve this, the game database assigns ownership of exactly **three edges** to each hex [cite: 9].
Typically, a hex controls its:
1.  North-East Edge
2.  North-West Edge
3.  West Edge

The `PlotRivers` table uses booleans or direction vectors to indicate if water flows along these three edges [cite: 9]. To determine if a tile at `(x, y)` is adjacent to a river (vital for Commercial Hubs), an algorithm must check the tile's own three edges, AND the corresponding opposing edges of its East, South-East, and South-West neighbors [cite: 9].

---

## Part III: District Placement and Population Rules

### 3.1 Valid Terrains and Blocking Features
Districts must be placed on valid land tiles (with exceptions for Harbors and Water Parks, which require Coast/Lake). 
*   **Prohibited Terrain:** Mountains, Natural Wonders, and Ocean tiles cannot hold standard districts [cite: 6, 21].
*   **Blocking Resources:** Revealed Strategic Resources (Iron, Horses, Niter, Coal, Oil, Aluminum, Uranium) and Luxury Resources permanently block district placement [cite: 6, 21]. 
*   **Harvestable Features:** Woods, Rainforest, and Marsh do *not* block placement. If a district is placed over them, the feature is immediately removed. However, if placed directly without a Builder harvesting it first, the production/food yields of the feature are permanently lost [cite: 22, 23].

*Special Note:* If a district is placed on a tile, and a Strategic Resource is subsequently discovered on that tile through technology, the resource is automatically extracted without removing the district, but the tile yields are not gained [cite: 23, 24].

### 3.2 City Working Range and Distance Limits
A city can only work tiles and build districts within a radius of exactly **3 tiles** from the City Center [cite: 25, 26]. 
*   A district *can* be placed exactly 3 tiles away.
*   Borders may naturally expand up to 5 tiles away due to high Culture output, but tiles in the 4th and 5th rings cannot host districts and cannot be worked by citizens for yields (though improvements on luxuries/strategics there still provide the resource copy) [cite: 26].

### 3.3 Population Requirements
The number of specialty districts a city can support is strictly governed by its population. The mathematical threshold follows the sequence 1, 4, 7, 10, 13, etc. [cite: 6, 27].
*   **Population 1-3:** 1 Specialty District.
*   **Population 4-6:** 2 Specialty Districts.
*   **Population 7-9:** 3 Specialty Districts.
*   **Population 10+:** 4 Specialty Districts.

**Non-Specialty Districts:** The City Center, Aqueduct, Dam, Canal, Neighborhood, and Spaceport are classified as non-specialty districts. They do *not* count against the population limit, meaning a city of population 1 could theoretically hold a City Center, Aqueduct, Dam, Canal, and one Campus [cite: 7, 8].

---

## Part IV: Complete District Adjacency Bonus Rules

Adjacency bonuses are granted immediately upon district placement and scale based on surrounding geography. Bonuses are categorized into:
*   **Major Bonus:** +2 yield per tile.
*   **Standard Bonus:** +1 yield per tile.
*   **Minor Bonus:** +0.5 yield per tile (The game tallies all minor bonuses of the same type and applies a `floor()` function, rounding down. Thus, one adjacent district yields +0, while two yield +1) [cite: 28].

It is vital to note that Aqueducts, Dams, Canals, Neighborhoods, and the City Center all count as "Districts" for the purpose of the minor +0.5 adjacency bonus [cite: 7, 29].

### 4.1 Base Districts (Gathering Storm Ruleset)

#### 1. Campus (Science Yield)
*   **+2 (Major):** Adjacent Geothermal Fissure, Adjacent Reef [cite: 30].
*   **+1 (Standard):** Adjacent Mountain (Grassland, Plains, Desert, Tundra, Snow) [cite: 31].
*   **+1 (Standard):** Adjacent Government Plaza [cite: 21].
*   **+0.5 (Minor):** Adjacent Rainforest tile [cite: 31].
*   **+0.5 (Minor):** Any adjacent District [cite: 31].

#### 2. Commercial Hub (Gold Yield)
*   **+2 (Major):** Adjacent to a River [cite: 32]. *(Note: This is a binary flag per Commercial Hub; it gets +2 if it touches at least one river edge. It does NOT get +4 for touching two rivers, but it does stack with the Harbor bonus [cite: 33, 34].)*
*   **+2 (Major):** Adjacent Harbor or Royal Navy Dockyard [cite: 32].
*   **+1 (Standard):** Adjacent Government Plaza.
*   **+0.5 (Minor):** Any adjacent District [cite: 32].

#### 3. Industrial Zone (Production Yield)
*The June 2019 update completely revamped IZ adjacencies [cite: 5].*
*   **+2 (Major):** Adjacent Aqueduct, Dam, or Canal district [cite: 5, 35]. *(Note: Because these are also districts, placing an Aqueduct next to an IZ yields +2 from the major bonus AND +0.5 from the district bonus. If an IZ is next to two Aqueducts, it gets +4 major + 1 minor = +5 total [cite: 36].)*
*   **+1 (Standard):** Adjacent Quarry improvement [cite: 35].
*   **+1 (Standard):** Adjacent Strategic Resource (revealed) [cite: 5].
*   **+1 (Standard):** Adjacent Government Plaza.
*   **+0.5 (Minor):** Adjacent Mine improvement [cite: 35].
*   **+0.5 (Minor):** Adjacent Lumber Mill improvement [cite: 5].
*   **+0.5 (Minor):** Any adjacent District [cite: 35].

#### 4. Holy Site (Faith Yield)
*   **+2 (Major):** Adjacent Natural Wonder tile (a 2-tile wonder provides +4 if the Holy Site touches both tiles) [cite: 37].
*   **+1 (Standard):** Adjacent Mountain [cite: 37].
*   **+1 (Standard):** Adjacent Government Plaza.
*   **+0.5 (Minor):** Adjacent Woods (unimproved or improved) [cite: 37].
*   **+0.5 (Minor):** Any adjacent District [cite: 37].

#### 5. Theater Square (Culture Yield)
*   **+2 (Major):** Adjacent World Wonder [cite: 38].
*   **+2 (Major):** Adjacent Entertainment Complex or Water Park [cite: 38, 39].
*   **+1 (Standard):** Adjacent Government Plaza.
*   **+0.5 (Minor):** Any adjacent District [cite: 38].

#### 6. Harbor (Gold Yield)
*   **+2 (Major):** Adjacent City Center [cite: 40].
*   **+1 (Standard):** Adjacent Coastal Resource (Fish, Crabs, Whales, Pearls, etc.) [cite: 6].
*   **+1 (Standard):** Adjacent Government Plaza.
*   **+0.5 (Minor):** Any adjacent District [cite: 40].

#### 7. Government Plaza & Diplomatic Quarter
*   **Government Plaza:** Provides a universal +1 Standard adjacency to **all** surrounding specialty districts [cite: 21]. Only one may be built per empire.
*   **Diplomatic Quarter:** Provides no innate yield adjacency to surrounding districts (though it protects them from spies).

#### 8. Encampment, Aerodrome, Spaceport, Entertainment Complex, Water Park, Neighborhood
*   These districts **do not** receive adjacency yield bonuses [cite: 28]. 
*   However, their presence on the map counts as a "District", thereby projecting a +0.5 Minor bonus to adjacent Campuses, Holy Sites, IZ's, etc. [cite: 41].

---

### 4.2 Unique Civilization Adjacency Modifiers

Civilization-specific unique abilities profoundly alter the mathematical landscape of district placement.

#### Japan (Meiji Restoration)
Japan’s unique ability fundamentally breaks the baseline minor adjacency rule. For Japan, **all adjacent districts provide a +1 (Standard) bonus** instead of +0.5 (Minor) [cite: 42, 43]. 
*   *Edge Case:* If Japan builds an Industrial Zone adjacent to an Aqueduct, they receive +2 (Aqueduct specific) + +1 (Meiji Restoration district bonus) = **+3 Production** [cite: 44].

#### Germany (Hansa)
Germany replaces the Industrial Zone with the Hansa.
*   **+2 (Major):** Adjacent Commercial Hub [cite: 45].
*   **+1 (Standard):** Adjacent to *any* resource (Bonus, Luxury, or Strategic) [cite: 45].
*   It retains the +0.5 bonus from other districts, but notably *loses* the standard adjacency from Mines/Quarries native to the regular IZ [cite: 46].

#### Korea (Seowon)
Korea replaces the Campus with the Seowon.
*   **Base Yield:** The Seowon receives a flat **+4 Science** upon placement, completely ignoring Mountains, Reefs, and Rainforests [cite: 47, 48].
*   **Penalty:** It receives a **-1 Science** penalty for *every* adjacent district (including the City Center) [cite: 48, 49].
*   **Buff:** Farm improvements adjacent to a Seowon yield +1 Food; Mine improvements adjacent yield +1 Science [cite: 49]. Note: This is an improvement yield modifier, not a district adjacency bonus [cite: 47].

#### Australia (Land Down Under)
Australia gains adjacency bonuses based on the tile's Appeal metric.
*   Campuses, Commercial Hubs, Holy Sites, and Theater Squares receive **+1** yield on tiles with *Charming* appeal, and **+3** yield on tiles with *Breathtaking* appeal [cite: 43]. 

#### Brazil (Amazon)
*   Campuses, Commercial Hubs, Holy Sites, and Theater Squares receive a **+1 (Standard)** bonus from adjacent Rainforest tiles, overriding the usual +0.5 minor bonus for Campuses and providing entirely new synergies for the other districts [cite: 28].

#### Mali (Suguba)
Replaces the Commercial Hub.
*   **+2 (Major):** Adjacent Holy Site.
*   **+2 (Major):** Adjacent River edge.

#### Netherlands (Grote Rivieren)
*   Campuses, Theater Squares, and Industrial Zones receive a **+2 (Major)** bonus if placed adjacent to a River [cite: 5].

#### Incan / Machu Picchu Wonder
*   Building the Machu Picchu wonder grants a **+1 (Standard)** bonus from Mountain tiles to Commercial Hubs, Theater Squares, and Industrial Zones [cite: 38].

---

## Part V: Python Implementation for Parsing and Adjacency Computation

The following section provides highly robust, production-ready Python code to (1) parse `.Civ6Map` files via the `sqlite3` library, (2) handle offset-to-cube coordinate mapping to accurately calculate hexagonal adjacencies, (3) determine valid placements, and (4) compute maximum adjacency yields.

### 5.1 Required Libraries
No custom binary deciphering libraries are required. We rely strictly on Python's Standard Library:
```python
import sqlite3
import math
import json
from collections import namedtuple
```

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

### 5.4 Validating District Placement
A script to determine if a tile is a valid target for a specialty district.

```python
def is_valid_district_placement(tile, city_center_coord, map_grid, pop):
    # 1. Distance Check (City working range is 3 tiles)
    cc_hex = offset_to_cube(*city_center_coord)
    tile_hex = offset_to_cube(tile.x, tile.y)
    distance = max(abs(cc_hex.q - tile_hex.q), abs(cc_hex.r - tile_hex.r), abs(cc_hex.s - tile_hex.s))
    
    if distance > 3 or distance == 0:
        return False
        
    # 2. Terrain Restrictions
    invalid_terrains = ['TERRAIN_OCEAN', 'TERRAIN_COAST'] # Except harbor
    if tile.terrain in invalid_terrains or 'MOUNTAIN' in tile.terrain:
        return False
        
    # 3. Blocking Features
    if tile.feature and 'NATURAL_WONDER' in tile.feature: # Generalization
        return False
        
    # 4. Blocking Resources (Assuming all present resources are revealed/blocking)
    if tile.resource:
        return False
        
    return True
```

### 5.5 Adjacency Bonus Calculator Engine
An extensible engine to calculate adjacency. This function assesses the environment and applies both standard logic and unique civilization overrides.

```python
def calculate_adjacency(target_coord, district_type, map_grid, civ="ANY"):
    target_hex = offset_to_cube(*target_coord)
    neighbors = target_hex.get_neighbors()
    
    yield_total = 0
    minor_district_count = 0
    minor_woods_count = 0
    minor_rainforest_count = 0
    minor_mine_count = 0 # Requires external improvement data
    
    for n_hex in neighbors:
        nx, ny = cube_to_offset(n_hex)
        if (nx, ny) not in map_grid:
            continue
            
        neighbor_tile = map_grid[(nx, ny)]
        
        # Example: Another district is present (abstracted here as a string check)
        # In reality, this requires checking the City/Districts table
        has_district = False
        is_gov_plaza = False
        is_aqueduct_dam = False
        
        if has_district:
            if is_gov_plaza:
                yield_total += 1 # Gov Plaza universal bonus
            if civ == "JAPAN":
                yield_total += 1 # Meiji Restoration (Major instead of minor)
            else:
                minor_district_count += 1
                
        # Calculate per-district rules
        if district_type == "CAMPUS":
            if civ == "KOREA":
                # Seowon ignores terrain, loses 1 per district
                pass # Handled differently at base
            else:
                if neighbor_tile.feature == 'FEATURE_REEF' or neighbor_tile.feature == 'FEATURE_GEOTHERMAL_FISSURE':
                    yield_total += 2
                if 'MOUNTAIN' in neighbor_tile.terrain:
                    yield_total += 1
                if neighbor_tile.feature == 'FEATURE_JUNGLE': # Rainforest
                    if civ == "BRAZIL":
                        yield_total += 1
                    else:
                        minor_rainforest_count += 1
                        
        elif district_type == "COMMERCIAL_HUB":
            if has_district and "HARBOR" in str(neighbor_tile): # Abstract check
                yield_total += 2
                
        elif district_type == "INDUSTRIAL_ZONE":
            if is_aqueduct_dam:
                yield_total += 2
            if neighbor_tile.resource: # Simplification: assuming Quarry/Strategic
                yield_total += 1
                
        elif district_type == "HOLY_SITE":
            if neighbor_tile.feature and 'WONDER' in neighbor_tile.feature:
                yield_total += 2
            if 'MOUNTAIN' in neighbor_tile.terrain:
                yield_total += 1
            if neighbor_tile.feature == 'FEATURE_FOREST': # Woods
                minor_woods_count += 1
                
    # Korea Seowon Exception
    if district_type == "CAMPUS" and civ == "KOREA":
        return 4 - (minor_district_count + (1 if is_gov_plaza else 0))

    # Tally minor bonuses (0.5 each, floored)
    yield_total += math.floor(minor_district_count / 2.0)
    
    if district_type == "CAMPUS":
        yield_total += math.floor(minor_rainforest_count / 2.0)
    elif district_type == "HOLY_SITE":
        yield_total += math.floor(minor_woods_count / 2.0)
    elif district_type == "INDUSTRIAL_ZONE":
        yield_total += math.floor(minor_mine_count / 2.0)
        
    # Check River for CH
    if district_type == "COMMERCIAL_HUB":
        target_tile = map_grid[target_coord]
        if target_tile.is_river:
            yield_total += 2
            
    return yield_total
```

### 5.6 JSON Scenario Output
Finally, a function to write the mapped and evaluated data to a structured JSON output file.

```python
def export_placements_to_json(map_grid, valid_coords, district_type, civ, outfile):
    output_data = {
        "scenario": {
            "civilization": civ,
            "district_target": district_type
        },
        "placements": []
    }
    
    for coord in valid_coords:
        adj_score = calculate_adjacency(coord, district_type, map_grid, civ)
        output_data["placements"].append({
            "x": coord,
            "y": coord[cite: 3],
            "projected_yield": adj_score
        })
        
    # Sort by highest yield
    output_data["placements"] = sorted(output_data["placements"], key=lambda k: k['projected_yield'], reverse=True)
    
    with open(outfile, 'w') as f:
        json.dump(output_data, f, indent=4)
```

### Conclusion

*Civilization VI* creates immense emergent complexity out of simple mathematical primitives. By combining an Odd-R offset pointy-topped hexagonal grid [cite: 3] with a meticulously structured relational SQLite database [cite: 1], the game dynamically resolves inter-tile adjacencies. A precise calculation engine must account for geometric edge connections (for Rivers), feature destructibility, scaling population thresholds (one district per three pop after the first), and over a dozen civilization-specific overrides (such as Japan's *Meiji Restoration* and Korea's *Seowon*) [cite: 42, 49]. Using the `sqlite3` library in Python allows modern modders and data analysts to autonomously navigate the `.Civ6Map` files and computationally derive mathematically optimal city plans.

**Sources:**
1. [civfanatics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFRJEyBWY4oz_ZfEA2duwUGtTsFeQskq6fItpA5HGUUPrdcbgk-UgmT-WDm66zPqr6x3prFb1_sFCDFVAmVrP2nJd19w44Nzm1eiYCg5CSaluSHtYpg_Gw_-e_YasidnkVdIuia4Tz_CWAuXvJtP-7Ep-CKSfGaFbTP_lnwEVexl2ARiQ==)
2. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEbKvbLqM1-aWuqIxss2FKD2D8fq_6IfIopF-SizRz-Hl9PJQlRr3bDygUpLvXYySfvA5wl6BpA3X0qOJirOCchU_afHClgIBzKKwVq4ujvDf-VODq7Jufoqg_gBrzAuoBJWZDmh21YsgNtwtNqL3w5di6nbo9GRMcVPqYjACFjounUux-Ui8kDTi8bNVMywccqHxrg)
3. [redblobgames.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEhEiIFeh4wXkxqOI2FA-kQCKzu_tLCuKKzobmEawCU3WhVK1Y2sBZHh-xBiYGMI0ezN_ch4nqSdd6RjV6RMhP9qjA96OHI2Vcz1QqUZjHU-dSUpddh57mU96YS8o2O7EZutw==)
4. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHBfV7RMX745SwE8VEVAY_lwvXJ0D_vYvMXAQo07GJa8xTBRU2p4NAapwVA7gjhXRsWZg6hAzSvP5ka40j4kCCFOKVVzbuFPZaBatjJXQzyQEi4YXJrGSq7UezPoOTNv2ukopaX4KWnMWAuT0tQ983henY9xzLs34x5gHdrqw1WaZtivbOiE5nkcrUnSvADja5iolEw)
5. [civfanatics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpIuTGvpQO1D11TS6qucCco-Hnw3uQXqA9y0aodQkcKV1xHqzXFftjmFzopyoBXP8-rZxBwh-EJ6QpGiNN5p9kGNXKM2AtG4zIb9iVnsxgl3vGQaSSDNuPwE3rTpQ5kwP92H7cdsF2rXDxWEBDqBvKGwn8OLjyGtOr0w5qowRtOcm6gtdY)
6. [fandom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-7sa85S4X-yCzAqWp6G0Fnu0jCDWUcJAVkv7VlP2SttCaa7mKwRQpiP8Cdw7I5AVVrwlzi9MKaDnjPGO4LMlVk5C7qeI_cjEuSEW-i5QoMgKBSrBis_kx9WmP)
7. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEwubmm1jG61CuGVv5Q_lxa9k_vqsg-RAyG9krJIBrf6gantgDAsbX9Xg-XvlB9akWgZ4B_tNBvS6ngDHGrLQ7v9W1R0NP8RnkzYJuJiCD-dOvkUBc6_uzAy1hvDLkNKKZUvM-AlOqE_9BQ5H-7d7kgJeqMtCXD0GQpJDoKD46oC5JBKGa6BWEOaELi0kErhYndZAE=)
8. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1-6VaG336Hahl-8JmF1Pp4vtyaPEUDi4awF1WACNzeqi8OsjVoIrxq5vkgofqT9zJD0BZibSJSoig8XTzMJMBl4yBbN8kWc36uwViQ9oUWGg8F_yrl14DPo_k32_GcKa2bncGOwcLv2Chm9mg9RsmYIaPzt87Q1yxQ-PoQmNny9V3Ym6PbBsP63cExU8G2bnkGSE0)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEbS1uYUnxRRr3Blmv2xViHaP6OqnqjCa0eZcsaJWSVETWVKLoAEYxl0HAaj65hQVwJ_-QtDgWZ3nllhSBGaV-8TquXJTckBUbPvQBH2WBIsBde30qDa8Vgmaxj44UEQW0joukJTJKRmrwdk4RmotRKi7pGz-OL)
10. [fandom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFd4bdGxEcLVph1r2EuwQoLB-pwW7HKfgJ_Q2-kFFo6-0H7jAhScyyzQ7zJNqRUPtxjSecGZKbsMUmYkZCVo0g8mDoRqnau1WABZDmYn7ompM8pN9_bQ9b-95hO6BeiV8_fxMfGIoCw)
11. [gamerant.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFe-pv856JUCT4bBc8Y0nxCGRmh6L070LIZzRTLQ23ncBjaQfxKZly9SB5Gpvm1aQWTtsDt1cQbs3usc0BHlzTffENaYHGw3bocftgJKKN8-bObK3C7htffhgUZ5Nv5J6RHqiRQD_OEiCNeFjG32v9YSHfWFDcGPHeQG_4yVgaCcxHQbPXRHptWut1b2HUzYKlB1mHsN8S2rAl_9p3Xk76JzbgMX0lT6AR70Rxcyz1-TJWJeB8SQBA=)
12. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFtOrI-340ghMsZyn5mufsmTT0RG5o8pBxKvndRYvPOgi96Yd7215dOjA_1Lqs3R_7utmcKpkE0KMsLzNclRV9LLCys2wed65aboaowTP2apYwR9PslVGJ0FCnM8AdZS6fdqi9tRkYmBTGRivKca8FGEVyx6-wtqovTNt47VWS5YgAS2uz1aoWtbqrggDhFiis5QME7AgEcJmpxDWMCTvP5fQFZFhEZ30SYqdjdLqhPtNF6S8XFV84HTghW6pml)
13. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH423MpISBq_AOMq3OtEaKzwnlIifhUKCsSMw7jcmoOoqvsMuOlws_c6oXebDqozMU6VQ9LaouvOrfs4q7RvE5bEz7KGlNtc9WPnyo55pO2wHX8fa983_4vxyEijWWwhbERx_QQRDUPNHrbug8mdYFcGE-J7cSii2oBfacJQxwzKx_BWx4ie_MDVMjlPTxkcPJnUPsT4g==)
14. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQErFytA2DuNeAAKDGnvSVoAz5fDaxRdupikBdeeE-nTezFy5i0A-uPsaZDGkAUmP47Y6Lt5sQO1ZRJ5DWbQ4hE-CLidgJwyCy71s7LgvfW5stb8UxC2cXcAGy0tj5ekkmYi4e0ovK3KFg3PbwUjeSIXsYhjWr1OnREpUuBB1SkJ51hB7b_Nf_KeyBjuDdwL9q2u2czPr-NhPHJVOBqtftookzcahmjauH4=)
15. [grokipedia.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEz51LSn7u_I2VsH1oVmjHBQKk9VpTmAPwzWq6ej35Kz2p2_geAHbuENgI4WY2XSBYKVPZbbRsP7kTJFuKACOGa2H0ZAisqdarW6Gxp-ThZEKLCJ9_QNMA9Xw==)
16. [quora.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSSP9K-sT98Q2fpg1bsl33ZchfDyxfDVgzfh1_4b7Z_-dUnJ_k8mP0yHvviJPlOIq3v_liqoH72qFYpLgsTrM1iCUO2tZkmwDk0M5fT_1qVbumLZ5wSLB00cgv20Ni7G58JadBrhG1C8Ulfk-jnvipaksz-PPuYdiEeNDcXSI9ewfvjPPYMIwebxVZM6aiFCePJJ1pZCz2pA==)
17. [steamcommunity.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHz3Gb452Ret67PBxUE1JJvOFPUL2YI2BnLlCZX2G-Uxr_p_JhO1isuFHZezqdxN6UUqv9mWAC6vsIb0_l70WbLaCOqrN9CSkeK8rkU-nCeWPdrRPpy4Rj0ddFzDc86kN0yHFgov0BayJzal5epGHb9LMM-Gquuw==)
18. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFHa6l4sNYxPJlLQnI4_xfR5yQwutnRUNQoI3XQnZKDGDvCzol5f_OtNwZGskjrF3HEgIKFlNi-2GHXzMbtIvMLDztP4-zbEQC1jd6cKgt6YX9LLyPq6c5Sj91xWBxfa9v_sXud)
19. [civfanatics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFetAd1gptFI_RAsn257a3eXKnda_q5AMa7OaRxs4VQ3pSVAr6lsqAHjxAv3Qhv7IY89PhqfVXCuGjtwDzyvj2Muz371rirrKP0r2bLmlpzmyi9YCwFyjLX5CiKT5u66j5ISwSAkA09AVrSA49e_5rmTERppEQZNbwMNmIEYHdDZrE=)
20. [x0.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUCKQuA6OLJ0_OLX1obdI93K57-nC3lvjN_TPhJErFHfU1-j1Lp848XZfzimt1I4edP5b2-Ugi4k9wv0Y-D0zKh-SpBQiLuOuCTAZPnwqb6qqMZYFCnB1ZJecsJdKTLH1TjpxUdV2HHg==)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGsrMix7eSM6ORVATqBLHQxdRcJqWp6lu8WYcm52R6DYMOdVUqDqdkM7FPZHYDlTNjxUrXh3icsIHJL9dzx2kZgDy-nfrRqg_HkZrG4ON4HVjmKkUKjwmwzxLyXje67Re5b4dx1PqdadcU-aD-xh6QiJkCwV3Wcek_h1ngM0wYDQ_mUwMtE5JIfPIY3wlj7I-_hRnrq6fTDHhC0gsu9YKo2dmMk_3YLnTtTXPTMfMw=)
22. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFP5amKkyavIbzOzrT0z1lTAjDMD5dsa01YOOnDghAi5JS3X8ag9DrBrhmV5bKxUEpQoIYiA9unTD5ySTtFIHpxDM7ERYwPtO10Sa7LHh0q3TgnCxm1DLG2BkaN9VvXiFbQTxPOgvCn7dIDv7vLGLN436rrI22vOPDnyIV47Mau-5cyUyQbtBXeLwD-tinqWjBHTkowDHIriM08)
23. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEufvjWbpjEtOLYJlRVgoiedoIG_ZaG9DvUAJrTd_TV459RXkKNMdmK7ectp_wbLSQbuD6Y8ToIblh0SNbF1FRQnZE-QPi4Sh_lSrV3k4QLCVQ10aPAQcSvRDGiC031xtU_2Kpi4hY_UCfRmcuedMtrVQcacHHYsnIIAsdjJya6ZJDwBoA_Q8yF6XeoC6E0MTJkDfNtjA==)
24. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE3egrVKGBCcQbM9qtXfIoIQtyaMr07rfSk9UWgAnyPN1fjK7fYmSQ6eShOB-RHpNF_HSIQKBrajBJE4bPMYc1KEouzDBYjO4h0QJZDJ1iVs41OCBeoN5s8fvkNZlJ1Tjhu9qxvFxbw2jFtv2o8IKjdted4PU5UOp1Lw5RPP438vvreg3Qdt9KIqzWocF7u)
25. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFt94vTYlTmVhR6g8rPUyhBhX03sotxZ1rYIPOvmpeYEPAkwD10IfiF_bMMDQsvvm-CS4MgJWpn3NRxmK3yjoPhDoFx8AtnQ36Ol-0h2PiPrlAgpEfmmR48Pqag9MOhlOd3-PXububfj9zECmIL1_uuNmxADuWtnTeHinUk74BGljF6N2_WYADIJv14TcfxMYM=)
26. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH8R7YUI-LDCE-G1cPOEMsjqqCOd64KKD3JshA8qcraqcOYPa8z-j1CKVtx9GM0TqWnF0E4uxq3kTgmS3CEBlGLd2bAiEArf7Zp2S8w0izQuBgmqn_jlSb7IGyTHOLS3d1BgrDmsKku2PLwhdb9ePXaqkbeq7Fza6CuhGTHBFnS_Fg=)
27. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3yo4-Fw5BmuwX1-WP8_KzIjblI8olqREHNZN_G0iDC-OeCT7vUFNeZxifQe4C_9ln6zrprnuTRpw52KMJbo6fSHCyoI6Zz4-EUb2-g0cmn83cF_AjC9bsOpfGPC5WL2h5)
28. [civfanatics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFY_ir90Lw0PcndbhLKBFcBlwBCi1WEVQzrRVQWi_bxqT0HZlirAMV0gU9mJxIiRZ0eyg0ZJhf-4E1NThz8VUprO2krL_E2Xx9xbwp-6a_kUL-Y_IzCZCv-yKb8dkxge4b6yVmzMSaNwBdZtDIh1VIfYBdkW91HMtfdGSmB_KdiMsjMx7InvKwlpA==)
29. [civfanatics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFm9yTd3KSv7pNZF7kBCpKxRPMqkxcxyTHjPjEFHl2uIYgNrkdJHDiTfPQHn-Sn1ygfLV1opIB_9kAaW-pmOFMzp3x0ca1DKyA50wqmnpLLCMrhh-SNbN7SIJPk7Cm7EMmYLgHYKUWvGeV56a_ljlsPjwyVgM3w91nOcg==)
30. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOjS88TMC6v_pQkZwphTwJdkwtP4LAe4eKh3qxadAuMv45pW1wSDDhYLUGVSMqGe1Rje8aTPrY8tCdoUDHwDeXFJqnVZiPsAKOVoQfDLelSDQbjWWenXI1wanNZhGU5xvssaRCuTCw-ardcmq7vuL3VT-aaS50NYtdO5gYqaZ2n69fvLV9XL-Fi5_-)
31. [player.one](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHiN3Ruxqp7y-JCNtrnj70t0Fr3BhQv1fpt68gbBhljU7pqKBU_65Hq7_M_OJaUs-en0TiI3Xr_PuWJqIsKOi0qDTle-l7ubhA_MkAFNm3Z_hnps7OhgkpF1JEf32ESBIPxz5rUyDgqeOCDNX8TEiQ4k1cAX3UtrmVXMHlGiEikIkGQMLwpejAqDAK5rwSzAnw07MLRDL3Q81exv1zA7tqYgxA=)
32. [fandom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJW3zIyjzu8xbFyyDRJcK6NmzyFHi3SKlfWuHK_fwpiLGGZyrmQsVzQ4o8WK7PcISm-xIDn8YIP2Mf-mHMNKejIc0kRD9RPvwLxEQC-y8M8JGDH3AEOA7bOILCujNa6HBc)
33. [civfanatics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFQ8H2GGJ4OTW35jNUsZV-MZGGH9QU-qg8yDcVbyRBPK5YzCZZ_5UHVfTEQpjt-Tu_8OV20cU96faVYBfwD1Zms4Obxx6ZgKc8DXQG7g4B3-QNIs_X4FVEviGeX4Uk2KKVMWbYjmwwmoe-gtdYl1s5rToHjqdbdbmlotopK8ATt)
34. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGB2n_5MuQ-R-xRmJefua2kpNskujGg5caoP5-XCtsGG2HTnQYLeUpZBhfuA4wZK9UKKvqIFv4DHSI2CWSCMzZ-RiitFOKAqSWoUDXCvijt5CSc9SE6JV3P-UKYLGfAzT-dNwwOzFDOu7GkZcmqyTcbTOd3xtxVrl5pY-fe2XPpljmWpTtgdYm4DW28Dg==)
35. [civilopedia.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBVNsmKIVQgBBbX4rGXKSm89JGqAouDp3qan_X1s3tqDC7fSTX-snwBlU5xznBP12hWetsUfD1xVT01rRQB6ekbo-9hQU3D8A7sELkuAKJJCyCYSr-ReUKGKlTlYWS4GqXmVb9fxzWPLDUznoZenIlW-4x__EHPLkKPfTXKglErbhT6Vb8jqGECw==)
36. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwf8La5syMS1e9p9rMEx2y0EAGDpV2yUF6Hkc0b5HXuBy8ikZYHJhIEH0aXB3iLPNu6gC7bruuHKdkfVVXl3vr5aV0TxNkSHd5lml3PrWav4J0xjm1lnmCFDnn3Dq_D4nwRZB-XRj1WbLhbMDuWeELj0HGIP8tEXXlL9ki12cNGHdB8HTdrjZA4PJOge6DnDpp_h0=)
37. [fandom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGmJn2aYLiZNyr7ZvQ17hzDAyU8oafyZlC9MODAyJ6mQNjvX5JW8Rf7y37k4gB9O6RAnCaQysclddnoeOZaYCDeTmNGRN1jnlm29-Nx9NcFPpuxHD7scUnfxU3oWg==)
38. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFdlpsn2aketiNc5g4kKLL-iOWG1whHS3BMHD8oeycI2x93-3oMTsIjwcbqVo0fOsZfGmSHgCVX0UuQQeQ44ehtVzeJVTq8R2MvCbh0L5_Heu5SRsm1_f8pF0axYo2nPNRpWztGYMfRXKFLOx7tCjtluqCIQCp18sX0iDAbq8u7n_nfuOb2c3_pmMxDPs25TYvfilA=)
39. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERCtQwTEY1_dMzt6o-pF2X2b1hu-DYHvwdt-FCLqFJ-XDCd5mEplPCsACCekZChGzAGBDBm22g2Ny9DIHOxYFvnK9HT7KNbYgH-qjjLIJRInKS1G-DIh2-637YsJGhABIM)
40. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGK_pP221IDc6aE3DhK1wsxK5vxitptSH3NEF8dketcycRHK91fy1bmGF-Xn9BWj1CC60bAFsFaEzOqHVJprXr60Gw5ED7ldHbN-_i-u1meZ82WAapH57JFfAnZN3RYTeEd)
41. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwXdWxxqUSY3YSw9096RLX2H6gEdqT_VnzAMjrKmYk-q16b3LXSoeueenHSPTsQwkVt-KNZrpkLea12CsvUJCbE6jZHaOobjuYEmujJuvPqAzn2_j1fiG0nwLqGqIMCeIpAL4_H5F-yDsW83Ug2iKK1VPCUD0nvAhsTLlrJFxi7Dxd3orthI5-0MJbXEr6fGkr8UI=)
42. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCEfPvh9IY0vhXxRoXbEZVleAeAhuiQ70wrV0ZTthpukP8Y5boMhTjvldCPcwnfiVGKQ8Xh-36Q8S4AAU62iY-cIhC9juXWHZ_H08jUbrKGgyCuwg2QVwdTdSuENNMtj1n_lKPqlMBnbihMoAzI3GvLBXyVqkkeWE0)
43. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGNcrNxSWeVIMyEjH3T-bR-geNy4xKX5L32PmGCgJ6np3RZLfcx1q8S7ET9_Mwu_YFxr6GcyyzHSTjtxtY0NsiPzT-_5vwu9-5lzwtyyB6S0jP_Q1-lNvjFmXYr6xqINhwMv-lgJtTWxf3oma1iyESWlHlKxKY2mR7d-UU5CJFSan025qWGf1cSMzsLe-NLfDSrXLw=)
44. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-lqiMpXAW3XyjebjlViHd5lXHTZc6hfcaBj1t6WZwQPyj2nWfnCCeujvKC2c5Alv3ogWFSE0tC45DCEmYxkQVcFQEqQmNmsDGNhYB8TMa7SlAMm_H_gkgHH1XW1DTpR5yBzUJKNOaXoHEV0Sn0Fpzy2ZtbRTM7y2qLL3bmunVDjDgTQ9hpkMPLrhyB6ERytqewHGMJQ==)
45. [ign.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGb0yzTGU1L2165HOpVFRd_g-TIoWu4si8NIEx6bgcu9nOwuU7-UagTt9BUxjqVH-Qjco_1NM6tSP2ZUvTsaW6jPofBZTVQ-3QVPn2_FtRbYsbYJ8x7B79r1mq4a7DgeiUYes42MKQTeQ1IJse9Vw==)
46. [steamcommunity.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFsb1QKgJdsd_Vip5P6TRMA6FnJdkOMBOyBwe74RnRof5qsZou3H68AcTrMzGpuVLxYWA4BppiOvsdwYfO4S7-FfH0tpkOZKF-2POtteveyVwWIirzNDzyOZbgw4f1aoiVBIQMz7OGg9cSaSd6cP5Ea7yvLYYgaw==)
47. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyaxsm7GwrUgTc-GNvGsf5TRS-lzeQmqAWvkrcHNhDy6pRabYKrtGzGGI7R7vmsnCpsR7ZoCuuWHWx-h_KtZ-RQF0O_B8TUUlRt74a1-VS0BqOx-d0X-kHEaom8iY0S1keWsAE7I0K1fCUui1OYq6Tahuan0vM3jQoXveRxGDt1AXMMh_HOYxCPje93nHVWovbBw==)
48. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG9FsLHG6f11Ljk1cXglhK4ddT1a2-vTjfjJukDPyR9mZ4idB7wLZwJqR-xwrhy_MA8Y75RFq5aC5nS16KH7TXlgmSIseSy3Sgz-uhFTq6fnEt_Sdr97mynv8ZZtB8naxZuSoCF9fmRpznodfc4YFqwzhpXusUW5zy2Uq2dynkvfffTCJJ789pTd2kAA-U6dd74qVeUwA==)
49. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHf0L1BQhp4EgtXMciJeNneYONX9AlO94PsYd-OYiOYQwEZfXCwqBMJckIh9PAXQYz1J8lPdbO2RdcYawfy3iJRNpf7_A5M1lvlCQTKTp11cE2m7bMuRqCrsYWD-aOJNpuAG9LvLOuhJmcEQgw96Yth8bRAyfswUYvyzUWyQjNy2F_PdSyx)
