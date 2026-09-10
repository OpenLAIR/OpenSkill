# Optimization Pipeline Utility Module: Integrating DBSCAN Clustering, Greedy Matching, and Pareto Frontier Analysis

**Key Points**
*   **DBSCAN with Custom Metrics**: `scikit-learn` 1.2.2 supports custom callable metrics and precomputed distance matrices for DBSCAN [cite: 1]. However, using a Python callable metric is computationally expensive and generally requires explicitly setting `algorithm='brute'` [cite: 2, 3].
*   **Performance Optimization**: To circumvent the performance bottleneck of callable functions in clustering, precomputing the distance matrix via `scipy.spatial.distance.pdist` and converting it via `squareform` is highly recommended for datasets that fit in memory [cite: 2, 4].
*   **Greedy Matching and Scoring**: For mapping predicted centroids to ground truth points, calculating pairwise distances via `cdist` and applying a greedy sorting mechanism offers an efficient heuristic approximation to the assignment problem [cite: 5].
*   **Pareto Optimization**: The `paretoset` library provides an efficient method to compute Pareto frontiers on pandas DataFrames, requiring precise configuration of the `sense` parameter (e.g., `["max", "min"]`) [cite: 6, 7].
*   **Parallelization**: `joblib` facilitates robust parallel grid searches. Choosing between `prefer='processes'` (default loky backend) and `prefer='threads'` is critical and depends on whether the underlying NumPy/SciPy operations release the Global Interpreter Lock (GIL) [cite: 8, 9].

**Overview of the Analytical Pipeline**
The integration of spatial clustering, bipartite matching, and multi-objective optimization forms the bedrock of many modern computer vision and spatial analysis pipelines. This report explores the development of a utility module designed to optimize hyperparameters for a custom spatial clustering task. By systematically iterating over variations in spatial weighting, the pipeline applies DBSCAN clustering, evaluates the accuracy using a greedy centroid-matching algorithm to compute the F1 score, and identifies the Pareto-optimal configurations. 

**Methodological Complexity and Nuance**
Building this pipeline requires navigating several nuanced behaviors within the Python scientific stack. The handling of missing data via `numpy.nanmean` [cite: 10, 11], the mitigation of edge cases in metric evaluations (such as division by zero in F1 scoring), and the nuances of memory management when scaling up `joblib` workers [cite: 12, 13] are primary concerns. Research suggests that while algorithmic defaults in `scikit-learn` are robust for standard use cases, custom metrics heavily disrupt standard execution paths, necessitating explicit configurations like bypassing tree-based spatial indexing [cite: 14].

---

## 1. scikit-learn 1.2.2 DBSCAN API and Custom Distance Metrics

The Density-Based Spatial Clustering of Applications with Noise (DBSCAN) algorithm groups points based on spatial density, classifying points in low-density regions as noise. 

### 1.1 Constructor Signature and Parameter Definition
In `scikit-learn` version 1.2.2, the `sklearn.cluster.DBSCAN` class constructor is defined with the following exact signature [cite: 1]:

```python
sklearn.cluster.DBSCAN(
    eps=0.5, 
    *, 
    min_samples=5, 
    metric='euclidean', 
    metric_params=None, 
    algorithm='auto', 
    leaf_size=30, 
    p=None, 
    n_jobs=None
)
```

**Parameter Breakdown:**
*   `eps` (float, default=0.5): The maximum distance between two samples for one to be considered in the neighborhood of the other [cite: 1].
*   `min_samples` (int, default=5): The number of samples (including the point itself) in a neighborhood required to declare a core point [cite: 15].
*   `metric` (str or callable, default='euclidean'): The metric to use for distance computation. Can be a standard string metric, `'precomputed'`, or a callable function [cite: 1, 16].
*   `metric_params` (dict, default=None): Additional keyword arguments to pass to the metric function [cite: 1, 15].
*   `algorithm` (str, default='auto'): The spatial indexing algorithm to use (`'auto'`, `'ball_tree'`, `'kd_tree'`, `'brute'`) [cite: 1, 15].
*   `leaf_size` (int, default=30): Leaf size passed to BallTree or cKDTree [cite: 16].
*   `p` (float, default=None): The power of the Minkowski metric, if utilized [cite: 16].
*   `n_jobs` (int, default=None): The number of parallel jobs to run during neighbor search [cite: 1, 16].

### 1.2 Implementing Custom Distance Metrics
There are two distinct paradigms for passing a custom distance metric (such as a weighted Euclidean distance) to DBSCAN: `metric=callable` and `metric='precomputed'`.

**Using `metric=callable`:**
When passing a callable to the `metric` argument, `scikit-learn` expects a function that takes two 1-dimensional arrays (representing a pair of points `(a, b)`) and returns a single float representing the distance [cite: 2, 17]. 

*Important Calling Convention*: The function receives individual point vectors, *not* the full array matrix [cite: 2, 18]. 

```python
import numpy as np
from sklearn.cluster import DBSCAN

# Define the custom callable metric for individual point pairs (a, b)
def weighted_euclidean_callable(u, v, w=1.0):
    dx = u - v
    dy = u[cite: 19] - v[cite: 19]
    return np.sqrt((w * dx)**2 + ((2 - w) * dy)**2)

# Instantiate and fit DBSCAN
# Note: metric_params allows passing the 'w' argument cleanly
db = DBSCAN(
    eps=15.0, 
    min_samples=3, 
    metric=weighted_euclidean_callable, 
    metric_params={'w': 1.5},
    algorithm='brute'
)
labels = db.fit_predict(X)
```

**Using `metric='precomputed'`:**
Alternatively, if `metric='precomputed'`, the `X` array passed to the `fit` method is assumed to be a square distance matrix of shape `(n_samples, n_samples)` [cite: 1, 17].

