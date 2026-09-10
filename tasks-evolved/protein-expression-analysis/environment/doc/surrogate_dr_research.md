To verify the protein expression analysis pipeline, you can implement the following surrogate tests in `pytest`. These anchors rely on the mathematical definitions of log-transformed proteomics data and standard statistical invariants.

### 1. Independently Computable Reference Values
Since the data is $\log_2$-transformed, the following identities must hold for any protein $P$ with control samples $C = \{c_1, \dots, c_n\}$ and treated samples $T = \{t_1, \dots, t_m\}$:

*   **Log2 Fold Change (L2FC):** $\text{L2FC} = \text{mean}(T) - \text{mean}(C)$
*   **Fold Change (FC):** $\text{FC} = 2^{\text{L2FC}}$

**Test Case Example:**
If a protein has control values $\{1.0, 2.0\}$ and treated values $\{3.0, 4.0\}$:
1.  $\text{Mean}(C) = 1.5$
2.  $\text{Mean}(T) = 3.5$
3.  $\text{L2FC} = 3.5 - 1.5 = 2.0$
4.  $\text{FC} = 2^{2.0} = 4.0$

**Pytest Assertion:**
```python
def test_fold_change_math():
    control_mean = 1.5
    treated_mean = 3.5
    expected_l2fc = 2.0
    expected_fc = 4.0
    
    # Assert L2FC calculation
    assert treated_mean - control_mean == pytest.approx(expected_l2fc)
    # Assert FC calculation
    assert 2**(treated_mean - control_mean) == pytest.approx(expected_fc)
```

### 2. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the specific expression values in the dataset:

*   **Completeness:** The number of proteins in the output (rows 32-41) must equal the number of target proteins (rows 11-20).
*   **Non-negativity of Standard Deviation:** Standard deviation values must be $\ge 0$.
*   **Consistency:** If $\text{Mean}(T) = \text{Mean}(C)$, then $\text{L2FC}$ must be $0$ and $\text{FC}$ must be $1$.
*   **Range:** $\text{FC}$ values must be strictly positive ($> 0$) because $2^x$ is always positive for any real $x$.

### 3. Cross-Validation Approaches
To verify the Excel formulas, you can use a Python script to perform the same calculations independently on the raw data and compare the results against the Excel output.

**Cross-Check Script (Python/Pandas):**
```python
import pandas as pd
import numpy as np

def verify_with_pandas(data_file):
    # Load raw data
    df = pd.read_excel(data_file, sheet_name="Data")
    
    # Assuming columns C-L contain the target samples
    # Assuming rows 24-27 are the calculated means
    # Calculate expected means using pandas
    expected_control_mean = df.iloc[10:20, 2:7].mean(axis=1) # Example indices
    
    # Compare with values extracted from the "Task" sheet
    # ... (code to extract Excel values)
    # assert np.allclose(excel_values, expected_values)
```

### 4. Benchmarks and Reference Implementations
*   **Standard Proteomics Workflow:** The methodology follows the standard practice for TMT-labeled proteomics data (e.g., CCLE/Broad Institute DepMap pipelines). Reference: *Ghandi et al., "Next-generation characterization of the Cancer Cell Line Encyclopedia," Nature 569, 503–508 (2019).*
*   **Formula Verification:** Use the `openpyxl` library to inspect the *formula strings* themselves rather than just the computed values. This ensures the logic is embedded in the sheet as requested.

**Formula Inspection Assertion:**
```python
def test_formula_integrity(ws):
    # Verify the cell contains a formula, not a hard-coded number
    assert ws['C32'].data_type == 'f' 
    # Verify the formula structure (e.g., subtraction of means)
    assert "AVERAGE" in ws['C32'].value
    assert "-" in ws['C32'].value
```