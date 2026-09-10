# Domain Reference for evo-civ6-adjacency-rules

**Responsibility**: District placement validation (terrain restrictions, distance limits, resource blocking), population-to-district-slot calculation, complete adjacency bonus computation for all district types (Campus, Commercial Hub, Industrial Zone, Holy Site, Theater Square, Harbor, Aqueduct, etc.), civilization-specific overrides (Japan, Germany, Korea, Australia, Brazil, Netherlands, Mali), and minor bonus floor rounding.

**Key functions to implement**: is_valid_district_placement, max_specialty_districts, calculate_adjacency_bonus, get_available_district_types, is_specialty_district, apply_civ_modifiers

---

## Part III: District Placement and Population Rules



## Part IV: Complete District Adjacency Bonus Rules


Adjacency bonuses are granted immediately upon district placement and scale based on surrounding geography. Bonuses are categorized into:
*   **Major Bonus:** +2 yield per tile.
*   **Standard Bonus:** +1 yield per tile.
*   **Minor Bonus:** +0.5 yield per tile (The game tallies all minor bonuses of the same type and applies a `floor()` function, rounding down. Thus, one adjacent district yields +0, while two yield +1) [cite: 28].

It is vital to note that Aqueducts, Dams, Canals, Neighborhoods, and the City Center all count as "Districts" for the purpose of the minor +0.5 adjacency bonus [cite: 7, 29].

### 4.1 Base Districts (Gathering Storm Ruleset)



### 4.2 Unique Civilization Adjacency Modifiers


Civilization-specific unique abilities profoundly alter the mathematical landscape of district placement.

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