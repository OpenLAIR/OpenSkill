# Macroeconomic Demand-Side Accounting Framework for Estimating Investment Spending Shocks in a Small Open Economy: A Methodological and Computational Approach for Georgia

**Key Points:**
*   Estimating the impact of a large-scale investment project on a national economy requires carefully linking international macroeconomic data with domestic statistical tables.
*   For a small open economy like Georgia, standard economic multipliers are often reduced to around 0.8 because a significant portion of spending "leaks" out of the country through the importation of construction materials and specialized services.
*   Infrastructure megaprojects do not spend money evenly; they typically follow a "bell curve" over time—starting slowly during planning, peaking during heavy construction, and tapering off during the finishing phases.
*   Automating this complex financial modeling using Python (specifically `openpyxl`) and LibreOffice allows economists to rapidly generate and test multiple hypothetical scenarios without manual spreadsheet errors.

Evaluating the economic footprint of a massive $6.5 billion infrastructure investment over an 8-year horizon demands a robust demand-side macroeconomic accounting framework. When an economy is relatively small and highly integrated into global trade, as is the case with the Republic of Georgia, researchers must account for the reality that a large influx of investment dollars will not circulate entirely within local borders. A substantial fraction of the capital is diverted to foreign suppliers for imported machinery, raw materials, and specialized labor. Consequently, accurately forecasting the net addition to the country's Gross Domestic Product (GDP) requires extracting structural economic data—specifically the Supply and Use Tables (SUTs)—to measure this "import leakage."

To operationalize this assessment, economists combine historical macroeconomic databases, such as the International Monetary Fund's World Economic Outlook (WEO), with local statistical data. By projecting baseline growth and inflation parameters, analysts can establish a baseline trajectory for the national economy. The exogenous investment shock is then mapped over an 8-year spending profile, converted to local currency, adjusted for inflation, stripped of its imported content, and finally processed through an economic multiplier. The final result illustrates how much the project will boost the nation's baseline growth rate year over year. Modern policy analysis further demands that this entire computational chain be automated, relying on programming tools like Python to manipulate complex spreadsheet models seamlessly.

## Introduction to Small Open Economy Investment Shocks

The injection of large-scale capital into a small open economy triggers a complex chain of macroeconomic effects. Unlike closed or highly diversified large economies where domestic supply chains absorb the entirety of an investment shock, a small open economy relies heavily on imports to fulfill the intermediate and final demands of large infrastructure projects [cite: 1]. Therefore, classical Keynesian multiplier effects are heavily dampened. 

To systematically estimate the net impact on GDP, analysts must construct a demand-side macro accounting framework. This framework reconciles external macroeconomic projections, such as those published by the International Monetary Fund (IMF), with internal structural data provided by national statistical bodies, such as the National Statistics Office of Georgia (GeoStat) [cite: 2]. This report details the comprehensive theoretical methodologies, mathematical formulations, and programmatic implementation patterns required to build an automated scenario analysis tool using Python's `openpyxl` library. 

## IMF World Economic Outlook (WEO) Database Structure and Data Extraction

The IMF World Economic Outlook (WEO) database serves as the foundational data source for establishing the baseline macroeconomic trajectory of a country before an exogenous shock is introduced. The WEO database provides harmonized, cross-country panel data with standardized subject codes [cite: 3, 4, 5].

### Required Variables and Exact Subject Codes

For demand-side macro accounting in Georgia, the baseline projection relies on nominal and real output measures, alongside inflation metrics. The exact WEO subject codes required are:
*   **NGDP**: Gross Domestic Product, current prices (National currency). This represents nominal GDP measured in the local currency (Georgian Lari - GEL) [cite: 3, 4].
*   **NGDPD**: Gross Domestic Product, current prices (U.S. dollars). This represents nominal GDP converted to USD at market exchange rates [cite: 4].
*   **NGDP_R**: Gross Domestic Product, constant prices (National currency). This is the real GDP, stripped of inflationary effects, chained to a specific base year [cite: 3].
*   **NGDP_D**: Gross Domestic Product deflator. This index measures the changes in prices for all domestically produced final goods and services [cite: 2, 6].
*   **NGDP_RPCH**: Gross Domestic Product, constant prices, percent change. This is the annual real GDP growth rate [cite: 5].
*   **PCPIPCH**: Inflation, average consumer prices, percent change. While the GDP deflator is broader, consumer price inflation provides supplementary context for domestic price stability [cite: 3, 4].

