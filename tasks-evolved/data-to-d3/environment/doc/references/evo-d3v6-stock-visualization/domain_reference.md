# Domain Reference for evo-d3v6-stock-visualization

**Responsibility**: All D3.js v6 client-side visualization logic: CSV loading/parsing, force simulation setup (forceX/forceY/forceCollide), scaleSqrt for bubble sizing, ordinal color scale for sectors, legend rendering, tooltip with v6 event handling, HTML table generation with formatted market cap, and bidirectional click interaction with scroll-into-view.

**Key functions to implement**: generate_visualization_js, build_force_simulation_code, build_bubble_chart_code, build_data_table_code, build_interaction_code

---

## 1. D3.js v6 Force Simulation API for Bubble Charts with Sector Clustering



### 1.1 The Physics of D3 Force Simulations


D3's force layout utilizes a physics-based simulator for positioning visual elements [cite: 1]. At its core, a force simulation implements a velocity Verlet numerical integrator for simulating physical forces on particles, which are represented as nodes in the graph [cite: 2, 3]. The simulation assumes a constant unit time step ($\Delta t = 1$) for each step and a constant unit mass ($m = 1$) for all particles [cite: 3]. Consequently, a force $F$ acting on a particle equates to a constant acceleration $a$ over the time interval $\Delta t$, and is simulated by directly adding to the particle's velocity, which subsequently updates the particle's position [cite: 3]. 

When constructing a bubble chart where bubbles (representing individual stocks or entities) must cluster by a categorical variable (such as market sector), the developer must apply competing forces:
1. **Collision Forces:** To prevent bubbles from overlapping.
2. **Position/Attraction Forces:** To pull bubbles toward a specific focal point designated for their sector.
3. **Many-Body Forces:** To introduce subtle repulsion or attraction among all nodes to maintain spacing.

### 1.2 Exact API Signatures and Chaining in D3 v6


The `d3-force` module is instantiated and configured via a chained API. Below are the specific method signatures and default parameter behaviors in D3 v6:

*   **`d3.forceSimulation([nodes])`**: Creates a new simulation with the specified array of nodes and no forces [cite: 3]. If `nodes` is not specified, it defaults to an empty array. It is critical to note that this function is impure; it mutates the passed-in `nodes` array, assigning properties such as `index`, `x`, `y`, `vx`, and `vy` [cite: 3]. The simulator starts automatically upon instantiation.
*   **`d3.forceX([x])`**: Creates a new position force along the x-axis towards the given position `x` [cite: 4]. If `x` is not specified, it defaults to 0. The force is configurable via `.strength(strength)`. The strength determines the increment applied to the node's x-velocity: `(x - node.x) * strength` [cite: 4]. The default strength is 0.1 [cite: 4].
*   **`d3.forceY([y])`**: Operates identically to `forceX`, but along the y-axis, pulling nodes toward a target `y` coordinate [cite: 4].
*   **`d3.forceCollide([radius])`**: Creates a collision force to stop circular elements from overlapping [cite: 1]. The `radius` can be a constant or an accessor function evaluated per node.
*   **`d3.forceManyBody()`**: Applies a many-body force among all nodes. By default, it simulates electrostatic repulsion (negative strength), making nodes repel each other, which is useful for untangling clusters [cite: 1].

**Chaining Pattern:**
```javascript
const simulation = d3.forceSimulation(nodes)
    .force("charge", d3.forceManyBody().strength(-5))
    .force("x", d3.forceX().x(d => sectorX(d.sector)).strength(0.1))
    .force("y", d3.forceY().y(d => sectorY(d.sector)).strength(0.1))
    .force("collide", d3.forceCollide().radius(d => radiusScale(d.marketCap) + padding).iterations(2));
```

### 1.3 Sector Clustering Using Custom Accessors


To cluster bubbles by sector so they form visually distinct groups, we utilize `forceX` and `forceY` with custom accessor functions. The goal is to define specific $(x, y)$ target coordinates for each sector and pull the corresponding bubbles toward those coordinates [cite: 4]. 

For a canvas of roughly 800x600 pixels containing 50 bubbles distributed among several sectors (e.g., Technology, Healthcare, Financials), we can calculate focal points using trigonometric distribution or a grid layout. A common and visually pleasing approach is placing the clusters in a grid or an ellipse around the center.

