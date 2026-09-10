# Architecting a Robust Python Utility Module for Data-Driven Travel Itinerary Planning Using Pandas 2.0.3

**Key Points:**
*   **Pandas 2.0.3 Paradigm Shifts:** The transition to Pandas 2.0.3 necessitates abandoning the deprecated `DataFrame.append()` method in favor of `pd.concat()`, while also offering experimental performance enhancements through PyArrow-backed string data types (`string[pyarrow]`).
*   **Benchmark Schemas:** Standardized travel planning datasets, such as those from the OSUNLP TravelPlanner benchmark, utilize specific schemas (e.g., `flights.csv` containing `origin_city` and `dep_station_code`, and accommodations utilizing a `Room rule` column for encoding pet policies).
*   **Algorithmic Routing Constraints:** Multi-city itinerary planning requires complex optimization, often leveraging distance matrices and Travelling Salesperson Problem (TSP) heuristics to minimize driving distances while strategically interleaving travel days with sightseeing days.
*   **Agentic Evaluation Challenges:** Research indicates that even frontier large language models (LLMs) struggle immensely with global constraint satisfaction in travel planning, achieving success rates of less than 1% on complex benchmarks, underscoring the critical need for deterministic, code-based programmatic guardrails.

**Systematic Information Retrieval and Processing**
The development of agentic travel planners fundamentally relies on the accuracy of the underlying data retrieval systems. Current research highlights that LLM agents frequently fail at long-horizon planning due to inadequate tool usage and an inability to maintain global constraint satisfaction (such as budget limits and scheduling conflicts) [cite: 1, 2]. Therefore, building a deterministic Python utility module using pandas acts as a critical programmatic sandbox, translating natural language constraints into rigorous, deterministic SQL-like operations over local CSV datasets.

**Addressing Pandas 2.0+ Nuances**
Pandas 2.0 represents a major evolutionary step in the Python data ecosystem. It introduces strict API changes—most notably the complete removal of the `append()` function [cite: 3, 4]—and ushers in memory-efficient data types via Apache Arrow [cite: 5, 6]. When querying millions of rows of travel data (flights, hotels, restaurants), adhering to Pandas 2.0.3 best practices ensures that the resulting planning module is both performant and resilient against runtime memory errors. 

---

## 1. Introduction: The Intersection of LLM Agents and Real-World Travel Planning

The domain of automated travel planning has historically been constrained by rigid, template-based systems that fail to account for the highly personalized and multi-faceted nature of real-world user preferences. The recent advent of large language models (LLMs) has catalyzed the development of "agentic" systems capable of natural language reasoning. However, as demonstrated by the TravelPlanner benchmark developed by the OSU NLP Group, current state-of-the-art models struggle significantly with complex travel tasks. For instance, GPT-4 achieved a mere 0.6% success rate when tasked with satisfying multi-day, multi-constraint travel queries [cite: 1, 2].

These failures primarily stem from an inability to manage **global constrained optimization**—such as ensuring a multi-day budget does not exceed a hard limit, or validating that transportation choices chronologically align with hotel check-ins [cite: 7]. To mitigate these LLM shortcomings, researchers advocate for combining neural reasoning with robust symbolic execution environments [cite: 8, 9]. 

This report provides a comprehensive architectural blueprint for constructing a deterministic Python utility module using `pandas==2.0.3`. This module is designed to query local CSV files and database exports (representing flights, accommodations, restaurants, and attractions) to facilitate the generation of mathematically valid, constraint-compliant travel itineraries. 

---

## 2. File Discovery Pattern and Schema Auto-Detection

Before a system can query travel data, it must systematically discover and catalog the available datasets. In a containerized application environment (e.g., `/app/data/`), files may be updated, replaced, or added dynamically. Hardcoding file paths and schemas leads to brittle architectures. Instead, developers should employ programmatic file discovery and schema auto-detection.

### 2.1 File Discovery Using `os` and `glob`
Python's standard library provides `os.listdir()` and `glob.glob()` for directory traversal. `glob` is generally preferred when specific file extensions (like `.csv`) need to be isolated recursively. 

### 2.2 Auto-Detecting Schemas with Pandas
Loading entire datasets into memory just to inspect their column names is computationally wasteful. Pandas provides the `nrows=0` parameter in `pd.read_csv()`, which reads only the header row, parsing the column names without loading any data into memory. 

### 2.3 Implementation Example
The following code demonstrates a robust `DataCatalog` class that discovers all CSVs in `/app/data/`, infers their schemas, and prepares them for subsequent querying:

