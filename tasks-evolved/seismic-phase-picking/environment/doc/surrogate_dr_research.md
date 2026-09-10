To verify the correctness of seismic phase picking without ground-truth labels, you can implement a suite of `pytest` assertions based on physical principles, statistical invariants, and cross-validation against classical algorithms.

### 1. Independently Computable Reference Values
Since you cannot access the ground truth, you must use **classical, physics-based heuristics** as your "oracle" for a subset of your data.

*   **The "Magic 8" Rule (Local Distance Constraint):** For local earthquakes (distance < 500 km), the P-wave arrival ($T_P$) and S-wave arrival ($T_S$) are related by the distance $D \approx (T_S - T_P) \times 8 \text{ km/s}$.
    *   **Assertion:** `assert (pick_S_idx - pick_P_idx) * dt > 0` (S-wave must arrive after P-wave).
    *   **Assertion:** `assert (pick_S_idx - pick_P_idx) * dt < max_expected_delay` (e.g., 60s for local events).
*   **Akaike Information Criterion (AIC) Picker:** Use the `obspy.signal.trigger.ar_pick` function as an independent reference implementation.
    *   **Computation:** Run `ar_pick` on a sample of your traces.
    *   **Assertion:** `assert abs(my_pick_idx - ar_pick_idx) * dt <= 0.1` (where 0.1s is the standard tolerance for a "correct" pick).

### 2. Dataset-Level Statistical Invariants
These invariants ensure the output adheres to the physical reality of seismic signals.

*   **Temporal Ordering:** In every trace, the P-wave must precede the S-wave.
    *   **Assertion:** For every file, `pick_idx(P) < pick_idx(S)`.
*   **Sampling Bounds:** Picks must exist within the waveform duration.
    *   **Assertion:** `0 <= pick_idx < 12000` (given 12,000 samples).
*   **Uniqueness:** A single trace should typically contain only one primary P-arrival and one primary S-arrival.
    *   **Assertion:** `df.groupby(['file_name', 'phase']).size().max() == 1` (or handle multiple picks if your model allows them, but ensure they are distinct).

### 3. Cross-Validation Approaches
Use alternative methods to verify the skill's output.

*   **Classical vs. Deep Learning:** Compare your model's picks against the `obspy` `classic_sta_lta` or `ar_pick` algorithms.
    *   **Code:**
        ```python
        from obspy.signal.trigger import ar_pick
        # Run ar_pick on the same data
        p_idx_ref, s_idx_ref = ar_pick(data[0], data[1], data[2], ...)
        # Assert that your model's pick is within a reasonable window of the classical pick
        assert abs(my_pick - p_idx_ref) * dt < 0.5  # 0.5s tolerance for cross-validation
        ```
*   **Polarization Analysis:** P-waves are compressional (longitudinal) and appear most clearly on the Vertical (Z) channel. S-waves are shear (transverse) and appear most clearly on the Horizontal (N/E) channels.
    *   **Assertion:** Verify that the signal energy (e.g., kurtosis or STA/LTA) at `pick_idx(P)` is higher on the Z-channel, and at `pick_idx(S)` is higher on the horizontal channels.

### 4. Benchmarks and Reference Implementations
Use these established standards to validate your F1 score requirements:

*   **Evaluation Metric:** A pick is a **True Positive (TP)** if $|T_{predicted} - T_{ground\_truth}| \leq 0.1s$.
*   **Reference Performance:**
    *   **EQTransformer:** Often achieves F1 scores $> 0.8$ for P-waves and $> 0.7$ for S-waves on standard datasets like STEAD or INSTANCE.
    *   **AR-AIC Picker:** A reliable baseline that typically achieves F1 scores $\approx 0.6–0.7$.
*   **Test Oracle:** If you have a subset of manually labeled data (even a small "gold standard" set of 10–20 files), use it to calculate the F1 score as a final gatekeeper test.

### Summary of Pytest Assertions
| Check Type | Assertion Logic |
| :--- | :--- |
| **Physical** | `assert pick_P < pick_S` |
| **Boundary** | `assert 0 <= pick_idx < 12000` |
| **Consistency** | `assert abs(model_pick - ar_pick) * dt < 0.5` |
| **Performance** | `assert f1_score(model_picks, gold_standard) >= 0.7` (for P) |