### Mathematical Projections: GDP Deflator and Real GDP

Because the WEO database typically provides projections only for a medium-term horizon (e.g., up to 2028 or 2029), long-term infrastructure projects operating out to 2043 require robust extrapolation methodologies. 

**1. Projecting the GDP Deflator:**
To establish a stable trajectory for domestic price levels, the GDP deflator is projected forward using the average growth rate of the most recent four years as a fixed anchor. If we denote the GDP deflator in year \( t \) as \( D_t \), the average growth rate \( \bar{g}_{def} \) over the anchor period \( [T-4, T-1] \) is calculated as:

\[ \bar{g}_{def} = \frac{1}{4} \sum_{i=1}^{4} \left( \frac{D_{T-i}}{D_{T-i-1}} - 1 \right) \]

For any future year \( t \ge T \), the deflator is projected recursively:

\[ D_t = D_{t-1} \times (1 + \bar{g}_{def}) \]

**2. Extending Real GDP (2027 to 2043):**
Similarly, real GDP must be extended assuming a constant growth rate. If the WEO ends its reliable projection at 2027, the real GDP for 2027 becomes the anchor value (\( Y_{2027} \)). Assuming a conservative, steady-state long-run growth rate assumption \( g_{lr} \) (for instance, the WEO implied growth rate at the end of the projection horizon), real GDP for subsequent years is calculated as:

\[ Y_t = Y_{t-1} \times (1 + g_{lr}) \quad \forall t \in  \]

These extrapolations form the "Baseline Scenario" against which the investment shock will be measured.

## Supply and Use Table (SUT) Methodology for Import Content Estimation

The fundamental constraint in evaluating an investment shock in a small open economy is the "import leakage." When $6.5 billion is spent on an infrastructure megaproject, a substantial portion pays for imported steel, foreign engineering services, and imported heavy machinery. This capital leaves the domestic economy immediately and generates no localized multiplier effect. To estimate this leakage, economists turn to Supply and Use Tables (SUTs).

### GeoStat's SUT Classification and Base Year

The National Statistics Office of Georgia (GeoStat) compiles the national accounts under the System of National Accounts 2008 (SNA 2008) framework [cite: 7]. Currently, the base year for Georgia's constant price calculations is 2019 (updated from the previous base year of 2015) [cite: 2, 7]. GeoStat publishes detailed SUTs at different classification levels, commonly utilizing a 38x38 industry/product matrix (based on NACE Rev. 2) which provides a granular view of the economy [cite: 8]. 

### The Structure of the SUT and "Column C-H"

A standard SUT framework consists of two matrices:
1.  **The Supply Table:** Shows the total supply of goods and services by product and by industry, including domestic production and imports at basic prices [cite: 9, 10, 11].
2.  **The Use Table:** Shows where these products go. It tracks intermediate consumption by industries and final demand categories [cite: 9, 10, 11]. 

In standard spreadsheet representations of Use Tables (often reflected in working files as specific column ranges, such as "Column C-H"), the columns denote the components of **Final Demand**. Typically, these columns represent:
*   Final consumption expenditure by households.
*   Final consumption expenditure by non-profit institutions serving households (NPISH).
*   Final consumption expenditure by government.
*   **Gross Fixed Capital Formation (GFCF)** (the critical column for investment shocks) [cite: 11, 12].
*   Changes in inventories.
*   Exports of goods and services [cite: 11, 12].

### Formulating the Import Content Share

To calculate the import content share of investment, we must link the supply-side imports to the use-side GFCF. Because a standard Use Table often does not perfectly separate the imported versus domestic origin of a product used in final demand, analysts apply the **proportionality assumption** [cite: 13]. This assumption posits that the share of imports in the total supply of a specific product is identical across all categories of use (whether it is used for household consumption, intermediate input, or capital formation) [cite: 13].

Let \( S_i \) be the total supply of product \( i \) at purchasers' prices, and \( M_i \) be the total imports of product \( i \). The product-specific import share \( \mu_i \) is:

\[ \mu_i = \frac{M_i}{S_i} \]