**Working Code Example for Cluster Positioning:**
```javascript
// Assume 4 distinct sectors
const sectors = ["Technology", "Healthcare", "Financials", "Consumer"];
const width = 800;
const height = 600;

// Create an ordinal scale to assign x and y coordinates per sector
// We split the width and height to form a 2x2 grid pattern
const sectorFocusX = d3.scaleOrdinal()
    .domain(sectors)
    .range([width * 0.25, width * 0.75, width * 0.25, width * 0.75]);

const sectorFocusY = d3.scaleOrdinal()
    .domain(sectors)
    .range([height * 0.3, height * 0.3, height * 0.7, height * 0.7]);

// Apply to simulation
simulation
    .force("x", d3.forceX(d => sectorFocusX(d.sector)).strength(0.15))
    .force("y", d3.forceY(d => sectorFocusY(d.sector)).strength(0.15));
```
By defining explicit foci, the physics engine will gradually pull each node toward its sector's center. The `strength(0.15)` parameter dictates how aggressively the nodes are pulled. Lower values (e.g., 0.05) result in loose, sprawling clusters, while higher values (e.g., 0.5) create tightly packed, rigid clusters that may overlap if collision forces are not adequately tuned.

## 2. D3.js v6 CSV Loading and Data Parsing



### 2.1 Promise-Based Fetch API in D3 v6


A significant architectural shift occurred between D3 v4 and v5/v6 regarding data fetching. The older callback-based approaches (`d3.csv("file.csv", function(error, data) {...})`) were replaced by the modern JavaScript Fetch API, returning Promises [cite: 7, 8].

In D3 v6, `d3.csv()` initiates an asynchronous network request and returns a Promise that resolves to an array of objects representing the parsed rows [cite: 7, 8].

**Basic Usage:**
```javascript
d3.csv("path/to/data.csv").then(data => {
    console.log(data); // Array of objects
}).catch(error => {
    console.error("Error loading data:", error);
});
```

### 2.3 Data Parsing and Type Coercion


By default, the DSV (Delimiter-Separated Values) parser in D3 extracts all values as strings [cite: 9]. Leaving numeric fields as strings is a frequent source of silent errors in scale calculations and force physics. D3 allows passing a row conversion function as the second argument to `d3.csv()` to coerce types immediately upon parsing.

```javascript
// Row conversion function
function rowConverter(d) {
    return {
        ticker: d.Ticker,
        name: d["Company Name"],
        sector: d.Sector,
        // The unary plus operator coerces strings to numbers [cite: 9]
        // If marketCap is empty (e.g., for ETFs), it falls back to null
        marketCap: d.MarketCap ? +d.MarketCap : null,
        isETF: d.Type === "ETF"
    };
}

// Usage with Promise
d3.csv("data/stock-descriptions.csv", rowConverter).then(data => {
    // data.marketCap is now guaranteed to be a number or null
});
```
Alternatively, `d3.autoType` can be used, though explicit converters provide strict control over complex schema transformations.

## 3. D3.js v6 Color Scales for Categorical Data (Sectors)



### 3.2 Building a Color Legend


A visualization is incomplete without a legend mapping colors to their semantic meanings. Utilizing D3's data join architecture (`selectAll`, `data`, `enter`, `append`), we can dynamically generate a legend.

```javascript
// Define legend dimensions and position
const legendGroup = svg.append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${width - 150}, 50)`);

// Create a group for each sector entry
const legendEntries = legendGroup.selectAll(".legend-entry")
    .data(sectors)
    .enter()
    .append("g")
    .attr("class", "legend-entry")
    .attr("transform", (d, i) => `translate(0, ${i * 25})`);

// Append colored circles
legendEntries.append("circle")
    .attr("cx", 0)
    .attr("cy", 0)
    .attr("r", 8)
    .style("fill", d => colorScale(d));

// Append text labels
legendEntries.append("text")
    .attr("x", 15)
    .attr("y", 0)
    .attr("dominant-baseline", "central") // Center text vertically with the circle
    .text(d => d)
    .style("font-family", "sans-serif")
    .style("font-size", "12px")
    .style("fill", "#333");
