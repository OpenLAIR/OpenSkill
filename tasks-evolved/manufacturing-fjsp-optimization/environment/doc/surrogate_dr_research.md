To verify the output of your Flexible Job-Shop Scheduling (FJSP) solver, you can implement a `pytest` suite that treats the generated `solution.json` and `schedule.csv` as inputs for a feasibility validator. Since you cannot rely on the solver's internal logic, your test must independently re-verify all constraints.

### 1. Independently Computable Reference Values
For a small, manually verifiable instance (e.g., 2 jobs, 2 machines), you can pre-calculate the expected makespan.
*   **Example Instance:**
    *   Job 1: Op1 (M1, dur=3), Op2 (M2, dur=2)
    *   Job 2: Op1 (M1, dur=2), Op2 (M2, dur=3)
*   **Computation Chain:**
    *   If M1 processes J1-Op1 (0-3) then J2-Op1 (3-5).
    *   If M2 processes J2-Op2 (5-8) then J1-Op2 (8-10).
    *   **Result:** Makespan = 10.
*   **Pytest Assertion:** Hard-code this as a test case where you load a known small instance and assert `output['makespan'] == 10`.

### 2. Dataset-Level Statistical Invariants
These invariants must hold true for any valid schedule regardless of the specific instance:
*   **Precedence Constraint:** For every job $j$, the end time of operation $o$ must be $\le$ the start time of operation $o+1$.
    *   `assert df[df['job'] == j].sort_values('op')['end'].shift(1) <= df[df['job'] == j].sort_values('op')['start']`
*   **Non-Overlap Constraint (Machine):** For any machine $m$, the time intervals $[start, end)$ must not overlap.
    *   Sort by `machine` and `start`. Check that for any two consecutive operations on the same machine, `start_next >= end_prev`.
*   **Downtime Constraint:** No operation interval $[start, end)$ can overlap with any downtime window $(ds, de)$ defined in `downtime.csv`.
    *   `assert not (start < de and end > ds)` for all downtime intervals.
*   **Policy Budget Invariants:**
    *   **L1 Shift:** $\sum |start_{new} - start_{base}| \le \text{Budget}_{L1}$.
    *   **Reassignment:** Count of rows where $machine_{new} \neq machine_{base} \le \text{Budget}_{Reassign}$.

### 3. Cross-Validation Approaches
You can use `pandas` to perform a "simulation" of the schedule to verify it independently:
```python
def test_schedule_feasibility(solution_df, downtime_df):
    # 1. Check Precedence
    for job_id, group in solution_df.groupby('job'):
        sorted_ops = group.sort_values('op')
        assert (sorted_ops['start'] >= sorted_ops['end'].shift(1).fillna(0)).all()

    # 2. Check Machine Overlap
    for machine_id, group in solution_df.groupby('machine'):
        sorted_ops = group.sort_values('start')
        assert (sorted_ops['start'] >= sorted_ops['end'].shift(1).fillna(0)).all()

    # 3. Check Downtime
    for _, row in solution_df.iterrows():
        for _, d in downtime_df[downtime_df['machine'] == row['machine']].iterrows():
            # Check for overlap: max(start, ds) < min(end, de)
            assert not (max(row['start'], d['ds']) < min(row['end'], d['de']))
```

### 4. Benchmarks and Reference Implementations
*   **Standard Instances:** Use the **Brandimarte (1993)** or **Hurink (1994)** datasets. These are the gold standard for FJSP.
*   **Verification Oracle:** You can use the `FJSPLib` or `PyJobShop` documentation to find the "Best Known Solutions" (BKS) for these instances.
*   **Test Oracle:** If your solver produces a makespan significantly higher than the BKS for a standard instance, your test suite should flag it as a performance regression.
*   **Constraint Programming:** If you need to verify if a *better* schedule exists, you can use a simple `OR-Tools` CP-SAT script as a reference solver in your test suite to solve the same small instance and compare the makespan.