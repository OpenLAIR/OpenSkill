To verify the accuracy of the investment spending shock model, you can implement a `pytest` suite that checks for structural integrity, accounting consistency, and mathematical correctness.

### 1. Independently Computable Reference Values

These values serve as "sanity checks" for your Excel formulas.

*   **Investment Profile (Bell Shape):**
    *   **Input:** Total Investment = $6.5B USD, Duration = 8 years.
    *   **Logic:** A bell-shaped distribution for an 8-year project typically follows a normal distribution curve (e.g., using `NORM.DIST` in Excel).
    *   **Reference:** If the project peaks in year 4 or 5, the annual spending ($S_t$) should satisfy $\sum_{t=1}^{8} S_t = 6.5$.
    *   **Test Assertion:** `assert sum(sheet['Investment_Column']) == 6.5` (within a small floating-point tolerance).
*   **Import Leakage Calculation:**
    *   **Input:** Use Table (Intermediate Consumption + Final Demand) and Import Matrix.
    *   **Logic:** Import Content Share ($ICS$) = $\frac{\sum \text{Imported Inputs}}{\sum \text{Total Inputs}}$.
    *   **Reference:** If the total intermediate use is $100$ and imported intermediate use is $20$, $ICS = 0.20$.
    *   **Test Assertion:** `assert abs(cell_C46 - 0.20) < 0.001`.
*   **Multiplier Effect:**
    *   **Logic:** $\Delta GDP = (\text{Net Investment}) \times \text{Multiplier}$.
    *   **Net Investment:** $Investment \times (1 - ICS)$.
    *   **Reference:** If Investment = $1B, ICS = 0.3$, Multiplier = $0.8$, then $\Delta GDP = 1 \times (1 - 0.3) \times 0.8 = 0.56B$.

### 2. Dataset-Level Statistical Invariants

These invariants must hold true regardless of the specific scenario:

*   **Non-Negativity:** All GDP growth rates and investment values must be $\ge 0$.
*   **Completeness:** The "WEO_Data" sheet must contain continuous data for the years 2026–2043.
*   **Fixed Exchange Rate:** The Lari/USD exchange rate must be constant at $2.746$ across all cells referencing it.
*   **Scenario Consistency:**
    *   Scenario 2 (Multiplier = 1.0) must result in a higher GDP impact than Scenario 1 (Multiplier = 0.8).
    *   Scenario 3 (Import Content = 0.5) must result in a lower net domestic impact than Scenario 1 (assuming baseline $ICS < 0.5$).

### 3. Cross-Validation Approaches

You can use Python's `openpyxl` to perform an independent calculation of the same logic to verify the Excel output:

```python
import pytest
import openpyxl

def test_gdp_impact_calculation():
    wb = openpyxl.load_workbook('test - demand.xlsx', data_only=True)
    ws = wb['NA']
    
    # Independent calculation in Python
    investment_usd = 6.5
    exchange_rate = 2.746
    multiplier = 0.8
    ics = ws['C46'].value # Assuming this is where the share is calculated
    
    expected_net_impact_lari = (investment_usd * (1 - ics)) * multiplier * exchange_rate
    
    # Assert against a specific cell in your Excel sheet
    actual_impact = ws['H10'].value # Example cell for total impact
    assert abs(actual_impact - expected_net_impact_lari) < 1.0
```

### 4. Benchmarks and Reference Implementations

*   **IMF WEO Database:** Use the [IMF WEO Data Mapper](https://www.imf.org/en/Publications/WEO) to verify your baseline GDP growth projections.
*   **GeoStat SUT:** The [National Statistics Office of Georgia (GeoStat)](https://www.geostat.ge/) publishes the official Supply and Use Tables. Ensure your $ICS$ calculation aligns with the "Imports" row relative to the "Total Use" row in the Use Table.
*   **Multiplier Theory:** Refer to standard macroeconomic textbooks (e.g., Blanchard, *Macroeconomics*) for the "Small Open Economy Multiplier" formula: $k = \frac{1}{1 - MPC + MPM}$, where $MPM$ (Marginal Propensity to Import) is the leakage factor.