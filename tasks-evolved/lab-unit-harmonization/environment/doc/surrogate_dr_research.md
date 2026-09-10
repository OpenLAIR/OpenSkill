To create a robust surrogate test for your clinical lab harmonization utility, you need to rely on physiological invariants and mathematical constants that are independent of your specific implementation.

### 1. Independently Computable Reference Values
Use these "Golden Pairs" to verify your conversion logic. These are derived from standard biochemical conversion factors.

| Analyte | Input (SI/Other) | Conversion Logic | Expected Output (US Conventional) |
| :--- | :--- | :--- | :--- |
| **Creatinine** | `88.40` µmol/L | $88.40 \div 88.4$ | `1.00` mg/dL |
| **Creatinine** | `0.0001768` mmol/L | $(0.0001768 \times 1000) \div 88.4$ | `0.00` mg/dL (or handle as <0.01) |
| **Hemoglobin** | `14.0` g/L | $14.0 \div 10$ | `1.40` g/dL |
| **Glucose** | `5.55` mmol/L | $5.55 \div 0.0555$ | `100.00` mg/dL |

**Step-by-step verification logic for Creatinine:**
*   **Input:** `88.40` µmol/L
*   **Constant:** 1 mg/dL = 88.4 µmol/L
*   **Calculation:** $88.40 \text{ µmol/L} \times (1 \text{ mg/dL} / 88.4 \text{ µmol/L}) = 1.00 \text{ mg/dL}$
*   **Assertion:** `assert harmonized_value == 1.00`

---

### 2. Dataset-Level Statistical Invariants
Your pytest suite should verify these properties on the output dataframe (`df_out`) to ensure data integrity:

*   **Completeness Invariant:** `assert df_out.isnull().sum().sum() == 0` (No missing values allowed after cleaning).
*   **Format Invariant:** `assert df_out.applymap(lambda x: len(str(x).split('.')[-1]) == 2 if '.' in str(x) else False).all().all()` (Ensures all values are rounded to 2 decimal places).
*   **Range Invariant (Physiological Bounds):**
    *   Define a dictionary of `MIN_MAX_BOUNDS` based on clinical textbooks (e.g., *Tietz Textbook of Clinical Chemistry*).
    *   `assert (df_out['creatinine'] >= 0.2).all() and (df_out['creatinine'] <= 20.0).all()`
*   **No-Scientific-Notation Invariant:** `assert not df_out.astype(str).str.contains('e').any().any()`

---

### 3. Cross-Validation Approaches
To verify your Python logic, use a "Dual-Path" validation in your test:

*   **SQL-based Verification:** If you have `sqlite3` available in your environment, load the raw data into an in-memory SQL table. Perform the conversion using SQL arithmetic and compare the result with your Python function's output.
    ```python
    # Example SQL check
    import sqlite3
    conn = sqlite3.connect(':memory:')
    # ... load data ...
    # Run: SELECT value / 88.4 FROM lab_data WHERE analyte = 'creatinine'
    ```
*   **Pandas `apply` vs. Vectorized:** Run the harmonization using two different methods (e.g., a standard `apply` function vs. a vectorized `np.where` block). The test should assert that `df_method1.equals(df_method2)`.

---

### 4. Benchmarks and Reference Implementations
Use these authoritative sources to hard-code your test thresholds:

*   **Reference for Conversion Factors:** [National Institute of Standards and Technology (NIST) - Guide for the Use of the International System of Units (SI)](https://www.nist.gov/pml/special-publication-811).
*   **Physiological Reference Ranges:** Use the **[LabCorp or Mayo Clinic Laboratories Reference Ranges](https://www.mayocliniclabs.com/test-catalog/)**.
    *   *Test Case:* If a value is 10x the upper limit of normal (e.g., Creatinine = 12.0 mg/dL), it is likely correct. If it is 100x (e.g., 120.0), it is likely a unit error (120 µmol/L = 1.36 mg/dL).
*   **Standard Test Case:**
    *   **Input:** `{"creatinine": "1,23e2"}` (String with comma and scientific notation).
    *   **Transformation:** `1.23e2` → `123.0` → `123.0 / 88.4` → `1.39`.
    *   **Assertion:** `assert result['creatinine'] == 1.39`.