Next, we look at the Gross Fixed Capital Formation column in the Use Table. Let \( I_i \) be the amount of product \( i \) used in GFCF. The estimated imported content embedded within total GFCF is the sum of the product-specific import shares multiplied by the investment in those products:

\[ M_{GFCF} = \sum_{i=1}^{n} (\mu_i \times I_i) \]

The overarching **Import Content Share of Investment** (\( \theta \)) is therefore the ratio of imported capital goods to total Gross Fixed Capital Formation:

\[ \theta = \frac{M_{GFCF}}{\sum_{i=1}^{n} I_i} = \frac{\sum_{i=1}^{n} \left( \frac{M_i}{S_i} \times I_i \right)}{\sum_{i=1}^{n} I_i} \]

In a small open economy like Georgia, \( \theta \) for infrastructure capital formation is often quite high (e.g., 0.4 to 0.6) because heavy machinery and specialized materials are largely sourced from abroad [cite: 12]. 

## Demand-Side Macro Accounting Framework for Investment Shock Analysis

Once the baseline data is established and the import leakage is quantified, the actual economic shock can be modeled. The parameters provided for this analysis are:
*   **Total Investment:** $6.5 billion USD.
*   **Exchange Rate:** 2.746 GEL/USD.
*   **Duration:** 8 years, starting in 2026.

### The "Bell Shape" Spending Profile

Infrastructure megaprojects do not distribute capital evenly across their lifespans. The spending profile typically follows a bell-shaped (normal) distribution [cite: 14, 15, 16]. An 8-year timeline includes an initial ramp-up (feasibility studies, environmental impact assessments, early earthworks), a peak in the middle years (heavy structural engineering, material pouring), and a wind-down (finishing works, electrical integrations, commissioning) [cite: 17].

Standard empirical allocations for an 8-year infrastructure megaproject modeled by multilateral institutions often look like this:
*   **Year 1 (2026):** 2% (Planning, permits, mobilization)
*   **Year 2 (2027):** 7% (Site prep, foundation work)
*   **Year 3 (2028):** 15% (Heavy construction scaling up)
*   **Year 4 (2029):** 22% (Peak construction phase I)
*   **Year 5 (2030):** 24% (Peak construction phase II)
*   **Year 6 (2031):** 18% (Substantial structural completion)
*   **Year 7 (2032):** 9% (Finishing, system installation)
*   **Year 8 (2033):** 3% (Testing, commissioning, demobilization)

These percentages sum to exactly 100% of the $6.5 billion total [cite: 17]. 

### The Demand Multiplier in a Small Open Economy

The multiplier effect measures how much additional economic activity is generated by an initial injection of spending. The standard Keynesian multiplier formula is:

\[ k = \frac{1}{1 - MPC(1-t) + MPM} \]

Where \( MPC \) is the marginal propensity to consume, \( t \) is the tax rate, and \( MPM \) is the marginal propensity to import [cite: 18].

In a large, relatively closed economy (like the United States), the multiplier might be 1.5 or even 2.0 [cite: 19, 20]. However, for a small open economy like Georgia, the \( MPM \) is highly elevated [cite: 1]. A significant portion of every newly earned Lari is spent on imported consumer goods (electronics, automobiles, foreign food products). This secondary leakage severely dampens the multiplier effect. Empirical macroeconomic literature consistently pegs the short-term aggregate demand multiplier for small open economies at approximately **0.8** [cite: 19, 21]. This implies that a $1 net domestic injection creates $0.80 of ultimate GDP, as the compounding rounds of spending quickly bleed out through the trade balance.

### The Full Formula Chain

To translate the gross USD investment into an isolated real GDP impact, the following computational chain is strictly executed for each year \( t \):

1.  **Annual Allocation (USD):** 
    \[ Inv\_USD_t = Total\_Investment \times Allocation\_Percentage_t \]
2.  **Conversion to Local Currency (Nominal GEL):**
    \[ Nom\_Inv\_GEL_t = Inv\_USD_t \times Exchange\_Rate \]
    *(Where Exchange Rate = 2.746)*
3.  **Deflation to Real Investment Shock (Constant Prices):**
    Because the investment spans 8 years, the nominal GEL value must be deflated using the projected GDP Deflator (\( D_t \), indexed to the base year).
    \[ Real\_Inv\_GEL_t = \frac{Nom\_Inv\_GEL_t}{D_t / 100} \]
