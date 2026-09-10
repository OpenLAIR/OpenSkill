# Domain Reference for evo-travel-data-search

**Responsibility**: All data discovery, CSV loading, schema detection, and filtered querying of travel datasets. Handles case-insensitive matching, pet-friendly filtering via Room rule column, cuisine substring matching, and distance/transportation lookups.

**Key functions to implement**: search_cities, search_accommodations, search_restaurants, search_attractions, search_transportation, search_distance, load_dataset, discover_datasets

---

## 2. File Discovery Pattern and Schema Auto-Detection


Before a system can query travel data, it must systematically discover and catalog the available datasets. In a containerized application environment (e.g., `/app/data/`), files may be updated, replaced, or added dynamically. Hardcoding file paths and schemas leads to brittle architectures. Instead, developers should employ programmatic file discovery and schema auto-detection.

## 3. Common Travel Planning Database Schemas


To write effective search utilities, one must understand the underlying data structures. The TravelPlanner benchmark, a standard in this domain, utilizes a highly curated sandbox environment containing nearly four million data records across diverse categories [cite: 1, 2]. Based on the benchmark's specifications [cite: 10], the expected database schemas are as follows:

## 4. Pandas CSV Data Loading and Querying Patterns


Pandas provides a multitude of ways to filter and slice data. For a travel planner utility, query performance, exact string matching (with case insensitivity), and multi-condition filtering are paramount.

## 5. Reusable Skill Function Patterns for Search Utilities


To empower an LLM to generate an itinerary, we must provide it with highly structured, error-resilient "skill functions" (or tools). These functions wrap the Pandas logic, handle missing data gracefully, and return standardized JSON-serializable dictionaries.

## 8. Pitfalls and Edge Cases with Pandas 2.0.3


Pandas 2.0.3 introduces several major structural changes compared to the 1.x series that can cause silent bugs or hard crashes in legacy travel planning codebases.