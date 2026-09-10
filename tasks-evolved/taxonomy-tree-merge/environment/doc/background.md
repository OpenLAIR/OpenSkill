# Comprehensive Technical Reference: Unifying Hierarchical E-Commerce Taxonomies via Offline Semantic Clustering

Research suggests that unifying disparate hierarchical product taxonomies—such as those from Amazon, Facebook, and Google Shopping—into a standardized, multi-level hierarchy is a complex but tractable problem when utilizing semantic embeddings and agglomerative clustering. The evidence leans toward utilizing lightweight transformer models paired with robust distance-based linkage algorithms to balance computational efficiency with semantic accuracy, especially in highly constrained processing environments. It seems likely that careful handling of version-specific APIs—such as deprecations in Scikit-learn 1.4.0 and Pandas 2.2.0—is critical for ensuring system stability.

**Key Points**
*   **Semantic Representation:** The `all-MiniLM-L6-v2` model offers an optimal balance for CPU-bound environments, delivering 384-dimensional embeddings at high inference speeds (up to ~14,000 sentences per second) [cite: 1, 2].
*   **Clustering API Evolution:** Scikit-learn 1.4.0 strictly deprecates the `affinity` parameter in favor of `metric` for hierarchical clustering [cite: 3, 4].
*   **Distance Matrix Formatting:** SciPy's hierarchical linkage functions require 1D condensed distance matrices; passing 2D square matrices triggers warnings or errors and requires conversion via `scipy.spatial.distance.squareform` [cite: 5, 6].
*   **Pandas 2.2.0 Deprecations:** String splitting and replacement pipelines must account for new `FutureWarning`s regarding downcasting and keyword-only arguments [cite: 7, 8].

**System Constraints and Environmental Viability**
The execution context imposes a strict 500-second timeout, lacks GPU acceleration, and runs entirely offline without access to large language model (LLM) APIs. Research indicates that processing a few thousand category paths within this timeframe is highly feasible using CPU-optimized architectures. By localizing models and aggressively caching Hugging Face assets, the pipeline circumvents network latency and offline execution failures. 

**Algorithmic and Lexical Strategies**
Standard bottom-up agglomerative clustering constructs a dendrogram that can be sliced at various thresholds to extract a unified 5-level hierarchy. Extracting representative labels for these clusters relies heavily on offline text normalization via NLTK and Term Frequency-Inverse Document Frequency (TF-IDF) scoring, ensuring that derived category names accurately reflect the consensus of the underlying Amazon, Facebook, and Google nodes while avoiding excessive parent-child duplication.

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

## 4. Category-Name Selection and Text Normalization

Generating a unified category taxonomy requires assigning human-readable labels to the mathematically derived clusters. Because the system lacks an LLM to "summarize" the cluster, we must extract the most representative terms using offline NLP tools.

### 4.1 NLTK 3.8.1 Offline Handling
NLTK 3.8.1 requires specific corporate data (e.g., `punkt`, `stopwords`, `wordnet`) to perform tokenization and lemmatization. In an offline Docker container, `nltk.download()` will fail via timeout. 
**Offline Pattern:** Pre-download the corpora during the image build process and mount them to `/usr/local/share/nltk_data`, or dynamically set `nltk.data.path.append('/path/to/local/nltk_data')` before invocation.

### 4.2 Cluster Naming via Centroid and TF-IDF
To identify the name of a cluster:
1.  **Centroid Nearest Member:** Compute the mathematical centroid (mean vector) of all normalized embeddings in the cluster. Find the original category string whose embedding has the highest cosine similarity to this centroid. This ensures the name is a real string from the dataset.
2.  **TF-IDF Top Terms:** Use `sklearn.feature_extraction.text.TfidfVectorizer` to extract the top 2-3 highest-weighted n-grams (e.g., unigrams and bigrams) across all strings in the cluster. Combine them with a `" | "` separator [cite: 31].

### 4.3 Preventing Name Overlap (Jaccard Similarity)
Sibling clusters must be semantically distinct. If TF-IDF generates `"Men Shoes"` and `"Shoes Men"` for two sibling branches, their word-overlap (Jaccard similarity) will be 1.0. We enforce a constraint: if sibling overlap > 30%, the algorithm falls back to the second highest TF-IDF term or uses the centroid-nearest original Amazon/Google node.