4.  **Net Domestic Real Shock (Adjusting for Direct Import Leakage):**
    Applying the import content share \( \theta \) calculated from the SUT.
    \[ Net\_Real\_Inv_t = Real\_Inv\_GEL_t \times (1 - \theta) \]
5.  **Application of the Demand Multiplier:**
    \[ Real\_GDP\_Impact_t = Net\_Real\_Inv_t \times Demand\_Multiplier \]
6.  **GDP Impact as % of Baseline:**
    \[ Impact\_Percentage_t = \left( \frac{Real\_GDP\_Impact_t}{Baseline\_Real\_GDP_t} \right) \times 100 \]

This final percentage represents the percentage point (pp) addition to the baseline real GDP growth rate for that specific year.

## Scenario Analysis Structure and Presentation of Results

Sound policy analysis requires stress-testing assumptions. In this framework, we define a structured scenario analysis to assess sensitivity to the multiplier and the import content share.

*   **Baseline Scenario:** This scenario utilizes the empirically grounded parameters. The demand multiplier is set to **0.8** (reflecting the small open economy reality), and the import content share \( \theta \) is rigorously estimated from the 38x38 GeoStat Supply and Use Table [cite: 8, 20].
*   **Scenario 2 (Higher Domestic Circulation):** This scenario tests what happens if secondary spending is retained more effectively within domestic borders. The demand multiplier is increased to **1.0** (a 1:1 translation of net spending to GDP), while the SUT-derived import content share remains unchanged.
*   **Scenario 3 (Lower Initial Leakage):** This scenario tests the impact of proactive local procurement policies. The demand multiplier returns to the baseline **0.8**, but the import content share \( \theta \) is forced down to an optimistic **0.5** (50%), assuming domestic industries are heavily mobilized to provide construction materials instead of relying on foreign supply chains.

### Presentation of Results
The results are typically organized into an output matrix where rows represent the years (2026 to 2033) and columns represent the Scenarios. The figures are presented as **percentage point (pp) additions to baseline real GDP growth**. 
For example, if the baseline real GDP growth for 2029 is projected at 4.5%, and the shock impact percentage for 2029 under the baseline scenario is calculated at 1.2%, the report will show that the megaproject adds 1.2 pp to growth, driving the total economic growth rate to 5.7% for that year.

## Openpyxl Implementation Patterns for Excel Manipulation

To automate this demand-side accounting framework, Python is utilized to programmatically read, manipulate, and generate Excel workbooks. The `openpyxl` (version 3.1.5) library is the standard tool for handling `.xlsx` files. However, working with complex macroeconomic models requires specific coding patterns to preserve existing structures and inject evaluating formulas.

### Reading Workbooks and Preserving Formatting

A common pitfall when opening Excel models in `openpyxl` is losing the formulas and formatting. If a workbook is loaded using `data_only=True`, `openpyxl` strips the underlying Excel formulas and only loads the last calculated values. To build a dynamic scenario tool, this must be avoided.

```python
import openpyxl

# Load workbook, preserving formulas and formatting
wb = openpyxl.load_workbook('Macro_Model_Georgia.xlsx', data_only=False)
sheet = wb['SUT_Calc']
```

### Writing Formulas Natively

To make the Excel file functional upon opening, Python must write the mathematical formulas as strings exactly as a user would type them into Excel. `openpyxl` handles the translation into Excel's native XML formula structure.

```python
# Writing a standard formula linking supply and use variables
# Assuming Column C is Baseline Real GDP, and Column D is Real GDP Impact
for row in range(5, 13): # Years 2026 to 2033
    cell_impact = f"D{row}"
    cell_baseline = f"C{row}"
    cell_percentage = f"E{row}"
    
    # Formula: (Impact / Baseline) * 100
    sheet[cell_percentage].value = f"=({cell_impact}/{cell_baseline})*100"
    
    # Applying number formatting for percentage
    sheet[cell_percentage].number_format = '0.00%'
```

### Handling Cross-Sheet References

In an integrated macro model, variables are spread across sheets (e.g., `WEO_Data`, `SUT_Matrix`, `Scenario_Analysis`). Cross-sheet references in `openpyxl` are implemented by precisely formatting the string, wrapping the sheet name in single quotes.