### 1.3 Extracting Cluster Labels and Computing Centroids
Once DBSCAN is fitted, the cluster assignments for each point in the dataset are stored in the `.labels_` attribute, which is a NumPy array of shape `(n_samples,)` [cite: 16, 20].

*   **Valid Clusters**: Points belonging to valid clusters are assigned integer labels starting from `0` to `k-1` [cite: 16].
*   **Noise Labels**: Any point designated as an outlier (noise) by the algorithm is assigned the label `-1` [cite: 15, 16].

To compute cluster centroids from these labels, it is imperative to filter out the noise points. 

```python
import numpy as np

def compute_centroids(X, labels):
    """
    Computes the geometric center (centroid) of each cluster.
    Noise points (label -1) are ignored.
    """
    unique_labels = np.unique(labels)
    centroids = []
    cluster_ids = []
    
    for k in unique_labels:
        if k == -1:
            continue  # Skip noise points
            
        # Create a boolean mask for the current cluster
        class_member_mask = (labels == k)
        
        # Extract points and calculate the mean across the rows (axis=0)
        cluster_points = X[class_member_mask]
        centroid = np.mean(cluster_points, axis=0)
        
        centroids.append(centroid)
        cluster_ids.append(k)
        
    return np.array(centroids), np.array(cluster_ids)
```

### 1.4 Performance Implications: Callable vs. Precomputed
The architectural choice between `metric=callable` and `metric='precomputed'` dictates the computational viability of the pipeline.

**The Callable Bottleneck**: Passing a Python function as the `metric` parameter is exceedingly slow [cite: 2, 18]. `scikit-learn` must utilize Python callbacks for every pair of points. For a dataset of size $N$, the algorithm evaluates the distance function $\frac{N(N-1)}{2}$ times. The overhead of the Python interpreter invoking the function for every iteration typically results in execution times orders of magnitude slower than native C/Cython implementations [cite: 2].

**The Precomputed Advantage**: Utilizing `scipy.spatial.distance.pdist` combined with `squareform` to generate a precomputed distance matrix shifts the nested loops into highly optimized C routines [cite: 5]. While memory complexity increases to $O(N^2)$, the actual elapsed time is dramatically reduced, making `metric='precomputed'` the strictly superior strategy for datasets that can comfortably fit into RAM [cite: 2, 18].

---

## 2. scipy.spatial.distance with Custom Metric

The `scipy.spatial.distance` module contains utilities for computing distance matrices for collections of vectors [cite: 5].

### 2.1 Generating Distance Matrices (`pdist` and `squareform`)
To construct a distance matrix efficiently, `pdist` calculates the pairwise distances between observations in an n-dimensional space [cite: 5, 19].

**Signature**: `scipy.spatial.distance.pdist(X, metric='euclidean', *args, **kwargs)` [cite: 4, 19].
*   `X`: An $m \times n$ array of $m$ original observations.
*   `metric`: A string or callable distance function [cite: 19].
*   `**kwargs`: Extra arguments to pass to the metric function (e.g., custom weights) [cite: 4, 19].

`pdist` returns a **condensed distance matrix**, a 1D array of shape $(m(m-1)/2,)$. Because `DBSCAN` with `metric='precomputed'` expects a redundant, square $m \times m$ matrix, the output of `pdist` must be converted using `squareform` [cite: 4].

**Signature**: `scipy.spatial.distance.squareform(X, force='no', checks=True)` [cite: 4, 5].

### 2.2 Computing Distances Between Point Sets (`cdist`)
While `pdist` computes pairwise distances within a single set, the pipeline requires distances *between* two different sets (e.g., Cluster Centroids vs. Ground Truth points) for the greedy matching step. This is accomplished using `cdist` [cite: 5, 19].

**Signature**: `scipy.spatial.distance.cdist(XA, XB, metric='euclidean', *args, **kwargs)` [cite: 5, 19].

### 2.3 Working Code for Weighted Euclidean Distances
We implement the requested formula: $d(a, b) = \sqrt{(w \cdot dx)^2 + ((2-w) \cdot dy)^2}$.

```python
import numpy as np
from scipy.spatial.distance import pdist, squareform, cdist

# Custom callable for scipy.spatial.distance
def weighted_euclidean(u, v, w=1.0):
    dx = u - v
    dy = u[cite: 19] - v[cite: 19]
    return np.sqrt((w * dx)**2 + ((2 - w) * dy)**2)

# 1. Generating Precomputed matrix for DBSCAN
X = np.random.rand(100, 2)  # 100 points in 2D
# Note: we pass w=1.5 as a kwarg to pdist
condensed_dist = pdist(X, metric=weighted_euclidean, w=1.5)
square_dist_matrix = squareform(condensed_dist)

# 2. Generating matrix between two different sets (Centroids vs Ground Truth)
centroids = np.random.rand(5, 2)
ground_truth = np.random.rand(6, 2)
# Here we might just want standard euclidean for matching
cross_distances = cdist(centroids, ground_truth, metric='euclidean')
```

---

## 3. Greedy Matching Algorithm Between Two Point Sets

After computing the centroids from the DBSCAN labels, the pipeline must associate predicted centroids with expert-annotated ground truth points to evaluate accuracy. 

### 3.1 Algorithmic Logic
The greedy matching strategy is a non-optimal heuristic for bipartite graph matching that avoids the computational cost of the Hungarian Algorithm ($O(N^3)$). The workflow is as follows:
1. Compute all pairwise standard Euclidean distances between `centroids` and `ground_truth` using `cdist`.
2. Flatten the matrix and sort all pair combinations by distance in ascending order.
3. Iterate through the sorted pairs. If the distance exceeds the threshold (100 pixels), terminate (since subsequent pairs are even further apart).
4. If neither the centroid nor the ground truth point has been assigned yet, log them as a match and mark both as assigned.

