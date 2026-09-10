To verify the OCR extraction pipeline without relying on the skill's own implementation, we establish verification anchors based on document structure invariants, regex formalisms, and cross-validation techniques.

### 1. Independently Computable Reference Values (Regex Anchors)
Since the task requires specific formatting for dates and currency, we define the expected output structure using formal regex patterns that must hold true for any valid output row.

*   **Date Invariant (ISO 8601):**
    *   **Pattern:** `^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$`
    *   **Verification:** Any extracted date must match this regex. For a hypothetical receipt dated "January 5th, 2024", the transformation must result in `2024-01-05`.
*   **Currency Invariant (Two Decimal Places):**
    *   **Pattern:** `^\d+\.\d{2}$`
    *   **Verification:** For a raw OCR string like "1,234.5", the logic must normalize this to `1234.50`. If the raw string is "1234", it must be `1234.00`.

### 2. Dataset-Level Statistical Invariants
These properties must hold true for the final `/app/workspace/stat_ocr.xlsx` file regardless of the OCR accuracy:

*   **Completeness Constraint:** The number of rows in the Excel file (excluding the header) must exactly equal the number of image files in `/app/workspace/dataset/img`.
    *   *Assertion:* `len(df) == len(os.listdir('/app/workspace/dataset/img'))`
*   **Ordering Invariant:** The output must be sorted lexicographically by the `filename` column.
    *   *Assertion:* `assert df['filename'].tolist() == sorted(df['filename'].tolist())`
*   **Schema Integrity:** The output must contain exactly three columns: `['filename', 'date', 'total_amount']`.
    *   *Assertion:* `assert list(df.columns) == ['filename', 'date', 'total_amount']`

### 3. Cross-Validation Approaches
To verify the extraction logic independently, we can use a secondary, simplified extraction method (a "Golden Reference" script) to compare against the skill's output.

*   **Alternative Tooling:** Use `grep` or `sed` via `subprocess` to perform a "dumb" extraction of potential currency values from the raw image text (if the text is pre-extracted) to verify the skill's logic.
*   **Cross-Check Logic:**
    ```python
    # Example of a cross-check assertion
    def test_total_amount_format(output_df):
        # Ensure no values have more than 2 decimal places
        for val in output_df['total_amount'].dropna():
            assert len(val.split('.')[1]) == 2
    ```

### 4. Benchmarks and Reference Implementations
For receipt OCR, the standard for "Ground Truth" is the **SROIE (Scanned Receipts OCR and Information Extraction)** dataset.

*   **Reference:** The SROIE dataset (ICDAR 2019) is the authoritative benchmark for this task.
*   **Oracle Strategy:** If you have a known receipt image from the SROIE dataset, you can use the provided ground-truth `.txt` annotation files to compare your skill's output.
    *   **SROIE Format:** The ground truth provides `total` and `date` fields in a JSON/TXT format.
    *   **Test Assertion:**
        ```python
        # If testing against a known SROIE sample
        expected_date = "2024-05-16"
        expected_total = "47.70"
        assert result_df.loc[result_df['filename'] == 'sample.jpg', 'date'].values[0] == expected_date
        assert result_df.loc[result_df['filename'] == 'sample.jpg', 'total_amount'].values[0] == expected_total
        ```
*   **Source:** [ICDAR 2019 Robust Reading Challenge on Scanned Receipts OCR and Information Extraction (SROIE)](https://rrc.cvc.uab.es/?ch=13) provides the standard evaluation metrics (Precision, Recall, F1-score) for these specific fields.