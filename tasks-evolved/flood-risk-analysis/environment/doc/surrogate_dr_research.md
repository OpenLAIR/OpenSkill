To verify the output of the flooding detection pipeline, you can implement a surrogate test suite using `pytest`. The following anchors provide the necessary logic to validate the output without needing the ground-truth solution.

### 1. Dataset-Level Statistical Invariants
These invariants must hold true for the output `flood_results.csv` regardless of the specific data:

*   **Schema Constraint:** The output must contain exactly two columns: `station_id` and `flood_days`.
*   **Data Type Constraint:** `station_id` must be treated as a string (to preserve leading zeros, e.g., "04044000"). `flood_days` must be an integer $\ge 1$.
*   **Completeness/Filtering Constraint:** The number of rows in the output must be $\le$ the number of unique stations in the input file `/root/data/michigan_stations.txt`.
*   **Range Constraint:** The value of `flood_days` must be within the range $[1, 7]$ (since the observation window is April 1–7, 2025).

### 2. Independently Computable Reference Values
For a small, controlled test case, you can define a mock input and compute the expected output manually:

*   **Input:** A mock CSV with one station (`04044000`) and 7 days of streamflow data (e.g., `[100, 105, 110, 150, 160, 120, 110]`).
*   **Threshold Calculation:** If the historical 90th percentile for this station on these dates is `140`, then the days with flow $> 140$ are day 4 (`150`) and day 5 (`160`).
*   **Expected Output:**
    *   `station_id`: "04044000"
    *   `flood_days`: 2
*   **Assertion:** `assert result_df.loc[result_df['station_id'] == '04044000', 'flood_days'].values[0] == 2`

### 3. Cross-Validation Approach
You can cross-validate the skill's logic by implementing a minimal, independent calculation using `pandas` within your test suite. This acts as a "reference implementation" to compare against the skill's output:

```python
import pandas as pd

def get_reference_flood_count(station_data_df, threshold):
    """
    Independent calculation: Count days where streamflow > threshold.
    """
    # Ensure station_id is string
    station_data_df['site_no'] = station_data_df['site_no'].astype(str).str.zfill(8)
    
    # Filter for the date range
    mask = (station_data_df['datetime'] >= '2025-04-01') & \
           (station_data_df['datetime'] <= '2025-04-07')
    
    # Count exceedances
    return station_data_df[mask & (station_data_df['flow'] > threshold)].groupby('site_no').size()
```

### 4. Pytest Implementation Strategy
Use these anchors to structure your `test_flood_results.py`:

```python
import pytest
import pandas as pd
import os

def test_flood_results_format():
    df = pd.read_csv('/root/output/flood_results.csv', dtype={'station_id': str})
    assert list(df.columns) == ['station_id', 'flood_days']
    assert df['flood_days'].min() >= 1
    assert df['flood_days'].max() <= 7

def test_station_id_integrity():
    df = pd.read_csv('/root/output/flood_results.csv', dtype={'station_id': str})
    # Ensure no station IDs were coerced to integers (e.g., "04044000" != 4044000)
    assert df['station_id'].str.len().min() >= 8 
```

**Note:** When performing these tests, ensure the environment has the same `pandas` version (`2.2.3`) to avoid discrepancies in how data types or grouping operations are handled.