### 3.2 Evaluation Metrics (TP, FP, FN) and F1 Score
*   **True Positives (TP)**: The number of successful matches created.
*   **False Positives (FP)**: The number of predicted centroids left unmatched.
*   **False Negatives (FN)**: The number of ground truth points left unmatched.

The F1 score is the harmonic mean of precision and recall. Instead of calculating Precision and Recall separately (which risks division by zero if TP+FP=0 or TP+FN=0), we use the aggregate formula:
$F_1 = \frac{2 \times \text{TP}}{2 \times \text{TP} + \text{FP} + \text{FN}}$

If the ground truth is empty and predictions are empty, the standard mathematical limit of F1 is 1.0. If TP=0 but FP and/or FN > 0, the denominator is greater than zero, safely returning `0.0`.

### 3.3 Working Python Code for Greedy Matching
```python
import numpy as np
from scipy.spatial.distance import cdist

def greedy_matching(centroids, ground_truth, threshold=100.0):
    """
    Performs greedy bipartite matching between centroids and ground truth points.
    
    Returns:
        matches (list of tuples): (centroid_idx, gt_idx, distance)
        TP (int): True Positives
        FP (int): False Positives
        FN (int): False Negatives
        F1 (float): F1 score
    """
    # Edge cases: empty arrays
    if len(centroids) == 0 and len(ground_truth) == 0:
        return [], 0, 0, 0, 1.0  # Perfect score if both are empty
    if len(centroids) == 0:
        return [], 0, 0, len(ground_truth), 0.0
    if len(ground_truth) == 0:
        return [], 0, len(centroids), 0, 0.0

    # Step 1: Compute pairwise standard Euclidean distances
    # Shape: (num_centroids, num_ground_truth)
    dist_matrix = cdist(centroids, ground_truth, metric='euclidean')

    # Step 2: Extract indices and sort by distance
    # argsort flattens the matrix by default if not given an axis, 
    # but we want 2D indices. We unravel the indices.
    sorted_flat_indices = np.argsort(dist_matrix.ravel())
    # Convert flat indices back to (row, col) format
    centroid_indices, gt_indices = np.unravel_index(
        sorted_flat_indices, dist_matrix.shape
    )

    matched_centroids = set()
    matched_gt = set()
    matches = []

    # Step 3: Greedy assignment
    for c_idx, gt_idx in zip(centroid_indices, gt_indices):
        dist = dist_matrix[c_idx, gt_idx]
        
        # Since the list is sorted, if we hit a distance > threshold, 
        # all subsequent distances will also be > threshold.
        if dist > threshold:
            break
            
        if c_idx not in matched_centroids and gt_idx not in matched_gt:
            matches.append((c_idx, gt_idx, dist))
            matched_centroids.add(c_idx)
            matched_gt.add(gt_idx)

    # Step 4: Compute TP, FP, FN
    TP = len(matches)
    FP = len(centroids) - TP
    FN = len(ground_truth) - TP

    # Step 5: Compute F1 Score safely
    # Denominator is strictly greater than 0 unless TP=0, FP=0, FN=0, 
    # which is handled by the first edge case.
    f1_score = (2 * TP) / (2 * TP + FP + FN)

    return matches, TP, FP, FN, f1_score
```

---

## 4. Pareto Frontier Computation using `paretoset` 1.2.3

In a hyperparameter optimization grid, multiple configurations will yield varying results. When seeking to simultaneously optimize conflicting objectives—for instance, maximizing the F1 score while minimizing the complexity or variance—the `paretoset` library allows for the robust identification of the Pareto frontier [cite: 21, 22].

### 4.1 Signature and Input Formats
The `paretoset` library expects an import from the top-level module [cite: 7, 21].
**Import Path:** `from paretoset import paretoset` [cite: 6, 21].

**Function Signature**:
`paretoset(data, sense=None, distinct=False, use_numba=True)`

**Input Formats**: The function seamlessly natively accepts `numpy.ndarray` and `pandas.DataFrame` objects [cite: 23, 24]. 

### 4.2 Specifying Optimization Direction
The `sense` parameter instructs the algorithm on the direction of optimization for each respective column or dimension. 
*   **Valid Values**: The parameter accepts a list of strings. The valid strings are `["max", "min", "diff"]` [cite: 6, 7, 21].
    *   `"max"` dictates the objective should be maximized [cite: 6, 21].
    *   `"min"` dictates the objective should be minimized [cite: 6, 21].
    *   `"diff"` computes the Pareto set relative to distinct groups [cite: 21].
*   It explicitly does *not* accept `["maximize", "minimize"]`.

### 4.3 Return Format and Working Example
The `paretoset()` function returns a boolean mask (a NumPy array of booleans) of the same length as the input dataset. Rows corresponding to `True` are Pareto-optimal (non-dominated) [cite: 7, 21].

```python
import pandas as pd
from paretoset import paretoset

# Assuming grid search generated the following DataFrame
# We want to MAXIMIZE 'f1_score' and MINIMIZE 'fp_count'
results = pd.DataFrame({
    'weight_w': [0.5, 1.0, 1.5, 2.0],
    'eps': [cite: 13, 23, 25, 26],
    'f1_score': [0.85, 0.88, 0.92, 0.90],
    'fp_count': [cite: 4, 17, 23, 27]
})

# Isolate the objective columns
# Sense order must match the column order passed to the function
objectives = results[['f1_score', 'fp_count']]
sense = ["max", "min"]

# Generate the boolean mask
pareto_mask = paretoset(objectives, sense=sense)

# Extract the Pareto-optimal points
pareto_front = results[pareto_mask].copy()
print(pareto_front)
```

---

## 5. pandas 2.2.2 Patterns for the Pipeline

### 5.1 Reading and Iterating over Grouped Data
If the raw ground-truth or prediction data is stored sequentially in CSVs, the standard pattern involves reading the dataframe and segmenting it. The efficient idiom for processing image-specific data iteratively leverages the `groupby` object:

