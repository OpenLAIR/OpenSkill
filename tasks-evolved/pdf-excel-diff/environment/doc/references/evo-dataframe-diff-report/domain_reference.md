# Domain Reference for evo-dataframe-diff-report

**Responsibility**: Perform outer merge with indicator to detect deletions, iterate matched rows for field-by-field comparison with NaN and float tolerance handling, format output per the required JSON schema, and serialize with custom NumPy encoder.

**Key functions to implement**: find_deleted_employees, find_modified_employees, build_diff_report, export_diff_to_json

---

## 4. DataFrame Comparison Patterns for Record Diffing


Once PDF and Excel data are loaded into DataFrames, the task is to compare them row-by-row based on a unique identifier (e.g., Employee ID). We must identify:
1.  **Insertions**: Present in PDF (new) but not Excel (old).
2.  **Deletions**: Present in Excel (old) but not PDF (new).
3.  **Modifications**: Present in both, but fields (like salary) have mutated.

### 4.1 The Outer Merge with `indicator=True`


The most statistically sound methodology for identifying structural overlap in Pandas is the outer merge utilizing the `indicator=True` parameter [cite: 19, 20, 21].

```python

### 4.2 Iterating Over Matched Rows for Field-by-Field Diffing


For the intersecting records (`_merge == 'both'`), we must compare the columns to identify modifications. Because column names were appended with suffixes (`_old` and `_new`) during the merge [cite: 23], we can iterate through the shared columns.

```python
columns_to_compare = ['Salary', 'Department', 'Role']
modifications = []

for index, row in intersecting_records.iterrows():
    emp_id = row['Emp_ID']
    row_diffs = {'Emp_ID': emp_id, 'changes': {}}
    
    for col in columns_to_compare:
        val_old = row[f"{col}_old"]
        val_new = row[f"{col}_new"]
        
        # NaN handling is critical here. np.nan != np.nan evaluates to True!
        # We must normalize the comparison.
        if pd.isna(val_old) and pd.isna(val_new):
            continue # Both are NaN, therefore equal
            
        if val_old != val_new:
            row_diffs['changes'][col] = {'old': val_old, 'new': val_new}
            
    if row_diffs['changes']:
        modifications.append(row_diffs)
```

### 4.3 Handling NaN Comparisons and Type Mismatches


A fundamental rule of IEEE 754 floating-point mathematics (inherited by Pandas/NumPy) is that `NaN == NaN` is strictly `False` [cite: 24]. Standard equality operators will falsely flag identical missing records as "modified". As shown above, `pd.isna()` must be used to neutralize this behavior.

Furthermore, type mismatches (e.g., PDF extracts salary as `"50020"`, Excel has `50020.0`) will trigger false positives in a strict `!=` evaluation [cite: 25]. This mandates aggressive data normalization *before* the merge is attempted.

---

### 5.4 Float Precision Tolerance


When comparing financial data or metrics, small precision errors can occur (e.g., `500.0000001` vs `500.0`). For comparing these efficiently, use `numpy.isclose()` instead of strict equality [cite: 24, 25]. `np.isclose()` provides an `rtol` (relative tolerance) and `atol` (absolute tolerance) parameter [cite: 24, 26].

```python
import numpy as np

## 6. JSON Output Formatting and Serialization


After the diffing engine computes the insertions, deletions, and modifications, the final enterprise step is frequently pushing this payload to an API or logging system via JSON.

### 6.1 The NumPy Serialization Bug (TypeError)


The standard Python `json` library is remarkably rigid. It only natively understands base Python data types (`int`, `float`, `str`, `dict`, `list`, `bool`, `None`) [cite: 27]. Because Pandas relies on NumPy arrays for fast computation, the values iterated out of DataFrames are often typed as `numpy.int64` or `numpy.float64`. 

If you attempt to execute `json.dumps({"id": np.int64(42)})`, Python will throw a fatal error: `TypeError: Object of type int64 is not JSON serializable` [cite: 28, 29]. Although one might assume NumPy ints would inherit from Python ints, `numpy.int64` deliberately does not, due to memory structuring [cite: 30, 31].

### 6.2 Designing a Custom JSON Encoder


To circumvent this, we must extend `json.JSONEncoder` and override the `default()` method to trap NumPy data types and cast them back to native Python types [cite: 27, 28, 32, 33].

```python
import json
import numpy as np

class NumpyTypeEncoder(json.JSONEncoder):
    """Custom encoder to convert NumPy types to Python primitives."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj) # Casts np.int64 to native int
        elif isinstance(obj, np.floating):
            if np.isnan(obj):
                return None # JSON represents NaN as null
            return float(obj) # Casts np.float64 to native float
        elif isinstance(obj, np.ndarray):
            return obj.tolist() # Casts arrays to nested lists
        elif isinstance(obj, np.bool_):
            return bool(obj) # Casts np.bool_ to native bool
        
        # Let the base class handle anything else (will raise TypeError if unsupported)
        return super(NumpyTypeEncoder, self).default(obj)
```

### 6.3 Formatting, Sorting, and Indentation


To produce human-readable JSON reports, utilize the `indent` and `sort_keys` parameters. For our specific payload, we want to ensure the list of differences is sorted by the Employee ID.

```python