```python
# Pulling the GDP Deflator from the WEO_Data sheet into the calculation sheet
target_sheet = wb['Shock_Calculations']
target_sheet['B5'].value = "='WEO_Data'!F12"  # F12 contains the 2026 Deflator
```

### Copying Sheet Structures

Creating multiple scenarios often requires duplicating a template sheet. While `openpyxl` provides a `wb.copy_worksheet()` method, this natively copies only values and formats, and sometimes struggles with complex named ranges or heavily merged cells.

```python
source_sheet = wb['Template_Scenario']
# Copy the sheet
new_sheet = wb.copy_worksheet(source_sheet)
new_sheet.title = "Scenario_2_Multiplier_1.0"

# Inject the specific scenario variable
new_sheet['H2'].value = 1.0 # Setting Demand Multiplier to 1.0
```

### Common Pitfalls to Avoid
1.  **Merged Cells:** `openpyxl` can read and write to merged cells, but you must reference the top-left cell of the merged block to assign a value or formula. Assigning a value to an interior cell of a merged range will cause workbook corruption.
2.  **Named Ranges:** While `openpyxl` supports reading named ranges, dynamically altering them or relying on them for formula injection can be volatile. It is highly recommended to use A1-style coordinate tracking programmatically.
3.  **Formula Translation:** `openpyxl` does not validate the syntax of your Excel formula. If you write `"=SUM(A1:A5)"` but your local Excel uses semicolons `"=SUM(A1;A5)"`, `openpyxl` uses the standard English/US syntax (comma). Excel will translate it upon opening, provided the string is standard US syntax.

## Headless Recalculation of Excel Formulas Using LibreOffice on Ubuntu

One of the most profound limitations of programmatic spreadsheet manipulation via `openpyxl` is that Python does not possess a calculation engine. When `openpyxl` writes `"=B5*C5"` into a cell and saves the workbook, the file contains the text of the formula, but the resulting *value* of that cell is essentially `NULL` or cached empty until the file is physically opened in a GUI application like Microsoft Excel, which triggers the calculation tree [cite: 22].

If this output file is part of a broader automated pipeline (for instance, feeding results into a database or generating a PDF report downstream without human intervention), those formulas must be evaluated silently in the background [cite: 23, 24].

On a Linux server (Ubuntu), Microsoft Excel is unavailable. The standard solution is LibreOffice's "headless" mode. However, a common misconception is that simply passing a file through LibreOffice headless mode will trigger a save. To force a recalculation, you must invoke a specific macro [cite: 23, 24, 25].

### Creating the UNO Macro for Recalculation

First, a macro must be established in the LibreOffice environment that instructs the UNO (Universal Network Objects) API to open a file, run `calculateAll()`, and save it [cite: 22, 24]. 

You can create a LibreOffice Basic macro (saved within the LibreOffice global application space, usually under "My Macros" -> "Standard" -> "Module1").

```basic
Sub RecalculateAndSave(sSourcePath As String)
    Dim oDoc As Object
    Dim sPath As String
    Dim loadComponentProperties(0) As New com.sun.star.beans.PropertyValue
    
    loadComponentProperties(0).Name = "Hidden"
    loadComponentProperties(0).Value = True
    
    ' Convert standard path to URL
    sPath = ConvertToURL(sSourcePath)
    
    ' Open the document silently
    oDoc = StarDesktop.loadComponentFromURL(sPath, "_blank", 0, loadComponentProperties())
    
    If Not IsNull(oDoc) Then
        ' Force hard recalculation of all formula chains
        oDoc.calculateAll()
        ' Save the updated values
        oDoc.store()
        ' Close document
        oDoc.close(True)
    End If
End Sub
```

### Triggering via Ubuntu Command Line

With the macro in place, you can execute this from the Ubuntu command line or wrap it in a Python `subprocess.call()` [cite: 23, 24].

```bash
# Executing the recalculation macro on Ubuntu in headless mode
libreoffice --headless --nologo "macro:///Standard.Module1.RecalculateAndSave(/path/to/your/Macro_Model_Georgia.xlsx)"
```

