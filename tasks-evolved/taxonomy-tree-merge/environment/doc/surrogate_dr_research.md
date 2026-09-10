To verify the unification of product taxonomies without relying on the skill's internal logic, you must implement a test suite that enforces structural integrity and semantic constraints based on the provided rules.

### 1. Independently Computable Reference Values (Verification Anchors)

Since the exact clustering output depends on the embedding model, you cannot hard-code the final cluster assignments. Instead, use **deterministic lexical anchors** for known category paths.

*   **Anchor Case:** Input `"Electronics > Computers > Laptops"` and `"Consumer Electronics > PCs"`.
*   **Verification Logic:**
    *   **Word Overlap Constraint:** The skill must map these to the same `unified_level_2` (e.g., "Computers").
    *   **Calculation:**
        *   `Set("Electronics", "Computers", "Laptops")` $\cap$ `Set("Consumer", "Electronics", "PCs")` = `{"Electronics"}`.
        *   Jaccard Similarity of normalized sets must be $> 0$ but $< 0.3$ for distinct siblings.
    *   **Assertion:** `assert set(row1_level2.split(" | ")) & set(row2_level2.split(" | "))` must be non-empty for semantically identical inputs.

### 2. Dataset-Level Statistical Invariants

These invariants must hold true regardless of the clustering algorithm used. Implement these as `pytest` assertions:

*   **Completeness (Row Count):** `len(unified_taxonomy_full) == len(amazon) + len(fb) + len(google)`.
*   **Hierarchy Depth:** `assert unified_taxonomy_full['depth'].isin([1, 2, 3, 4, 5]).all()`.
*   **Pyramid Structure (Constraint 6):**
    *   `assert 10 <= df['unified_level_1'].nunique() <= 20`
    *   For any `level_n` (1-4), the number of unique `level_n+1` values per `level_n` must be in the range `[3, 20]`.
*   **Naming Constraints (Constraint 2 & 4):**
    *   `assert all(len(name.split(" | ")) <= 5 for name in df['unified_level_1'])`
    *   `assert all(level_n != level_n_plus_1 for row in df)` (Parent-child name overlap check).

### 3. Cross-Validation Approaches

Use an alternative, non-ML method to verify the "representative" nature of the clusters (Constraint 2).

*   **Method:** **TF-IDF + Cosine Similarity** using `scikit-learn`'s `TfidfVectorizer`.
*   **Verification Code Snippet:**
    ```python
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    def test_representativeness():
        # Vectorize the input category paths and the assigned unified label
        vectorizer = TfidfVectorizer()
        # Calculate cosine similarity between the unified label and its subcategories
        # Assert that the average similarity > 0.7 (70% threshold)
        tfidf_matrix = vectorizer.fit_transform(all_paths)
        # ... compute similarity ...
        assert mean_similarity >= 0.7
    ```

### 4. Benchmarks and Reference Implementations

To validate the taxonomy structure, compare the output against the **IAB (Interactive Advertising Bureau) Tech Lab Content Taxonomy 3.0**.

*   **Source:** [IAB Tech Lab Content Taxonomy](https://iabtechlab.com/standards/content-taxonomy/)
*   **Usage:** The IAB taxonomy is the industry standard for 5-level hierarchical classification.
*   **Test Oracle:**
    *   Map your `unified_level_1` categories to the top-level IAB categories.
    *   **Assertion:** `assert set(unified_taxonomy['unified_level_1'].unique()).issubset(set(iab_top_level_categories))`.
    *   This ensures your unified taxonomy is not creating arbitrary, non-standard top-level categories.

### Summary of Pytest Assertions to Implement

| Test Name | Assertion Logic |
| :--- | :--- |
| `test_row_count` | `df_full.shape[0] == sum(input_counts)` |
| `test_hierarchy_width` | `df.groupby('unified_level_1')['unified_level_2'].nunique().between(3, 20).all()` |
| `test_naming_length` | `df['unified_level_1'].apply(lambda x: len(x.split(' | ')) <= 5).all()` |
| `test_parent_child_distinct` | `df.apply(lambda r: r['unified_level_1'] != r['unified_level_2'], axis=1).all()` |
| `test_iab_compliance` | `set(df['unified_level_1']) <= set(iab_reference_list)` |