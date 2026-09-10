# Domain Reference for evo-d3-webapp-scaffold

**Responsibility**: Directory creation, D3.js dependency fetching, data file copying, CSV data inspection/processing, HTML template generation, and CSS styling.

**Key functions to implement**: create_output_structure, fetch_d3_library, copy_data_files, parse_stock_csv, generate_index_html, generate_style_css

---

## 2. D3.js v6 Data Loading and CSV Parsing


In earlier versions of D3 (v4 and prior), data loading relied on `XMLHttpRequest` with asynchronous callbacks. D3 v5 introduced native Promises via the Fetch API, which remains the standard in D3 v6 [cite: 10].

## 6. Python Utility Module for Generating the Web App


A robust Python generator script automates the creation of the required directory structure, resolves dependencies, and dynamically embeds configuration within the HTML, JS, and CSS files.