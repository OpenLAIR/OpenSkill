# Domain Reference for evo-reflow-json-output

**Responsibility**: All JSON serialization, type-safe encoding of numpy/pandas types, rounding to 2 decimals, sorting by run_id/board_family/board_id, null handling, and file writing to /app/output/.

**Key functions to implement**: build_q01_output, build_q02_output, build_q03_output, build_q04_output, build_q05_output, safe_json_dump, numpy_pandas_encoder

---

## 4. JSON Output Formatting in Python


Serialization of pandas DataFrames to JSON for integration with REST APIs, MES backends, or web dashboards introduces significant edge cases. The Python built-in `json` module is completely unaware of the C-based numpy datatypes (`np.int64`, `np.float64`) underlying pandas structures. Attempting to use `json.dump()` directly on a dictionary generated via `df.to_dict()` routinely results in `TypeError: Object of type int64 is not JSON serializable` [cite: 28, 29, 30]. Furthermore, missing data (`np.nan` or `pd.NaT`) does not automatically map to the standard JSON `null` token, often resulting in structurally invalid JSON [cite: 31, 32].

## 6. Edge Cases and Pitfalls in Manufacturing Automation


When transitioning these utility modules from academic logic to factory-floor production code, several robust error-handling patterns must be accommodated.

1.  **Runs with No Thermocouple Data**: 
    Machine network timeouts frequently result in recorded `run_id` entries with zero row counts in the telemetry CSV. When calculating TAL or peak temp, an empty DataFrame throws an `IndexError` or `ValueError`.
    *Mitigation*: Implement guard clauses using `if df.empty:` early in utility functions. During joins, these runs will expose `NaN` values for thermal metrics, which should be aggressively flagged as `FAIL - UNVERIFIED` rather than inferred or interpolated.

2.  **Multiple Thermocouples and Placement Variance**:
    J-STD-020 guidelines demand that analysis accommodates localized variations. As shown in the code above, aggregating all thermocouples blindly averages out extreme errors. The standard protocol requires evaluating the **coldest spot** on the board (to verify minimum liquidus parameters) and the **hottest spot** (to verify absolute maximum package constraints are not breached) [cite: 9, 12]. Grouping by `tc_id` to evaluate compliance strictly against both extremes is mandatory.

3.  **Time and Velocity Unit Mishandling**:
    Thermocouple dataloggers often log relative time in seconds, while MES logs represent machine cycle times in minutes. Furthermore, conveyor speed is predominantly measured in centimeters per minute (cm/min) globally, but US facilities may log inches per minute (in/min). 
    *Mitigation*: Normalize all incoming time-series datasets to **SI base units (seconds)** upon ingestion. Calculations involving conveyor speed should strictly define units in the function signature (e.g., `calculate_speed_cm_min()`) to prevent mathematical scaling disasters.

4.  **Noisy Sensor Readings**:
    Industrial thermocouples frequently experience EMI (Electromagnetic Interference) from nearby heavy machinery. A singular spike from 210°C to 240°C back to 215°C within 1 second will incorrectly trigger peak temperature compliance and falsely alter the derivative ramp rate. 
    *Mitigation*: The rolling mean strategy (provided in Section 3) is a prerequisite. For superior fidelity in academic contexts, a Savitzky-Golay filter (`scipy.signal.savgol_filter`) preserves peak shapes much better than a simple moving average, though implementing this adds a `scipy` dependency.

5.  **Null Serialization Pitfalls**:
    JSON parsers in downstream Web UIs (like React or Vue.js dashboards) critically fail if presented with `NaN` (a token valid in JavaScript but strictly forbidden by the JSON RFC). As demonstrated, native pandas serialization (`df.to_json`) correctly converts `NaN` to the compliant `null` string [cite: 33, 35].