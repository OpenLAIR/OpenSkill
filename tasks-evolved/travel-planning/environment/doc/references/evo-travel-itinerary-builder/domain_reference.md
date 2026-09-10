# Domain Reference for evo-travel-itinerary-builder

**Responsibility**: Route optimization across multiple cities, day-by-day itinerary construction, budget calculation and validation, temporal allocation of travel vs sightseeing days, and JSON output generation to /app/output/itinerary.json.

**Key functions to implement**: optimize_route, allocate_days_to_cities, validate_budget, build_daily_plan, generate_itinerary_json

---

## 6. Budget Calculation Logic


Budget constraint satisfaction is categorized as a "Hard Constraint" in benchmark evaluations [cite: 2]. An itinerary fails entirely if it exceeds the specified total budget by even a single dollar.

## 7. Route Planning Logic for Multi-City Itineraries


Multi-city routing fundamentally maps to the Travelling Salesperson Problem (TSP). In a scenario where a user starts in Minneapolis and must visit 3 Ohio cities (e.g., Cleveland, Columbus, Cincinnati) over 7 days, the system must establish an optimal visit order and intelligently allocate time.

## 9. JSON Output Generation in Python


The output of an AI agent's planning process must be serialized into a structured JSON file. In benchmark evaluation setups, strict schema compliance is demanded for the generated itinerary [cite: 17].