```

## 4. D3.js v6 Tooltip Implementation



## 5. D3.js v6 Interactive Data Table with Click-Based Highlighting



### 5.3 Bidirectional Click Interaction and Auto-Scrolling


Connecting the bubble chart to the table creates a powerful exploratory interface. Clicking a bubble should highlight the corresponding table row and scroll it into view; clicking a table row should highlight the corresponding bubble.

**CSS Classes for State Management:**
```css
.highlighted-bubble {
    stroke: #000;
    stroke-width: 3px;
    filter: brightness(1.2);
}
.highlighted-row {
    background-color: #ffeb3b; /* Distinct yellow */
    font-weight: bold;
}
```

**JavaScript Implementation:**

```javascript
// Centralized state handling function
function highlightEntity(ticker) {
    // Reset all highlights
    d3.selectAll(".bubble-group circle").classed("highlighted-bubble", false);
    d3.selectAll(".table-row").classed("highlighted-row", false);

    // Apply specific highlights if a ticker is provided
    if (ticker) {
        // Highlight bubble
        d3.select(`#bubble-${ticker} circle`).classed("highlighted-bubble", true);
        
        // Highlight row
        const rowSelection = d3.select(`#row-${ticker}`);
        rowSelection.classed("highlighted-row", true);
        
        // Scroll the row into view native DOM API
        const rowNode = rowSelection.node();
        if (rowNode) {
            rowNode.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }
}

// Bind click events to Bubbles
d3.selectAll(".bubble-group")
    .attr("id", d => `bubble-${d.ticker}`)
    .on("click", function(event, d) {
        // Toggle behavior: if already highlighted, clear it
        const isCurrentlyHighlighted = d3.select(this).select("circle").classed("highlighted-bubble");
        highlightEntity(isCurrentlyHighlighted ? null : d.ticker);
    });

// Bind click events to Table Rows
d3.selectAll(".table-row")
    .on("click", function(event, d) {
        const isCurrentlyHighlighted = d3.select(this).classed("highlighted-row");
        highlightEntity(isCurrentlyHighlighted ? null : d.ticker);
    });
```

## 6. D3.js v6 Text Labels Inside Circles


Centering text cleanly within SVG circles requires specific SVG attributes, as HTML/CSS centering models (`flexbox`, `text-align`) do not apply to SVG coordinates.

## 8. Common Pitfalls in D3 v6


Migrating or learning D3 v6 presents several specific pitfalls that cause catastrophic failures in rendering or interaction. These are heavily documented across developer forums.

### 8.1 The Event Handler Signature Break

As detailed in the Tooltip section, D3 v6 removed `d3.event` and changed the `.on()` callback signature from `function(d, i)` to `function(event, d)` [cite: 13, 14]. A developer accustomed to v4/v5 writing `.on("click", function(d) { console.log(d.ticker); })` will find that `d` is actually a `MouseEvent` object in v6, resulting in `undefined` errors when trying to access data properties [cite: 13, 14]. This is the single most critical migration error.

### 8.2 Force Simulation Initial Positions

When passing the nodes array into `d3.forceSimulation(nodes)`, D3 checks if the `x` and `y` properties exist. If they do not, D3 assigns random positions utilizing a phyllotaxis arrangement or pure random logic [cite: 29]. If the data is poorly scaled, or if nodes begin precisely at the same `(0,0)` coordinate, collision forces can "explode," shooting nodes off the canvas instantly at high velocity. 
**Solution:** Pre-initialize node positions close to their ultimate intended targets.
```javascript
nodes.forEach(d => {
    // Start nodes roughly near their sector center
    d.x = sectorFocusX(d.sector) + (Math.random() - 0.5) * 50;
    d.y = sectorFocusY(d.sector) + (Math.random() - 0.5) * 50;
});
```

### 8.3 CSV Parsing Coercion

The `d3.csv` function parses all file content as strings [cite: 9]. If `marketCap` is left as a string, `d3.scaleSqrt` will attempt implicit conversion, but operations like `d3.max()` or sorting comparisons will treat "100" as less than "20" (alphabetical sorting). Explicitly applying the unary plus operator (`+d.marketCap`) within a row conversion accessor is mandatory [cite: 9].

### 8.4 Promise Handling Missteps

The asynchronous nature of `d3.csv().then()` means any logic dependent on the data (drawing scales, rendering SVGs, configuring force physics) must execute *inside* the `.then()` block or be called from within it. Defining dependent logic synchronously below the fetch call will result in "undefined variable" errors, as the data has not yet loaded over the network.