To verify the correctness of the D3.js visualization independently, you can implement a `pytest` suite that uses **Playwright** to inspect the rendered DOM and **Python/Pandas** to validate the underlying data processing logic.

### 1. Independently Computable Reference Values
Since the bubble chart relies on market capitalization for sizing, you can pre-calculate the expected scaling behavior.
*   **Input:** A CSV row with `marketCap` (e.g., "1.64T").
*   **Normalization Logic:** D3's `d3.scaleSqrt` or `d3.scaleLinear` is typically used for bubble radii.
*   **Reference Calculation:**
    *   If `marketCap` = 1.64T ($1.64 \times 10^{12}$) and the domain is $[min, max]$, the radius $r$ is:
        $r = \text{rangeMin} + (\text{rangeMax} - \text{rangeMin}) \times \frac{\sqrt{marketCap} - \sqrt{min}}{\sqrt{max} - \sqrt{min}}$.
    *   **Assertion:** In your test, parse the `r` attribute of the SVG circle element for a known stock and assert it falls within the expected range calculated via this formula.

### 2. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the D3 simulation's stochastic nature:
*   **Completeness:** The number of SVG `circle` elements must exactly match the number of non-ETF entries in `stock-descriptions.csv`.
*   **Categorical Integrity:** Every `circle` must have a `fill` color attribute corresponding to its `sector` as defined in the input data.
*   **Data Table Mapping:** The number of rows in the HTML table (excluding the header) must equal the total number of stocks (50).
*   **Formatting Invariant:** Market cap values in the table must follow the `X.XX[T/B/M]` format. Use a regex assertion: `assert re.match(r"^\d+\.\d+[TBM]$", table_cell_text)`.

### 3. Cross-Validation Approaches
Use Python to independently verify the data processing before it reaches the browser:
*   **Pandas Verification:** Load the CSV in your test script using `pandas`.
    ```python
    import pandas as pd
    df = pd.read_csv('/root/data/stock-descriptions.csv')
    # Verify total count
    assert len(df) == 50
    # Verify sector grouping
    expected_sectors = df['Sector'].unique()
    ```
*   **Playwright Interaction Check:**
    *   Click a bubble (e.g., `page.click('circle[data-ticker="AAPL"]')`).
    *   Assert that the corresponding table row gains a specific CSS class (e.g., `.highlight`) and that no other rows have it.

### 4. Benchmarks and Reference Implementations
*   **Force Layout Stability:** D3 force simulations are non-deterministic due to the `alpha` cooling parameter. Do **not** assert exact `x` and `y` coordinates. Instead, assert **relative positioning**:
    *   For two stocks in the same sector, their distance $d$ should be significantly smaller than the distance between stocks in different sectors.
    *   **Assertion:** `assert distance(nodeA, nodeB) < distance(nodeA, nodeC)` where A and B are in the same sector, and C is in a different one.
*   **Reference:** Refer to the [D3.js Observable "Clustered Bubbles" notebook](https://observablehq.com/@d3/clustered-bubbles) for the standard implementation of `forceCollide` and `forceX/Y` clustering, which serves as the authoritative reference for expected behavior.