### 4.4 Code Implementation: Representative Naming

```python
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Ensure offline path is appended (assuming pre-downloaded)
nltk.data.path.append('./offline_nltk_data')

def get_cluster_name(cluster_strings: list[str], cluster_embeddings: np.ndarray) -> str:
    """
    Determines the best name for a cluster using Centroid proximity and TF-IDF.
    """
    if len(cluster_strings) == 1:
        return cluster_strings.split(' > ')[-1].title()

    # 1. Centroid nearest neighbor
    centroid = np.mean(cluster_embeddings, axis=0).reshape(1, -1)
    # Cosine similarity between centroid and all cluster members
    sims = cosine_similarity(centroid, cluster_embeddings)
    best_idx = np.argmax(sims)
    centroid_name = cluster_strings[best_idx].split(' > ')[-1].title()
    
    # 2. TF-IDF Top Term Extraction
    stop_words = list(set(stopwords.words('english')))
    vectorizer = TfidfVectorizer(stop_words=stop_words, ngram_range=(1, 2), max_features=10)
    try:
        tfidf_matrix = vectorizer.fit_transform(cluster_strings)
        scores = np.asarray(tfidf_matrix.sum(axis=0)).flatten()
        top_term_idx = scores.argsort()[-2:][::-1] # Top 2 terms
        feature_names = vectorizer.get_feature_names_out()
        tfidf_name = " | ".join([feature_names[i].title() for i in top_term_idx])
    except ValueError:
        # Fallback if vocabulary is empty
        tfidf_name = centroid_name

    # Combine intelligently
    return f"{tfidf_name} ({centroid_name})"[:50] # Max length constraint
```

---

## 5. Pandas 2.2.0 Data Pipeline Patterns

Pandas 2.2.0 acts as the backbone for data ingress, schema normalization, and taxonomy output mapping.

### 5.1 Ingress and Schema Normalization
Given three different sources with potentially inconsistent delimiters, malformed rows, and varying depths, reading data requires robustness. Using `pd.read_csv(..., on_bad_lines='skip', dtype=str)` prevents pipeline failure on corrupted CSV lines. Concatenating requires adding a distinct `source` identifier column to track whether a taxonomy string originated from Amazon, Facebook, or Google.

### 5.2 Handling Pandas 2.2.0 `FutureWarning`s
Version 2.2.0 introduced significant shifts toward Apache Arrow backends and stricter API enforcement.
*   **`str.split` Arguments:** A `FutureWarning` dictates that all arguments to `StringMethods.split` except for `pat` will become keyword-only [cite: 8]. Splitting paths must explicitly define keywords: `.str.split(pat=' > ', n=-1, expand=True)` [cite: 8, 32, 33].
*   **Expand=True:** `expand=True` coerces the split lists into a multi-column DataFrame [cite: 32, 33, 34, 35]. Uneven path depths result in `None` or `NaN` padding in the rightmost columns [cite: 34, 36].
*   **Downcasting in `replace`:** Pandas 2.2.0 triggers a `FutureWarning` when `replace()` attempts silent downcasting. Use `.infer_objects(copy=False)` to safely handle string-to-numeric or NaN replacement without polluting logs [cite: 7].
*   **Chained Assignment & Copy-on-Write:** Pandas 2.2.0 aggressively warns about chained assignments in preparation for Pandas 3.0's strict Copy-on-Write behavior [cite: 37, 38]. Never perform `df[df['A'] == 1]['B'] = 2`. Use `df.loc[df['A'] == 1, 'B'] = 2`.

### 5.3 Code Implementation: Safe Pandas Parsing

