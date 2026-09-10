To verify the district adjacency bonus optimizer, you can use the following verification anchors and invariants derived from *Civilization VI* mechanics.

### 1. Independently Computable Reference Values
For a standard **Campus** district, the adjacency bonus is calculated as follows:
*   **+2** for each adjacent **Geothermal Fissure** or **Reef**.
*   **+1** for each adjacent **Mountain**.
*   **+0.5** for each adjacent **Rainforest** (rounded down, so +1 per 2 tiles).
*   **+0.5** for each adjacent **District** (including City Center, rounded down, so +1 per 2 tiles).

**Example Calculation:**
If a Campus is placed adjacent to 1 Mountain (+1), 1 Reef (+2), and 1 District (+0.5), the total is $1 + 2 + 0.5 = 3.5$. Per game rules, this rounds down to **+3**.

### 2. Dataset-Level Statistical Invariants
Your output JSON must satisfy these constraints to be considered valid:
*   **Summation Invariant:** The sum of all values in the `adjacency_bonuses` dictionary must exactly equal the `total_adjacency` field.
    *   `sum(adjacency_bonuses.values()) == total_adjacency`
*   **Placement Uniqueness:** No two districts (including City Centers) can occupy the same `[x, y]` coordinate.
*   **City Capacity Constraint:** The number of specialty districts (Campus, Industrial Zone, etc.) must not exceed the capacity allowed by the city's population: `1 + floor((Population - 1) / 3)`. Note: City Centers, Aqueducts, Dams, and Neighborhoods do not count toward this limit.
*   **Coordinate Validity:** All `[x, y]` placements must exist within the bounds of the provided `.Civ6Map` file.

### 3. Cross-Validation Approaches
To verify the optimizer's output without running the skill, you can use a simple Python script to re-calculate the adjacency based on the tile data:
1.  **Parse the Map:** Use `sqlite3` to query the `.Civ6Map` database for tile features (Mountains, Rivers, Reefs, etc.) at the coordinates provided in your output.
2.  **Adjacency Logic:** Implement a function that checks the six neighbors of a given hex using the **odd-r offset** coordinate system (as specified in the domain knowledge).
3.  **Assertion:**
    ```python
    def test_adjacency_calculation(output_json, map_data):
        for district, coords in output_json['placements'].items():
            expected = calculate_expected_bonus(district, coords, map_data)
            assert output_json['adjacency_bonuses'][district] == expected
    ```

### 4. Benchmarks and Reference Implementations
*   **Detailed Map Tacks (Mod):** This is the community-standard reference for visualizing and calculating adjacency bonuses in-game. Its logic is widely documented in the *Civ 6* modding community as the ground truth for UI-based adjacency calculations.
*   **Civilopedia:** The in-game Civilopedia (or the [Civilization Fandom Wiki](https://civilization.fandom.com/wiki/)) provides the definitive list of adjacency bonuses for every district type. Use these tables to hard-code the "major" (+2), "standard" (+1), and "minor" (+0.5) multipliers for your pytest assertions.