```python
import os
import glob
import pandas as pd
from typing import Dict, List, Any

class TravelDataCatalog:
    def __init__(self, data_dir: str = '/app/data/'):
        self.data_dir = data_dir
        self.schemas: Dict[str, List[str]] = {}
        self.dataframes: Dict[str, pd.DataFrame] = {}
        self._discover_and_catalog()

    def _discover_and_catalog(self) -> None:
        """
        Scans the data directory for CSV files and extracts their schemas using nrows=0.
        """
        # Ensure directory exists
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")
            
        search_pattern = os.path.join(self.data_dir, '*.csv')
        csv_files = glob.glob(search_pattern)
        
        if not csv_files:
            print(f"Warning: No CSV files found in {self.data_dir}")
            
        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            table_name = os.path.splitext(file_name)
            
            try:
                # Efficient schema detection using nrows=0
                header_df = pd.read_csv(file_path, nrows=0)
                columns = header_df.columns.tolist()
                self.schemas[table_name] = columns
                print(f"Cataloged '{table_name}' with columns: {columns}")
            except Exception as e:
                print(f"Error cataloging {file_path}: {str(e)}")

    def load_table(self, table_name: str, **kwargs) -> pd.DataFrame:
        """
        Loads a specific table into memory dynamically upon request.
        """
        if table_name not in self.schemas:
            raise ValueError(f"Table '{table_name}' not found in catalog.")
            
        if table_name not in self.dataframes:
            file_path = os.path.join(self.data_dir, f"{table_name}.csv")
            # In Pandas 2.0, utilizing PyArrow backend can improve efficiency
            self.dataframes[table_name] = pd.read_csv(
                file_path, 
                engine='pyarrow', 
                dtype_backend='pyarrow',
                **kwargs
            )
            
        return self.dataframes[table_name]
```

This pattern ensures that the planning module is schema-aware at initialization, allowing LLM agents to accurately construct queries based on verified available columns.

---

## 3. Common Travel Planning Database Schemas

To write effective search utilities, one must understand the underlying data structures. The TravelPlanner benchmark, a standard in this domain, utilizes a highly curated sandbox environment containing nearly four million data records across diverse categories [cite: 1, 2]. Based on the benchmark's specifications [cite: 10], the expected database schemas are as follows:

### 3.1 `flights.csv`
Flight data is highly structured, requiring precise temporal and geographical identifiers.
*   **`origin_city`** (string): Origin city name [cite: 7, 10].
*   **`destination_city`** (string): Destination city name [cite: 7, 10].
*   **`dep_date`** (string): Departure date, format YYYY-MM-DD [cite: 7].
*   **`dep_station_code`** / **`dep_station_name`** (string): Departure airport IATA code and full name [cite: 7, 10].
*   **`arr_station_code`** / **`arr_station_name`** (string): Arrival airport IATA code and full name [cite: 7, 10].
*   **`dep_datetime`** / **`arr_datetime`** (string): Local datetimes for departure and arrival [cite: 7, 10].
*   **`seatClassName`** (string): Classification such as Economy/Business/First [cite: 10].
*   **`price`** (float): Total cost of the ticket per person.

### 3.2 `accommodations.csv` (or `hotels.csv`)
Accommodation schemas must capture location, pricing, and stringent property rules.
*   **`city`** (string): City where the hotel is located [cite: 2, 10].
*   **`name`** (string): Hotel name.
*   **`latitude`** / **`longitude`** (float): Geographic coordinates for distance matrix calculations [cite: 10].
*   **`hotelStar`** (string/int): Rating of the hotel (e.g., 1-5 stars) [cite: 10].
*   **`Room type`** (string): Categories like “Entire Room”, “Private Room”, or “Shared Room” [cite: 2].
*   **`Room rule`** (string): A comma-separated or text block outlining policies. Real-world restrictions include “No parties”, “No smoking”, “No children under 10”, and crucially, **“No pets”** [cite: 2]. 
*   **`price`** (float): Cost **per night**. Note that unlike flights (per ticket) or meals (per person), hotels are fundamentally billed per night for the room capacity.

**Encoding Pet-Friendly Logic:** In datasets like TravelPlanner, "pet-friendly" is rarely encoded as a simple boolean (`is_pet_friendly: True`). Instead, it is typically inferred from the `Room rule` column [cite: 2]. A hotel is considered pet-friendly if the `Room rule` string does *not* contain "No pets". 