```python
import pandas as pd

df = pd.read_csv('expert_annotations.csv')

# Efficient iteration pattern per image
for file_rad, group_df in df.groupby('file_rad'):
    # Extract coordinates as a numpy array for spatial operations
    points = group_df[['x', 'y']].to_numpy()
    # Execute image-specific DBSCAN and matching pipeline here
    # ...
```

### 5.2 Formatted Output Writing
After generating the aggregated metrics and Pareto front, dumping the data to disk via `.to_csv()` requires specific handling to prevent massive decimal expansions or ugly scientific notations [cite: 28].

The `float_format` parameter of the `to_csv()` method accepts a string or callable [cite: 29, 30]. To enforce a specific decimal precision (e.g., 4 decimal places), passing a printf-style format string is the standard approach [cite: 29, 31].

```python
# Saves the results with exactly 4 decimal places for floating-point columns
pareto_front.to_csv('optimized_parameters.csv', index=False, float_format='%.4f')
```
Rounding the dataframe beforehand using `df.round(4)` is an alternative, but `float_format` is generally preferred as it alters the serialization representation without modifying the in-memory data precision [cite: 29].

---

## 6. joblib 1.3.2 for Parallel Grid Search

Evaluating combinations of `eps`, `min_samples`, and custom weighting parameter `w` across thousands of images constitutes an embarrassingly parallel task. The `joblib` library is uniquely designed for this [cite: 12, 32].

### 6.1 `Parallel` and `delayed`
*   `joblib.Parallel` constructs a parallel computing context pool.
*   `joblib.delayed` is a decorator-like function used to capture arguments and function calls to be queued up for parallel execution.

**Signatures**:
`joblib.Parallel(n_jobs=None, backend=None, prefer=None, ...)` [cite: 13]
`joblib.delayed(function)` [cite: 32]

### 6.2 `n_jobs=-1`, `backend`, and `prefer` Parameters
*   `n_jobs`: Setting `n_jobs=-1` signals `joblib` to spawn as many workers as there are CPU cores available via `os.cpu_count()`. If `n_jobs=-2`, it uses all cores minus one [cite: 13].
*   `backend`: The underlying concurrency implementation. Defaults to `'loky'` [cite: 8, 13]. Other options include `'multiprocessing'` and `'threading'` [cite: 33].
*   `prefer`: Rather than hard-coding a backend, providing a hint via `prefer` is highly advised.
    *   `prefer='processes'`: The default behavior. Creates fully separate Python processes. It bypasses the Python Global Interpreter Lock (GIL) but incurs significant memory and serialization overhead because arguments and results must be pickled and passed across inter-process pipes [cite: 8].
    *   `prefer='threads'`: Creates threads within the same memory space. Virtually zero serialization overhead. However, due to the GIL, this only achieves true parallelism if the executed code heavily relies on compiled C extensions (like `numpy`, `scipy`, or `pandas`) which explicitly release the GIL during execution [cite: 8].

Given that our custom metric bottleneck might occur in native Python, `prefer='processes'` is generally safer to ensure full core utilization, unless utilizing strictly `precomputed` C-based distance matrices [cite: 8].

### 6.3 Parallel Grid Search Code Example
A parallel loop using `joblib` returns a standard Python list of whatever objects the delayed function returns, preserved in the original submission order [cite: 13].

```python
from joblib import Parallel, delayed
import itertools

def evaluate_hyperparameters(eps, min_samples, w, all_images_data):
    """
    Processes the entire image dataset for one combination of hyperparameters.
    Returns a dictionary of aggregated metrics.
    """
    total_f1 = 0
    # ... logic over all images utilizing the parameters ...
    return {'eps': eps, 'min_samples': min_samples, 'w': w, 'mean_f1': total_f1}

# Define hyperparameter grid ranges
eps_grid = [cite: 13, 23, 25]
min_samples_grid = [cite: 5, 17, 27]
w_grid = [0.8, 1.0, 1.2]

# Generate all combinations via itertools
hyperparameter_combinations = list(itertools.product(eps_grid, min_samples_grid, w_grid))

# Execute parallel grid search using processes
results_list = Parallel(n_jobs=-1, prefer='processes')(
    delayed(evaluate_hyperparameters)(eps, ms, w, all_images_data) 
    for eps, ms, w in hyperparameter_combinations
)

# Convert the resulting list of dictionaries directly into a DataFrame
results_df = pd.DataFrame(results_list)
```

---

## 7. numpy 1.24.3 Specifics

Handling coordinates effectively requires robust aggregation techniques, particularly if encountering missing data points or empty arrays.

### 7.1 `numpy.nanmean` vs `numpy.mean`
*   **`numpy.mean(a, axis=None)`**: Computes the arithmetic mean. If the array contains *any* `NaN` value along the specified axis, the resulting mean will be `NaN`. The NaN propagates [cite: 10].
*   **`numpy.nanmean(a, axis=None)`**: Computes the arithmetic mean while explicitly ignoring `NaN` values. The denominator adjusts to count only valid, non-NaN elements [cite: 10, 11]. If a slice consists entirely of `NaN`s, `nanmean` returns `NaN` and raises a `RuntimeWarning` [cite: 11].

### 7.2 Grouped Coordinate Averaging
When computing the $X$ and $Y$ centroids of a cluster containing floating-point representations, leveraging `np.nanmean` ensures resilience against spurious NaNs that might have been introduced during preprocessing.

```python
def robust_centroid(cluster_points):
    # cluster_points is an N x 2 array of coordinates [x, y]
    # np.nanmean over axis=0 calculates the column-wise mean
    centroid = np.nanmean(cluster_points, axis=0)
    return centroid
```

---

## 8. Common Pitfalls and Edge Cases

Constructing this pipeline exposes a developer to several esoteric quirks and sharp edges within the scientific Python stack.

