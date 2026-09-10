# Domain Reference for evo-web-scaffold-generator

**Responsibility**: Directory setup, data copying, D3.js library fetching, HTML boilerplate generation, and CSS stylesheet creation. Does NOT contain visualization logic.

**Key functions to implement**: setup_output_directory, copy_input_data, download_d3_library, generate_index_html, generate_style_css

---

### 4.1 HTML/CSS Div Overlays


While SVG `<text>` elements can be used for simple labeling, modern dashboards rely on absolute-positioned HTML `<div>` elements for tooltips. This approach supports complex HTML formatting (bolding, line breaks) and CSS transitions.

**CSS Setup:**
```css
.tooltip {
    position: absolute;
    text-align: left;
    padding: 10px;
    font: 14px sans-serif;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #ddd;
    border-radius: 4px;
    pointer-events: none; /* Crucial: prevents tooltip from blocking mouse events [cite: 9] */
    opacity: 0;
    transition: opacity 0.2s;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
}
```

## 7. Python Utility Functions for File Generation


A sophisticated data engineering pipeline uses Python to validate raw CSV files, structure a deployment directory, download dependencies, and generate static HTML/JS files via templating. This ensures the web application is completely standalone and reproducible.