# Domain Reference for evo-d3-stock-visualization

**Responsibility**: All D3.js v6 JavaScript code generation: force simulation with forceX/forceY/forceCollide for sector clustering, bubble rendering with sqrt-scaled radii, color legends, tooltip behavior, HTML data table with formatted market cap, and bidirectional click-based cross-highlighting between chart and table.

**Key functions to implement**: generate_visualization_js, build_bubble_chart_code, build_data_table_code, build_linked_interactivity_code, build_legend_code

---

## 1. D3.js v6 Force Simulation API for Bubble Charts


The D3 force layout employs a physics-based simulator to determine the positioning of visual elements [cite: 1]. It relies on a velocity Verlet numerical integrator to simulate physical forces on particles (in this case, nodes representing stocks). The simulation assumes a constant unit time step \(\Delta t = 1\) and a constant unit mass \(m = 1\) for all particles [cite: 2].

## 2. D3.js v6 Data Loading and CSV Parsing


In earlier versions of D3 (v4 and prior), data loading relied on `XMLHttpRequest` with asynchronous callbacks. D3 v5 introduced native Promises via the Fetch API, which remains the standard in D3 v6 [cite: 10].

## 3. D3.js v6 Interactive Data Table


Creating HTML tables using D3 involves data binding through the `selectAll`, `data`, `join` (or `enter`/`append`) pattern. The v6 paradigm heavily encourages the use of `.join()`, which simplifies the enter/update/exit lifecycle.

## 4. Linked Interactivity Between Chart and Table


A sophisticated SPA leverages user interaction in one visual component to contextually update another. When a bubble is clicked, the table should scroll to the relevant row and highlight it; conversely, clicking a row should highlight the bubble.

## 5. D3.js v6 Color Scales and Legends


Colors provide immediate visual segmentation for categorical data. D3 includes several ready-to-use palettes in the `d3-scale-chromatic` module.

## 7. Common Pitfalls and Migration Strategies


Constructing complex layouts in D3.js involves navigating several common mathematical, rendering, and API-versioning pitfalls.