### 8.1 The `algorithm='brute'` Requirement for Callables
When configuring `metric=callable` for `DBSCAN`, one must manually stipulate `algorithm='brute'`.
By default, `algorithm='auto'` attempts to ascertain the most efficient spatial index (`BallTree` or `KDTree`). However, these tree-based structures rely heavily on strict geometric properties (such as the triangle inequality) and highly optimized Cython backend metrics. They do not accept arbitrary Python callables. Attempting to use a callable without forcing `'brute'` will result in a `ValueError` indicating that the metric is invalid for tree structures [cite: 3, 14]. The brute-force approach ensures every pairwise distance is computed without structural assumptions.

### 8.2 Label Edge Cases (All Noise vs Single Points)
*   **All Noise**: If parameters are excessively strict (e.g., high `min_samples` or very low `eps`), DBSCAN will designate every point as an outlier. In this scenario, `.labels_` consists entirely of `-1`s [cite: 16, 26]. Any downstream processing iterating through `np.unique(labels)` must specifically trap and ignore `-1`, otherwise it will erroneously compute a single "noise centroid."
*   **Single Points**: If the dataset `X` contains only a single point, and `min_samples > 1`, DBSCAN trivially assigns it to noise (`-1`).

### 8.3 F1 Computation Division by Zero
As demonstrated in the greedy matching section, evaluating edge cases where Precision and Recall both collapse to $0$ is critical. 
Recall the standard definition: $P = \frac{TP}{TP + FP}$, $R = \frac{TP}{TP + FN}$, $F_1 = 2 \frac{P \times R}{P + R}$.
If $TP = 0$, both $P = 0$ and $R = 0$. Plugging this into the $F_1$ formula yields $0 / 0$, throwing a `ZeroDivisionError`. Utilizing the algebraically simplified formulation $F_1 = \frac{2 \times TP}{2 \times TP + FP + FN}$ restricts the $0$ value exclusively to the numerator, cleanly evaluating to `0.0`.

### 8.4 Performance Profile: Precomputed vs. Callable
As highlighted in Section 1.4, switching from a `callable` to a `precomputed` distance matrix via `pdist` accelerates execution but invokes a quadratic memory profile: $O(N^2)$.
*   **Small Datasets** ($N < 5,000$): `pdist` will consume negligible RAM (~100 MB). Highly efficient.
*   **Large Datasets** ($N > 50,000$): The matrix necessitates storing ~1.25 Billion elements. A 64-bit float array will consume approximately $10 \text{ GB}$ of contiguous RAM. At this threshold, `memory_error` exceptions become prevalent. In extreme circumstances, an algorithm utilizing sparse neighbor graphs (`NearestNeighbors.radius_neighbors_graph`) should replace the dense matrix [cite: 1, 16].

### 8.5 Deprecation Warnings in scikit-learn 1.2.2 DBSCAN
Historically, passing keyword arguments into metric computations via `**kwargs` inside the constructor was permissible. In modern scikit-learn versions (and enforced cleanly in 1.2.2), any extraneous parameters (such as the weights for a custom distance) *must* be passed via the `metric_params` dictionary argument [cite: 1, 16]. 
Additionally, internal changes mean that referring to older submodule aliases like `sklearn.cluster.dbscan_` rather than the top-level API is heavily deprecated and will raise `FutureWarning` or fail entirely [cite: 34]. Always import via `from sklearn.cluster import DBSCAN` [cite: 26].

---

## 9. Comprehensive Pipeline Utility Implementation

Integrating all constraints, optimizations, and API requirements yields the following cohesive Python utility framework.

