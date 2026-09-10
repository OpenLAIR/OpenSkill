# Domain Reference for evo-semantic-hierarchical-clustering

**Responsibility**: Offline embedding generation using sentence-transformers 2.5.1, condensed distance matrix computation, recursive top-down clustering with min/max children constraints to produce strictly nested 5-level cluster IDs.

**Key functions to implement**: generate_normalized_embeddings, compute_condensed_distance, recursive_top_down_cluster, extract_flat_clusters, enforce_size_balance

---

## 1. Sentence-Transformers 2.5.1: Embedding Short Category Strings


The `sentence-transformers` library (version 2.5.1) provides the foundational semantic representation for category strings. Because the system lacks LLM API access, computing dense vector embeddings locally is the sole method for capturing the semantic overlap between strings like `"Electronics > Computers > Laptops"` and `"Consumer Electronics > PCs"`.

### 1.1 Model Selection and Specifications

For short-text semantic similarity within a CPU-constrained, 500-second timeout window, the `all-MiniLM-L6-v2` model is strongly recommended [cite: 1, 9]. 
*   **Dimensions:** It maps text to a 384-dimensional dense vector space [cite: 1, 10].
*   **Size:** It contains approximately 22 million parameters, distributed across 6 transformer layers, and occupies only ~90MB of disk space [cite: 10, 11].
*   **Inference Speed:** It is heavily optimized for CPU inference, processing up to ~14,000 sentences per second, compared to the ~4,000 sentences per second of larger models like `all-mpnet-base-v2` [cite: 2]. While `all-mpnet-base-v2` offers 768-dimensional embeddings and slightly higher benchmark accuracy (110 million parameters), its higher computational cost may jeopardize the 500-second timeout if data volume scales unexpectedly [cite: 2].

### 1.2 Exact API Signature and Usage

The correct import path is `from sentence_transformers import SentenceTransformer` [cite: 12, 13]. The `encode` method transforms raw text into embeddings. 

The signature and critical parameters for `SentenceTransformer.encode()` in version 2.5.1 include [cite: 12, 13]:
*   `batch_size` (int): Determines how many strings are processed simultaneously. A default of `32` is standard, though CPU systems can often scale this to `128` or `256` depending on available RAM.
*   `show_progress_bar` (bool): Useful for logging, but can be set to `False` to reduce stdout noise in automated agents [cite: 12].
*   `convert_to_numpy` (bool): Defaults to `True`. Returns a standard `numpy.ndarray`, which is strictly required for downstream Scikit-learn and SciPy compatibility.
*   `convert_to_tensor` (bool): Should be `False` for this pipeline, as PyTorch tensors are not directly consumable by Scipy's spatial modules.
*   `normalize_embeddings` (bool): **Crucial parameter.** When set to `True`, the resulting vectors are L2-normalized [cite: 12, 14, 15]. This normalization allows the computationally expensive cosine distance to be calculated natively or simplifies it to a dot product, substantially boosting retrieval and clustering speeds.

**Deprecation Pitfall in 2.5.1:** Version 2.5.1 enforces strict parameter validation. Passing unused keyword arguments (such as the legacy `normalize=True` instead of `normalize_embeddings=True`) will throw a `ValueError: SentenceTransformer.encode() has been called with additional keyword arguments` [cite: 16].

### 1.3 Handling Offline Execution and Truncation

In offline Docker environments, the library will attempt to connect to Hugging Face by default and crash if unauthenticated or disconnected. To bypass this, the model must be downloaded during the Docker build phase. At runtime, the model should be loaded from a local directory.
Furthermore, transformer tokenizers truncate sequences exceeding a maximum length (typically 256 word pieces for MiniLM) [cite: 1, 10]. For deeply nested category paths (e.g., 10+ levels), ensure that the strings do not exceed this limit, or truncate them preemptively, prioritizing leaf nodes which carry the most specific semantic meaning.

### 1.4 Code Implementation: Embedding Generation

```python
import os
import numpy as np
from sentence_transformers import SentenceTransformer

def get_normalized_embeddings(category_paths: list[str], model_path: str = 'all-MiniLM-L6-v2') -> np.ndarray:
    """
    Generates L2-normalized embeddings for a list of category paths.
    In an offline environment, model_path should point to a local directory.
    """
    # Initialize the model (loads from local path if specified, else downloads)
    # To ensure offline capability, set the environment variable HF_HOME to a cached directory
    model = SentenceTransformer(model_path)
    
    # Encode with strict 2.5.1 kwargs
    embeddings = model.encode(
        category_paths,
        batch_size=128,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True  # Strictly required for accurate cosine distance clustering
    )
    return embeddings
```

---

## 2. Scikit-learn 1.4.0 and SciPy 1.12.0 Hierarchical Clustering APIs


Unifying three separate taxonomies requires mapping thousands of overlapping categories into a rigid 5-level structure. Agglomerative (bottom-up) hierarchical clustering is the standard method for this task.

