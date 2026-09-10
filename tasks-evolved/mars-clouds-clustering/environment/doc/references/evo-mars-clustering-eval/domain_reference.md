# Domain Reference for evo-mars-clustering-eval

**Responsibility**: Implements the custom distance metric, runs DBSCAN with precomputed distance matrices on a single image's citizen science points, computes cluster centroids, performs greedy matching against expert points (max distance 100px), and returns F1 score and delta (average matched distance) for that image.

**Key functions to implement**: weighted_euclidean_pairwise, compute_precomputed_distance_matrix, run_dbscan_and_get_centroids, greedy_match, score_image

---

## 1. scikit-learn 1.2.2 DBSCAN API and Custom Distance Metrics


The Density-Based Spatial Clustering of Applications with Noise (DBSCAN) algorithm groups points based on spatial density, classifying points in low-density regions as noise.

## 2. scipy.spatial.distance with Custom Metric


The `scipy.spatial.distance` module contains utilities for computing distance matrices for collections of vectors [cite: 5].

## 3. Greedy Matching Algorithm Between Two Point Sets


After computing the centroids from the DBSCAN labels, the pipeline must associate predicted centroids with expert-annotated ground truth points to evaluate accuracy.

## 7. numpy 1.24.3 Specifics


Handling coordinates effectively requires robust aggregation techniques, particularly if encountering missing data points or empty arrays.

## 8. Common Pitfalls and Edge Cases


Constructing this pipeline exposes a developer to several esoteric quirks and sharp edges within the scientific Python stack.