### 3.3 `restaurants.csv` and `attractions.csv`
*   **Restaurants:** `restaurant_name`, `city`, `cuisine_type` (often a comma-separated list like "Italian, Seafood"), `average_cost` (cost **per person per meal**), and `rating`.
*   **Attractions:** `attraction_name`, `city`, `duration_minutes` (recommended visit duration), `ticket_price` (cost **per person**), and `opening_hours` [cite: 10].

### 3.4 `googleDistanceMatrix.csv` (Routing and Transportation)
For determining driving feasibility between cities or intracity points of interest:
*   **`origin`** / **`destination`** (string): Coordinate pairs or city names.
*   **`distance_meters`** (int/float): Road distance.
*   **`duration_minutes`** (int/float): Driving time.
*   **`cost`** (float): Estimated fuel or toll costs [cite: 10].

---

## 4. Pandas CSV Data Loading and Querying Patterns

Pandas provides a multitude of ways to filter and slice data. For a travel planner utility, query performance, exact string matching (with case insensitivity), and multi-condition filtering are paramount.

### 4.1 Exact Function Signatures for Pandas Operations

*   **`pd.read_csv()`**: 
    `pd.read_csv(filepath_or_buffer, *, sep=',', delimiter=None, header='infer', names=None, index_col=None, usecols=None, engine=None, dtype=None, dtype_backend=None, nrows=None, ...)`
*   **`DataFrame.query()`**:
    `DataFrame.query(expr, *, inplace=False, **kwargs)`
    *Note: `expr` is a string evaluating to a boolean vector. It uses `numexpr` under the hood for performance.*
*   **`DataFrame.loc[]`**:
    `df.loc[row_indexer, column_indexer]`
    *Note: Primarily used for boolean masking based on series evaluations.*
*   **`Series.str.contains()`**:
    `Series.str.contains(pat, case=True, flags=0, na=None, regex=True)`
    *Note: Extremely useful for searching within comma-separated strings (like cuisines or room rules). Setting `na=False` is critical to prevent `ValueError` when masking.*

### 4.2 Filtering Rows by Multiple Criteria

When filtering, case sensitivity is a common pitfall. A user might search for "minneapolis", but the database contains "Minneapolis". Standardizing case or using case-insensitive search flags resolves this.

Here is a working code example demonstrating how to filter a consolidated dataset (or multiple datasets) using `loc` and boolean masking:

```python
import pandas as pd

def filter_accommodations(df: pd.DataFrame, 
                          city: str, 
                          max_budget_per_night: float, 
                          pet_friendly: bool = False,
                          room_type: str = None) -> pd.DataFrame:
    """
    Filters accommodations based on multiple criteria.
    """
    # 1. City Matching (Case-Insensitive Exact Match)
    # Using str.lower() on both sides ensures "Minneapolis" == "minneapolis"
    mask = df['city'].astype(str).str.lower() == city.lower()
    
    # 2. Budget Constraint
    mask = mask & (df['price'] <= max_budget_per_night)
    
    # 3. Room Type Constraint (if specified)
    if room_type:
        mask = mask & (df['Room type'].astype(str).str.lower() == room_type.lower())
        
    # 4. Pet Friendly Boolean Flag
    # In schemas like TravelPlanner, policies are in the 'Room rule' column.
    # If pet_friendly is True, we must EXCLUDE rows where rule contains "No pets".
    if pet_friendly:
        # Check if the column exists to avoid KeyErrors
        if 'Room rule' in df.columns:
            # na=False ensures that if 'Room rule' is NaN, it evaluates to False for the 
            # contains check. We invert (~) the check to exclude "No pets".
            contains_no_pets = df['Room rule'].str.contains('No pets', case=False, na=False)
            mask = mask & (~contains_no_pets)
        else:
            # Fallback if boolean column exists
            if 'is_pet_friendly' in df.columns:
                mask = mask & (df['is_pet_friendly'] == True)
                
    # Apply the mask using .loc
    filtered_df = df.loc[mask]
    
    return filtered_df

# Example usage of DataFrame.query() for restaurants
def search_restaurants_query(df: pd.DataFrame, city: str, cuisine: str, max_price: float) -> pd.DataFrame:
    """
    Demonstrates filtering using the .query() API.
    """
    # Sanitize inputs for query string interpolation
    city_lower = city.lower()
    cuisine_lower = cuisine.lower()
    
    # We cannot easily do case-insensitive substring search inside .query() without engine='python'
    # but we can filter numericals and exact matches easily.
    # For substring on cuisines, we create a temporary boolean mask first or use the str accessor within query.
    
    q_str = "city.str.lower() == @city_lower and price <= @max_price"
    temp_df = df.query(q_str)
    
    # Substring search for cuisine (e.g., matching "Italian" inside "Italian, Seafood")
    final_df = temp_df.loc[temp_df['cuisine_type'].str.contains(cuisine, case=False, na=False)]
    
    return final_df
```

