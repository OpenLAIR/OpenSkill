# Macroeconomic Modeling of Investment Shocks: An Automated Framework for Small Open Economies

*   **Data acquisition for macroeconomic modeling requires specific institutional codes**: Extracting data from the Penn World Table (PWT), IMF World Economic Outlook (WEO), and the European Central Bank's Statistical Data Warehouse (ECB SDW) requires precise series keys, such as `rnna` for capital stock and `NGDP_R` for real GDP.
*   **The Hodrick-Prescott (HP) filter parameter for annual data is debated**: While traditional software often defaults to \(\lambda = 100\), mathematical research strongly suggests that \(\lambda = 6.25\) is optimal for isolating annual business cycles. 
*   **Python's openpyxl does not evaluate formulas or run Excel Solver**: `openpyxl` only writes formulas as text strings. Automating an optimization task (like an HP filter) requires either a Python-UNO bridge to LibreOffice Calc or an external numerical optimizer.
*   **Investment shocks rely on the Perpetual Inventory Method (PIM)**: Modeling a multibillion-dollar capital injection involves simulating the trajectory of the capital stock using geometric depreciation, which directly shifts the potential output frontier in a Cobb-Douglas production function.

Research suggests that evaluating the macroeconomic impact of large-scale investment shocks—such as a $6.5 billion foreign direct investment in a small open economy like Georgia—requires a rigorous synthesis of national accounts data, production function theory, and time-series econometrics. It seems likely that the most robust method for determining the baseline trajectory of such an economy involves calculating potential output via a Cobb-Douglas production function, detrending historical data using an HP filter, and projecting the capital stock using the Perpetual Inventory Method (PIM). 

The evidence leans toward using automated programmatic pipelines to ensure reproducibility. By utilizing Python to manipulate spreadsheet models, researchers can dynamically update datasets, calculate the Solow residual, and apply mathematical solvers to unobserved component models. However, because standard Python libraries like `openpyxl` cannot natively execute Excel's proprietary Solver add-in, alternative approaches, such as bridging Python with the LibreOffice UNO API, must be employed to minimize the HP filter's objective function programmatically.

## 1. Database Structures and Programmatic Acquisition

Constructing a macroeconomic model for a small open economy requires harmonized historical data. Three primary databases are utilized: the Penn World Table (PWT), the IMF World Economic Outlook (WEO), and the ECB Statistical Data Warehouse (SDW).

### 1.1 Penn World Table (PWT) Database Structure

The Penn World Table (currently version 10.x) provides purchasing power parity (PPP) adjusted national accounts data designed for cross-country comparisons of relative income, output, inputs, and productivity [cite: 1, 2]. For Georgia, the exact country identifier is the ISO 3166-1 alpha-3 code **GEO** [cite: 1, 3]. 

The exact variable names and codes required for a Cobb-Douglas production function are as follows:

| Variable Code | Description | Application in Modeling |
| :--- | :--- | :--- |
| **rnna** | Capital stock at constant 2017 national prices (in millions of 2017 USD). | This is the absolute level of the capital stock (\(K\)) used in the production function [cite: 1, 4]. |
| **rkna** | Capital services at constant 2017 national prices (2017 = 1). | This is an index of capital services, suitable for growth accounting but less optimal for level-based Cobb-Douglas estimations [cite: 1, 4]. |
| **emp** | Number of persons engaged (in millions). | Represents the labor input (\(L\)) [cite: 1, 3]. |
| **labsh** | Share of labor compensation in GDP at current national prices. | Used to calibrate the labor share (\(1-\alpha\)) [cite: 4, 5]. |
| **hc** | Human capital index. | Based on years of schooling and returns to education, used to augment raw labor into effective labor (\(L \cdot hc\)) [cite: 1]. |

**Metadata Sheet**: The PWT dataset includes a "Data Information" or metadata sheet. This sheet defines the concepts, details the construction of the data variables, and provides a binary or categorical flag indicating whether a specific data point (like relative price data or exchange rates) is benchmarked, interpolated, or extrapolated [cite: 1, 6]. It allows researchers to gauge the statistical capacity and reliability of the data for specific countries.

