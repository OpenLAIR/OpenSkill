To verify the demographic analysis report, you can implement a `pytest` suite that treats the generated Excel file as an immutable data source. Since you cannot access the ground-truth solution, you must rely on **data invariants** (mathematical properties that must hold true regardless of the specific data values) and **cross-validation** (re-computing specific aggregates using independent logic).

### 1. Dataset-Level Statistical Invariants
These assertions verify the integrity of the transformation process. They should be checked against the `SourceData` sheet and the resulting pivot tables.

*   **Row Count Invariant**: The number of rows in the `SourceData` sheet must equal the number of rows in the input `income.xlsx` file.
    *   *Assertion*: `assert len(df_source) == len(df_income_input)`
*   **Completeness Invariant**: Every `STATE` present in the input must exist in the output pivot tables.
    *   *Assertion*: `assert set(pivot_table_population.index) == set(df_income_input['STATE'].unique())`
*   **Aggregation Invariant (Summation)**: The sum of `POPULATION_2023` across all states in the pivot table must equal the total sum of `POPULATION_2023` in the raw data.
    *   *Assertion*: `assert pivot_table_population['POPULATION_2023'].sum() == df_source['POPULATION_2023'].sum()`
*   **Derived Column Invariant**: The `Total` column in `SourceData` must strictly satisfy `Total = EARNERS * MEDIAN_INCOME`.
    *   *Assertion*: `assert (df_source['Total'] == df_source['EARNERS'] * df_source['MEDIAN_INCOME']).all()`
*   **Quartile Distribution Invariant**: The number of records assigned to "Q1", "Q2", "Q3", and "Q4" in `SourceData` should be approximately equal (if using `qcut`), or at least all four categories must be present.
    *   *Assertion*: `assert set(df_source['Quarter'].unique()) == {'Q1', 'Q2', 'Q3', 'Q4'}`

### 2. Cross-Validation Approaches
Use these methods to independently verify the pivot table calculations.

*   **SQL-Style Verification**: Use `pandas` to perform a "manual" groupby aggregation and compare it to the pivot table output.
    ```python
    # Independent verification of "Population by State"
    expected_pop = df_source.groupby('STATE')['POPULATION_2023'].sum()
    pd.testing.assert_series_equal(
        pivot_table_population['POPULATION_2023'], 
        expected_pop, 
        check_names=False
    )
    ```
*   **Cross-Tabulation Check**: For the "State Income Quartile" sheet, verify the counts independently using `pd.crosstab`.
    ```python
    # Independent verification of Quartile counts
    expected_quartiles = pd.crosstab(df_source['STATE'], df_source['Quarter'])
    # Compare this structure against the generated pivot table
    ```

### 3. Reference Implementation Logic
When writing your `pytest` assertions, use the following logic to define your "oracles":

| Pivot Table Sheet | Verification Logic |
| :--- | :--- |
| **Population by State** | `df.groupby('STATE')['POPULATION_2023'].sum()` |
| **Earners by State** | `df.groupby('STATE')['EARNERS'].sum()` |
| **Regions by State** | `df.groupby('STATE')['SA2_REGION'].nunique()` |
| **State Income Quartile** | `df.pivot_table(index='STATE', columns='Quarter', values='EARNERS', aggfunc='sum')` |

### 4. Implementation Note for `pytest`
To make these tests robust:
1.  **Load the generated file** using `pd.read_excel(..., sheet_name=None)` to get a dictionary of all sheets.
2.  **Use `pd.testing` utilities**: Always prefer `pd.testing.assert_frame_equal` or `pd.testing.assert_series_equal` over manual equality checks, as they provide detailed diffs when tests fail.
3.  **Handle NaNs**: Explicitly define how to handle missing values in your assertions (e.g., `na_action='ignore'` or filling with 0) to prevent false negatives.