### 2.1 Scikit-Learn 1.4.0: `AgglomerativeClustering`

In Scikit-learn 1.4.0, the `AgglomerativeClustering` API underwent a major parameter rename to standardise distance definitions. 
*   **Deprecation of `affinity`:** The `affinity` parameter has been officially deprecated and replaced by the `metric` parameter [cite: 3, 4, 17]. Using `affinity` in 1.4.0 will trigger warnings and potential application failure [cite: 3].
*   **Accepted `metric` values:** `euclidean`, `l1`, `l2`, `manhattan`, `cosine`, or `precomputed` [cite: 17]. Since we are dealing with text embeddings, `cosine` or `precomputed` are the mathematically sound choices [cite: 18]. Note that if the `linkage` parameter is set to `ward`, the metric *must* be `euclidean` [cite: 17]. 
*   **Linkage Criteria (`linkage`):** Determines how distance between clusters is measured. Options include `ward` (minimizes variance), `average` (average distance of all points), `complete` (maximum distance), and `single` (minimum distance) [cite: 17]. `average` linkage paired with `cosine` metric frequently yields the most semantically coherent clusters for NLP tasks [cite: 17].
*   **Building Dendrograms:** By default, Scikit-learn does not compute the full distance matrix for the hierarchical tree. To extract `.distances_` and `.children_` for dendrogram construction or tree-cutting, you must set `compute_distances=True` (added in recent versions) or `distance_threshold=0` [cite: 17, 19, 20].

### 2.2 SciPy 1.12.0: `linkage`, `fcluster`, and the Condensed Distance Matrix

While Scikit-learn provides an excellent high-level wrapper, SciPy 1.12.0 provides granular control over the hierarchical tree structure, which is essential for forcing exactly 5 hierarchical levels. 

**The Uncondensed Matrix Pitfall:**
The most common point of failure when using SciPy's `scipy.cluster.hierarchy.linkage` is passing a 2D square distance matrix. The function strictly expects a **1D condensed distance matrix** [cite: 5, 21]. Passing an \(N \times N\) matrix will trigger a `ClusterWarning: The symmetric non-negative hollow observation matrix looks suspiciously like an uncondensed distance matrix` and may result in nonsensical clustering topology [cite: 5, 6].
To resolve this, use `scipy.spatial.distance.squareform` to convert a 2D square matrix to a 1D condensed array, or compute the condensed array directly using `scipy.spatial.distance.pdist(X, metric='cosine')` [cite: 5, 22, 23].

**Cutting the Tree:**
The `scipy.cluster.hierarchy.fcluster` function flattens the generated linkage matrix `Z` into discrete cluster assignments [cite: 24, 25]. 
*   `criterion='maxclust'`: Finds a distance threshold that results in exactly `t` clusters [cite: 24, 25].
*   `criterion='distance'`: Forms clusters where no two items have a distance greater than `t` [cite: 24, 25, 26].

### 2.3 Code Implementation: Distance Matrix and SciPy Linkage

For optimal performance within the 500-second window, bypassing Scikit-learn's wrapper and directly using SciPy's `pdist` and `linkage` is computationally faster and requires less memory overhead.

```python
import numpy as np
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster

def compute_hierarchical_tree(embeddings: np.ndarray) -> np.ndarray:
    """
    Computes the hierarchical linkage matrix using SciPy.
    """
    # Compute 1D condensed distance matrix directly (memory efficient)
    # pdist computes O(N^2) pairwise distances. For N=5000, this is ~12.5M floats (~100MB RAM)
    condensed_dist_matrix = pdist(embeddings, metric='cosine')
    
    # Perform agglomerative clustering using 'average' linkage
    # Returns an (N-1) x 4 linkage matrix Z
    Z = linkage(condensed_dist_matrix, method='average', metric='cosine')
    return Z

def extract_flat_clusters(Z: np.ndarray, num_clusters: int) -> np.ndarray:
    """
    Cuts the dendrogram to extract a specific number of clusters.
    """
    # criterion='maxclust' guarantees exactly 'num_clusters' assignments
    labels = fcluster(Z, t=num_clusters, criterion='maxclust')
    return labels
```

---

## 3. Multi-Level Taxonomy Construction Patterns


To achieve a rigid 5-level taxonomy from an arbitrary flat list of category paths, one must deploy structural control patterns. There are two primary paradigms: Bottom-Up Dendrogram Cutting and Top-Down Recursive Clustering.

### 3.1 Bottom-Up Dendrogram Cutting

This method computes a single global linkage matrix `Z` for all items, and then applies `fcluster` five times with progressively larger `maxclust` constraints.
*   **Pros:** Highly efficient. Distances and linkages are computed only once (O(N²) time complexity for `average` linkage) [cite: 21].
*   **Cons:** Cutting a global dendrogram at arbitrary $K$ thresholds does not guarantee perfectly nested child-to-parent relationships in edge cases, as the horizontal cut lines might slice unevenly nested branches. Furthermore, it does not guarantee balanced cluster sizes; it frequently yields heavily populated mega-clusters and degenerate singleton clusters [cite: 27].

