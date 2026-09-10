To verify the correctness of the normalization skill without access to ground-truth labels, you can implement a `pytest` suite that uses **invariant-based testing** and **deterministic reference calculations**.

### 1. Independently Computable Reference Values
Use these known string-distance examples to verify your matching logic. The Levenshtein distance ($LD$) is the standard metric for this task.

| Input String A | Input String B | Expected $LD$ | Calculation Chain |
| :--- | :--- | :--- | :--- |
| `"apple"` | `"appel"` | 2 | `a`=0, `p`=0, `p`=0, `e`→`l` (sub), `l`→`e` (sub) |
| `"cat"` | `"cats"` | 1 | `c`=0, `a`=0, `t`=0, `s` (insert) |
| `"error"` | `"err"` | 2 | `e`=0, `r`=0, `r`=0, `o` (del), `r` (del) |

**Pytest Assertion Example:**
```python
def test_levenshtein_logic():
    # Using a standard implementation (e.g., from difflib or custom)
    assert levenshtein("apple", "appel") == 2
    assert levenshtein("cat", "cats") == 1
```

### 2. Dataset-Level Statistical Invariants
Your output must satisfy these structural and logical constraints, which can be checked via `pytest` assertions on the generated `solution.json`:

*   **Completeness**: Every `record_id` present in `test_center_logs.csv` must exist in the `records` list of `solution.json`.
*   **Confidence Bounds**: All `confidence` scores must be in the range $[0.0, 1.0]$.
*   **Unknown Labeling**: If `pred_code == "UNKNOWN"`, then `pred_label` must be an empty string `""`.
*   **Confidence Thresholding**: If `pred_code == "UNKNOWN"`, the `confidence` score must be strictly less than the threshold used for valid matches (e.g., if you use a 0.8 threshold, `assert confidence < 0.8`).
*   **Span Integrity**: For every `span_text`, `assert span_text in raw_reason_text`.

### 3. Cross-Validation Approaches
You can cross-check your Python-based normalization by implementing a secondary, simpler matching method in your test suite and asserting that the primary skill's output is at least as good or consistent.

*   **Alternative Method**: Use `difflib.SequenceMatcher.ratio()` as a secondary check. If your primary skill uses a complex Levenshtein implementation, ensure that for high-confidence matches (e.g., >0.9), the `SequenceMatcher` also reports a high similarity.
*   **SQL/Pandas Verification**: If you have `pandas` installed, perform a group-by operation to verify that the number of unique `pred_code` values does not exceed the number of unique codes in the provided codebook.

```python
def test_codebook_consistency(output_df, codebook_df):
    # Ensure no hallucinated codes
    valid_codes = set(codebook_df['code'])
    pred_codes = set(output_df['pred_code']) - {"UNKNOWN"}
    assert pred_codes.issubset(valid_codes), "Found codes not in codebook"
```

### 4. Benchmarks and Reference Implementations
For industrial text normalization, the following principles serve as your "test oracle":

*   **Normalization Pipeline**: Reference the standard pipeline: `Lowercasing` → `Unicode Normalization (NFKC)` → `Punctuation Stripping` → `Fuzzy Matching`.
*   **Standard Oracle**: Use the **Levenshtein distance ratio** ($1 - \frac{LD}{\max(len(A), len(B))}$) as the baseline for confidence scores.
*   **Reference**: For string similarity, the `difflib` documentation (Python Standard Library) is the authoritative reference for the "Gestalt pattern matching" algorithm, which is the industry standard for Python-native fuzzy matching.