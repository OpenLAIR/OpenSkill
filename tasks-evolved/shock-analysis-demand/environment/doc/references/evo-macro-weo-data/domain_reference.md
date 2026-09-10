# Domain Reference for evo-macro-weo-data

**Responsibility**: Reading pre-downloaded IMF WEO data files and GeoStat SUT files from /root/data/, populating the WEO_Data sheet with the correct WEO subject codes (NGDP, NGDPD, NGDP_R, NGDP_D, NGDP_RPCH, PCPIPCH), extending GDP deflator and real GDP projections to 2043 using Excel formulas, and copying the 38x38 SUPPLY and USE sheets into the workbook.

**Key functions to implement**: populate_weo_data, extend_deflator_projection, extend_real_gdp_projection, copy_sut_sheets

---

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

### GeoStat's SUT Classification and Base Year


The National Statistics Office of Georgia (GeoStat) compiles the national accounts under the System of National Accounts 2008 (SNA 2008) framework [cite: 7]. Currently, the base year for Georgia's constant price calculations is 2019 (updated from the previous base year of 2015) [cite: 2, 7]. GeoStat publishes detailed SUTs at different classification levels, commonly utilizing a 38x38 industry/product matrix (based on NACE Rev. 2) which provides a granular view of the economy [cite: 8].

## Openpyxl Implementation Patterns for Excel Manipulation


To automate this demand-side accounting framework, Python is utilized to programmatically read, manipulate, and generate Excel workbooks. The `openpyxl` (version 3.1.5) library is the standard tool for handling `.xlsx` files. However, working with complex macroeconomic models requires specific coding patterns to preserve existing structures and inject evaluating formulas.

### Reading Workbooks and Preserving Formatting


A common pitfall when opening Excel models in `openpyxl` is losing the formulas and formatting. If a workbook is loaded using `data_only=True`, `openpyxl` strips the underlying Excel formulas and only loads the last calculated values. To build a dynamic scenario tool, this must be avoided.

```python
import openpyxl

### Handling Cross-Sheet References


In an integrated macro model, variables are spread across sheets (e.g., `WEO_Data`, `SUT_Matrix`, `Scenario_Analysis`). Cross-sheet references in `openpyxl` are implemented by precisely formatting the string, wrapping the sheet name in single quotes.

```python