```python
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform, cdist
from sklearn.cluster import DBSCAN
from paretoset import paretoset
from joblib import Parallel, delayed
import itertools
import warnings

# ==========================================
# 1. Distance Metric & Matching Logic
# ==========================================

def weighted_euclidean_pdist(u, v, w=1.0):
    """Callable for pdist calculating weighted Euclidean distance."""
    dx = u - v
    dy = u[cite: 19] - v[cite: 19]
    return np.sqrt((w * dx)**2 + ((2 - w) * dy)**2)

def compute_centroids(X, labels):
    """Computes geometric centroids, robust to NaNs, ignoring noise (-1)."""
    unique_labels = np.unique(labels)
    centroids = []
    
    for k in unique_labels:
        if k == -1:
            continue
        cluster_points = X[labels == k]
        # Utilize nanmean to handle potential floating point artifacts
        centroid = np.nanmean(cluster_points, axis=0)
        centroids.append(centroid)
        
    return np.array(centroids)

def score_clustering(centroids, ground_truth, threshold=100.0):
    """Greedy bipartite matching returning F1 score and components."""
    if len(centroids) == 0 and len(ground_truth) == 0:
        return 1.0, 0, 0, 0
    if len(centroids) == 0:
        return 0.0, 0, 0, len(ground_truth)
    if len(ground_truth) == 0:
        return 0.0, 0, len(centroids), 0
        
    dist_matrix = cdist(centroids, ground_truth, metric='euclidean')
    sorted_flat_indices = np.argsort(dist_matrix.ravel())
    c_indices, gt_indices = np.unravel_index(sorted_flat_indices, dist_matrix.shape)
    
    matched_c = set()
    matched_gt = set()
    TP = 0
    
    for c_idx, gt_idx in zip(c_indices, gt_indices):
        if dist_matrix[c_idx, gt_idx] > threshold:
            break
        if c_idx not in matched_c and gt_idx not in matched_gt:
            TP += 1
            matched_c.add(c_idx)
            matched_gt.add(gt_idx)
            
    FP = len(centroids) - TP
    FN = len(ground_truth) - TP
    f1 = (2 * TP) / (2 * TP + FP + FN)
    
    return f1, TP, FP, FN

# ==========================================
# 2. Pipeline Execution Logic
# ==========================================

def process_single_image(image_df, gt_df, eps, min_samples, w):
    """Applies DBSCAN to one image and evaluates against its ground truth."""
    X = image_df[['x', 'y']].to_numpy()
    gt_points = gt_df[['x', 'y']].to_numpy()
    
    if len(X) == 0:
        return score_clustering(np.array([]), gt_points)
        
    # Optimization: Precomputed distance matrix via pdist
    condensed_dist = pdist(X, metric=weighted_euclidean_pdist, w=w)
    sq_dist_matrix = squareform(condensed_dist)
    
    # DBSCAN execution
    db = DBSCAN(eps=eps, min_samples=min_samples, metric='precomputed')
    labels = db.fit_predict(sq_dist_matrix)
    
    centroids = compute_centroids(X, labels)
    return score_clustering(centroids, gt_points)

def evaluate_hyperparameters(eps, min_samples, w, predictions_df, ground_truth_df):
    """Processes entire dataset for one hyperparameter configuration."""
    total_tp, total_fp, total_fn = 0, 0, 0
    
    # Efficient pandas groupby pattern
    for file_rad, img_preds in predictions_df.groupby('file_rad'):
        # Extract matching ground truth
        img_gt = ground_truth_df[ground_truth_df['file_rad'] == file_rad]
        
        f1, tp, fp, fn = process_single_image(img_preds, img_gt, eps, min_samples, w)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        
    # Aggregate F1 over the entire dataset
    dataset_f1 = (2 * total_tp) / (2 * total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0.0
    
    return {
        'eps': eps, 
        'min_samples': min_samples, 
        'w': w, 
        'dataset_f1': dataset_f1,
        'dataset_fp': total_fp
    }

# ==========================================
# 3. Main Grid Search and Pareto Logic
# ==========================================

def optimize_pipeline(predictions_csv, ground_truth_csv):
    preds_df = pd.read_csv(predictions_csv)
    gt_df = pd.read_csv(ground_truth_csv)
    
    eps_grid = [cite: 17, 23, 25]
    min_samples_grid = [cite: 4, 5, 17]
    w_grid = [0.5, 1.0, 1.5]
    
    grid = list(itertools.product(eps_grid, min_samples_grid, w_grid))
    
    # Joblib Parallel Execution using processes
    print(f"Launching grid search with {len(grid)} tasks...")
    results = Parallel(n_jobs=-1, prefer='processes')(
        delayed(evaluate_hyperparameters)(eps, ms, w, preds_df, gt_df)
        for eps, ms, w in grid
    )
    
    results_df = pd.DataFrame(results)
    
    # Pareto Analysis: Maximize F1, Minimize False Positives
    # Note: 'sense' matches the order of the subset dataframe
    objectives = results_df[['dataset_f1', 'dataset_fp']]
    pareto_mask = paretoset(objectives, sense=["max", "min"])
    
    optimal_front = results_df[pareto_mask].copy()
    
    # Dump to CSV with precise floating formatting
    optimal_front.to_csv(
        'pareto_optimal_configs.csv', 
        index=False, 
        float_format='%.4f'
    )
    
    print("Optimization Complete. Pareto configurations saved.")
    return optimal_front
```