**URL Structure and Download**: The PWT data is hosted by the Groningen Growth and Development Centre (GGDC). Programmatic downloads can directly target the Excel or Stata files hosted on the DataverseNL repository or the GGDC URL endpoint. The URL structure typically follows `https://www.rug.nl/ggdc/productivity/pwt/` for the landing page [cite: 7], with direct file downloads routed through their specific release subdirectories.

### 1.2 IMF World Economic Outlook (WEO) Database

The IMF WEO database is updated biannually (April and October) and contains macroeconomic projections for up to five years into the future [cite: 8, 9]. Starting with recent vintages, the IMF transitioned to a new Data Portal, replacing three-digit IFS codes with standard three-letter ISO codes (e.g., **GEO** for Georgia) [cite: 10].

| WEO Subject Code | Subject Descriptor | Unit |
| :--- | :--- | :--- |
| **NGDP_R** | Gross domestic product, constant prices | Billions of national currency [cite: 11, 12]. |
| **NGDP_RPCH** | Gross domestic product, constant prices | Percent change (Annual year-on-year) [cite: 11, 12]. |

**Format and Access**: The traditional WEO data format provided bulk downloads in tab-separated values (TSV) disguised with an `.xls` extension, though the modern IMF Data Portal provides true CSV and SDMX-JSON APIs [cite: 10, 13]. Programmatically, researchers can use Python to parse the CSV file, filter for `WEO Country Code == 'GEO'`, and pivot the data to create a time-series panel [cite: 13].

### 1.3 ECB Statistical Data Warehouse (SDW)

While the ECB primarily focuses on the Euro Area, it maintains an International Data Cooperation (IDCM) dataset containing national accounts for non-EU countries, including Georgia [cite: 14, 15].

**Data Series Key**: In the ECB SDW SDMX format, series keys are concatenated dimensions. For "Consumption of fixed capital" (CFC), the ESA2010 transaction code is **P51C** [cite: 16]. The annual series key for Georgia's CFC follows the pattern:
`IDCM.A.N.GE.W2.S1.S1.D.P51C.N1G._T._Z.XDC.V.N` [cite: 15, 17, 18].

*   `IDCM`: International Data Cooperation dataset [cite: 15].
*   `A`: Annual frequency.
*   `GE`: Georgia (Eurostat/ECB 2-letter geographical code).
*   `P51C`: Consumption of fixed capital [cite: 16].
*   `XDC`: Domestic currency.

**Units**: The data is reported in domestic currency (Georgian Lari - GEL) at current prices [cite: 18, 19]. 

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

## 4. Python `openpyxl` Integration

`openpyxl` (version 3.1.5) is the premier Python library for reading and writing `.xlsx` files [cite: 31, 32]. 

### 4.1 Writing Formulas via `openpyxl`

`openpyxl` writes formulas simply by assigning a string that begins with `=` to a cell's value [cite: 33]. 
*   **Syntax**: `ws['A1'] = '=SUM(B1:B10)'`
*   **Cross-sheet referencing**: Use the standard Excel syntax with an exclamation mark. If the sheet name contains spaces, it must be wrapped in single quotes [cite: 34]. Example: `ws['A1'] = "='PWT Data'!B5"`

**Standard Formulas Implementation**:
```python
# AVERAGE
ws['C1'] = '=AVERAGE(B1:B10)'
# Natural Logarithm and Exponential
ws['D1'] = '=LN(A1)'
ws['E1'] = '=EXP(D1)'
# INDEX and MATCH
ws['F1'] = '=INDEX(A1:A10, MATCH(100, B1:B10, 0))'
```

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

## 5. LibreOffice Calc Solver via Command Line and Python-UNO

To automatically solve the HP filter objective function directly within a spreadsheet file without manual intervention, one can invoke LibreOffice Calc's Solver engine via a headless Python script using the UNO (Universal Network Objects) bridge [cite: 40, 41, 42].

### 5.1 Invoking LibreOffice UNO

LibreOffice must be started in a headless listening mode:
```bash
soffice --headless --accept="socket,host=localhost,port=2002;urp;StarOffice.ComponentContext" --calc
```
From Python, the `uno` module connects to this socket [cite: 41, 43]. 

### 5.2 Programmatic Solver Implementation

The `com.sun.star.sheet.Solver` service provides access to LibreOffice's optimization algorithms [cite: 44]. The following Python code demonstrates how to bridge to LibreOffice, configure the non-linear solver for the HP Filter, and execute it:

