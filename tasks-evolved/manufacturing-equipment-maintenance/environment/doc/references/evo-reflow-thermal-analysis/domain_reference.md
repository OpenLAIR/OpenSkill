# Domain Reference for evo-reflow-thermal-analysis

**Responsibility**: All CSV data loading, merging, time-series computation (ramp rates, TAL, peak temps), conveyor speed feasibility checks, and multi-criteria best-run selection logic. Produces Python dicts/DataFrames ready for serialization.

**Key functions to implement**: load_thermocouple_data, load_mes_log, load_test_defects, calculate_ramp_rates, get_max_preheat_ramp_by_run, calculate_tal_by_run, extract_peak_temperatures, select_representative_thermocouple, check_conveyor_speed_compliance, find_best_run_per_board_family

---

## 2. Reflow Soldering Thermal Profile Domain Knowledge


The reflow soldering process is a highly sensitive thermodynamic operation designed to mechanically and electrically bond surface-mount technology (SMT) components to printed circuit boards (PCBs). This process is governed by stringent international standards, most notably the **IPC/JEDEC J-STD-020** standard for Moisture/Reflow Sensitivity Classification [cite: 9, 10]. The standard delineates the process into four primary zones: Preheat, Soak (Thermal Equalization), Reflow (Time Above Liquidus), and Cooling [cite: 11, 12].

## 3. Pandas Data Processing Patterns for Time-Series Thermocouple Analysis


In a manufacturing automation context, extracting thermal features from continuous time-series thermocouple data is central to quality control. Thermocouple dataloggers generate high-frequency CSV files detailing time, temperature, run ID, and thermocouple ID (`tc_id`). Python's `pandas` version 2.2.3 provides highly efficient vectorized approaches to derive these metrics.

## 5. MES Log and Test Defect Data Analysis Patterns


Automated correlation of upstream thermal anomalies with downstream electrical test defects allows for closed-loop continuous improvement. Typical environments consist of disparate CSV sources:
1.  **Thermal Summary**: Contains `run_id`, peak temps, TAL, and ramp rates.
2.  **MES Logs**: Contains `run_id`, `board_family`, operator data, and timestamps.
3.  **Defect CSVs**: Contains `run_id`, `board_family`, `defect_count`, and `cycle_time`.

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