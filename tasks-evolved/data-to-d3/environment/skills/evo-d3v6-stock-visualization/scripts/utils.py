import csv
import json

def format_market_cap_js():
    """Returns JS function to format market cap as readable string like 1.64T."""
    return '''
function formatMarketCap(val) {
    if (!val || isNaN(val)) return "N/A";
    if (val >= 1e12) return (val / 1e12).toFixed(2) + "T";
    if (val >= 1e9) return (val / 1e9).toFixed(2) + "B";
    if (val >= 1e6) return (val / 1e6).toFixed(2) + "M";
    return val.toString();
}
'''

def load_stock_data(csv_path='/root/data/stock-descriptions.csv'):
    """Load stock data from CSV and return as list of dicts."""
    stocks = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mc = row.get('marketCap', '')
            stocks.append({
                'ticker': row['ticker'],
                'name': row['full name'],
                'sector': row['sector'],
                'marketCap': float(mc) if mc else None,
                'country': row.get('country', '') or None,
                'website': row.get('website', '') or None
            })
    return stocks

def generate_embedded_data_js(stocks):
    """Generate JS array literal from stock data."""
    lines = ['const data = [']
    for s in stocks:
        mc = str(s['marketCap']) if s['marketCap'] else 'null'
        # Escape quotes in name
        name = s['name'].replace('"', '\\"')
        lines.append('    {ticker: "%s", name: "%s", sector: "%s", marketCap: %s, country: %s, website: %s},' % (
            s['ticker'],
            name,
            s['sector'],
            mc,
            json.dumps(s['country']),
            json.dumps(s['website'])
        ))
    lines.append('];')
    return '\n'.join(lines)

def build_force_simulation_code():
    """Returns JS code for force simulation with sector clustering."""
    return '''
    // Sector focus positions - 5 sectors arranged nicely
    const sectors = ["Information Technology", "Industry", "Energy", "Financial", "ETF"];
    const sectorFocusX = d3.scaleOrdinal()
        .domain(sectors)
        .range([chartWidth * 0.2, chartWidth * 0.5, chartWidth * 0.8, chartWidth * 0.2, chartWidth * 0.5]);
    const sectorFocusY = d3.scaleOrdinal()
        .domain(sectors)
        .range([chartHeight * 0.3, chartHeight * 0.3, chartHeight * 0.3, chartHeight * 0.7, chartHeight * 0.7]);

    // Color scale
    const colorScale = d3.scaleOrdinal()
        .domain(sectors)
        .range(["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f"]);

    // Radius scale using scaleSqrt for area-proportional sizing
    const maxMarketCap = d3.max(data, d => d.marketCap);
    const radiusScale = d3.scaleSqrt()
        .domain([0, maxMarketCap])
        .range([4, 50]);

    const uniformETFRadius = 12;
    const padding = 2;

    function getRadius(d) {
        if (!d.marketCap || d.sector === "ETF") return uniformETFRadius;
        return radiusScale(d.marketCap);
    }

    // Pre-initialize positions near sector centers
    data.forEach(d => {
        d.x = sectorFocusX(d.sector) + (Math.random() - 0.5) * 50;
        d.y = sectorFocusY(d.sector) + (Math.random() - 0.5) * 50;
    });

    const simulation = d3.forceSimulation(data)
        .force("charge", d3.forceManyBody().strength(-5))
        .force("x", d3.forceX(d => sectorFocusX(d.sector)).strength(0.15))
        .force("y", d3.forceY(d => sectorFocusY(d.sector)).strength(0.15))
        .force("collide", d3.forceCollide().radius(d => getRadius(d) + padding).strength(1).iterations(3));
'''