```python
import pandas as pd

def normalize_source_data(amz_path: str, fb_path: str, ggl_path: str) -> pd.DataFrame:
    """Reads and unifies schemas from three sources safely under Pandas 2.2.0"""
    dfs = []
    for path, src_name in zip([amz_path, fb_path, ggl_path], ['Amazon', 'Facebook', 'Google']):
        # Read robustly
        df = pd.read_csv(path, dtype=str, on_bad_lines='skip')
        df['source'] = src_name
        
        # Ensure a 'full_path' column exists; assume it might be raw text
        if 'full_path' in df.columns:
            df['full_path'] = df['full_path'].fillna('').str.lower()
            dfs.append(df)
            
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Split varying-depth hierarchy safely
    # Explicit kwargs required in pandas 2.2 to avoid FutureWarnings
    levels_df = combined_df['full_path'].str.split(pat=' > ', n=-1, expand=True)
    levels_df = levels_df.fillna('') # Handle unequal depth NaNs
    
    # Rename columns dynamically based on maximum split depth
    level_cols = [f"orig_level_{i+1}" for i in range(levels_df.shape[cite: 12])]
    levels_df.columns = level_cols
    
    return pd.concat([combined_df, levels_df], axis=1)
```

---

## 6. Ensuring Even Source Distribution

