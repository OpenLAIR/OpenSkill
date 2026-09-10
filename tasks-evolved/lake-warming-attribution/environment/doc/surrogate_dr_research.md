To verify the outputs of your lake water temperature analysis without relying on the skill's internal logic, you can implement the following surrogate test strategy. These anchors rely on mathematical invariants and independent verification methods.

### 1. Independently Computable Reference Values
For a small subset of your data (e.g., the first 10 rows), you can manually compute the expected trend to verify the `trend_result.csv` output.

*   **Sen's Slope Verification:**
    *   **Method:** For a time series $X = \{x_1, x_2, ..., x_n\}$, calculate all possible slopes $Q_{ij} = \frac{x_j - x_i}{j - i}$ for all $1 \le i < j \le n$.
    *   **Reference:** The Sen's slope is the median of all $Q_{ij}$.
    *   **Test Assertion:** `assert abs(computed_slope - manual_median_slope) < 1e-6`.
*   **Dominant Factor Contribution:**
    *   **Method:** If using Random Forest `feature_importances_`, the values are normalized by definition.
    *   **Reference:** The sum of all feature importances must equal $1.0$ (or $100\%$).
    *   **Test Assertion:** `assert abs(df['contribution'].sum() - 1.0) < 1e-6`.

### 2. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the specific data values, serving as "sanity checks" for your output files.

*   **`trend_result.csv` Invariants:**
    *   **P-value Range:** The p-value must strictly reside in the interval $[0, 1]$.
    *   **Slope Sign Consistency:** If the Mann-Kendall statistic $S > 0$, the slope must be $\ge 0$. If $S < 0$, the slope must be $\le 0$.
*   **`dominant_factor.csv` Invariants:**
    *   **Category Constraint:** The "variable" column must contain only values from the set: `{'Heat', 'Flow', 'Wind', 'Human'}`.
    *   **Completeness:** The output must contain exactly one row (the most important variable) as requested.
    *   **Contribution Bounds:** The "contribution" value must be in the range $(0, 1]$.

### 3. Cross-Validation Approaches
Use alternative, independent methods to verify the skill's results.

*   **Trend Validation (Parametric vs. Non-Parametric):**
    *   Compute a simple linear regression slope using `scipy.stats.linregress(time, temperature)`.
    *   **Cross-Check:** While not identical to Sen's slope, the sign of the linear regression slope and the Mann-Kendall slope should match for monotonic trends.
    *   **Code:**
        ```python
        from scipy import stats
        slope, intercept, r_value, p_value, std_err = stats.linregress(time_index, temperature_data)
        # Assert that the sign of the MK slope matches the linear regression slope
        assert (mk_slope > 0) == (slope > 0)
        ```
*   **Factor Attribution Validation:**
    *   Compute the Pearson correlation coefficient between each category (Heat, Flow, Wind, Human) and the water temperature.
    *   **Cross-Check:** The category with the highest absolute correlation coefficient should generally align with the "most important" factor identified by the Random Forest model.

### 4. Benchmarks and Reference Implementations
*   **Mann-Kendall:** The `pymannkendall` library is the standard Python implementation. You can verify your code's output against the [official documentation examples](https://github.com/mmhs013/pymannkendall) by running the same function on a known monotonic sequence (e.g., `[1, 2, 3, 4, 5]`) and asserting the expected output (e.g., `slope=1.0`, `p-value < 0.05`).
*   **Random Forest:** For feature importance, use the [Scikit-learn User Guide on Feature Importance](https://scikit-learn.org/stable/modules/permutation_importance.html). A robust test is to add a "noise" feature (random Gaussian noise) to your dataset; the skill's output should consistently rank the noise feature as less important than the physical drivers (Heat, Flow, etc.).