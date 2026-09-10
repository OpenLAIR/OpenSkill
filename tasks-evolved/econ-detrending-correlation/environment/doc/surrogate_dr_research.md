To verify the output of the macroeconomic analysis pipeline without access to the ground-truth solution, you can implement a `pytest` suite that enforces statistical invariants, data integrity, and known properties of the Hodrick-Prescott (HP) filter.

### 1. Dataset-Level Statistical Invariants
These assertions verify that the data processing pipeline adheres to the expected structure and properties of macroeconomic time series.

*   **Temporal Coverage:** The output series must contain exactly 52 data points (2024 - 1973 + 1).
*   **Non-Negativity:** Nominal and real PCE/PFI values must be strictly positive.
*   **Log-Transformation Property:** After taking the natural logarithm, the series should be approximately linear (if the trend is exponential) or at least stationary in growth rates.
*   **HP Filter Invariants:**
    *   **Sum of Components:** The sum of the cyclical and trend components must equal the original log-transformed series: $y_t = \tau_t + c_t$.
    *   **Mean of Cycle:** For the HP filter, the mean of the cyclical component ($c_t$) should be approximately zero (within machine precision, e.g., `abs(mean) < 1e-10`).
    *   **Trend Smoothness:** The second difference of the trend component should be significantly smaller than the second difference of the original series, reflecting the penalty $\lambda=100$.

### 2. Independently Computable Reference Values
While the exact correlation depends on the specific ERP data, you can validate the **implementation logic** using a synthetic test case.

*   **Synthetic Test Case:** Create a simple series $y_t = t + \sin(2\pi t / 8)$ for $t=1 \dots 52$.
    *   Apply the HP filter with $\lambda=100$.
    *   Verify that the extracted cycle $c_t$ matches the expected sine wave (the trend should capture the linear $t$ component).
    *   **Assertion:** `assert np.allclose(hp_filter(y, lamb=100)[0], expected_sine_wave, atol=0.1)`

### 3. Cross-Validation Approaches
You can cross-check the Python implementation against alternative computational methods to ensure the `statsmodels` HP filter is being used correctly.

*   **Matrix Algebra Verification:** The HP filter is a linear smoother. You can independently compute the trend $\tau$ using the matrix formula:
    $$\tau = (I + \lambda K'K)^{-1} y$$
    where $K$ is the $(N-2) \times N$ second-difference matrix.
    ```python
    import numpy as np
    from scipy import sparse

    def hp_filter_manual(y, lamb=100):
        n = len(y)
        # Create second difference matrix K
        d = sparse.diags([1, -2, 1], [0, 1, 2], shape=(n-2, n))
        K = d.tocsr()
        I = sparse.eye(n)
        # Solve (I + lambda * K'K) * trend = y
        trend = sparse.linalg.spsolve(I + lamb * K.T @ K, y)
        return y - trend, trend
    ```
    *   **Assertion:** Compare the `statsmodels` output with this manual matrix implementation. They must be identical within `1e-8` tolerance.

### 4. Benchmarks and Reference Implementations
*   **Standard Correlation Range:** Historically, the correlation between detrended real PCE and PFI in the US is positive and typically falls in the range of **0.5 to 0.8**. If your calculated correlation is outside this range (e.g., negative or > 0.95), it indicates a likely error in data alignment or deflation.
*   **Reference for $\lambda$:** The use of $\lambda=100$ for annual data is the standard convention established by Backus and Kehoe (1992) and is widely documented in `statsmodels` and academic literature. Any deviation from this parameter for annual data should be flagged as a potential configuration error.