---

## 5. Reusable Skill Function Patterns for Search Utilities

To empower an LLM to generate an itinerary, we must provide it with highly structured, error-resilient "skill functions" (or tools). These functions wrap the Pandas logic, handle missing data gracefully, and return standardized JSON-serializable dictionaries.

### 5.1 Principles of Skill Functions
1.  **Error Handling:** Always catch `KeyError` (missing columns) and `FileNotFoundError`.
2.  **Empty Results:** If a query yields no results, return a structured payload indicating zero matches rather than throwing an exception. This allows the LLM agent to backtrack and adjust its parameters [cite: 1, 2].
3.  **Type Coercion:** Ensure that Pandas specific types (like `np.int64` or `pd.Timestamp`) are converted to native Python types (`int`, `str`) for JSON serialization.

### 5.2 Complete Working Examples

```python
import pandas as pd
import numpy as np

class TravelSearchUtilities:
    def __init__(self, catalog: TravelDataCatalog):
        self.catalog = catalog

    def _format_result(self, df: pd.DataFrame) -> dict:
        """Helper to convert DataFrame to list of dicts, handling NaNs."""
        if df.empty:
            return {"status": "success", "count": 0, "data": []}
        
        # Replace NaNs with None for JSON compliance
        df = df.replace({np.nan: None})
        records = df.to_dict(orient='records')
        return {"status": "success", "count": len(records), "data": records}

    def _format_error(self, message: str) -> dict:
        return {"status": "error", "message": message, "data": []}

    def search_cities(self, state: str) -> dict:
        try:
            df = self.catalog.load_table('cities')
            if 'state' not in df.columns:
                return self._format_error("Column 'state' missing from cities dataset.")
            
            mask = df['state'].str.lower() == state.lower()
            return self._format_result(df.loc[mask])
        except Exception as e:
            return self._format_error(str(e))

    def search_accommodations(self, city: str, constraints: dict) -> dict:
        """
        Constraints dict can contain: 'max_price', 'pet_friendly', 'room_type'
        """
        try:
            df = self.catalog.load_table('accommodations')
            
            # Base city mask
            mask = df['city'].str.lower() == city.lower()
            
            # Budget
            if 'max_price' in constraints:
                mask &= (df['price'] <= constraints['max_price'])
                
            # Pet friendly
            if constraints.get('pet_friendly', False):
                if 'Room rule' in df.columns:
                    mask &= (~df['Room rule'].str.contains('No pets', case=False, na=False))
                    
            # Room type
            if 'room_type' in constraints:
                mask &= (df['Room type'].str.lower() == constraints['room_type'].lower())
                
            results = df.loc[mask]
            
            # Sort by price ascending as a helpful default heuristic
            if not results.empty and 'price' in results.columns:
                results = results.sort_values('price', ascending=True)
                
            return self._format_result(results)
        except Exception as e:
            return self._format_error(str(e))

    def search_transportation(self, origin: str, destination: str, date: str = None) -> dict:
        """
        Searches flights between two cities.
        """
        try:
            df = self.catalog.load_table('flights')
            
            mask = (df['origin_city'].str.lower() == origin.lower()) & \
                   (df['destination_city'].str.lower() == destination.lower())
                   
            if date:
                # Assuming date is passed in YYYY-MM-DD
                mask &= (df['dep_date'] == date)
                
            results = df.loc[mask]
            return self._format_result(results)
        except Exception as e:
            return self._format_error(str(e))
```

By structuring the outputs as `{"status": "success", "count": X, "data": [...] }`, the calling LLM can easily evaluate `if response['count'] == 0:` and formulate a secondary plan.

---

## 6. Budget Calculation Logic

Budget constraint satisfaction is categorized as a "Hard Constraint" in benchmark evaluations [cite: 2]. An itinerary fails entirely if it exceeds the specified total budget by even a single dollar.

