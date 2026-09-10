To verify the correctness of the DOTS scoring implementation, you can use the following independent anchors and verification strategies.

### 1. Independently Computable Reference Values
The DOTS score is calculated as:
$$\text{DOTS} = \text{TotalKg} \times \left( \frac{500}{A \cdot BW^4 + B \cdot BW^3 + C \cdot BW^2 + D \cdot BW + E} \right)$$

**Reference Case (Male):**
*   **Input:** $BW = 100.0$ kg, $TotalKg = 600.0$ kg
*   **Male Coefficients:** $A = -0.000001093$, $B = 0.0007391293$, $C = -0.1918759221$, $D = 24.0900756$, $E = -307.75076$
*   **Step 1 (Denominator Calculation):**
    *   $A \cdot BW^4 = -1.093$
    *   $B \cdot BW^3 = 739.1293$
    *   $C \cdot BW^2 = -1918.759221$
    *   $D \cdot BW = 2409.00756$
    *   $E = -307.75076$
    *   **Denominator** $= -1.093 + 739.1293 - 1918.759221 + 2409.00756 - 307.75076 = 920.533879$
*   **Step 2 (Coefficient):** $500 / 920.533879 \approx 0.54316$
*   **Step 3 (Final Score):** $600 \times 0.54316 \approx 325.896$

### 2. Dataset-Level Statistical Invariants
These invariants can be used as `pytest` assertions to ensure data integrity after processing:
*   **Non-Negative Scores:** For any valid lifter (TotalKg > 0), the DOTS score must be strictly positive.
*   **Bomb Handling:** Any lifter with a "TotalKg" of 0 (due to failed attempts/bombs) must result in a DOTS score of 0.
*   **Monotonicity:** For a fixed bodyweight, the DOTS score must be strictly increasing with respect to `TotalKg`.
*   **Completeness:** The number of rows in the "Dots" sheet must exactly match the number of rows in the "Data" sheet (excluding headers).
*   **Mx Category:** Ensure that any lifter marked as `Mx` in the `Sex` column is processed using the male coefficients (as per standard convention).

### 3. Cross-Validation Approaches
To verify your implementation independently:
*   **Python/Pandas Verification:** Create a small, separate script that performs the calculation using `numpy` or standard math libraries and compare the output of your Excel-based solution against this script for a subset of rows.
*   **Online Calculator Comparison:** Use a reputable online DOTS calculator (e.g., [Strength Level](https://strengthlevel.com/dots-calculator)) to manually verify 5–10 random rows from your dataset.
*   **Excel Formula Audit:** Use Excel's "Evaluate Formula" tool on a single cell in the "Dots" sheet to step through the calculation and ensure it matches the manual calculation provided in Section 1.

### 4. Pytest Assertion Examples
```python
import pytest
import openpyxl

def test_dots_calculation_accuracy():
    # Test against the reference case (100kg BW, 600kg Total, Male)
    # Expected: ~325.896
    wb = openpyxl.load_workbook('/root/data/openipf.xlsx')
    sheet = wb['Dots']
    
    # Assuming row 2 is the test case
    # Adjust indices based on your column mapping
    total_kg = sheet['E2'].value 
    dots_score = sheet['F2'].value
    
    assert pytest.approx(dots_score, abs=0.001) == 325.896

def test_bomb_handling():
    # Ensure a 0 total results in a 0 DOTS score
    # ... logic to find a 'bomb' row ...
    assert sheet['F_bomb_row'].value == 0
```