### 3.2 Top-Down Recursive Clustering

To guarantee strict parent-child nesting and enforce constraints (e.g., 10-20 categories at Level 1, 3-20 children per parent at deeper levels), top-down recursive clustering is the superior algorithmic pattern [cite: 28, 29, 30]. 
1.  **Level 1:** Cluster the entire dataset into \(K_1\) clusters (e.g., 15 clusters).
2.  **Level 2:** Iterate over each of the 15 Level 1 clusters. For the data points within a single parent cluster, compute a sub-linkage matrix and cluster them into \(K_2\) children.
3.  **Repeat:** Recurse down to Level 5.

**Balancing Cluster Sizes:**
Standard agglomerative clustering is prone to creating singletons (clusters with only 1 item) if outliers are present [cite: 27]. To avoid degenerate taxonomy nodes, one can fall back to size-constrained K-Means or apply a minimum-size check. If a sub-cluster contains fewer than 3 items, it can be mathematically forced to merge with its nearest neighbor centroid, or recursive splitting can be prematurely halted.

### 3.3 Code Implementation: Recursive Top-Down Hierarchy


```python
import pandas as pd

def recursive_clustering(df: pd.DataFrame, embeddings: np.ndarray, current_level: int, max_level: int = 5) -> pd.DataFrame:
    """
    Recursively clusters dataframe subsets to build a strictly nested multi-level taxonomy.
    df must contain an 'item_id' and 'local_index' corresponding to the embeddings array.
    """
    # Base case: if we reached the maximum depth or the group is too small to split
    if current_level > max_level or len(df) < 3:
        for lvl in range(current_level, max_level + 1):
            df[f'level_{lvl}_id'] = df[f'level_{current_level-1}_id'] if current_level > 1 else 0
        return df
    
    # Determine dynamic K based on group size
    # Target 15 clusters for root, then ~5-10 children per parent, capped by data size
    target_k = min(15 if current_level == 1 else 8, len(df) // 2)
    target_k = max(2, target_k) # Minimum 2 splits
    
    # Subset embeddings for current recursive branch
    local_indices = df['local_index'].values
    sub_embeddings = embeddings[local_indices]
    
    # Cluster
    condensed_dist = pdist(sub_embeddings, metric='cosine')
    Z = linkage(condensed_dist, method='average')
    labels = fcluster(Z, t=target_k, criterion='maxclust')
    
    # Create unique identifiers for the new sub-clusters based on parent ID
    parent_prefix = df[f'level_{current_level-1}_id'].iloc + "-" if current_level > 1 else "L1-"
    df[f'level_{current_level}_id'] = [f"{parent_prefix}{lbl}" for lbl in labels]
    
    # Recurse for children
    child_frames = []
    for cluster_id, child_df in df.groupby(f'level_{current_level}_id'):
        processed_child = recursive_clustering(child_df.copy(), embeddings, current_level + 1, max_level)
        child_frames.append(processed_child)
        
    return pd.concat(child_frames, ignore_index=True)
```

---

## 7. Common Pitfalls Specifically for this Task


When an AI coding agent executes this module autonomously within a 500-second window, environmental and logical traps must be preemptively countered.

1. **Hugging Face Hub Timeout/Failure:**
   If the environment lacks internet access, the `SentenceTransformer` initialization will hang attempting to ping `huggingface.co`. 
   *Solution:* Explicitly wrap the loading mechanism in a `try/except` block, and verify the existence of local weight files (e.g., `pytorch_model.bin` or `model.safetensors`) prior to instantiation.

2. **O(N²) Memory Blowup with Large N:**
   Calculating an \(N \times N\) float64 distance matrix consumes \( N^2 \times 8 \) bytes. For 5,000 strings, this is ~200MB, which is safe. However, if the agent inadvertently feeds 50,000 strings (e.g., product item titles instead of category paths), the matrix demands ~20GB of RAM and will trigger an Out-Of-Memory (OOM) kill.
   *Solution:* Hard-cap the input matrix to 10,000 distinct paths before invoking SciPy `pdist`. Use `df.drop_duplicates(subset=['full_path'])` before computing embeddings.

3. **Inconsistent Clustering on Reruns (Reproducibility):**
   While Agglomerative Clustering is deterministic, any fallback methods (like MiniBatchKMeans or TSNE visualization) rely on pseudo-random initializations. 
   *Solution:* Enforce global random seeds (`np.random.seed(42)`) at the entry point of the module.

4. **Scikit-learn 1.4 Deprecation Traps:**
   Beyond the `affinity` deprecation, Scikit-learn 1.4 removes certain legacy attributes. For example, relying on `n_features_in_` is safe, but older scripts checking `n_components_` will fail as it has been replaced by `n_connected_components_` [cite: 17, 39].

---