This command launches the LibreOffice engine without a GUI (`--headless`), suppresses the splash screen (`--nologo`), and executes the custom macro that loads the file, recalculates the formulas written by `openpyxl`, saves the cached values, and exits gracefully [cite: 23, 24]. Subsequent Python scripts (e.g., using `pandas` or `openpyxl` with `data_only=True`) can now read the newly calculated outputs of the scenario analysis to generate automated visualizations or summary reports [cite: 22]. 

## Conclusion

Constructing a robust macroeconomic demand-side accounting framework for a small open economy like Georgia requires the meticulous integration of international data (IMF WEO) and localized structural matrices (GeoStat SUTs). Because large infrastructure shocks of $6.5 billion suffer from massive import leakages and dampened multipliers (empirically ~0.8), utilizing a granular 8-year bell-curve distribution allows for a realistic, year-over-year impact assessment. By wrapping this economic methodology within a Python-driven architecture using `openpyxl`, and bridging the calculation gap via headless LibreOffice macro execution, analysts can create an automated, reproducible, and mathematically rigorous pipeline for continuous policy and scenario analysis.

**Sources:**
1. [ecomod.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFw8lQKSxJqqp0pgNuTob6k7kQO0Hy5B9yrikixz--B8DZVyPxEThDiuOZGqEKFerolqKrqIToMZvltaI0ex8YIxp0qXS4zSKhtxhHZCFpUAsqYkwsAAuuvqHZBUpbM40Sx6RazkZOrNhlC3yUUcBkHCFCMzmaztphhEjrxChKGGBrGCA==)
2. [geostat.ge](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdgj3dCQSMapfs9jcmagvV0AfkwhDLjMdEO5JRG7H0h4erZUMweIxQ8DEkXVBUYIfYllpIpbPNQQjXrAA-R2tcTQ89Ix2sct_P2BhDN1CjGpPi0xBL7ya2edAhuU8p2fkUzeLqPHsp)
3. [datapolicyanalyst.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGd8rGReREWKyx5up3otwaw7CBRVF4gcxjAKVDe3_tvPnw81CTxaxGlNHetapV_nq3O0FYc7I_6ZQT1inOxwv5tl2j4zKSG6epQhWLfaxHkfXqZ_c9sysrtLDQBWAJynFfOHROblVs6LjeFJ5ZlJFG3Sg-_eIjXPMthxihUOt-qG7CZtMNQgPiuW0exF0hBAaws7oCQDR-X-fTj5G4crEwRbovYruvBGLeTp8QeyQvIq-s=)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHG1LYS4pCUu9DmFBp2GsFtr4NNcUMlxfpik_-sJ45cYB-RpIXXMhPpyLKUfS1emC2PY5XHEx9jKQbFi15WPimxH0P7KDdWixBymQHI5qydsHkawuVlGo--kcqMRMXCdrNTwNLr4b8ebYXCADgHdjYTo2USnL7_5O9z)
5. [rogermariolopez.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYIes3ifi6YzkPLSn7HF-UluH53fKYw470uBeJ72PpaQHTuVlH2GMeqBjOnLHGImOpPz0n6vUljzuH7YB5vp3DHaIXEmPiHmHMJZqYjzVIKzj9JB9B-j5vQuJh6u1X56nx9wqxjQ==)
6. [geostat.ge](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHbX1eetXHEOgFD-mzlPD_MBEAh5stnAQi22nDuwbli4zNuxWavoSEu9IQCQ5CvQr7gCfEXaTKebSHrzM0ha3LRjJCOegxcjYQKw5Z74TbXpf8pqhv7XipAt0yUxJOAG_4Xhv45pHbGLNmGcQSvegln3K9K)
7. [imf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSiJqaWsLFiWOhggYf3tnGdTwtqb_oAu9TSx2Ghu-g5RnBKDBMzr061xBnWiWVp9XDaVU9oY6OONQJlma2xuwA-bCLA-PI947z2fy8flE-xmgs-LPD3HcVHeSexYimueu2nKeIayBvErA1lgpfvLmNyw0t_Q==)
8. [geostat.ge](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHGY3tuKJri9N4943J2ewQI9vM_oG1CCgtA1v4VkwQlv0jIX6Ju-XG0Iepx7dv31kyzgqph3idsw6gtzmml-Pm3qQgRNoX5KV1iHEKf4WwXBbGGzLfPvOCl3IUf7wRW-VLn4QX4s-hr)
9. [oecd.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlBEDqH4gZNTHFwkLEsVl_RIJlFQTxTJVEl0w0CYz_4g6a3B16HR8oFFKcAKoEFPjXdulJAtuVSeLIBN12ZvXPzSRw2LQKs1PpvZX3psUv54p19VWW9fG7WpnY4zji6WFhBMrc212122_FASfDyIrDlrwRRppS)
10. [imf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4xF6R6crCNlZUhnnqCxYkPxJJxo5xDBi7UAeFLxFuCr88AvOm-jub1ojqIr3zUdSRHHlotBARLV5zRa8zu5kh6h3KpEHpUQdpzdGzkKzXaMHMNVnlx2dHExZCu8ddqueP45eJhfqvjUFbldgdn7uHyh9_DQ6D_8a4BbuGUKzFeLs=)
11. [cso.ie](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEs2ELMYCCzS8IdOfxEg4SsmJXbGdXuJHue7tb5ZgwYGnVFt7IGlsjDxRZTdt2WreNvVINvqKtnrzwlXMqckYxgvAKcc-3vwhcn93tqR95YSwU6fOJTrQt0YR99P-iS48US3VxIHHEDVQ3prty9blVDjL8kFfwZfQilB54UIH9mkW-AUV6PfsuGhwX8SkOALJxHKOg52KnSqVHoGu4qUbM=)
12. [centralbank.ie](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFGKlGZbjxPIYmcStp19czO01UXfiy6oPSL1eUvcP-1ydU5IALyrmsEn5zfFf7P8baKGEgub27rNGfHe6uzDQpIEFdB1tGktI8QF4_r4-VA-bigE6edbpWHz2gq6i8-Pf3tNsGDpZ4XXSgpZN4zfHNDTtodbn2lwLciQDUxIOGQ-P778MMfAflYs60Ao_4cgJRnKs0XYt-2SCtMyZHK6tFDDEEb7MP6cFojwprGokVhkXmbua-PqTN62e-ldLygM698xsZ3uAhvwDq5Jw_viA==)
13. [iioa.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHr3w3yttCYvw87NcZ4Abo8t3PgnImsv4MqizZiiJRWGxkO0e4GkwJC8rz30e9SrqC6zseY46nAo-g2U5IQciu0GIGS98C6vJ1wiTSAZktaQT_a8W6rypH04UzGPBv5k-sAXRDtIyQrxNzNjYqmkxRmiNestg==)
14. [projectmanagementacademy.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGv1pwAQiRctMzd093jYpfUMJf2bKJ5e_Zvl1l5iPbpfdUYOT1MQ88J9xzMOzJEVWfZxPMhnUJEiFD3J_WTUEhaQyM9BuReLXv1_lwhgLy7-ju2cy0nVzwLKNys1RrmWX5nATZVrj2EgREELUQJGoht0d_yid0liTw9ygQTrgFKPJe7aMrxjcQhs9XBQ4hHlKqlx8bBFAT3rSMBFIyKiseEyyZeWhvsEw==)
15. [ascelibrary.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1heVrQA6ZpWPwbWfh--_HDuz3Q4rSXV5-2LOsjkNfqbH2NZ-qBW3b3og8XE2L7KL4nai8JdA3X-LYLXx19JoKjlEMMYxrRd_3A4EpHyJGKSmCeciW0Cy7uXANuq8Y16lzn5zd15JnDZXdU-P8r-KfPaRWhX_bHvo=)
16. [broadwaysubway.ca](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEadILHgwUCibgW_8PKxV9ItYnV9M9coqDZPjOJJablswD50xI2UmZYZwCA5oGzgUNIVofaKjtLyWJnXStCRN6uttm4WV-ZEhnz8UjTRT4yqzOhu2kDBRUKD3_hRrNC5vw8JOmKSsUYKGt3QrlenkY7Ny2Ys0ybgTCm0QPIrl8nlu0YTTOTMxPz6kt-EQ==)
17. [aem.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-BdgKjfY7ZKBOVwm5UMHMexd7JYJZSe-_QtQYvJkCsn8-e5pYhRAl-WlHxL8TEMtU3Jwq9FcvnJLnXKs_Ur3gcKcKXJOTonGVegpTzvZ2La-abb-G8w-OJ03XqDYVo-Wmkp0Qj8GZdc6lzsOnc_l4310xV8VEkOqcSD5fWSGe5y_yIHVUWZybQcRdz2Kgo19Kx7w=)
18. [mrarch.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHF5KHRXjve15bH1YFOkSu5v0QdBMv0aSL5PNkLd-vTQwXBCB5yKvkbN2WLC2if6RGyL3f1klrf3PJmHdxne1pfqLcjyqc4m7e4bPYffuBEcyDKZmrm1l30oqcJvPrRRAdDqY5HtuWtlyZu27j5tLPituJEk80vYbl_z2bPmSirJd3o9ACX)
19. [cbo.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFt_o0lwrYQ-XWHjbfGNY5Ws03JKSswZphKgWjd8PpmV0dIunTjaDiVtRHD5iBr_fAwvHzKYGTBe3vUF1Z_VulO5JbJVVavliCbiIt9wrG82nuHERgIx3LCH9giXxdKHDIDrZE374JjCeDJQow8cz0xMy7b9tkB_xaVy1wmCUCXO4GIIhHAoEcInOoLi-MP6B6hun3hErlVNwRRVA==)
20. [cbo.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFp5Zz2267qfgyip0qJfwyOS6bSDceRfYNf7CH3iH-EtlBl03KqXI_j1USUgYq9fWpyovO5d14qtv24EYPnQT3-ufqr4yy3P6yRYOsPwFZC8Ng_0jK8CcViRVtm--DVEgw7nQg4S-ylpEvsSs_x_SBIpyESkbvE-wORCh6vwq5N-_hPi6AIyOyU64UAbzbtOTaVGeSEzvUI)
21. [federalreserve.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqj1OXazSmqVa6kVviTJvkEpQsjCphIhuM9wnFEpS1EotZf2LsTZi5l9HpG6Qwj2H0010HmVVu6lp6zZZmCrpheB2LZoaplvuFTnNgHY7UpI6hUWVd-8a5fqNz_IRhJmUzighyJTOfP0r4deoX7WY2jK2N4RLxA8M=)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0AQ2L-xvlkD9m9bwyVRgmC44S5sleVekJ0PsLTR0VkaZu0wzNSJzjdcojFl8zc8-ffTk-wPuEMo0eOf0bH7b9yPLpFWR3Y-rk8CcgWTnGLC1gVcbDY3xUS7ovKBn_cAWwzWIffRc6LuknXcG2YdbAqTVbbAF9w0LYcbLhFiDaPREHx8WLYbe90Ni8IZQ6Y4lyIhjwpZ2Rmj-3clEzqmeGI-lK0FwVqSh3G7VIIQ==)
23. [askubuntu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzcJ0GKpK5__dIjiI_Lwu4sTdpnJoFzv6mfQVZySKB2nOUCsJnVXi-tbBsJ5Ey_F9ma0I0h6d5n0VaPWf0DVPgGnyM--Y80xZUJCxhB9aC3nrb10lI8y2Nt9YvwdkaNehk7m26ayLoQHNoZx4Z7ZJZ1cVr2wyjev8M4EErEp5K6Kuo92ohgahsEOFhqlTsd0cDaQXzEvx8)
24. [libreoffice.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCJb0lBnSTwt39Hvu8JLHXo0GuvNRdIjZgK-e6Q4iOPzu9cHVt5u7iREk4WC4PLkapSYdyBVXFzCnUxe6ZF2wp0tSrjGgF6YXyxJh019No1qd0XutQAiGs5CimKz-lr-VBkx7-1YlpdztVgeaY_Ug-_nA4Bg7XivOHGk2vEd-Wn5VgzwlVNGHIbcCfaXJUo6BlRSorn1i6)
25. [askubuntu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHviTH4y5Mkge4z-532v0FW_6xnv6QfXIYhUEGGJ5mBZDnoIYZzOHLIWh4VekMMu6VIxcfzfpg9wVaujoaKkVu6SMgXcXm6XD-qVjHrfFVHr7BG2mqxk_RuzMA-K9cvD1epPN7OyTme1Ib_I3Vn0szOX7BwtxGJL5MeRQnzUGw8V6qnI9FFQVei6z0c3kFNZ4d7dXGqdiTFkarRUukMJKW-BlxSCN3_BbZBEMfKFSs=)