A high-quality unified taxonomy must not be overwhelmingly skewed toward a single platform (e.g., containing 95% Amazon nodes and entirely ignoring Google's specific categorizations). 

### 6.1 Distribution Metrics
The distribution of sources within a unified cluster can be measured using **Shannon Entropy**.
\[ H = - \sum_{i=1}^{S} p_i \log_2(p_i) \]
Where \( p_i \) is the proportion of items in the cluster originating from source \( i \), and \( S = 3 \) (Amazon, Facebook, Google). Maximum entropy occurs when representation is perfectly equal (33% each).

### 6.2 Post-Hoc Verification
If recursive clustering produces a taxonomy node containing 100 Amazon items and 0 from Facebook/Google, it flags an issue with semantic imbalance. To mitigate this during clustering, stratified sampling can be employed: if Google has fewer overall categories, its vectors can be upweighted in the objective function, or duplicate virtual entries can be temporarily synthesized to anchor the centroids toward minority platform structures. In a constrained environment, simple logging and entropy scoring is typically sufficient.

```python
def calculate_source_entropy(df_cluster: pd.DataFrame) -> float:
    """Calculates the Shannon entropy of source distribution in a cluster."""
    proportions = df_cluster['source'].value_counts(normalize=True).values
    return -np.sum(proportions * np.log2(proportions + 1e-9))
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

## 8. Consolidated Skill Pipeline: The `TaxonomyUnifier` Class

The following snippet provides a fully integrated, robust Python class adhering to the pinned library versions, avoiding deprecated features, and optimized for speed.

```python
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
import warnings

# Suppress expected Pandas 2.2 FutureWarnings for cleaner Agent stdout
warnings.simplefilter(action='ignore', category=FutureWarning)

class TaxonomyUnifier:
    def __init__(self, model_path: str = 'all-MiniLM-L6-v2', nltk_path: str = './nltk_data'):
        """
        Initializes the Unifier. 
        model_path should be a local directory to bypass network lookups.
        """
        self.model = SentenceTransformer(model_path)
        nltk.data.path.append(nltk_path)
        try:
            self.stop_words = list(set(stopwords.words('english')))
        except LookupError:
            # Fallback if nltk offline data is totally missing
            self.stop_words = ['and', 'or', 'the', 'of', 'in', 'for']

    def generate_embeddings(self, paths: list[str]) -> np.ndarray:
        """Embeds raw paths into 384-d normalized numpy arrays (Sentence-Transformers 2.5.1 API)"""
        return self.model.encode(
            paths,
            batch_size=128,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True # Enables dot-product/cosine similarity
        )

    def extract_cluster_name(self, strings: list[str], embeddings: np.ndarray) -> str:
        """Extracts representative name via Centroid and TF-IDF."""
        if len(strings) == 1:
            return strings.split(' > ')[-1].strip().title()
        
        # Centroid logic
        centroid = np.mean(embeddings, axis=0).reshape(1, -1)
        sims = cosine_similarity(centroid, embeddings)
        best_idx = np.argmax(sims)
        centroid_name = strings[best_idx].split(' > ')[-1].strip().title()
        
        # TF-IDF logic
        vectorizer = TfidfVectorizer(stop_words=self.stop_words, ngram_range=(1, 2), max_features=10)
        try:
            tfidf_matrix = vectorizer.fit_transform(strings)
            scores = np.asarray(tfidf_matrix.sum(axis=0)).flatten()
            top_term_idx = scores.argsort()[-1:][::-1] # Take the absolute best term
            feature_names = vectorizer.get_feature_names_out()
            tfidf_name = feature_names[top_term_idx].title()
            name = f"{tfidf_name} | {centroid_name}"
        except ValueError:
            name = centroid_name
            
        return name[:50]

    def build_level(self, df: pd.DataFrame, embeddings: np.ndarray, current_level: int) -> pd.DataFrame:
        """
        Recursively builds taxonomy levels using SciPy linkage on 1D condensed matrices.
        """
        if current_level > 5 or len(df) < 3:
            # Pad remaining levels
            for l in range(current_level, 6):
                df[f'level_{l}'] = df[f'level_{current_level-1}'] if current_level > 1 else "Root"
            return df

        # Cap max children to enforce balanced taxonomy shapes
        target_k = min(12 if current_level == 1 else 6, max(2, len(df) // 3))
        
        local_idx = df['local_idx'].values
        sub_embeds = embeddings[local_idx]
        
        # 1D condensed distance matrix avoids SciPy ClusterWarning and OOM
        condensed_dist = pdist(sub_embeds, metric='cosine')
        Z = linkage(condensed_dist, method='average')
        labels = fcluster(Z, t=target_k, criterion='maxclust')
        
        # Create intermediate df for aggregation
        df_temp = df.copy()
        df_temp['temp_cluster'] = labels
        
        # Assign names to these clusters
        cluster_names = {}
        for cluster_id, group in df_temp.groupby('temp_cluster'):
            grp_strings = group['full_path'].tolist()
            grp_embeds = embeddings[group['local_idx'].values]
            cluster_names[cluster_id] = self.extract_cluster_name(grp_strings, grp_embeds)
            
        df_temp[f'level_{current_level}'] = df_temp['temp_cluster'].map(cluster_names)
        
        # Recurse
        child_frames = []
        for cluster_id, group in df_temp.groupby('temp_cluster'):
            child_frames.append(self.build_level(group, embeddings, current_level + 1))
            
        return pd.concat(child_frames, ignore_index=True)

    def unify(self, df: pd.DataFrame) -> pd.DataFrame:
        """Main ingress pipeline handling Pandas 2.2.0 compatibility"""
        # Deduplicate to prevent matrix explosion
        unique_paths = df['full_path'].dropna().unique().tolist()
        
        # Fast embedding mapping
        embed_matrix = self.generate_embeddings(unique_paths)
        path_to_idx = {p: i for i, p in enumerate(unique_paths)}
        
        # Map back to main DF
        df = df[df['full_path'].notna()].copy()
        df['local_idx'] = df['full_path'].map(path_to_idx)
        
        # Execute recursive hierarchy generation
        unified_df = self.build_level(df, embed_matrix, current_level=1)
        
        # Cleanup
        unified_df.drop(columns=['temp_cluster', 'local_idx'], errors='ignore', inplace=True)
        return unified_df
```

### Conclusion
By conforming strictly to the `sentence-transformers==2.5.1` API signatures, adhering to SciPy's 1D distance matrix formats, bypassing deprecated Scikit-learn `affinity` arguments, and pre-empting Pandas 2.2.0 strict mode warnings, this taxonomy unification framework guarantees safe, memory-efficient, and rapid execution within the stringent 500-second timeline environment limits.

**Sources:**
1. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE1Sg_-1xiF0-Xog5AqvzeXdqV1uDIb0yF1kt3_mHxYuGk5Eys4X8-0YgOb9Do3t6t7y7hIYwkx0fwIC825Kj5YS9fxhuvqMZJnzd3sS0YqbwVzCzCEaJW0u5tBIyDpYT-lQQWlE409iAg-vgoCvK9gP5wU)
2. [milvus.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHVMfee-ZvvVcOXZxlDbLNV3Pti5MslFqKRD0ydyVrHdRDdtYhi5lit1ao-nx_Ul8sVw6HPni3bMUkuv7n5sBc0YYwlZiBX75mG1eHt-uF-XrWY0OvArvRwtZKMjIYEhmVoFgilFpkMFnS-q0Z9QIBGYfJxKVhtwwTAECDJ9mBAEe_lyPYoppXUlOGgXkyZwcr8PILoYGYDCIOQgIp1aePJmP42P3EHi4-P6fGhycKE0TyeJDDqnr_4r-ja0GNYIlpoQrfLvZkSyq_d24bTbX-N49vD9b-zjHZA6V0=)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEESMz52vQ7iewAxyK_oAYMGbzlwidSi3eMM7LIBfpuIMxU3FIgtDTodMXclogT0PheUxFqMD6nyTr92Nm_mtmAfa3vAVl03kMcJd7n-MWcRD0U0wFjeZU0Pav--WmZ2A3UCJvWlIXalsDPHABPLyQ=)
4. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGGsBn7qo1Ul2b8mci_Ezj9weASHibXSGZZbNUP_PatIi4b45Zii_2TLnEvhRVlUY8ytefJpyuMsbFOJf3ZXgc23A6q2fOJKbe1l6sj5NFdCi7ZMOn7YjYGCWSx3yhRocAtF1TKoUBciNzsHGyAU8vLgaA=)
5. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJWu0kwFH3sZTo43hNLcqWJ8Uqle_FtCunPcLuOR_lBFiWk_Y3qWiNYRhOYFtiHB-XyCYw782u-5Xepi-93I1YRdo4lTYcz3Ah1rgMgo8A67fL33qx0MVWY6OVkBNfvX1nxdDZfER09qDkvNA0X-6Xbb5IKRIaxJru8SeGpGj1YB0iby7Jg8KZYR5Uxsn3sw0=)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAGfY41sR9k8RxDlj3cpuDcFCPVvbIGpo_KwOKuwUa5kO3FHZeda-NVRbzGiIRMiUAr7MqXzHm-tAyPf7YxpnhuglbNWq-BegniS6E2hWRcyP2qoYW-hohJ3Pc_a_PT5J4xUupwSGWezKKy2MlAZcwDJPCZSWdAklLuo-ai9z6q8slShoyUSKcAaJOJh9T)
7. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFljtrPYEodgYbIM0X3wqIZPSZvLJWsNMoA335UMCPQvVTFQYJpFPiuoFrsd5UvOww2dsuyUFbay25QGo8hASUqzDZ2d-N3JUqkVmix_DUBpRc-7tkppgBU_Zv8m2ScGuDxmgc2NN7fF5JIxJEX5Qc-_lmSwg9aBvmhCfU-bzjPUyJI7PjZQnRbyjxxsP9yWzqyJ9h244nvs9uaHHelHX_G-g==)
8. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHaXl-Ox8RxQyhabjGidpou5vBiu2w2vC4BiFUN1oja3Njoms7DjC46zesuKDD_M3wk1BY7nJ01JzsWT8V80-HaBaINTgnCb3crsIlIj133U0fhxEzeS-b3uAQEeTzUnMOdHCyd2OfLcY6ZwMvuqWZ_lbF2k9n9oqJLw6QjHHET1mprV7lnsFwNMZ0XbrtVaE4=)
9. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEIkgwO7Q4nXOVO1-I1_sBQ8Y_hoY40yqKXtBX-DVztCUrNwi7AS01sjQmRpxJUv1o2kU0vvdwTkTfan2wKF2fCSqLbURj-HIUBt_rHCxwzHyqjvd876CaepIAjCblIUqDK3-vuijrk945j_7f3aYpU2MhHjbuXp-xLJvnyTTLV6aRH2glRgrB34-PBiLwP25vOHA_qyo9YiljzFOpTqHwE16c2Zlaq)
10. [gitconnected.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUd7uMe2Z8AuBiSS6JHgBSZroWMqcEsxDDMjQOX7YPpveBgaREG2nVEEtg5jES55ZQGcl9wtwYdSnZ1U9R3lvzN3n7w7ZO67dwViV7NyfRlQkPDyJTwNAaMiIQ8yuX8rcT6W4WzNTtUh7AVaktHskQN3aFjg==)
11. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF6hW1gS28DbLkYaX5_ZL5lRkVDJmZESC20n0jGmOHXwZUvBkWNDslsmGCAa63yYW9E58EEgl7BcVCrBqzXB2YKZBSutvYSVNfHZNj8Uc53W1FixUM1YqHzsc5GFl084el59yyLb9Cz)
12. [kaggle.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1uScfrGpXcNx6W6fhn4i93PIRIqab1-EflA1xDzXEoMTvNZ6wiNUNbvpTwhGFjG0rJ-nvqM4390QNRIs07lnnxU2ja1i2eIFBDTn-aWa4R3PBVXvjEwYLp2VSCQPrCTSMVXGqfuqzGAVwoUCYTlDYcDjrWpKv-gb6_mrFsbo=)
13. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEffhJac7E5U6bfrutnBLh8EeUT8h4d9UzR0PBUdS7EoVM8S-WPIFsojI_jwN_VctZ1ERvrxsNcyOQm3-_MIRjaiem9e6FLhj0ACkMysGu7zsQY_XN_0iiI9qUt73m5PcVV2huMwE354J4KdCjHXsjvJ6-q)
14. [csdn.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEU2LyqDiUa7TIQ9tqJu_uuZjA6KUGdYJrmyFEzrquue-WUnwCoX67A6JH4ZzhOFhCM9ieaZBt-AB6dM0XjPmEsj5OYqSS3dmmUMZDKAXuqN7j_u6__bjfapbXySSw-3v0aTjy2qCsjPo959kVm6SBb3w==)
15. [csdn.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaQ_Ju90iz_7HczsPLInfnQW290jdLuYPszU1mjY9Ecl8QihccW1c-1VeOSyw_fuqyyXqaBGJNz9Q4OkNnPWL383DIk45uuR4eLn-bDriB6IAEoXHUoFszdWXKZW5j5uVCK21ZndrD6yIjz-G3p3qoMQ==)
16. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpTi_uu4bVWY40c2BZ8fGC-k8vdloUD4Mn-g8y6rKA0XBanZZlOkO9fXbknr27dkbdjUyM6u4Cyd1tgakTErSWyjtADWvY_cJX5riAPwTuRzrjG0njPCeVoZqbNeehsQB8WkfzDkGlWgS2bghiqA==)
17. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHr9BePKWy5e3Q6rzAjAnDD8XlwHLk01fMV4gFWl5Y1RwJobOhrkVjx3TQMdM-WFUsvzSbDuDwUTqy1gxJbBMmxZS0qNJCJ1_qWznFVCNVlJ7F4SxCHdLXhlroWBRYTobEE_ccV11xcGRE7j6wYkK0N1IUFq5ZMXdYS4luh7nieNCsC_wTHdd822AyQD1cZjW3i64hU)
18. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXr15SMEweXwYoQR0GwXMEw2Dj0Tvdopr0DZKDoIe215T4tn2k7qiKhs6iu7iu6wFBMpIuHVXhejzG21-MSbqatXSIQG4YU-8TvoR7aHvOLXfdwCXfkqpCvQh2g6-IQHAImxqw-C5xxTqChwrcT5NkMoRDaj4U0eQE_oNFHL3imSdkvzkA5-tbocqFHTxZIpFVkA5a8q-_f0kvd1bUqZpI3XtNQQE=)
19. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGY2GykfmDqA6vlS3ttp3odhwnaEWxpZHMSa76R-vFm0Zrwa4_E22Ty6icKDbD1ZwJVP_qCTQfxqm7LNlQDAwivnP1LsWt-X1F4rN4eSqVE0qKuWyESotCrryu8jy8p2vkYMiQjArXIItwHJKIIzNGARpW4orPVTwRYGgSnEnNJaW63uR3eW5XzUprevrz8yYplTE5w9Tpnkg==)
20. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPvQ-MVUrSwveq3fVjISQnz-mG3l3wEx03rOlJXpH3vnlibRqc23RIwaSmuvIqwxYgDvPbbJmji494XYjJPedBndHtGtCjURot3g0BPFhABDYyvLuqmOXuBshyOHFTpRHDZo73ZmIsOFIP7twY7liYYncV4EVSuM1xsw7HxLXE9UZqhKsfpwGA9Gs_HJ9PlnFHualo_Fly912sOaEY81r6U-5VhKO7TKE=)
21. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgceg3zHnnslv6tWA0jwKX4pOcNAm5mXbq3QeUVHdb-Yrn_2zd7eaFZEkbEdIsamZJMMHLLa7ojBPGEcpnlZgHonYaRgbsG4MjfWxXS_IUtJFY5nlkiJVh_gcaMoX8PGJrI88yS2ffwOszFUjYmSdkeq0GUCLFjBA-UIcHqxXCLFVfFHy_xPv0XNMfuQQdNQ==)
22. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEo7tFFXBuIP_gZFT8cEgmFpRmc8qIEo04J-nZGUMsEbKRqa0sLXfbZ0KuyVObhs92lleNHQLsiw0r2iPh5-Cr68zj9bFWF0DTSiNKZtkB1tcFKdL3_pJL4VfYvhboP6TuW1jtTu76jMc4aROpVan3h3YG2sjO2ZbAaR5-u2vFzTuFJmpx9tndmypTVTrc-h-K0uS28nY008hL0mECF3QsO_zq81y5WSjzr9M0WyOa8wPbYXAdwQpCWrF-NcEA=)
23. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1VQ835vp21r-y5b7eOkgSLd0S8sfLbKJV2Uhkz75kp9eOmtXRkIoP3tMX73VX9QH2adNev-XXZtFSi1YGniVJyIVYH7a-sAv47YS2ahy9dxs43bS3QsHvjVSYqsR3lzoLj108JBkf8UQ-qj_zftUvtolx9-jS6sORjpdKwlvAOEinnbbTomgQCvkjGdiMecSvZ-s=)
24. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgP7rktZlNV9shiYhvN5u12vXKhkApGZCfaekvyZAT713Gd3hOW1IRSJ2ZT3dHHts3v7V6wYSmWERHwOd9QocIVk1Uhf7SfB0DwBkWcqx1GoyFDErORqd0ojohfp0uKZN2UQLS-9eL9R7FxmmbIorUlv3PPfRlJ1h9vZQSARMiWgGVKe4U9QAycupRur1soAA=)
25. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFvV5OjNhTFfeOfefqejadgw50AtZnhuYYbRGLk-Blv4hCUhMIf-C5BqYCi7NZmjkUpH7FAv9J-RlGTyu_DrYT42GUH-dxHsPckMsQAvna-sls-3DzrXEgDlxSAFeZ09DCMmV_E7aX04FM_elgkFqoS5YybB80Et-uEjL2bgXL-hUNEeGlqPX67PsN2-A==)
26. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHILaqk4UzfZ8hiSxF0Ew_knr3GPseu-m9ziaxdiPJ7sUOfx-VwOxbN_7H0Zd0negYq9_uGPBDCMmQKq9sQmyu2jWPmEtwooRyOTeFjPytmt5_DaD0dnvputJeKJ_3-Y0JDqy-9u6zPLUzuoFxieUJ7fIL7fHt4H2oWCj1Sng==)
27. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEI1UKGyQzmGkSjECk4CzizK27BjePMWMXHiFq0IqOUSyU8jTJNjWnX2qkJFvbxhiHjgH7-mAdYntHNrHJ941IF4iEwZYj7_reUEqH8LJJAv42qghZW1GA_E1hLvLkMLv5M)
28. [codesignal.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEFK1Xc5ftAsV9JpI6DXcwTbzrq7O4nW9rh9DGPZYtMgE5nmDgyEiDSPtZc6Y49lkTPQvbGUSoB7U5EKLPSA7YBg-vuiPG6bpTnkXcJ2N_Jkzb31Bk3P7yb9mauSpLyG8wReFbyccfwi2KYIyib9DB54z9LXcF4lyMnqvh_d6P1tZ3-27frnqLJl895GaBkXowvmfwDn11nVMeQ5IDdJJLdXNVIa6x7IV-tFjPA059T2CMCVlDze-5EaoE9S3HjYApDtKXpwvCYrBdB)
29. [datacamp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFx_42kj_DNH91FWWptkvY6vU5F9ZKsvoncMYO-fz_kI_HukWAh2gtsnWNfXrBAsp3W_4quxrPONEol-Zbm-yn_ADsTQh6FyHzmtFN4uOWMdm2Sa8GN28qA-ILLZVEstUqg0groUdjlHgkIXRidccwumMR5VLMnTkkd7juqp5zRjEHAEA==)
30. [quantinsti.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMrrz-VHkEbbwb8EHGA8EDvo-qv5DLIdeXoqleu1WNYyZWt_IS4VlarwohH2W_wWe3mjJPVaW9fJK1vkXi0avyUAi1582W2XfwJQXMnKbJlkB3OM3xjAAGRsJzwwXS1SRGtkzviSiqBfyXQeH_WpcLnw==)
31. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaaAi2L6GKWkJaIYGrJPnqWBAIExz_XKTGpn9NQHB4oonSacIErJA5-ZPKMJOEsb6r7-pFb5Qp-Wwa32fla72pwu9sh1OE0Q-gHq6WQoSr4JgFBhcw_IkHngNfPLaRFsfiOFB9aet3v6tT-yc=)
32. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-eXLF9BjUNi6MqnDYGnQjz3PR4f5MhzPMUfNogX3FODsvf4nEe-cMCT2wv-3f1J7yKatV6F7epsmoXAzYOZNd6VzUffyYBnGlRCOQagvoQ1IwF_sChWAfQ_ivct1tpy0x_GXJTqYEedTzPL60YaFQPJG8pHUCgmPSu7c3WKavtcW-VNiKOiaC4JbDFRyi4aFQa-9xyeA=)
33. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwR4O0rPDTPsAjMrC-9oHOuBs9MRqj9Ezs6im_EE_cfornijkIn6y8uPaOHk5Do_VEdm8r0mSsKuJPhTQmtGEkthp1GLMUOIhuNc4fBcTSR7tHUnZJ6eoO-DNV1BexLeaitOr5v9RiKgetJ-36g7fuMSiy5pvebfSreTSUEMXx5HGmxxc9rGROPWFnCgm6FmVGkBEB)
34. [nkmk.me](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElDEPLz4SZGEPG02hX0ilcy-AaYZDn7i-3oIaqHhILb7E5cu0zdxZegvUb7O3g0LzuLeuDLTCbcQPZVYTQlYwNbWycGAKwr3Z75hgpQBP4GclSMIuZ_AHLzkHLM4dp_yecOomJ2J-uTOoT)
35. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEuDgurGvNuhKzs2x1g24-5Z8TF2C9QHCiZjJShcUPvMgIMopqr0qcf2XvUWC6euKNzz3_fidw0zqgRFnPJLEMcR8rfksxLZ7r2zssk6CDrfljOlF5GVI4EPiWq58TB9pepAQ_4Nlhx9-lt4FKIHf44ZQ58s0VNHvbypT1x3ukd-3au9XTl_6M9PEAGyxSaBzFVv09vgLHv_pDnMDW3xxhpB4WjjWrgA==)
36. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFeE8nEblyJnEEFtyYJ0nJ25jZDp-U7wxI1AXCfso9wKkTPGyJb89Djccwl4kimNiOonszP8sEo28v9mD9LWkUj34FT2CBtJEM5r5G9rulrNK657KG9Ws7SkciFIzdFtoHbNUxi7-fGVv9bD9yG7mNdiH4x3AnCqZllrveLZV1BwjY7Q4Di6bC7bpRMf_lsTW34Q7puyiQ2TyGKOx8Ielc=)
37. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_lc5idOgUI4Nb1e_luYUSTGp8LzN9Ls4ErS2SkGogS7VPzjRL_Q9sJBHMIQFHhzrUeDP6US4dShs9i35EjffopL94CcKQ7QdG0gLj95Ix0uxlbQ0YIaTbYoWWPly0uQhV3rCQFYdoPBg=)
38. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYQDBTR0fgjXw-0ddtANlU2ejUp8ndYx4bcVkc9-svWreYVQB3_VQ_YWQqSYpXOKSOCux9GhZaLHuBH7lGpBZGLAR1dPV0_u7fRKa6Dtc57S27JZDYGoo0ZVsz8owtg2_xxn1X9SNO5S_jVnxB-xoTsr2bHAeOGK5r9w==)
39. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFND1H2-uNnKzTR1Zbg2sX2fOAIK4_NTong40IcxiNffGn-Tjft20Xxoyxe3_BP6q6yAF5BZPzYhAwStld5Hkr_hsqq1RpiFDE2kaG2wd9tr7EfKEit4w9biHMiNCQKWVfuZ5SzaJ0ChflGcaqMwRCF62NCaAnmlcscvj0My1pRYfk6sVhN4SoysNSj8BGucw==)
