# Skill Creation Plan

**Task**: Build a 7-day travel itinerary JSON for 2 travelers from Minneapolis covering 3 Ohio cities, with pet-friendly accommodations, specific cuisine preferences, no flights, and $5,100 budget

**Rationale**: The task requires two distinct capabilities: (1) searching/querying CSV datasets for cities, accommodations, restaurants, attractions, and transportation data, and (2) assembling the queried data into a constraint-compliant itinerary and outputting valid JSON. These naturally separate into a data querying layer and an itinerary assembly layer.

**Number of skills**: 2

---

## Skill 1: evo-travel-data-search

**Description**: Provides utility functions to discover, load, and query travel planning CSV datasets (cities, accommodations, restaurants, attractions, distance matrix) with filtering support for constraints like pet-friendly, cuisine type, city, state, and budget.

**Responsibility**: All data discovery, CSV loading, schema detection, and filtered querying of travel datasets. Handles case-insensitive matching, pet-friendly filtering via Room rule column, cuisine substring matching, and distance/transportation lookups.

**Key functions**: `search_cities`, `search_accommodations`, `search_restaurants`, `search_attractions`, `search_transportation`, `search_distance`, `load_dataset`, `discover_datasets`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-travel-data-search/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-travel-itinerary-builder

**Description**: Assembles a complete 7-day travel itinerary by orchestrating search queries, optimizing multi-city routing, validating budget constraints, and generating the final JSON output file.

**Responsibility**: Route optimization across multiple cities, day-by-day itinerary construction, budget calculation and validation, temporal allocation of travel vs sightseeing days, and JSON output generation to /app/output/itinerary.json.

**Key functions**: `optimize_route`, `allocate_days_to_cities`, `validate_budget`, `build_daily_plan`, `generate_itinerary_json`

**Depends on**: evo-travel-data-search


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-travel-itinerary-builder/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