### 6.1 The Cost Formula
The total trip cost is calculated using specific multipliers based on the nature of the expense:
*   **Transportation (Flights):** `Ticket Price × Number of Travelers`
*   **Transportation (Self-Driving):** `Distance Cost / Fuel Cost` (Usually an absolute value for the vehicle, not multiplied by passengers).
*   **Accommodations:** `Cost per Night × Number of Nights` (Assuming one room accommodates the travel party. If 2 travelers require 2 rooms based on constraints, multiply accordingly).
*   **Meals:** `Cost per Person per Meal × Number of Travelers × Number of Meals per Day (usually 3) × Number of Days`.
*   **Attractions:** `Ticket Price × Number of Travelers`.

### 6.2 Example: 7 Days, 2 Travelers, $5,100 Budget
To calculate this using pandas aggregations, one would typically aggregate the selected itinerary choices.

```python
def validate_itinerary_budget(selected_flights_df: pd.DataFrame, 
                              selected_hotels_df: pd.DataFrame, 
                              selected_meals_df: pd.DataFrame, 
                              travelers: int = 2, 
                              days: int = 7, 
                              budget: float = 5100.0) -> dict:
    
    # 1. Transportation Cost (Flights for round trip)
    # Summing the 'price' column of selected flights, multiplied by travelers
    flight_cost = selected_flights_df['price'].sum() * travelers if not selected_flights_df.empty else 0.0
    
    # 2. Accommodation Cost
    # Assuming the selected_hotels_df contains a row for each distinct hotel stay
    # and a 'nights' column representing the duration of that stay.
    if not selected_hotels_df.empty and 'nights' in selected_hotels_df.columns:
        hotel_cost = (selected_hotels_df['price'] * selected_hotels_df['nights']).sum()
    else:
        hotel_cost = selected_hotels_df['price'].sum() * (days - 1) if not selected_hotels_df.empty else 0.0

    # 3. Meals Cost
    # Assuming selected_meals_df contains 3 meals per day for 7 days (21 rows)
    meal_cost = selected_meals_df['average_cost'].sum() * travelers if not selected_meals_df.empty else 0.0
    
    total_cost = flight_cost + hotel_cost + meal_cost
    
    is_valid = total_cost <= budget
    
    return {
        "is_valid": is_valid,
        "total_cost": total_cost,
        "budget": budget,
        "remaining": budget - total_cost,
        "breakdown": {
            "flights": flight_cost,
            "hotels": hotel_cost,
            "meals": meal_cost
        }
    }
```
This deterministic verification acts as a hard programmatic safeguard against LLM arithmetic hallucinations [cite: 1, 7].

---

## 7. Route Planning Logic for Multi-City Itineraries

Multi-city routing fundamentally maps to the Travelling Salesperson Problem (TSP). In a scenario where a user starts in Minneapolis and must visit 3 Ohio cities (e.g., Cleveland, Columbus, Cincinnati) over 7 days, the system must establish an optimal visit order and intelligently allocate time.

### 7.1 Algorithmic Patterns for Optimal Visit Order
Given that the number of cities is small ($N=3$ destinations plus $1$ origin), exact algorithms like brute-force permutations or simple dynamic programming are computationally trivial and guarantee an optimal (shortest distance) route.

Utilizing the `googleDistanceMatrix.csv` [cite: 10], we can retrieve edge weights (distances or driving times).

```python
import itertools

def optimize_multi_city_route(origin: str, destinations: list, distance_df: pd.DataFrame) -> list:
    """
    Finds the route minimizing total driving distance starting from the origin and visiting all destinations.
    """
    def get_distance(city_a, city_b):
        # Look up distance in symmetric distance matrix
        mask = ((distance_df['origin'] == city_a) & (distance_df['destination'] == city_b)) | \
               ((distance_df['origin'] == city_b) & (distance_df['destination'] == city_a))
        res = distance_df.loc[mask, 'distance_meters']
        return res.values if not res.empty else float('inf')

    best_route = None
    min_distance = float('inf')
    
    # Generate all possible permutations of the 3 Ohio cities
    for perm in itertools.permutations(destinations):
        current_distance = 0
        current_city = origin
        
        for next_city in perm:
            current_distance += get_distance(current_city, next_city)
            current_city = next_city
            
        if current_distance < min_distance:
            min_distance = current_distance
            best_route = list(perm)
            
    return [origin] + best_route
```

