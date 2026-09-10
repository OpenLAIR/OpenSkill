# Domain Reference for evo-macro-excel-formulas

**Responsibility**: Write Excel formulas in sheets Production, WEO_Data, CFC data, and Investment for: depreciation rate from CFC/K, LnK/LnY/LnZ calculations, HP filter objective function and second-order differences, average depreciation rate, K/Y ratio anchoring, TREND function for extending LnZ, Ystar_base and Ystar_with calculations, deltaK and K_With from investment shock, and all linking formulas between sheets

**Key functions to implement**: build_depreciation_formulas, build_hp_filter_formulas, build_production_function_formulas, build_capital_projection_formulas, build_investment_shock_formulas, link_cross_sheet_references

---

## 2. Macroeconomic Accounting and Calibration



### 2.1 Depreciation Rate Calculation


The **Perpetual Inventory Method (PIM)** dictates the evolution of the capital stock:
\[ K_t = (1 - \delta_t) K_{t-1} + I_t \]
where \(K_t\) is the capital stock, \(I_t\) is gross fixed capital formation (investment), and \(\delta_t\) is the depreciation rate [cite: 20, 21].

To calculate the implied historical depreciation rate from national accounts data, the standard macroeconomic convention relies on the beginning-of-period capital stock (which is the end-of-period stock of the previous year). Therefore, the formula is:
\[ \delta_t = \frac{CFC_t}{K_{t-1}} \]
where \(CFC_t\) is the Consumption of Fixed Capital in period \(t\) [cite: 21, 22]. Using \(K_{t-1}\) is theoretically consistent with geometric depreciation, where a fraction of the existing capital stock at the start of the period is consumed during the production process over the year [cite: 20].

### 2.2 Cobb-Douglas Production Function


The standard Cobb-Douglas production function used to estimate potential GDP (\(Y^*\)) incorporates total factor productivity (\(A\)), capital (\(K\)), and effective labor (\(L\)):
\[ Y_t^* = A_t \cdot K_t^\alpha \cdot (L_t \cdot hc_t)^{1-\alpha} \]
In its logarithmic form, this becomes:
\[ \ln Y_t^* = \ln A_t + \alpha \ln K_t + (1-\alpha) \ln (L_t \cdot hc_t) \]

**Calibrating Capital's Share (\(\alpha\))**:
Under the assumption of perfectly competitive factor markets, the output elasticity of capital (\(\alpha\)) equals the share of capital in total income. Consequently, \(\alpha\) is typically calibrated as \(1 - \text{labsh}\), where `labsh` is the labor share of income derived from the PWT [cite: 4, 23]. For advanced economies, \(\alpha\) is usually calibrated at \(0.33\). However, for small open, developing, or transition economies like Georgia, capital is relatively scarce and highly productive, while labor compensation accounts for a smaller share of output. Thus, \(\alpha\) for Georgia is often empirically calibrated higher, typically between \(0.40\) and \(0.50\).

**Computing the Solow Residual**:
Total Factor Productivity (TFP), or the Solow residual (\(A_t\)), is the portion of output not explained by the accumulation of capital and labor. It is computed algebraically as:
\[ \ln A_t = \ln Y_t - \alpha \ln K_t - (1-\alpha) \ln (L_t \cdot hc_t) \]
Once the historical series of \(\ln A_t\) is calculated, it is filtered (detrended) to find the structural, potential TFP (\(\ln A_t^*\)).

## 3. HP Filter and Trend Extraction


The Hodrick-Prescott (HP) filter decomposes a macroeconomic time series \(y_t\) into a non-stationary trend component \(\tau_t\) and a cyclical component \(c_t\) [cite: 24].

### 3.1 The Objective Function and Lambda (\(\lambda\))


The filter operates by minimizing a two-part objective function. The first part penalizes the variance of the cyclical component (Goodness-of-fit), and the second part penalizes variations in the growth rate of the trend component (Degree of smoothness) [cite: 25, 26]. 

Excel Solver must minimize the following function by changing the values of \(\tau_t\):
\[ \min_{\tau_t} \sum_{t=1}^{T} (y_t - \tau_t)^2 + \lambda \sum_{t=2}^{T-1} [(\tau_{t+1} - \tau_t) - (\tau_t - \tau_{t-1})]^2 \]

**The Standard Lambda Value**:
The smoothing parameter \(\lambda\) determines the strictness of the trend. For quarterly data, a value of \(1600\) is universally accepted [cite: 26]. However, for annual data, there is significant debate:
*   **\(\lambda = 100\)**: The traditional value suggested by Hodrick and Prescott (1997) and Backus and Kehoe (1992) [cite: 27, 28].
*   **\(\lambda = 6.25\)**: Suggested by Ravn and Uhlig (2002). They demonstrated mathematically via both time domain and frequency domain analyses that \(\lambda\) should be adjusted by the fourth power of the frequency ratio [cite: 29]. Since there are four quarters in a year, the adjustment is \(1600 / 4^4 = 1600 / 256 = 6.25\) [cite: 28, 30]. Research strongly suggests that \(\lambda = 6.25\) yields a trend for annual data that perfectly matches the aggregated quarterly trend [cite: 29].

### 3.2 HP Filter Implementation in Excel Formulas


