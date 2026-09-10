To verify the correctness of your `report.json` output without relying on the skill's execution, you can use the following verification anchors and cross-validation methods. These are designed to be implemented as `pytest` assertions.

### 1. Independently Computable Reference Values
Since you cannot access the live GitHub API during the test, you must use a **static subset** of data for your surrogate test.

*   **Test Case Input (Mock Data):** Create a `test_data.json` file containing 3 PRs and 2 Issues from December 2024.
    *   **PR 1:** Created `2024-12-01T10:00:00Z`, Merged `2024-12-03T10:00:00Z` (Duration: 2.0 days).
    *   **PR 2:** Created `2024-12-05T10:00:00Z`, Merged `2024-12-10T10:00:00Z` (Duration: 5.0 days).
    *   **PR 3:** Created `2024-12-15T10:00:00Z`, Closed (not merged).
*   **Computation Chain:**
    *   **Total PRs:** 3
    *   **Merged PRs:** 2
    *   **Closed PRs:** 1
    *   **Avg Merge Days:** $(2.0 + 5.0) / 2 = 3.5$
*   **Assertion:**
    ```python
    # Example pytest assertion
    assert report["pr"]["avg_merge_days"] == 3.5
    assert report["pr"]["total"] == 3
    ```

### 2. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the specific data retrieved, serving as "sanity checks" for your logic.

*   **Non-Negativity:** `total`, `merged`, `closed`, `bug`, and `resolved_bugs` must be $\ge 0$.
*   **Subset Constraint:** `merged` + `closed` (non-merged) should equal `total` PRs.
*   **Bug Constraint:** `resolved_bugs` must be $\le$ `bug` (total bug reports).
*   **Time Bound:** `avg_merge_days` must be $\ge 0$. If `merged` is 0, `avg_merge_days` should typically be 0 or `null`.
*   **Assertion:**
    ```python
    assert report["pr"]["merged"] <= report["pr"]["total"]
    assert report["issue"]["resolved_bugs"] <= report["issue"]["bug"]
    assert report["issue"]["bug"] <= report["issue"]["total"]
    ```

### 3. Cross-Validation Approaches
You can verify the skill's logic by running an independent, minimal SQL-like aggregation on the raw JSON output from the `gh` CLI.

*   **Alternative Method:** Use `jq` to perform the same calculation as the Python script. If the `jq` result matches the `report.json` result, the logic is verified.
*   **Command:**
    ```bash
    # Verify total PRs using jq
    gh pr list -R cli/cli --search "created:2024-12-01..2024-12-31" --json number | jq 'length'
    ```
*   **Verification Logic:**
    ```python
    import subprocess
    import json

    def test_pr_total_count():
        result = subprocess.check_output(['gh', 'pr', 'list', '-R', 'cli/cli', '--search', 'created:2024-12-01..2024-12-31', '--json', 'number'])
        count = len(json.loads(result))
        with open('/app/report.json') as f:
            report = json.load(f)
        assert report["pr"]["total"] == count
    ```

### 4. Benchmarks and Reference Implementations
*   **GitHub API Schema:** Pull requests are technically issues in the GitHub API. Any PR is an issue, but not every issue is a PR. Your logic must ensure you are querying the `pr` endpoint specifically for PR metrics and the `issue` endpoint for issue metrics to avoid cross-contamination.
*   **Time-to-Merge Definition:** The standard industry definition for "Time to Merge" is the difference between `created_at` and `merged_at`. Ensure your Python script uses `datetime.strptime` with the `%Y-%m-%dT%H:%M:%SZ` format to parse these ISO 8601 strings correctly.