### 7.2 Handling Travel Days vs. Sightseeing Days
Once the spatial order (e.g., Minneapolis -> Toledo -> Columbus -> Cincinnati) is established, temporal allocation must be processed. Common algorithmic patterns dictate:
1.  **Thresholding:** If driving time > 5 hours, designate the day primarily as a "Travel Day". Allocate 0 or 1 minor local attraction.
2.  **Even Distribution:** Subtract travel days from total days (7 days). If Minneapolis to Toledo takes 1 day, 6 days remain. Allocate 2 days per Ohio city.
3.  **Constraint Enforcement:** Ensure hotel checkout dates align precisely with the departure to the next city [cite: 2]. TravelPlanner hard constraints state that "changes in cities during the trip must be reasonable" and chronological [cite: 2].

---

## 8. Pitfalls and Edge Cases with Pandas 2.0.3

Pandas 2.0.3 introduces several major structural changes compared to the 1.x series that can cause silent bugs or hard crashes in legacy travel planning codebases.

### 8.1 The Removal of `DataFrame.append()`
The most pervasive error developers encounter when migrating to Pandas 2.x is `AttributeError: 'DataFrame' object has no attribute 'append'` [cite: 4, 11]. `DataFrame.append()` and `Series.append()` were deprecated in Pandas 1.4 and completely excised in Pandas 2.0 [cite: 3, 4, 12, 13].

*   **Legacy Pattern (Broken):**
    ```python
    # Raises AttributeError in 2.0.3
    itinerary_df = itinerary_df.append(new_hotel_row, ignore_index=True)
    ```
*   **Modern Pattern (Correct):**
    Use `pd.concat()` inside a list comprehension for efficiency [cite: 3, 11].
    ```python
    rows_to_add = [new_hotel_row, another_hotel_row]
    itinerary_df = pd.concat([itinerary_df, pd.DataFrame(rows_to_add)], ignore_index=True)
    ```
    *Note: Repeatedly concatenating inside a `for` loop is highly inefficient. Collect data in a standard Python list of dictionaries first, then concatenate or build the DataFrame once at the end [cite: 14].*

### 8.2 PyArrow String Dtype Handling
Pandas 2.0 introduces deep integration with Apache Arrow. Historically, pandas stored text as NumPy `object` types, which are memory-inefficient and prone to missing data (`NaN`) quirks. Pandas 2.0.3 permits specifying strings as `string[pyarrow]` [cite: 5, 15, 16].
*   **Benefit:** PyArrow strings consume up to 70% less memory and execute vectorized string operations much faster [cite: 5, 16]. 
*   **Pitfall:** The Arrow dtype `string[pyarrow]` handles `NA` differently than the traditional `np.nan`. When executing `df['Room rule'].str.contains('No pets', na=False)`, ensure your Pandas environment properly handles Arrow `NA` types, as it can occasionally return `pd.NA` rather than a standard boolean if `na=False` is omitted [cite: 15].

### 8.3 Handling NaN Values for Pet-Friendly Filtering
When searching the `Room rule` column for policies, many rows might lack a defined rule, resulting in a `NaN` value. 
*   If you apply `.str.contains('No pets')` to a `NaN` value, Pandas by default returns `NaN`, not `False`. 
*   If this resulting mask is passed to `.loc[]`, Pandas will throw a `ValueError: Cannot mask with non-boolean array containing NA / NaN values`.
*   **Solution:** Always use the `na=False` keyword argument: `.str.contains('No pets', case=False, na=False)` [cite: 2].

### 8.4 Case Sensitivity Quirks
As noted in Section 4.2, matching "Minneapolis" against "minneapolis" will fail on exact `==` matches. For robust utilities, always cast both the dataset column and the query variable to lowercase using `.str.lower()` during condition building.

---

## 9. JSON Output Generation in Python

The output of an AI agent's planning process must be serialized into a structured JSON file. In benchmark evaluation setups, strict schema compliance is demanded for the generated itinerary [cite: 17].

### 9.1 Ensuring Directory Existence
The file path `/app/output/itinerary.json` requires the `/app/output/` directory to exist. The standard pattern utilizes `os.makedirs(..., exist_ok=True)`.

### 9.2 Constructing the Nested Structure
A travel plan requires a hierarchical structure mapping the trip down to specific days and logged tool calls.

