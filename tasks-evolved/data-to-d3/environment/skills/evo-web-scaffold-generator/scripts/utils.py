import os
import shutil
import subprocess

def setup_output_directory(output_dir='/root/output'):
    """Create the output directory structure."""
    dirs = [
        output_dir,
        os.path.join(output_dir, 'js'),
        os.path.join(output_dir, 'css'),
        os.path.join(output_dir, 'data'),
        os.path.join(output_dir, 'data', 'indiv-stock'),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    return output_dir

def copy_input_data(input_dir='/root/data', output_dir='/root/output/data'):
    """Copy input data files to output data directory."""
    # Copy stock-descriptions.csv
    src_csv = os.path.join(input_dir, 'stock-descriptions.csv')
    dst_csv = os.path.join(output_dir, 'stock-descriptions.csv')
    shutil.copy2(src_csv, dst_csv)
    
    # Copy individual stock files
    src_indiv = os.path.join(input_dir, 'indiv-stock')
    dst_indiv = os.path.join(output_dir, 'indiv-stock')
    os.makedirs(dst_indiv, exist_ok=True)
    for f in os.listdir(src_indiv):
        shutil.copy2(os.path.join(src_indiv, f), os.path.join(dst_indiv, f))

def download_d3_library(output_dir='/root/output/js'):
    """Download d3.v6.min.js to the output js directory."""
    d3_path = os.path.join(output_dir, 'd3.v6.min.js')
    try:
        subprocess.run(
            ['curl', '-s', '--max-time', '30', 'https://d3js.org/d3.v6.min.js', '-o', d3_path],
            check=True
        )
    except Exception:
        # Fallback: copy from tmp if already downloaded
        if os.path.exists('/tmp/d3test.js'):
            shutil.copy2('/tmp/d3test.js', d3_path)
    return d3_path

def generate_index_html(output_dir='/root/output'):
    """Generate the index.html file."""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Visualization Dashboard</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <h1>Stock Visualization Dashboard</h1>
    <div class="container">
        <div id="bubble-chart">
            <h2>Bubble Chart by Sector</h2>
        </div>
        <div id="data-table">
            <h2>Stock Data</h2>
            <div class="table-container">
                <table id="stock-table">
                    <thead>
                        <tr>
                            <th>Ticker Symbol</th>
                            <th>Full Company Name</th>
                            <th>Sector</th>
                            <th>Market Cap</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="tooltip"></div>
    <script src="js/d3.v6.min.js"></script>
    <script src="js/visualization.js"></script>
</body>
</html>'''
    with open(os.path.join(output_dir, 'index.html'), 'w') as f:
        f.write(html)

def generate_style_css(output_dir='/root/output/css'):
    """Generate the style.css file."""
    css = '''* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    background-color: #f5f5f5;
    padding: 20px;
}

h1 {
    text-align: center;
    margin-bottom: 20px;
    color: #333;
}

h2 {
    text-align: center;
    margin-bottom: 10px;
    color: #555;
    font-size: 16px;
}

.container {
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: flex-start;
    gap: 20px;
    max-width: 1400px;
    margin: 0 auto;
}

#bubble-chart {
    flex: 1;
    min-width: 700px;
    background: white;
    border-radius: 8px;
    padding: 15px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

#data-table {
    flex: 0 0 450px;
    background: white;
    border-radius: 8px;
    padding: 15px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.table-container {
    max-height: 600px;
    overflow-y: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

thead th {
    position: sticky;
    top: 0;
    background-color: #4a90d9;
    color: white;
    padding: 8px 6px;
    text-align: left;
    font-weight: bold;
}

tbody td {
    padding: 6px;
    border-bottom: 1px solid #eee;
}

tbody tr:hover {
    background-color: #f0f7ff;
    cursor: pointer;
}

tbody tr.highlighted-row {
    background-color: #ffeb3b !important;
    font-weight: bold;
}

.bubble-group {
    cursor: pointer;
}

.bubble-group circle.highlighted-bubble {
    stroke: #000;
    stroke-width: 3px;
    filter: brightness(1.2);
}

.tooltip {
    position: absolute;
    text-align: left;
    padding: 10px;
    font: 14px sans-serif;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #ddd;
    border-radius: 4px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    z-index: 1000;
}

.tick-label {
    font-size: 10px;
    fill: white;
    text-anchor: middle;
    pointer-events: none;
    font-weight: bold;
}

.legend-label {
    font-family: sans-serif;
    font-size: 12px;
    fill: #333;
}
'''
    with open(os.path.join(output_dir, 'style.css'), 'w') as f:
        f.write(css)

if __name__ == '__main__':
    setup_output_directory()
    copy_input_data()
    download_d3_library()
    generate_index_html()
    generate_style_css()
    print('Scaffold generation complete!')