```python
import uno
from com.sun.star.beans import PropertyValue

def run_hp_filter_solver(file_url, sheet_name, objective_cell_name, variable_cells_range):
    # Connect to the headless LibreOffice instance
    local_ctx = uno.getComponentContext()
    smgr_local = local_ctx.ServiceManager
    resolver = smgr_local.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local_ctx)
    ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    smgr = ctx.ServiceManager

    # Open Document
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL(file_url, "_blank", 0, ())
    
    # Get Sheet and Cells
    sheets = doc.getSheets()
    sheet = sheets.getByName(sheet_name)
    objective_cell = sheet.getCellRangeByName(objective_cell_name).getCellAddress()
    variable_cells = sheet.getCellRangeByName(variable_cells_range).getRangeAddress()

    # Initialize Solver
    solver = smgr.createInstanceWithContext("com.sun.star.sheet.Solver", ctx)
    solver.Document = doc
    solver.Objective = objective_cell
    solver.Variables = (variable_cells,)
    solver.Maximize = False # We want to minimize the HP filter objective

    # Use SCO evolutionary algorithm for non-linear HP filter objective
    # Alternatively, use "com.sun.star.comp.Calc.CoinMPSolver" for LP
    solver.SolverEngine = "com.sun.star.comp.Calc.NLPSolver.SCOSolverImpl"

    # Execute Solver
    solver.solve()
    
    if solver.Success:
        # Save changes if successful
        doc.store()
        print(f"Solver achieved objective value: {solver.ResultValue}")
    else:
        print("Solver failed to converge.")
        
    doc.dispose()
```

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

## 7. Complete Python Integration Module

The following code synthesizes `openpyxl` usage to create the macroeconomic baseline matrix, apply the PIM, and construct the HP Filter cells [cite: 32, 45].

```python
import openpyxl
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

def build_macro_model(output_file="Georgia_Macro_Model.xlsx"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Macro_Model"
    
    # Headers
    headers = [
        "Year", "Y (Real GDP)", "K (Capital)", "L (Labor)", "A (TFP)", 
        "Trend_A (tau)", "HP_SSD", "HP_SS2D", "I_Base", "I_Shock", "K_With", "Y_With"
    ]
    ws.append(headers)
    
    # Calibration Parameters (Georgia context)
    alpha = 0.45
    delta = 0.05
    lambda_hp = 6.25 # Annual data [cite: 29]
    
    # Mock Historical Data (2015-2025)
    for year in range(2015, 2026):
        # Using dummy data for demonstration
        ws.append([year, 100 * (1.05**(year-2015)), 250 * (1.04**(year-2015)), 2.0, ""])
    
    # Write Formulas
    for row in range(2, 13):
        # Solow Residual A = Y / (K^alpha * L^(1-alpha))
        ws[f'E{row}'] = f'=B{row} / ((C{row}^{alpha}) * (D{row}^{1-alpha}))'
        
        # Initialize Trend_A with A (Solver will change these)
        ws[f'F{row}'] = f'=E{row}'
        
        # HP Filter Sum of Squared Deviations (SSD)
        ws[f'G{row}'] = f'=(E{row} - F{row})^2'
        
        # HP Filter Sum of Squared Second Differences (SS2D)
        if row >= 4 and row <= 11:
            ws[f'H{row}'] = f'=((F{row} - F{row-1}) - (F{row-1} - F{row-2}))^2'
        else:
            ws[f'H{row}'] = 0
            
    # HP Filter Objective Cell
    ws['M1'] = 'HP Objective'
    ws['N1'] = f'=SUM(G2:G12) + {lambda_hp} * SUM(H4:H11)'
    
    # Projections (2026-2033)
    shock_distribution = [1.2, 1.1, 1.0, 0.9, 0.8, 0.6, 0.5, 0.4] # 6.5B Front-loaded
    
    for i, year in enumerate(range(2026, 2034)):
        row = 13 + i
        ws.cell(row=row, column=1, value=year)
        
        # Excel TREND function for baseline projection
        ws[f'B{row}'] = f'=TREND(B2:B12, A2:A12, A{row})'
        ws[f'D{row}'] = f'=TREND(D2:D12, A2:A12, A{row})'
        ws[f'F{row}'] = f'=TREND(F2:F12, A2:A12, A{row})' # Extrapolate structural TFP
        
        # Baseline Investment and Capital
        ws[f'I{row}'] = f'=0.25 * B{row}' # Assuming 25% I/Y ratio
        ws[f'C{row}'] = f'=(1-{delta})*C{row-1} + I{row}'
        
        # Shock Investment and K_With
        ws[f'J{row}'] = shock_distribution[i]
        ws[f'K{row}'] = f'=(1-{delta})*K{row-1} + I{row} + J{row}' if i > 0 else f'=(1-{delta})*C{row-1} + I{row} + J{row}'
        
        # Potential Output with Shock
        ws[f'L{row}'] = f'=F{row} * (K{row}^{alpha}) * (D{row}^{1-alpha})'

    wb.save(output_file)
    print(f"Model saved to {output_file}")

if __name__ == "__main__":
    build_macro_model()
```

