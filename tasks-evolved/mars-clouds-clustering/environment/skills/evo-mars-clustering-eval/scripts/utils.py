import numpy as np
from scipy.spatial.distance import pdist, squareform, cdist
from sklearn.cluster import DBSCAN


def weighted_euclidean_pairwise(u, v, w=1.0):
    """Custom weighted Euclidean distance: d = sqrt((w*dx)^2 + ((2-w)*dy)^2)"""
    dx = u[0] - v[0]
    dy = u[1] - v[1]
    return np.sqrt((w * dx)**2 + ((2 - w) * dy)**2)


def compute_precomputed_distance_matrix(X, w=1.0):
    """Compute precomputed distance matrix for DBSCAN using weighted Euclidean.
    
    Args:
        X: numpy array of shape (n, 2) with x, y coordinates
        w: shape_weight parameter
    Returns:
        Square distance matrix of shape (n, n)
    """
    if len(X) == 0:
        return np.array([])
    if len(X) == 1:
        return np.array([[0.0]])
    condensed = pdist(X, metric=weighted_euclidean_pairwise, w=w)
    return squareform(condensed)


def run_dbscan_and_get_centroids(X, eps, min_samples, dist_matrix):
    """Run DBSCAN with precomputed distance matrix and return cluster centroids.
    
    Args:
        X: numpy array of shape (n, 2) with original x, y coordinates
        eps: DBSCAN epsilon parameter
        min_samples: DBSCAN min_samples parameter
        dist_matrix: precomputed square distance matrix
    Returns:
        centroids: numpy array of shape (k, 2) with cluster centroids
    """
    if len(X) == 0:
        return np.array([]).reshape(0, 2)
    
    db = DBSCAN(eps=eps, min_samples=min_samples, metric='precomputed')
    labels = db.fit_predict(dist_matrix)
    
    unique_labels = np.unique(labels)
    centroids = []
    for k in unique_labels:
        if k == -1:
            continue
        cluster_points = X[labels == k]
        centroid = np.mean(cluster_points, axis=0)
        centroids.append(centroid)
    
    if len(centroids) == 0:
        return np.array([]).reshape(0, 2)
    return np.array(centroids)


def greedy_match(centroids, ground_truth, threshold=100.0):
    """Greedy bipartite matching between centroids and ground truth points.
    
    Uses standard Euclidean distance. Matches closest pairs first.
    
    Args:
        centroids: numpy array of shape (m, 2)
        ground_truth: numpy array of shape (n, 2)
        threshold: max distance for a valid match (100 pixels)
    Returns:
        matches: list of (centroid_idx, gt_idx, distance) tuples
        TP, FP, FN: counts
    """
    if len(centroids) == 0 and len(ground_truth) == 0:
        return [], 0, 0, 0
    if len(centroids) == 0:
        return [], 0, 0, len(ground_truth)
    if len(ground_truth) == 0:
        return [], 0, len(centroids), 0
    
    dist_matrix = cdist(centroids, ground_truth, metric='euclidean')
    sorted_flat_indices = np.argsort(dist_matrix.ravel())
    c_indices, gt_indices = np.unravel_index(sorted_flat_indices, dist_matrix.shape)
    
    matched_c = set()
    matched_gt = set()
    matches = []
    
    for c_idx, gt_idx in zip(c_indices, gt_indices):
        dist = dist_matrix[c_idx, gt_idx]
        if dist > threshold:
            break
        if c_idx not in matched_c and gt_idx not in matched_gt:
            matches.append((int(c_idx), int(gt_idx), float(dist)))
            matched_c.add(c_idx)
            matched_gt.add(gt_idx)
    
    TP = len(matches)
    FP = len(centroids) - TP
    FN = len(ground_truth) - TP
    return matches, TP, FP, FN


def score_image(citsci_points, expert_points, eps, min_samples, w):
    """Score a single image: run DBSCAN on citizen science points, match to expert.
    
    Args:
        citsci_points: numpy array of shape (n, 2) or None
        expert_points: numpy array of shape (m, 2)
        eps: DBSCAN epsilon
        min_samples: DBSCAN min_samples
        w: shape_weight for custom distance
    Returns:
        f1: F1 score for this image
        delta: average standard Euclidean distance of matches, or NaN if no matches
    """
    # No citizen science points -> no clusters -> no matches
    if citsci_points is None or len(citsci_points) == 0:
        if len(expert_points) == 0:
            # Both empty: F1=1.0, delta=NaN (no matches to average)
            return 1.0, float('nan')
        return 0.0, float('nan')
    
    # Compute custom distance matrix for DBSCAN
    dist_matrix = compute_precomputed_distance_matrix(citsci_points, w=w)
    
    # Run DBSCAN and get centroids
    centroids = run_dbscan_and_get_centroids(citsci_points, eps, min_samples, dist_matrix)
    
    # If no clusters found
    if len(centroids) == 0:
        if len(expert_points) == 0:
            return 1.0, float('nan')
        return 0.0, float('nan')
    
    # Greedy match centroids to expert points
    matches, TP, FP, FN = greedy_match(centroids, expert_points, threshold=100.0)
    
    # Compute F1
    if (2 * TP + FP + FN) == 0:
        f1 = 1.0
    else:
        f1 = (2 * TP) / (2 * TP + FP + FN)
    
    # Compute delta (average standard Euclidean distance of matches)
    if len(matches) == 0:
        delta = float('nan')
    else:
        delta = np.mean([m[2] for m in matches])
    
    return f1, delta
