# Skill Creation Plan

**Task**: Find the earthquake furthest from the Pacific plate boundary within the Pacific plate using GeoPandas projections, and output results to JSON.

**Rationale**: This task involves three distinct concerns: (1) handling antimeridian-aware tectonic plate geometry loading and normalization, (2) earthquake data parsing and spatial filtering within the Pacific plate, and (3) projected distance computation and result formatting. However, these are tightly coupled in a single pipeline, so two skills suffice: one for antimeridian-safe geometry handling of plate data, and one for the full earthquake analysis pipeline.

**Number of skills**: 2

---

## Skill 1: evo-geospatial-antimeridian-plates

**Description**: Load and process PB2002 tectonic plate boundaries and polygons with antimeridian-safe coordinate normalization (0-360 longitude shift) using Shapely 2.0 transform and GeoPandas 1.0 APIs.

**Responsibility**: Load PB2002 plate polygon and boundary GeoJSON files, filter by plate code, normalize coordinates across the antimeridian to 0-360 range, and return properly prepared GeoDataFrames and unified boundary geometries.

**Key functions**: `shift_antimeridian_coords`, `load_plate_polygon`, `load_plate_boundaries`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-geospatial-antimeridian-plates/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-geospatial-earthquake-distance

**Description**: Parse USGS earthquake GeoJSON, spatially filter earthquakes within a tectonic plate, compute projected distances to plate boundaries using EPSG:3832, and output the furthest earthquake as formatted JSON.

**Responsibility**: Parse earthquake data, shift earthquake coordinates to 0-360 space, perform spatial join to filter earthquakes within the Pacific plate, reproject to EPSG:3832 for metric distance calculation, identify the earthquake with maximum distance from the plate boundary, format timestamps to ISO 8601, and serialize result to JSON.

**Key functions**: `parse_usgs_earthquakes`, `filter_earthquakes_within_plate`, `compute_boundary_distances`, `find_furthest_earthquake`, `format_and_export_result`

**Depends on**: evo-geospatial-antimeridian-plates


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-geospatial-earthquake-distance/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