def build_bubble_chart_code():
    """Returns JS code for rendering bubble chart with labels, legend, tooltip."""
    return '''
    // Create SVG
    const svg = d3.select("#bubble-chart")
        .append("svg")
        .attr("width", chartWidth)
        .attr("height", chartHeight);

    // Tooltip
    const tooltip = d3.select(".tooltip");

    // Create bubble groups
    const bubbleGroups = svg.selectAll(".bubble-group")
        .data(data)
        .enter()
        .append("g")
        .attr("class", "bubble-group")
        .attr("id", d => "bubble-" + d.ticker);

    // Append circles
    bubbleGroups.append("circle")
        .attr("r", d => getRadius(d))
        .style("fill", d => colorScale(d.sector))
        .style("opacity", 0.85)
        .style("stroke", "#fff")
        .style("stroke-width", 1);

    // Append ticker labels inside bubbles
    bubbleGroups.append("text")
        .attr("class", "tick-label")
        .attr("dy", ".35em")
        .text(d => d.ticker)
        .style("font-size", d => {
            const r = getRadius(d);
            return Math.max(7, Math.min(r * 0.6, 14)) + "px";
        });

    // Tooltip events - D3 v6 signature: (event, d)
    bubbleGroups
        .on("mouseover", function(event, d) {
            if (d.sector === "ETF") return; // No tooltip for ETFs
            tooltip.transition().duration(200).style("opacity", 1);
            tooltip.html(
                "<strong>" + d.ticker + "</strong><br/>" +
                "Name: " + d.name + "<br/>" +
                "Sector: " + d.sector
            )
            .style("left", (event.pageX + 15) + "px")
            .style("top", (event.pageY - 20) + "px");
        })
        .on("mousemove", function(event, d) {
            if (d.sector === "ETF") return;
            tooltip
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 20) + "px");
        })
        .on("mouseout", function(event, d) {
            tooltip.transition().duration(200).style("opacity", 0);
        });

    // Update positions on tick
    simulation.on("tick", () => {
        bubbleGroups.attr("transform", d => {
            // Keep bubbles within SVG bounds
            const r = getRadius(d);
            d.x = Math.max(r, Math.min(chartWidth - r, d.x));
            d.y = Math.max(r, Math.min(chartHeight - r, d.y));
            return "translate(" + d.x + "," + d.y + ")";
        });
    });

    // Legend
    const legendGroup = svg.append("g")
        .attr("class", "legend")
        .attr("transform", "translate(" + (chartWidth - 180) + ", 10)");

    const legendEntries = legendGroup.selectAll(".legend-entry")
        .data(sectors)
        .enter()
        .append("g")
        .attr("class", "legend-entry")
        .attr("transform", (d, i) => "translate(0, " + (i * 22) + ")");

    legendEntries.append("circle")
        .attr("cx", 0)
        .attr("cy", 0)
        .attr("r", 7)
        .style("fill", d => colorScale(d));

    legendEntries.append("text")
        .attr("x", 15)
        .attr("y", 0)
        .attr("dominant-baseline", "central")
        .text(d => d)
        .attr("class", "legend-label");
'''

def build_data_table_code():
    """Returns JS code for building the data table."""
    return '''
    // Build data table
    const tbody = d3.select("#stock-table tbody");
    const rows = tbody.selectAll("tr")
        .data(data)
        .enter()
        .append("tr")
        .attr("class", "table-row")
        .attr("id", d => "row-" + d.ticker);

    rows.append("td").text(d => d.ticker);
    rows.append("td").text(d => d.name);
    rows.append("td").text(d => d.sector);
    rows.append("td").text(d => formatMarketCap(d.marketCap));
'''

def build_interaction_code():
    """Returns JS code for bidirectional click interaction."""
    return '''
    // Bidirectional click interaction
    function highlightEntity(ticker) {
        // Reset all highlights
        d3.selectAll(".bubble-group circle").classed("highlighted-bubble", false);
        d3.selectAll(".table-row").classed("highlighted-row", false);

        if (ticker) {
            // Highlight bubble
            d3.select("#bubble-" + ticker + " circle").classed("highlighted-bubble", true);
            // Highlight row and scroll into view
            const rowSel = d3.select("#row-" + ticker);
            rowSel.classed("highlighted-row", true);
            const rowNode = rowSel.node();
            if (rowNode) {
                rowNode.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }

    // Click on bubbles
    bubbleGroups.on("click", function(event, d) {
        const isHighlighted = d3.select(this).select("circle").classed("highlighted-bubble");
        highlightEntity(isHighlighted ? null : d.ticker);
    });

    // Click on table rows
    rows.on("click", function(event, d) {
        const isHighlighted = d3.select(this).classed("highlighted-row");
        highlightEntity(isHighlighted ? null : d.ticker);
    });
'''

def generate_visualization_js(output_path='/root/output/js/visualization.js', csv_path='/root/data/stock-descriptions.csv'):
    """Generate the complete visualization.js file with embedded data."""
    # Load stock data from CSV
    stocks = load_stock_data(csv_path)
    embedded_data = generate_embedded_data_js(stocks)
    
    js_code = '''// Stock Visualization Dashboard - D3.js v6

''' + format_market_cap_js() + '''

// Embedded stock data
''' + embedded_data + '''

(function() {
    const chartWidth = 700;
    const chartHeight = 600;
''' + build_force_simulation_code() + '''
''' + build_bubble_chart_code() + '''
''' + build_data_table_code() + '''
''' + build_interaction_code() + '''
})();
'''
    with open(output_path, 'w') as f:
        f.write(js_code)
    return output_path

if __name__ == '__main__':
    generate_visualization_js()
    print('visualization.js generated!')
