# Domain Reference for evo-civ6-placement-optimizer

**Responsibility**: Loading scenario configuration, enumerating candidate city center locations, enumerating valid district placement combinations within city working range (3 tiles), running optimization/search (brute force, greedy, or heuristic) to maximize total adjacency, handling multi-city scenarios, and writing the final output JSON in the required format.

**Key functions to implement**: load_scenario, find_optimal_placements, enumerate_city_center_candidates, enumerate_district_combinations, evaluate_placement, write_solution_json

---

## Part III: District Placement and Population Rules



## Part IV: Complete District Adjacency Bonus Rules


Adjacency bonuses are granted immediately upon district placement and scale based on surrounding geography. Bonuses are categorized into:
*   **Major Bonus:** +2 yield per tile.
*   **Standard Bonus:** +1 yield per tile.
*   **Minor Bonus:** +0.5 yield per tile (The game tallies all minor bonuses of the same type and applies a `floor()` function, rounding down. Thus, one adjacent district yields +0, while two yield +1) [cite: 28].

It is vital to note that Aqueducts, Dams, Canals, Neighborhoods, and the City Center all count as "Districts" for the purpose of the minor +0.5 adjacency bonus [cite: 7, 29].

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