By unifying institutional definitions from the PWT and IMF, applying strict mathematical derivation to HP filter parameters, and deploying programmatic execution via `openpyxl` and LibreOffice UNO, researchers can construct a highly robust, automated, and scalable framework for analyzing capital shocks in small open economies.

**Sources:**
1. [rdocumentation.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEViVHaoRWUDvHkY9sLg_fpHY7T0LrkwcwYw6bMhH31R2sv9RGG-to4IdkVVNxTPfjespZoeu-Z6te9X7oMwMc7bLbSdyl2QmUOM-76hJroUhdGDYDUY7LevxlXU8Qezb12ERvyQCE50SEtb8Qqb-Ipa6XCMzDNhe63ICSNx3cuHKy39g==)
2. [stevens.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHrKVwn7rdprVW9iOqVbHHPRoHK466UXqNWz_zLyjXRSxuzxusVJ0bv6rOHhyI14R9ulmgzEfxvqkMLzUysCItys80z_9enWc9ehZ2FFfDyAnR2pyNmI3QgTH70bRQRzzS62_4=)
3. [pinggu.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEs_5ZCUPTdL0FIJQb4vR1HIkKmqk7FDsf3An8s-S4weWDCiV7mdSyaUGx6WCOA3nt-qIJMWldkUqsn6mfg7LVNCIRIx5aYQHCRyLcmkJ2qUY_jHq6J7Pc-vWZOJC-ZrPVuEETdgA==)
4. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCSAMKEsAFaQfDb_1poWauwkR3yex6eZjaih2DNv9P8LwfCDU1xIH8D2iKpXBpBHOn83N5ETgaumB0MutSEp2vkNz1LsB8L6EP2RNp83wGbfQ1q7O3R8bTTOVosNm-7BbXPQI4Pc3XsHtye7yJD6DQhec-VYs=)
5. [rdocumentation.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-X6A--SwO0XINvNpc3ers1uTKRQjkjQUB1sb0HuamMv_-BX-UquMz7mldmIYaAQIamZgn56rFJdvV0lp_MX-frSvB1NUWnDtXj-2qUc-3c-N3DLbHqgsKXPDerNM_ThmMmiTRl6N7xkSHa8OBQ5e_8thBd5m3P9-YvZ-1PaRc)
6. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGrY0rQ5J3WdGb97zAulIZRfVzdeZU89Ms6cREZOc56D7hZ2kPuD24xjQ4j1EluV0ZuX-ySRSphNi0IgVwYr6aPIEd4ycYBlyPwHYrKOclvH26_ZDj3roAGTMRhfkrkTO6xrW-U1w==)
7. [rug.nl](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGFwCisGoSb_ZVOfyOZbb0plsL6CHM2OTqnWDjy-aQOSoi4nHHN5a7GuSMFuTaxFQXn9x5IxW-qD5Hy6oXjpG4iKlnosaNsXkxkL-F1_S2am2UhNwMm8Acrlq85sWftZpzgDORHNueGR_CTt4k76SyxhO9reEUfERbEiw==)
8. [imf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElZ9aBBhyfM6cGZ9tTetcIpDLEkoo-NwmMYMOEpPXHEVqoqVXuMyG9yRdQymbPEm5IQteQsIVCL-k6DYf00QZs9UewJnXRUn3j3seI9hnzeMr3XBD15kU_UQ5nVDVHk-P2H3tQM5S4UntGDSB5JsOUeqjN-2DL9UUWSBiMeK3ogs0F)
9. [imf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFmbs8to7tTieoaXlB7D8zqsa7QBwmDj82KSpVIlMjtF8Hd4LLHC3GKsGQsj_Orz-z4Q5k3oQHim16-j_OmBmMfck8n4HrWZH4RcpdTuzDiyz8VVPhM_jENTGkI_mp4B4bIBg==)
10. [imf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2TZlXng5-WcUWihC-2JFpd0CsC0nxNaq7Bte-Rvfw6rBaUFsFJtvByZQddMuL17ntG3Elkx6lwMkAWgUYgQuB3GH5YcL-9yL3B61lgjyMKP1UE5EqBWnT58mxX1jPUMWdWcp16CaylDBLsxsCNuFJlQwOy3GDhC33w27zw1hLCGcBJTbLELzKXQoBzJyCGSlRrlCuo0RVAm6mRlZ0B3CZlnP23pcXw8vnU2J-xfUXYQcsYr0LrMKFvOA=)
11. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAyWYjWdz-pJKm2tb6WwAcD2Tee_hguyAIqltxBZLUGcGYnlduIDjsvEjRY9SDUZcxZy5PPBQiT1gvEhSavCQ4LsFlJV8L0kc3_HA_HLQJhk9_YIn99cTKB5VQwAy7fcvRIHJ-25PWCUMofydNSrimx7TqzLhAZV-k)
12. [johnsnowlabs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFdApIpIwcASR3Yl0-3dXb-y35eWxYz5dXaCTuisemJyueAlwSTWFZrpL9R5cx3BifshFAF7RfpKnwAZomTPKMGnK1_Pn6ZUyrcpz-EakITrupBRIX-xBb2fJCGtV9ss9eMfFjuXyWsHuM8Q9ajAUZQt_avamUEPSZLJSRJRJnOB8C3MA==)
13. [datapolicyanalyst.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnwUY45F5gkPNmW5Stmr5Fv5K1ppJyJmer5ipE21jO54X3wDO7R6P7PICbdghjV_EwFGfw1Y47sqC9qbPie1Cn19PCoK4tVnhZcE5JX39UBYdSFmH3py4AC6e4_ZnOHp-j2_VMfSTdV-3thqyzrSZPqWn1K2omOIxDKqoVAOwiBAC4cHJzTZPxXN0dQaFW7lZk7ZhDajQPeR7LdXtPaHKEo6osP7ojzbI496HoR73fVsg=)
14. [europa.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdV8TDKOBTCgVCdRj8BHzItLFi3AuYBLGr7SEGz1c_u-miJljoIqbpqn80G2cLhXxowQVB3IhiiOX3OekYvWKW-01JR-BAoAgN0G0XvldfdkaoWTCG2aQ0x4pOlwprTJSwWfu7uEft2C-5s27LUFAj3StnGsn8ZvvdEcuRzrPIkVe6jALuQ8zRNIiQZ9NVZsHlIuUwMd88uPFch6SfVWy-HOpMGP2IYb7Rcgey_NPYY-bVdVtIn06Tpde5PZZsma6YWUnRmoPxJOXsb8rs_Ds3)
15. [europa.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdtjI-QrdjwMXkYV6ZP_yJOUuLgdpXCGtZXgCCfRWMDNUp4mBF-XO7ezvusEP9IH70slxLAg801NyMPuLXzBUB2dB3TwNyBISpXGc28P0mVR0ez7vbod23IyIzU4PbptLgxlc=)
16. [sdmx.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFBiePTTMlV6J1FzKyBk9njQg492l_Y7KWTcKKm_WOQfK6P5QIzs52Oe7ibMmhKaltjb0F5bnO6CaQ7YPTePkFCw-rpTacm5L1mrcGZ93u1OK_hsFy2hWZ676z9wHZqUoeiga0d-bFnmqTupihyijBx4CXxWyUjMshRFrx8UV3LAD7kIUnRE1AoRqhtO9PDwDM0GZplcr-LiRj-N6djC6vuIzFx4BtBqBkxb0wiLTe-mg3k9SJm)
17. [europa.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEuRQZVJpdqRLEyb_t6vWA2-Kv3I56MzsQqgs862ri1OKNzmubHqRX-Qmpcfyvf36Y5tDLPqQYFzd7ShCZUHu41F0-Ulp25wX0N4eh7D7Bjugq5vgKSqkJLQBm5gWXjaYlGiyvYmBlCAPVPWufYBLV7WqY33X5t6VJ69h1WT3iwVweEIUgup3FoEgUoOSb_0Ifw)
18. [europa.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESlLMgw_w4WecdayUvnNO0P6Gcu0HaPGjB2bSFQpFmjFTW5KgfscgCjsss9ErouRsxZbfSKeGzXru_qUM2sN-Vl1NxDT-WpCTlb0yawXoCad3Aja9vtZkl8Hkgy4leIflZi4u4Se-TGbKEjfGa3ba_65WJCTSG_xFExcH6rSlmN8KCiFNLs6i3wRMtvPDm-f18U1hbsa2sWyvZ2IaZeQyGONpORxwuHQe9ulnLNq2z88QHRVNe-JEiyJjL4pCWPFq-KaaIVsps2AxKKK-JknKTzZbtVnIEqlvYQDsqiWlqUjVfql4AYJqM_U2UphtvPY509HVabakCIayObZOofSVypRZxer5h7oM47WtAj04f7GC3WavR8zpzsVANtrDvN210HvzBuDZx8or1aAcaq36hNyWkPInVLat90LFN8CS6TtgEgu0JT-eoXf3zlahadK-GR7TKJlXj7kU=)
19. [ceicdata.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFARH4apA2HgBP_vVadIZjSqKnVC5VkNmEGlcb5eIXMGiCg0jYmYGNEMgQ-gYdWJdQ2ZqX4wJTVuQ9KIGA2BXb8s3IPJ-3w92fiNpagTE2AJ7f6rOv0iLjlWPLWqMp6Oin-ZsEVL2j66IwzoW8WngU9btpUe2WXU5V6J6FtwH1A6mfaDV6Gqi3JVpdF3XxnvFDBoEgL0eqaSEQE0e9tetuobAaolhS-1Wlxqw==)
20. [scispace.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_snRv1ykSyDz-Nf_7TJSLk5LafuuYfV8vVbiTZfcLY1vGIAw77ih4A9_vlUeLRGJhuGSQH-JsG5slr8izLBJyI1whqOdIJbMBBVq03h7M28pEKa4qg7oo0dCekJHBZHFTZ4a_KCuqAWnfOCb6zyMiq-vb0tPCz4fHssDz_D3bil8BCjEUrXIKwcyrlels)
21. [review-of-economics.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH8_gKbW2wj11bxIX1tx0_1FcdvmfJ0FnyReWEGWKy4InUklnhh1q3TzYfxsD5ny4pRIILmfnS4RDQtXtPFGdCuevgZdY1Htlbu44kzNx2EU0IMYIsv6fk_BHMdPUpBZKYdXnM_HcvtAvFw_969hDSfEEqfcqR91Wrbm-FLG6vyEg==)
22. [mnb.hu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHe2rn-9NvNbAyfFeAdinvmhmqMKYzZHzvG7ZSlDYjG3gAzX1uJHedXtzAyLMcAznodrBRSIIZ0VAO-aamnOpIaosoJgLmEsZILLH_Nh-XtEviJrrz-gppqycMAHpIcMA==)
23. [rpubs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEJNzpdxbfOY0HR248jtdEzA6yOTa-WkyVjxl2nvFfILhJ2oCotODCHU_p3FUcg8PCvkMQV3UqE8oOcMbkfhSFlcAK0PBPYE2TwkE2SAiUvjERgpBNO)
24. [mathworks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHoN_vpJ5ovDxpPoVdTvi9Fta90mDZjRpNeigKiLjN-rUQHFCfMwGx9W6DVNeTxz8LiYi1BOJ0PuFIXUAednCxZCq0ReZKC2c6lQk6DAod9bPBR7-oq8eLCjQXjG6W8usJuAbGniXrN)
25. [euifis.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1oyV42gI_hVOFX3VwD0JneQbC0Ge4IIAxJfwyxDZLWXi7KHsyuGdHZXnaTGK07cmjvb7QpV0WlT_HWXeDlSESitwiDMT1RakPRPyr_pfLpWUnWCldXVw_5gleOmZWwmm4DS4=)
26. [crei.cat](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH3NOISG7wldCiz-9vLR2tfhT2_K3olayCMtwBzXwkeu9CCv50xG0IZjinuC441UVt0ee43DgEC7TQFSw2BG9RF0tNkpLFqvM-R1Ub-rE9CicuZwGeEKA3g9sCFE2ordvyo7jWDGY4hIWE=)
27. [uni-muenchen.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8jZ_1HO16ignMy-5g8jLIv79K7I9L6M4G8TWHRcPSnX5UixlPkIJVIMHcxZ3VURyGc9P-ZS91B4zYAYqvXkLoUJdInnoAr7ksfRwShQwa0U_JjGUqNcBzfp9zdCIyAS91a8Zv521l6ZOxK-vt0fb6RrE=)
28. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEUbiDnf6qGOGL_jE1rQCvB5e1Q_KkgxevfTqhcYyXuOooaj_Bkaew32hL20nLjamorjRNWmnwQLAkWrmloSjCYKziJCk_gv94-Nmn6NBXk5a8eawmhx1qo2x2ZrhWZAQvxdS7pTq2PF_vUtbbn-izxRZFAJjp-702AWpyec9U2nn9dK0gxHQ==)
29. [uchicago.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH79V7qPf4XUmyFPthVEVsrz2rPEd9seE4MqAgl02nhL0KHiMVefd_kMig-a0ViTsZ7GaUqb09E9fev1FNFnsz_Gjy40Spknl6DyPPkUTvHbrXoNQmhJPDkj4wy023v3z2Asb7df86lGyA6aRIsUk-9D4RJ17NN)
30. [econstor.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaj4d1c-Q3UXk4BMIq-CwBYOLtv5MQFjdXWJuHW2HBgpC7ANksI4rLta9wnnRIfHse8LpjhVr0XNYiDmOoZr1d5rUGtcKIWhSxE43qecNj6S1H_IJGVdHHlXgUrSt9pDvUdft5IJNi7M8tNl8CJavGJRhGtUGt)
31. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF8QI8Qokd0lYUlYOrlgYBC0f3PytF1PiZkGqlMitjfnUX1guSGozH4Ct8M1jWhooU-KsmDbXWzWUzC23B94YDIHseaHWv-0CeGQdfe2KgPhP_dZyWboQ==)
32. [softwaretestinghelp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqxykhXOmKEmi_lJDKqAg6CCLHu3FNRcrqRKA1ABaxPRb5_XzIsVdLDLe8fXFvhqVJulqxIroZVdst7Y8bWRHzfxsvpmJq_ulP98chkNa2GwWDeTW9y7OoQoPF7Go487aQ779X8reJkjavwqvFfkxH3AmW)
33. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH368M0DSZTsGTyj5p3_97HtHgCoWrbuVgDQdo3chNXLHgtt8NO18oH52XTNUXk6Wlsr9y4aDwXFhn9zon4eNLp71QOXNSTvvCQwZENLW2hdiswGNVweiAt0TEXtKgxP4DaN-hrH-97cm0st3PAexPaBA==)
34. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHiUafre5JGrWDVO106Ag9OHadvuyNT5kvd92Fhd5bRo47zR8laohdzNBUFikr3_AWifj71HfHH5jLR4thCllv6fFqcBJT4Wrp6Jm-gMq4ZX0apB4eNe-JGKGinbOi5GBQFLduxSKXqFAhksEI=)
35. [corporatefinanceinstitute.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF69bp1Mg-EOc8hYulBw1VD7CsJtvUbFULjlD_gp7XPL9E9C4w7IvZlMuAJl9Z8o897EccYOh6NZjcBSWI4ZEOBh0P12HI8zrOmQdBNfctAAwHn9FSQm8BDnNRwCutZdm41Zlk9rMNPJfOOKiVSrGZSc5oQGXrKD8rqgxBndu-CtleFY0e72dRIJRQf4Nc=)
36. [ablebits.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOvQL8sSygTA3IgVNy4Jzd4AFj33p5dkapcBW48GoYWOHmDB3KdqGNezOKUrN5nAYJ9XvYiDVWRZWD4oS8GHz6Zda_Eoy3_ZL2W-GFr6K8TJ0dR7B6pfjzPmYq-HJePNF6fU8mlsyNi8BYSGwsc_xmsqMXtYmltA==)
37. [microsoft.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdEbGBR0Ch4gtpjeCngAx11hJEb6abJJ0u_RlNdgvAN6G7jXh6tV-eR-Ennz4bWFh1IamWLXx8M3jdWwYWr_bWFEBjUQIDVo1y2Nh1cUOONHpahsQBrXtY_BcFHe-OOuBQaBKCN9ooO9oAYfz3G6ejdoSpJ6tvYQZqVgc2ev8c7H-zckQynAsj3-VhdmKqaPJffgx5)
38. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEbIa-vvNgJEuePrco7i9mphVNOo-iSol67HXDEJAYwBt-brQZ0UfS6F6L9jJXrg-wa083-MMesTIFfP5OtYyJ-XThnz4cPTUx4y8HYgkwaHJlyLJnMZXmRcw9xtOJ6qLBtycXlgymtVTXQ8qjyG9WpX1HdrC3tcosq8yIV7rmqMufADBZBc6isW6THG5DNrSZXw6mst2ClYQDap9E2_3r1JkDoPW7ZZolOV1Capnn4lFdM-A==)
39. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFjuXPbZ8tA3K0lKK6FxKKCcJ3MpNmsufZOj65r3TZx-7n1NZiGN8ckvAPgmbJZcHg3-PLVrp_xSAL6FYTb2I0IONhP-TZfFOccYe9LgkvqfBKJUFIz79amXzeT73LNgugFY0JBnz3xQAlyDMlzIdT34jgcyuaEPYQhoXew46vm7blxOzOcV7Uo6rdwWKc=)
40. [pythonhosted.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYYhbcsCzcGZl3TR3DMUcp531RCtIbAaDvW_N9mCpiyA-Sn-iefBfeFRQOVOAhWb8ZZcPoRgJRpsuG-tvzTaRNCH7MYMFVQErG6K_wODRbnKT7eV7s8fAOmXTtRHZFEZsDzZpl8sEp)
41. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElAG_JnbTpnVVfiDPKeTZXpGwwoZPA3ZP7hIffLRzJN_v8NkHzshA3iKBWxTqvctVYkzSbMJ0nbNVhoDX1PBVRzQPRLVIe7cMkqrWMUwC5qBNQpGdYR6-Oli36MtbaVXOPPh-HnWNGC1BgGOA-g3x4cDqIdmhJsN_gpL8nCUo3kiyWLIlWrRd-fOOmr1ThxIDaiQp3944IWVAsdwVlISjsvR5JOhCFCMbQ6q3juzbkKXp-Xw==)
42. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnhh8Ch7VtaNSWDAT6las6voEfHdv4GM3bD8NJ4oMQW-Jzypi0nFerNrL8noxFkjf91sZ9RgpUSB27VC4N-qwmBva1ROGQa3SYKrUNUCwDFowWuMrlk8sP3zQHuTnKA7MvgpqZ_lhDFl0q9z-Bj78IzrXl3a9Ds1jyc32lPHravcQcmj6yiQ==)
43. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXl8Fh81d5uCY_MIA3ar65riUbA_8x_9fc-xYHS73nWFVcgkUhi1lvSNIH3_fP4KrUKzDgnGWmJxkG87rHSm3Ikio3XTPUqHc1NOfhUOPLh_5K30vR4pfHR2zzkIP7hXGybRlN0TGwxK4vVTrCE2_GsJu6w4gIRsMPxsOlzVejWcq5px9dwIhpzJmr7Kkh5bBeJXKG)
44. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_qy6i58rleDfrkJUS3TQyHc6_WDyVHInGYFHH8aqmPRCPwPJg47ZWYyH3U58o5IMPjXhrnPLYZDGLoBF9cnpOu67uKrUFvqKjCCiITgLuAqq8Un7uf7XpAyIKpzEet8WMhymfPySqJVJcOt9xb-Q_run6zrTSsDFk5WpfKAQ0g96KTAECgqIOHcU=)
45. [topcoder.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsnYeGMGi-YSyT2xJyXndYzIYSoqTt2G4Wy-l0PzCRR4lLS1T3sO9gTynWEs3VcUMjY18iw5F3t7gxGjIglqTMPVxxxPogWpYRkvgYuUp55lQiI4ZckkE3hnnfoG8Y31JuInWmrhwmWd_Z9nYgpen61Bf_9Y2mtZz16-0etyAa4onWk1kMVhU=)