```python
import json
import os
from typing import List, Dict

def generate_itinerary_json(plan_days: List[Dict], tool_calls: List[Dict], output_path: str = '/app/output/itinerary.json'):
    """
    Constructs a nested JSON structure and writes it to disk.
    """
    # 1. Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    # 2. Build the nested dictionary
    final_output = {
        "metadata": {
            "status": "success",
            "total_days": len(plan_days)
        },
        "tool_called": tool_calls,
        "plan": plan_days
    }
    
    # 3. Write to JSON
    # ensure_ascii=False supports international characters.
    # indent=4 provides human-readable pretty-printing.
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=4)
        print(f"Itinerary successfully written to {output_path}")
    except Exception as e:
        print(f"Failed to write JSON output: {str(e)}")

# Example Payload Structure Construction
mock_tool_calls = [
    {"tool": "search_cities", "params": {"state": "Ohio"}, "status": "success"},
    {"tool": "search_accommodations", "params": {"city": "Columbus", "pet_friendly": True}, "status": "success"}
]

mock_plan_days = [
    {
        "day": 1,
        "current_city": "Minneapolis",
        "transportation": {"mode": "drive", "destination": "Columbus", "distance_miles": 750},
        "accommodation": {"name": "Pet Friendly Inn Columbus", "price_per_night": 120.0},
        "meals": [
            {"type": "breakfast", "restaurant": "Minneapolis Diner", "cost": 15.0},
            {"type": "dinner", "restaurant": "Columbus Steakhouse", "cost": 45.0}
        ],
        "attractions": []
    }
]

# generate_itinerary_json(mock_plan_days, mock_tool_calls)
```

This strict JSON hierarchy allows downstream evaluation scripts (like those used in the TravelPlanner benchmark) to parse and verify constraints (e.g., verifying that the breakfast location matches the `current_city` of the morning) [cite: 2].

---

## 10. Conclusion

Architecting a Python utility module for querying travel databases demands a rigorous fusion of algorithmic routing, strict API adherence to Pandas 2.0.3, and robust defensive programming against missing or malformed data. By cataloging schemas dynamically, enforcing constraints via vectorized boolean masking, and utilizing exact mathematical verifications for budgets and TSP-based routing, developers can construct a robust programmatic foundation. This deterministic sandbox effectively bridges the gap between the probabilistic reasoning of language agents and the concrete, constraint-heavy reality of real-world travel planning, paving the way toward highly reliable, multi-modal automated itinerary generation.

