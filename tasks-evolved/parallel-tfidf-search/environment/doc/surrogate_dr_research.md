To verify the correctness of your parallel TF-IDF implementation without relying on the sequential baseline's internal state, you can use the following independent verification anchors, statistical invariants, and cross-validation strategies.

### 1. Independently Computable Reference Values
For a small, controlled corpus, you can manually compute the expected TF-IDF values to verify your parallel implementation's output.

**Example Corpus:**
*   **Doc 1:** "apple banana"
*   **Doc 2:** "apple apple"
*   **Query:** "apple"

**Manual Calculation Steps:**
1.  **Vocabulary:** `{"apple": 0, "banana": 1}`
2.  **Document Frequencies (DF):**
    *   `apple`: 2 (appears in Doc 1 and Doc 2)
    *   `banana`: 1 (appears in Doc 1)
3.  **IDF (using $\log(\frac{N}{DF})$ or $\log(\frac{N+1}{DF+1}) + 1$):**
    *   *Note: Use the exact formula implemented in your engine.*
    *   Assuming $\text{IDF}(t) = \log(\frac{\text{Total Docs}}{\text{Docs with } t})$:
    *   $\text{IDF}(\text{apple}) = \log(2/2) = 0$
    *   $\text{IDF}(\text{banana}) = \log(2/1) \approx 0.693$
4.  **TF-IDF Scores:**
    *   Doc 1: `apple` = $0.5 \times 0 = 0$; `banana` = $0.5 \times 0.693 = 0.3465$
    *   Doc 2: `apple` = $1.0 \times 0 = 0$
5.  **Verification:** Assert that your `build_tfidf_index_parallel` produces these exact values for this specific input.

### 2. Dataset-Level Statistical Invariants
These properties must hold true regardless of the parallelization strategy:

*   **Non-Negativity:** All TF-IDF scores must be $\ge 0$.
    *   *Assertion:* `assert np.all(index.tfidf_matrix >= 0)`
*   **Sparsity:** If the corpus is large, the TF-IDF matrix should be sparse.
    *   *Assertion:* `assert (index.tfidf_matrix != 0).sum() < (index.tfidf_matrix.shape[0] * index.tfidf_matrix.shape[1]) * 0.5` (adjust threshold based on data).
*   **Score Range:** If using cosine similarity, all search results must have a score in the range $[0, 1]$.
    *   *Assertion:* `assert all(0 <= result.score <= 1 for result in search_results)`
*   **Completeness:** The number of documents in the index must equal the number of documents provided in the input.
    *   *Assertion:* `assert len(index.documents) == len(input_documents)`

### 3. Cross-Validation Approaches
You can cross-check your implementation by comparing it against `scikit-learn`, which is the industry standard for TF-IDF.

*   **Method:** Use `sklearn.feature_extraction.text.TfidfVectorizer` to compute the TF-IDF matrix for the same input corpus.
*   **Code Snippet for Pytest:**
    ```python
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np

    def test_against_sklearn(documents):
        # Your parallel implementation
        parallel_index = build_tfidf_index_parallel(documents)
        
        # Sklearn reference
        vectorizer = TfidfVectorizer(use_idf=True, norm='l2')
        sklearn_matrix = vectorizer.fit_transform(documents)
        
        # Compare (allow small tolerance for floating point differences)
        assert np.allclose(parallel_index.tfidf_matrix, sklearn_matrix.toarray(), atol=1e-5)
    ```

### 4. Benchmarks and Reference Implementations
*   **Scikit-Learn Documentation:** Use the [TfidfVectorizer API reference](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) to understand the exact normalization and smoothing parameters (e.g., `smooth_idf`, `sublinear_tf`) that define the "correct" output.
*   **Consistency Check:** To verify that parallelization does not introduce non-determinism, run the search multiple times on the same input and assert that the results are identical:
    ```python
    def test_parallel_determinism(documents, queries):
        result1, _ = batch_search_parallel(queries, index)
        result2, _ = batch_search_parallel(queries, index)
        assert result1 == result2
    ```