To verify the investment shock model, you can implement a `pytest` suite that checks the mathematical consistency of the Excel-based calculations. Since the model relies on the Perpetual Inventory Method (PIM) and a Cobb-Douglas production function, the following anchors and invariants are robust for verification.

### 1. Independently Computable Reference Values
You can verify the core logic of the PIM and Cobb-Douglas function using these small-scale calculations:

*   **Depreciation Rate ($\delta$):** The annual depreciation rate is calculated as $\delta_t = \frac{CFC_t}{K_{t-1}}$, where $CFC$ is the Consumption of Fixed Capital and $K$ is the capital stock.
    *   *Verification:* If $CFC = 500$ million USD and $K_{t-1} = 10,000$ million USD, $\delta$ must equal $0.05$ (or $5\%$).
*   **Capital Stock Evolution (PIM):** The capital stock for the next year is $K_t = K_{t-1}(1 - \delta) + I_t$.
    *   *Verification:* Given $K_{2025} = 20,000$, $\delta = 0.05$, and $I_{2026} = 6.5$ billion (6,500 million), $K_{2026}$ must equal $20,000(0.95) + 6,500 = 25,500$ million USD.
*   **Cobb-Douglas Potential GDP ($Y^*$):** $Y^* = A \cdot K^\alpha \cdot L^{(1-\alpha)}$.
    *   *Verification:* If $\alpha = 0.33$, $A = 1.5$, $K = 25,500$, and $L = 1.5$ (million persons), then $Y^* = 1.5 \cdot (25,500^{0.33}) \cdot (1.5^{0.67})$.

### 2. Dataset-Level Statistical Invariants
These properties must hold true regardless of the specific data values:

*   **Monotonicity of Capital:** With a positive investment shock ($I > 0$), the capital stock $K_t$ must be strictly increasing from 2026 to 2034 ($K_{2026} < K_{2027} < \dots < K_{2034}$).
*   **Elasticity Constraint:** The sum of output elasticities ($\alpha + (1-\alpha)$) must equal $1.0$ to maintain the constant returns to scale assumption inherent in the Cobb-Douglas model.
*   **HP Filter Smoothness:** The HP filter trend component ($\tau_t$) must be smoother than the original series ($y_t$). A common invariant is that the variance of the cyclical component ($y_t - \tau_t$) should be significantly smaller than the variance of the original series.
*   **Completeness:** All years from 2000 to 2043 must be populated; no `NaN` or `#REF!` errors should exist in the projection range.

### 3. Cross-Validation Approaches
To verify the Excel output without re-running the entire model:

*   **Python/SciPy Check:** You can use `statsmodels.tsa.filters.hpfilter` to independently compute the HP trend.
    ```python
    import statsmodels.api as sm
    # lambda=6.25 for annual data
    cycle, trend = sm.tsa.filters.hpfilter(data_series, lamb=6.25)
    ```
*   **Algebraic Solver Check:** The Excel Solver minimizes the sum of squared deviations. You can verify the result by checking if the first-order condition (the Euler equation for the HP filter) is satisfied: $\sum (y_t - \tau_t) = 0$ (approximately) and that the trend is linear in the limit.

### 4. Benchmarks and Reference Implementations
*   **HP Filter Parameter:** The standard for annual macroeconomic data is $\lambda = 6.25$. Any model using $\lambda = 100$ or $\lambda = 1600$ for annual data is likely using an incorrect frequency adjustment.
*   **PIM Methodology:** The Perpetual Inventory Method is the standard approach for capital stock estimation. Ensure the depreciation rate $\delta$ is applied to the *previous* year's capital stock ($K_{t-1}$) before adding current investment ($I_t$).