To implement the HP filter in an Excel spreadsheet for the Solver to minimize, the following cell structures are required:

1.  **Column A (\(y_t\))**: The observed log-level data (e.g., `LN(GDP)`).
2.  **Column B (\(\tau_t\))**: The trend values. These are the *variable cells* the Solver will change. They can be initialized to equal \(y_t\).
3.  **Column C (Squared Deviations)**: The sum of squared deviations (SSD). 
    *   Formula: `=(A2 - B2)^2`
4.  **Column D (Squared Second Differences)**: The SS2D.
    *   Formula starting at row 3 (for \(t=2\)): `=((B4 - B3) - (B3 - B2))^2`
5.  **Objective Cell**: A single cell summing the components:
    *   Formula: `=SUM(C:C) + 6.25 * SUM(D:D)`

### 4.2 Excel's TREND Function


The Excel `TREND(known_y's, [known_x's], [new_x's])` function fits a linear trend using the least squares method [cite: 35, 36]. Because `TREND` returns an array of values, it acts as a dynamic array formula in modern Microsoft 365. In older Excel versions, it required `Ctrl+Shift+Enter` [cite: 37]. 

When writing this via `openpyxl`, you write it into the top-left cell of the intended output array:
```python
ws['C2'] = '=TREND(B2:B20, A2:A20, A2:A30)'
```
*Note: `openpyxl` does not automatically calculate or expand dynamic arrays.*

### 4.3 Pitfalls and Formatting


1.  **Comma vs. Semicolon**: In some European localized versions of Excel, functions separate arguments with a semicolon `;` (e.g., `=SUM(A1;B1)`). However, the Office Open XML standard underlying `openpyxl` strictly requires the English comma `,` separator (e.g., `=SUM(A1,B1)`) [cite: 33]. Excel will handle the localization automatically when the file is opened by the user.
2.  **Reading Formulas vs. Values**: By default (`data_only=False`), `openpyxl` reads the formula string from a cell [cite: 38]. If you need the calculated result, you must open the workbook with `data_only=True`. However, if the workbook has been generated by `openpyxl` and has *never been opened and saved by the Excel application itself*, the cached values will be `None` because `openpyxl` does not contain a calculation engine [cite: 38].
3.  **Solver Execution**: `openpyxl` cannot interact with or execute Excel's Solver Add-in [cite: 39]. Solver configurations in Excel are stored in proprietary VBA/XML binaries (`solver.xlam`) that `openpyxl` ignores. To run an optimization, one must use external Python optimizers (like `scipy.optimize`) or an API like LibreOffice UNO.

## 6. Capital Stock Projection and Investment Shocks


Modeling the impact of a significant investment shock—such as a $6.5 billion capital injection over 8 years starting in 2026—involves simulating the macro-accounting identities.

### 6.1 Baseline Capital Stock Projection


To project the baseline scenario (\(Y^*_{base}\)), the capital stock must be extended into the future. A standard methodology is **K/Y ratio anchoring**. In the steady-state, the capital-to-output ratio (\(K/Y\)) is roughly constant [cite: 21]. If Georgia's historical \(K/Y\) ratio averages 2.5, the baseline investment required to maintain this ratio, given a baseline trend GDP growth rate (\(g\)) and depreciation (\(\delta\)), can be formulated as:
\[ \left( \frac{I}{Y} \right)^* = (g + \delta) \left( \frac{K}{Y} \right)^* \]
Using this baseline investment \(I_t^{base}\), the baseline capital stock is projected via the PIM:
\[ K_{t+1}^{base} = (1-\delta)K_t^{base} + I_t^{base} \]

### 6.2 Investment Shock Modeling


An exogenous investment shock of $6.5 billion USD over 8 years must be converted into constant domestic currency (matching the `rnna` unit) using the projected PPP exchange rate.

**Distribution of the Shock**:
*   **Evenly Distributed**: $812.5 million per year.
*   **Front-Loaded**: A common empirical assumption for large infrastructure or FDI projects is a front-loaded distribution (e.g., 25% year 1, 20% year 2, 15% year 3, etc.) due to initial massive capital outlays for procurement and construction. 

**Impact on Capital Stock (\(\Delta K\))**:
The new investment trajectory becomes \(I_t^{with} = I_t^{base} + I_t^{shock}\). 
Applying the PIM recursively calculates the new capital stock (\(K_t^{with}\)):
\[ K_{t+1}^{with} = (1-\delta)K_t^{with} + I_t^{with} \]
The change in the capital stock \(\Delta K_t = K_t^{with} - K_t^{base}\) accumulates over time, though the gap narrows after the 8-year injection ceases due to geometric depreciation.

**Impact on Potential GDP**:
Using the calibrated Cobb-Douglas function, the projected potential GDP with the shock is:
\[ Y_{t, with}^* = A_t^* \cdot (K_t^{with})^\alpha \cdot (L_t^*)^{1-\alpha} \]
The macroeconomic impact of the shock is evaluated by comparing the \(\Delta Y_t^*\) trajectory:
\[ \text{Impact} = Y_{t, with}^* - Y_{t, base}^* \]
This tracks the permanent marginal increase in the economy's supply capacity, assuming the investment does not simultaneously cause a TFP (\(A_t^*\)) spillovers, which could be modeled as a secondary multiplier effect.