# Domain Reference for evo-taxonomy-data-pipeline

**Responsibility**: CSV I/O, schema normalization across the three platforms, path splitting, text cleanup, deduplication, and writing final output files (unified_taxonomy_full.csv and unified_taxonomy_hierarchy.csv).

**Key functions to implement**: load_source_csvs, normalize_category_paths, split_hierarchy_columns, write_unified_outputs, compute_source_entropy

---

## 5. Pandas 2.2.0 Data Pipeline Patterns


Pandas 2.2.0 acts as the backbone for data ingress, schema normalization, and taxonomy output mapping.

### 5.1 Ingress and Schema Normalization

Given three different sources with potentially inconsistent delimiters, malformed rows, and varying depths, reading data requires robustness. Using `pd.read_csv(..., on_bad_lines='skip', dtype=str)` prevents pipeline failure on corrupted CSV lines. Concatenating requires adding a distinct `source` identifier column to track whether a taxonomy string originated from Amazon, Facebook, or Google.

### 5.2 Handling Pandas 2.2.0 `FutureWarning`s

Version 2.2.0 introduced significant shifts toward Apache Arrow backends and stricter API enforcement.
*   **`str.split` Arguments:** A `FutureWarning` dictates that all arguments to `StringMethods.split` except for `pat` will become keyword-only [cite: 8]. Splitting paths must explicitly define keywords: `.str.split(pat=' > ', n=-1, expand=True)` [cite: 8, 32, 33].
*   **Expand=True:** `expand=True` coerces the split lists into a multi-column DataFrame [cite: 32, 33, 34, 35]. Uneven path depths result in `None` or `NaN` padding in the rightmost columns [cite: 34, 36].
*   **Downcasting in `replace`:** Pandas 2.2.0 triggers a `FutureWarning` when `replace()` attempts silent downcasting. Use `.infer_objects(copy=False)` to safely handle string-to-numeric or NaN replacement without polluting logs [cite: 7].
*   **Chained Assignment & Copy-on-Write:** Pandas 2.2.0 aggressively warns about chained assignments in preparation for Pandas 3.0's strict Copy-on-Write behavior [cite: 37, 38]. Never perform `df[df['A'] == 1]['B'] = 2`. Use `df.loc[df['A'] == 1, 'B'] = 2`.

### 5.3 Code Implementation: Safe Pandas Parsing


```python
import pandas as pd

def normalize_source_data(amz_path: str, fb_path: str, ggl_path: str) -> pd.DataFrame:
    """Reads and unifies schemas from three sources safely under Pandas 2.2.0"""
    dfs = []
    for path, src_name in zip([amz_path, fb_path, ggl_path], ['Amazon', 'Facebook', 'Google']):
        # Read robustly
        df = pd.read_csv(path, dtype=str, on_bad_lines='skip')
        df['source'] = src_name
        
        # Ensure a 'full_path' column exists; assume it might be raw text
        if 'full_path' in df.columns:
            df['full_path'] = df['full_path'].fillna('').str.lower()
            dfs.append(df)
            
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Split varying-depth hierarchy safely
    # Explicit kwargs required in pandas 2.2 to avoid FutureWarnings
    levels_df = combined_df['full_path'].str.split(pat=' > ', n=-1, expand=True)
    levels_df = levels_df.fillna('') # Handle unequal depth NaNs
    
    # Rename columns dynamically based on maximum split depth
    level_cols = [f"orig_level_{i+1}" for i in range(levels_df.shape[cite: 12])]
    levels_df.columns = level_cols
    
    return pd.concat([combined_df, levels_df], axis=1)
```

---

## 6. Ensuring Even Source Distribution


A high-quality unified taxonomy must not be overwhelmingly skewed toward a single platform (e.g., containing 95% Amazon nodes and entirely ignoring Google's specific categorizations).

### 6.1 Distribution Metrics

The distribution of sources within a unified cluster can be measured using **Shannon Entropy**.
\[ H = - \sum_{i=1}^{S} p_i \log_2(p_i) \]
Where \( p_i \) is the proportion of items in the cluster originating from source \( i \), and \( S = 3 \) (Amazon, Facebook, Google). Maximum entropy occurs when representation is perfectly equal (33% each).

### 6.2 Post-Hoc Verification

If recursive clustering produces a taxonomy node containing 100 Amazon items and 0 from Facebook/Google, it flags an issue with semantic imbalance. To mitigate this during clustering, stratified sampling can be employed: if Google has fewer overall categories, its vectors can be upweighted in the objective function, or duplicate virtual entries can be temporarily synthesized to anchor the centroids toward minority platform structures. In a constrained environment, simple logging and entropy scoring is typically sufficient.

```python
def calculate_source_entropy(df_cluster: pd.DataFrame) -> float:
    """Calculates the Shannon entropy of source distribution in a cluster."""
    proportions = df_cluster['source'].value_counts(normalize=True).values
    return -np.sum(proportions * np.log2(proportions + 1e-9))
```

---