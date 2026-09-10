# Domain Reference for evo-macro-sut-import-share

**Responsibility**: Populating columns C-H of the SUT Calc sheet by linking data from the copied SUPPLY and USE sheets, computing import-to-supply ratios per product, applying them to GFCF column, and deriving the aggregate import content share theta using Excel formulas.

**Key functions to implement**: link_sut_to_calc_sheet, compute_import_shares, calculate_import_content_share

---

## Supply and Use Table (SUT) Methodology for Import Content Estimation


The fundamental constraint in evaluating an investment shock in a small open economy is the "import leakage." When $6.5 billion is spent on an infrastructure megaproject, a substantial portion pays for imported steel, foreign engineering services, and imported heavy machinery. This capital leaves the domestic economy immediately and generates no localized multiplier effect. To estimate this leakage, economists turn to Supply and Use Tables (SUTs).

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

### Writing Formulas Natively


To make the Excel file functional upon opening, Python must write the mathematical formulas as strings exactly as a user would type them into Excel. `openpyxl` handles the translation into Excel's native XML formula structure.

```python

### Handling Cross-Sheet References


In an integrated macro model, variables are spread across sheets (e.g., `WEO_Data`, `SUT_Matrix`, `Scenario_Analysis`). Cross-sheet references in `openpyxl` are implemented by precisely formatting the string, wrapping the sheet name in single quotes.

```python