# Domain Reference for evo-geospatial-antimeridian-plates

**Responsibility**: Load PB2002 plate polygon and boundary GeoJSON files, filter by plate code, normalize coordinates across the antimeridian to 0-360 range, and return properly prepared GeoDataFrames and unified boundary geometries.

**Key functions to implement**: shift_antimeridian_coords, load_plate_polygon, load_plate_boundaries

---

### 1.1 The PB2002 Tectonic Plate Model

Peter Bird's 2002 global model (PB2002) is a foundational digital map of plate boundaries and tectonic zones [cite: 13]. Published to assist in kinematic and dynamic modeling of the lithosphere, it partitions the Earth into 52 plates. 

The dataset is typically consumed in GIS software and Python via derived GeoJSON files (`PB2002_plates.json` and `PB2002_boundaries.json`), which encode the geometries with structured metadata [cite: 14].
*   **Plates (Polygons):** The `PB2002_plates.json` file contains `Polygon` or `MultiPolygon` geometries representing the area of each tectonic plate. To isolate the Pacific Plate, the software must filter the GeoDataFrame for the exact string identifier `"PA"` under the `Code` column (or alternatively, `"Pacific"` under the `PlateName` column) [cite: 1]. 
*   **Boundaries (LineStrings):** The `PB2002_boundaries.json` file dictates the fault lines and spreading ridges separating these plates [cite: 13, 15]. The segments are defined as `LineString` geometries. Because any boundary separates two distinct plates, the properties dictionary utilizes `PlateA` and `PlateB` to denote the neighboring lithospheric blocks [cite: 2, 3]. Therefore, the full Pacific plate boundary is the union of all boundary segments where `PlateA == 'PA'` or `PlateB == 'PA'`.

### 2.1 Theoretical Implications of the Antimeridian

Standard geometries in WGS 84 (EPSG:4326) limit longitudes to the range $[-180, 180]$. When a single polygon—such as the Pacific Plate—crosses this boundary, coordinates wrap abruptly from $+179.9^\circ$ to $-179.9^\circ$ [cite: 8]. If these coordinates are indiscriminately ingested into a coordinate transformation algorithm without topology correction, the projection engine assumes the polygon stretches all the way backward across the entire globe [cite: 8]. The resulting projected geometry is effectively inverted, causing "inside-out" polygons or rendering extreme artifacts often colloquially described as "drying up the ocean" in cartographic rendering [cite: 7].

### 2.2 Coordinate Normalization to 0°–360°

To conduct planar operations on Pacific-centric geometries, longitudes must be normalized. Rather than splitting the plate into multipolygons at the dateline (which complicates distance calculations and boundary associations), the optimal technique shifts the spatial frame of reference to a continuous $0^\circ$ to $360^\circ$ domain [cite: 8, 18]. 

By systematically targeting all longitude ($x$) coordinates where $x < 0$ and applying the transformation $x' = x + 360$, the Pacific plate's geometry becomes a unified, unbroken polygon spanning roughly $110^\circ$ to $290^\circ$ [cite: 8, 19].

### 2.3 Pacific-Centric Projections (EPSG:3832)

Calculating true metric distances across continental scales requires moving from geodetic degrees (EPSG:4326) to a projected Cartesian coordinate system [cite: 11].

For the Pacific Ocean basin, **EPSG:3832** (WGS 84 / PDC Mercator) is the optimal standard. Developed by the Pacific Disaster Center, it is a Mercator projection uniquely modified with a central meridian at $150^\circ$ E [cite: 20, 21]. Because its domain explicitly covers the Pacific region (Australasia, Oceania, and the Pacific coasts of the Americas), it avoids the extreme distortion that plagues standard Web Mercator at dateline borders [cite: 20]. Reprojecting our normalized $0^\circ$--$360^\circ$ coordinates into EPSG:3832 yields high-fidelity planar distance metric outputs.

### 2.4 GeoDataFrame `set_crs` vs `to_crs`

A common source of error in GeoPandas involves the distinction between assigning and transforming coordinate reference systems:
*   **`GeoDataFrame.set_crs()`**: This method assigns metadata. It explicitly tells GeoPandas what projection the raw numerical data currently belongs to, without mathematically altering the $x$ and $y$ coordinate values [cite: 22]. 
*   **`GeoDataFrame.to_crs()`**: This method performs a rigorous mathematical reprojection. It takes the active coordinates and transforms them from the currently defined CRS into a new target CRS, physically altering the numerical values stored in the geometry array [cite: 7, 22].

For our methodology, we maintain the geometries as "shifted WGS 84" unprojected degrees, declare them with `set_crs("EPSG:4326", allow_override=True)`, and mathematically transform them to planar meters via `to_crs("EPSG:3832")`.

---

### 3.2 Vectorized GEOS ufuncs and the Array Interface

Shapely 2.0.6 fundamentally rewrote the library's backend. Previously, Shapely iterated over scalar geometries in Python. Shapely 2.0 exposes the underlying C++ GEOS operations as highly optimized NumPy universal functions (ufuncs) [cite: 25, 26]. This new architecture implements array broadcasting, significantly improving computational speed while stripping out Python loop overheads [cite: 25, 27].

Consequently, geometries in Shapely 2.0 are now strictly **immutable** [cite: 28]. Furthermore, legacy transformation functions have been deprecated. Specifically, `shapely.ops.transform` is deprecated in favor of `shapely.transform`, which operates entirely on arrays of coordinates rather than looping over geometry parts [cite: 12, 29]. When applying our $x + 360$ antimeridian shift, we utilize `shapely.transform(geometry, transformation_func)`, which accepts an $(N, 2)$ NumPy array of coordinates and returns the shifted coordinate array [cite: 30, 31].

Similarly, the old `cascaded_union` method used for merging overlapping polygons or boundary strings has been fully deprecated and superseded by `shapely.unary_union` [cite: 9, 11].