**Sources:**
1. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyW4W_dBXKLB-cCLE9FCuy1xjA0e-OSfDSBFEO66A5ElxPl_tLqQMk6yLS93thbaIBzOhcvpykW801tiD3qNNqpzJFl5-xLBI9GOPRQkaQ6JJg_L1e5Psbpa8D4kRPXc0eDAEErexmxnrx4hFIDzqL-jYkY5kQIA1H8-B8jSPkjo0KGg==)
2. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEyX1HgED4UzsPnzTRiEVLvi_OmEser5gNEY_qgtQcs0cAavDdRSWBkyoCyZMrzjfS-q5aa4_dHX5OusUREBgZ7LixnpD7kB_C6qsA5eIPhExkFedu7A7qupBpUbB-hEuqYGWNxrC5jdeRRL-n8LW5xdQ5SwaT07YM8qCr-xzc0s81MOeFisJm-aGE=)
3. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEbUmXmkFfIIf_SpSCwgue_P6M8ZK5mHzP_E6sOJumvyniOizv-ZVZP1mlSvNO-5xFPGTgI0Ho_g2FdHxnMSwFHo48Gvmb_6lYW5P5W89yWMxn93q3HGImdQ38ZLXBH7EYlfl5lYcfEwCp0FTZiR3NM61HWhqFqlvIGuXafwV_Uq73wnvjMjQpJlSNw_OXSzmXaCirLQNPsQZhXMLbso45dfsW825MSk6z5-U6oU8KvSdpx)
4. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVDyObKzQJZLVa1ICZrTNyh47cQZZZZeuYyx2J8Ustu4_2AkZhMBs6-MbdgtnChDezBzXEVheOtp6BKGSSBGUb6qG39T6YzCEqw2h8R_TQpPFxa-M_UXvb8UIbe11r5C3kEGkeYPohPBLvpu5bD2jbIlM6WQDK1WHomJ-iA4JcswRAyN2pN9VX60oAlA==)
5. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjc--LLc6drA06fQRydTtYWZddfkxeBdebW4Ku144baRDJPIPtA7VYnG8lIluC_P2m6Lt3Z4ofGfY7Lkbi3aEeaW7SBd6cZDP7yx_mxkNpUDJLLdTWAA6BxEDaMKUeXDVy6ou5sI6u64o6YceE_88LVke0aCuc)
6. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFXNoKlyWmKCUPkpvb9ixFdFDhO77GyoxT1nv1aGqmKao5Zbt9XTRlqH8Qwg1rXJ7SZk3rF7Q1jZDvkM3Eeo_xvUnG3E7GVBVuByscAILHK2xJcILgXJ1mLGsyd1J8GHabmaCeUImiOcBXpLniWSMd5SvstFHrozeZTUfBKQGpYAQ==)
7. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHWktFV1yEGjVYJ5nJ7wgbel4HRPO4a3ZBM9wvLJL980jy7naCqDm6sIXqGzrvsjf1-DuJJgMQKf4Tqxc50vrZyy8B3iiIrz0IbPMcFx4iKFWm361QalrH5rxFtVT_1oD7zzrRghKCywXFwF0NDfJvzdOQOlj3-3NR2NW66ADW86Q==)
8. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEs-9M9lFG07cawQ84F4iyGaJOGnAXD_ngUKj1Wr36qlLhQ7jM0poODtubFmmbQ4w6RMQGBjdJLP-4OYqqLq4g_fwXbK24XV4CPzV-nJ_zvBaIJPmEhTp0C6ZtOJuL0HCaTuaioJGEWfywWZQ==)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEb4mmoAyDuUbB_uHhwbj9koZ-1VacMbheZ6JpJyok79b8md6slUTeqBPjBSZicNBhZ3Tczo2ldXD1cuIB9NtqoU7WXm3QbJWvjVbXsrTNARETck5N90lgsfJV5DL4AyzcvIyrqdZtSm4helqIaH6hBZRImUWezCw==)
10. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEeEIOMeMZnyY_5zo9p2CR7qTJ1Q5G7_WJzpQGcotZ2TetxTveFjoyKfn-zn1Ua9-KTNPSWbW1dGQPax_vHMDwHFf8a-hEwFzvAcCrqGxxOrKYvvMLWTI-em6iQ3G4qtrLVsRCIh0ceTcXZeJXZLvdFobXKic4=)
11. [numpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGqMNElfHYGESDENIlPN7LD7OBs6P8cev_N0bAUyeDLqwKr2qb8EzlI3yWEG15TmcxIOT3H0G9PZDuh4FTy4Bm-NKP-S7Vf8bA0DRRnLAc4DgnhMpG9TjRIdNxYjj9ze2b6vmb13ZhduSk0NrwcRaJczxhRVZqO)
12. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSdF2W7Atx7T_6Iius-qVCd8NXkgykzN9zyWtsaTEvlj8n_4HarLrS4ZbYbOTIzjL5hKa_Gx-pmtaul64Fs4jD1ldLT_aWUWLct2IUyUGNimrrX5CVYi-xj66zv5ridXQzCNHoi4yDoZDu-hp81-_d)
13. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUoVcEgcYqD-NVBHdbyOKBP5T3jjxZ13hcALZf-p9DelV5Wu2VCA5JJLDMBTb6V8d-Y3QbVtjQ6CfE0hjd9RSvCjRfoOeH5-SGkAjmYsnhHiVGVsu2Ncn82RRb4jkW2AD_R2_8_89w3MxH4VpMkUTsWrVolJeUdat6s3fV)
14. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaLM4ZiWZownBFaBw-suv_A9eiP3m3Pb9HfQrijdN12kg10OEQNj-Ck6UEPtz5YUrbXSZve6k5qPDNc3nzFg7L9aCGzPil4PDsR3AvjNBIgkGEW_x-p1fRPwiJ9F6kJ1ScTT5Lbzq6bSgzGtCSDVDbDZIEp9zG7RIDny6QK9jVVvQNfKM=)
15. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8hx8XIk_DAovZaBJfrQqeo8KVVwNlweziWmhTjjcawe4H-YwXDKaOglpUN0GgbXp2V2MNM-XphEKQwUjHsYVdcRdGYeE1IYJSIBoO_2FavgMAIKnEKrefcoZHs8llz0gNZpPZWcdAGIMmLbfQPZzoko4I4GFx-p9M6ea9CuwgDUU=)
16. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZyoe0J53XAZWtJ9mndu-xDbvlyxJPGWJf2tIs3-alOZHUHokBUNzIpKLPGW56XdiOwQT6wYL5DVpR67vyFFq-ikf3ZZYg_sbf1tCC-waJrE3WR0uwzwqJhIg_cuoIwbwbz90bvRBaPdFcqJkOUu5fBMY4tl5RU8U9yLdc)
17. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGu6do91CIdgISCQn4U9R7uqIGd6xU3M4xESiqd57hUcKtpcBZCmexV9gTVXLb5OMh0wowkykLww9OaOiUZYfy3DkgqFRie_Zux2D4ukl8H5qIlxT5X786Rx2X5stEE6YH5RYs_7dfLxU81tIQpRKxfWfp-V_mc_LluE9dtDULbp8dYDU6iMM1-JnyBlX1TMw==)
18. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzNoPN0SbsYMwgTsI65SkFzHlJvt_Syj1xaQROx6e7DJdQmLZmxGsiuNcHo1FQy1bhEC1TVGV9TTXfva89IlyUvuFa1eSDRwRGXzKqNaA3c3JtUQkuxRDipGYLKjRuT0Yc16zjxJZ6xhmOO0JEgIc6jCzmKr5-w0T99Ac=)
19. [cupy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPh3ywXQKqln38CGwyducv-YzOwlS1m2AMW7dAHkgEgH153gblXpWqOm5KvbTqoVuZ6C8847x3UYKc4BPSUhKRaQjE0O5d9UmKmpvMc27VE0OBlQ47FGQooXbzg1xZlELRrVINxqzTYTTpxtjRKUGJ2lrcT67OCBhzXos0qaMPnhgG_N6Mp4SDwSmyc26WXn5w)
20. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFK1V8FyA2Y6XgoLqwXcSCIq7PuKkcUdU1h6s6CppuU_eOUgvenbcAdbVLxWCofxYrmmmyYjGqwj0kqq5xO17f_Nwi7BrNHenpLe-tVx7hXe9g4Mm58P-rHzMeSLKU4K-mjbA8zMnUMrnslq40daHWA1IDInwwaCFNpS86uh2VV2kwuGumRv1hL2eRO0K5THfn_aTgZ45cAbSTZU375o1A=)
21. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGbnptTPlzmxfmc547JfOgNPGUzAS2NnMnZXj19uq0P_F_jWgthwmyU2WG66UuAij77hm6ob8mj9FsGI-oaBCvhKwORilPO_mfcdNECebTU06Gr7oT7wlg=)
22. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwgQ73UNXSiJOp2QET9T9m8sln0h8pwRrxddreQ8OQBXnmjYpdG7IWiXHrWz8V3_aoKDtDeJZK5VUTpAuB9KkplehcsOET1g0ysqWcb2DTtuMtOpTnWoEzIPCOuiuuSkusFFEnDj1IFQ==)
23. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdxqUWWM8nJfNgrOlcdo6LJXH3uZ1xfpvzeqjtncbFSxWojdWY7WB29iRkGAQngFX9W-Dm7w9Jiveh3tSp7dA8X30YX8bZqXG298RyRP_rU0L6tGNuCr9n5a_6H7YEefbm)
24. [climaax.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGPNNUPrO77t2yPKlzzH5lxox-4WJjLPsbzgJLTk32xkPnvfvPhfu1cxk6Qn5IwWxzMQMZMpjOAHqp7Q2EA88XZPFKKRNWv4IijF7ktxeAxD6O0z_x2Nn9-727TDCVz_3J4JCg0WYSeton4ONGwiTGyw4yTZFEvpmDufqhJ7d4RmpFh8qeVFIBBtoOge6ybeMV_h9c=)
25. [openxcell.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGRm86Ic7uTm0ZMD3vqqo8Qa_kGrHc8vkICZjs1v73RFvOd7eX6cJCclaU2NQyBS9ho0YEFmz0SEsCtG1nxnEwY-WhZKYIRjgaVNGiKLWwU1H52dDb6xIKs0jpLqmSYhQHFNAL0bzYubscEbEM=)
26. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG75Hhe5P7J1FyF5kzTiO6t54CQGzCrPdztZbDs-xnpU5j_x2aFF9lKHasjzQkGOcXeSwdspVc38Ci-FbfUA8lFMX4swWAp4sVxZDOtJDSQKfGZV2X_J7wv6iQtbVXigMqrm7KzpQk5LEkOp3bJaQuDnoXKuOhw0QrjtiQ1Lw3rukz4MZzhsUh-m8dEv5yBIZ1g3bM=)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJsq41e4CKzwRYBxB0BmkCxA1v8kIgh_dmd0uqMNUMbVSHteAKTwkiJhVdiF009Psr7KTuloFUkI4AejF0OAJFvLECl1_SEzO1pQTywpuR6iKm_pSOUZyurOBug6hAkpsS4brsz5cP7T4qZEYPF9-X1SZXcd_AzUhWIJe5YEwzEBZPlqOozpgoowgitKaez2-AAf0w_hwLTcP2-LFOTBpOL83gm7E=)
28. [latenode.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJ5s2kE5Ne-ktLeMigtW4JG1Td6buCTsTIeMjWVeJgXgqxp3X1BXw9LFSS2hhhOhNBqphi2BrzCN9fQLk9x2RNNGlmVLF5Bf2t-lI51Xx7qEDc-0X2rKAysvatHx1p9rhiRWGp6N8vIiJnI2v4RWQvW8TEJrLlMHTCLT_cDJUyChoUrkRnN6edtyhhg5FyFk9tT8yQz61MAVbtigdvM6YkKoMXvmI=)
29. [nkmk.me](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoYbAZa3Ntcr3QNxuU_vNU9pxUIrJhB8WS9MXH-MiGjVIspgEVWYML5lFnUObOVpcZWoaQu-EPFksWZv5gDylLRQSbRYexp4OPe3qDFeZChZHTiApi2XQiutFZXzsxMOHcvOE=)
30. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF8Ec1cEn1sgbrI1iwzrgdrVcORpa-GSlscFuzeCQ_YK4YWe-JQ9xQcONd9SdXWFJ08hZYGcG_8ntSPNyYMuy7YRIwa0-cNnKXTAxw7P1mE5v8E0izgBHrMSb67PltXNuljQFOzNRCQK3OT-1nTmgbupCsytMTtHoXOY11NUVCX)
31. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNl0s8htBGBroChUpIvbiY29gmlj1R3GHyhMUgq_VS1NnCjUoDpSD2JZpC4Da3OHy-juuBDCOuXw0LIZwO_RbcZgLUg36RanbfRfS1Sv5Zrx_y9K_YnYi9gVD8slstvy7-CVfo8-GGm6ZvNkI-xSVfAEyAN2yeSGxgkhKH_A==)
32. [coderzcolumn.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFrfREK2_Ch9K_bIZhLfAdfY3uWS1g29XlUKL_p0GMrKmsfGtVgj7gp99N8F7V_TkDvrvqKWPIgC59fTRSNdli2g_8blLp9DVxFY2aLxLJsv_hQLp6nrdfJHuNWgWaggRDI78LeavW3QqT3-1TUEshepqgGjF2zOj7rO9CgJYOC6LbGD5c=)
33. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDHQ6lm339cKLOK3Hum3cPiuZ8oDxh_Als1owVY7S1fINyzjo0Qckv_z8R_hi5L9ikVXMErliHnl3PapUaYgST6j7OfjBuwa7tIWi4Q94DuEgkig4YeaJ-2Bzo27VoBChkUr8xG_IM_rIAWwH41cObghX6tZ_sNFvPDGLbxVkZGgZQ_uI=)
34. [scikit-learn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUAl460aqf2RoEj5ciyH0mMxwYNMOXwzjzZykFQvBlhc0mo2MxuW9DMtWNLOpehEbKDXSsqyykVEwIDs_vyLzZVEk4l9-r4GesQgpFbF0A_vEZZE3f7CCtNzgUZKPwIkEGg8s=)