**Sources:**
1. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMT0IJLzzrrxMuZKqIaEWpyNUGVzD1z3i4fr7RLSiqHBN88ICyQkW95z2PTY1tIbmzgU2P0OEqjZB2on76SOQd_1yjnO_pVfjQm54R7heWGWqWCYt09w==)
2. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnYkj2PLcAhwK2XbhJVP_UURrOIMP6b9fTRoby_yRE5953TL456xm9wemamfbp77Ij3naBT6I1_VUMKxIT6OfxQDmuHmTOhA3SZLkiKa10zAszU-wCttWZDA==)
3. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGyDEJHq8XyWswi2DHs27gQVUHqnM-zp-9if1loNd52ZX7S3cWmloITif717bqxSLppHWfFgN-fOX7CxE2EFfnf9mdbTDvy12ywgSPdU2Tz9hrRnuV6zQ56TqYM8XXBJvW7hqHw9bDJTodE3lGdqTXgmnJekcyJwcLoMA==)
4. [builtin.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSoYm_snsOaYDEAayzZYaLmuFRjLYzYDQp-cxQiuAujbJMcK3km4-GxjaGOCvFkIsIOdRjVm16Fn7Kja5VzQMyFN5oj5bnYSSYiHDxRNFPx0TidHIuEgQpjMj_IC15N56UnSs3k7yFv219CFjzsf9_vH-mOvprR9YqXiQMsoUb5i61KBjd0PEHvqA=)
5. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHAhICgxrMd22lj9DgMT-rhk18hikWtsaaC4KpTX-myUyYsMqdqq08UHXxYPFJchV-75RsIq53KsL6g5fqfh7Y_anM1fRTKbfZ9sbg4ZH7HoTg6nCXESeDh4k7tcCoRZw3EZ1QIfcg6gQBXXYRdjfKBZxhBJQ8YmzlN-ffZBP3zTEuXio_O6gtyHRY7DLrO_UvD9ounyqvGAiI=)
6. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjMurA5nLHelgj-yF6ZE3QQoSowb4rDIQm9immlir9K1HClKbUXKxr_Xctd53CYxL1youWcZ1et_yFsgVx6VuQXW8cS6jzffCvQm1-pkdP6cA6CZphpDnYyQgKtj_Cx8Jzl6HYtWh9sOhcaz7Sjoa8nqeJ31Z_uWEy4wA=)
7. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEHgejaQv0i9YqBLSk-OlS6WPtCLM-GLd4vvgY1vMiBF2r20EMnhMW1DZx4Zjj15MLc73JOGvLXrAOv60SSVEtnwmE47dtvEQDIRmCtYXqkypYzbrQUOg==)
8. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2pNlAyT3d3mFwCYhGFnPqUOmVfAwLrOO8xG4RTc5ASKOsl4k272P8ANwGjzyOfAE_UD2VBnV04_W9mBBvqL439w5LGKXOEVW-wgacaygfvttLkQ0J0GsyyQ==)
9. [iitd.ac.in](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3_ucfQuxP0AShrvji3bTwscBqD6pUTJXwJxeesRNmay1Pgt0J7vgmU6UR_0QQkMZB4LNRb0_5ZFxF49ZdTMjuVEZy-5Fl34lEdsfM64D36gQ0iaeMc2tOvZKjr9BnZAy5xMo_orXfBkiT-7WNip7SXK4W)
10. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpgpErs8r1B4YY3GrS_VU2HCvxqusekxUHR28jspbYqIRo8Oq2yemywHfGgMd34GmxqwF3yLXanC-xFseB4R4w-dP9xgyOQEwKxpXNbVxkoNaBk7-IQxwcDw==)
11. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHj5t91OZ2DiQrsDmYYlvkrSla-nOQAoqoeBa2x5NelueH2cLIlOb6ZC8_d386yuM6QCDIxA_0v3IenQp8ehWcGg_Bj_818Zioqf3hN7ecOqi_q7dlleE8u8qvdOns_K4KJxThIsvA2xijXvoDZToCmco0ZaAlTK4_91EP9J1T3fklHrV8dZ1SjGzMWvNlEQuYDUQinTg-6_6CTxw=)
12. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUZnxXCUVPU5IOniWvJgQasuhsgKxSBsup6a6bNujHRbOcZigfL4ki8HqbucHBk1KICW94jU-dnwfeaGmLH1ez5PgumY_poPLNBBMnVa3k8paNFyPDa2me6nxS9Az5lYYSC8Esnc2gKQwWjRs1)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnuQn95ZtX_aQ7k4F8u4ZLXWJD0ID-OAXQwkImhLb89VeW6BN3gF-LKFyMHBOQ_Q6ryRrMI4RAFeA85kEXsIn-_H3BVArrniciyCyEHoKYx1d8a1jLZi2aLemM6vnHLRihnEVIMGB8-rAZAQ==)
14. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGrwEK4E8FpTgMhpQSFX4PZ3j003kXa_BgACwo9fRrdlcfN6CbAW0-bDZ7WOrFWeqjV50LxLMiMyWKRY2tyU1ZvS0fZy3ZzmbtdYydyHX5-Ac4TL6OeV5lrG3WVwwjCUv-TnUCkZcF6QCTYskQl7oBIJZoF-WYlAphfH91H6YRMiNVtRhlz3Hs148qjhfCtAV8_CLT-QmjQLweCyqfGaae-gEPS7pjeSofhRzlK2yyu847vkZ8qvCg=)
15. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFnsUhIUdLU0ovjaqahXOb6nftYJjSp504cd-7asJBsIOIgO84bkjH9ZU8XE5QEGhRbnlefBbdOUDqy_T1LrTfeItFzM9nSGfD_F1986kskhh6QVhE-pBPpgLcIqgN3vqv0ivJHtKlE4VQxc3TkqVNTsMgGEGADZ-upoPZ-fxuF)
16. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDt3ygp-dyZ8D9j_CctjuVcICymGdJgS6ngcaO86vdH8Keo07ncMKjv8Dwxxe-c4q-VAblbUiSWoSblrSV_LQAX1ZXGIfQXra0okkCm9V53i9YOtadsbwNEwpUx8YxL-E8G-U3Rqe1lo0ELK3_dNoi1G0v4Z8Z6dVVZahXOvsthSxWr58092sROzumDBEgCgM=)
17. [openreview.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJqlNVpaXjrvG-suW6TJH3-Rs5HOG5yTDhQfdVVeDOROHcpyRwKzB-t9qevdNTOb9EjCyI3qrHv1YNIAsJtLNUiYwCRO0REUf_BJe5x1a6IRyM4frQXPJKiXNipKGIFNlDC6ZcubvspPIJNpJl6UtUeqdBX0sRSVbXH6y1Hw==)
