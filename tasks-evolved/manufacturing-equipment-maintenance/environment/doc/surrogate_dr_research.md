To verify the correctness of the coding skill's output without access to the ground-truth solution, you can use the following verification anchors and statistical invariants derived from industry standards (IPC/JEDEC J-STD-020 and IPC-7530).

### 1. Independently Computable Reference Values
These values serve as the "Gold Standard" for your assertions.

*   **Preheat Ramp Rate Limit**: The industry standard (IPC/JEDEC J-STD-020) specifies a maximum ramp-up rate of **3.0°C/s**. Any run exceeding this value is non-compliant.
*   **Liquidus Temperature ($T_L$)**: For SAC305 lead-free solder, the liquidus temperature is **217°C**.
*   **Time Above Liquidus (TAL)**: The standard recommended window is **45–90 seconds** (or 60–90s depending on the specific paste, but 45–90s is the common IPC-7530/J-STD-020 compliant range).
*   **Peak Temperature**: For SAC305, the target peak temperature is **235–250°C**.

**Example Computation Chain for Ramp Rate:**
1.  **Input**: Thermocouple data (time $t$, temperature $T$).
2.  **Calculation**: For any interval $[t_i, t_{i+1}]$, the ramp rate $R = \frac{T_{i+1} - T_i}{t_{i+1} - t_i}$.
3.  **Verification**: Assert `max(R) <= 3.0` for all runs.

### 2. Dataset-Level Statistical Invariants
Your code's output must satisfy these properties to be considered valid:

*   **Completeness**: Every `run_id` present in `thermocouples.csv` must appear in the output JSON files (`q01.json`, `q02.json`, `q03.json`).
*   **Monotonicity/Sorting**: All output arrays must be sorted by `run_id` (ascending).
*   **Range Constraints**:
    *   `tal_s` must be $\ge 0$.
    *   `peak_temp_c` must be a real number (if data exists) or `null` (if missing).
    *   `meets` (in `q04.json`) must be a boolean.
*   **Consistency**: If a run is marked as `non-compliant` in `q02.json` (TAL), it must be consistent with the calculated `tal_s` value relative to the `required_min_tal_s` and `required_max_tal_s`.

### 3. Cross-Validation Approaches
You can use `pandas` to perform an independent "sanity check" within your test suite:

```python
import pandas as pd
import pytest

def test_ramp_rate_compliance():
    df = pd.read_csv('/app/data/thermocouples.csv')
    # Calculate ramp rate independently
    df['diff_t'] = df.groupby('run_id')['temp'].diff()
    df['diff_time'] = df.groupby('run_id')['time'].diff()
    df['ramp'] = df['diff_t'] / df['diff_time']
    
    # Check against the 3.0°C/s limit
    violations = df[df['ramp'] > 3.0]['run_id'].unique()
    
    # Assert that the skill's output matches these violations
    # (Load q01.json and compare)
```

### 4. Benchmarks and Reference Implementations
*   **Standard Reference**: Use the **IPC/JEDEC J-STD-020** classification profile as the oracle for all temperature-related assertions.
*   **Test Oracle**:
    *   **Input**: A dummy CSV with a linear ramp of 4°C/s.
    *   **Expected Output**: `violating_runs` must include the `run_id` of this dummy data.
    *   **Input**: A dummy CSV with a TAL of 30s.
    *   **Expected Output**: `status` must be `non-compliant` (since 30s < 45s).

By hard-coding these limits (3.0°C/s, 217°C, 45–90s TAL) into your `pytest` assertions, you create a robust verification layer that does not rely on the skill's internal logic.