import numpy as np
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.cluster import KMeans

_MODEL = None

def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return _MODEL


def generate_normalized_embeddings(texts, batch_size=128):
    model = _get_model()
    emb = model.encode(list(texts), batch_size=batch_size, show_progress_bar=False,
                       convert_to_numpy=True, normalize_embeddings=True)
    return emb.astype(np.float32)


def compute_condensed_distance(embeddings, metric='cosine'):
    return pdist(embeddings, metric=metric)


def _cluster_indices(emb_subset, k):
    n = len(emb_subset)
    if n <= 1:
        return np.ones(n, dtype=int)
    k = min(k, n)
    if k <= 1:
        return np.ones(n, dtype=int)
    if n > 1500:
        km = KMeans(n_clusters=k, n_init=4, random_state=42)
        return km.fit_predict(emb_subset) + 1
    try:
        cd = pdist(emb_subset, metric='cosine')
        Z = linkage(cd, method='average')
        labels = fcluster(Z, t=k, criterion='maxclust')
        if len(np.unique(labels)) < k:
            # Try KMeans to force k clusters
            km = KMeans(n_clusters=k, n_init=4, random_state=42)
            labels = km.fit_predict(emb_subset) + 1
        return labels
    except Exception:
        km = KMeans(n_clusters=k, n_init=4, random_state=42)
        return km.fit_predict(emb_subset) + 1


def _ensure_min_clusters(labels, emb, k_min):
    """If fewer than k_min unique labels, re-split largest cluster."""
    labels = labels.copy()
    while True:
        uniq, cnts = np.unique(labels, return_counts=True)
        if len(uniq) >= k_min:
            return labels
        # Pick largest
        big = uniq[np.argmax(cnts)]
        idxs = np.where(labels == big)[0]
        if len(idxs) < 2:
            return labels
        sub_emb = emb[idxs]
        try:
            km = KMeans(n_clusters=2, n_init=4, random_state=42)
            sub_labels = km.fit_predict(sub_emb)
        except Exception:
            return labels
        new_id = labels.max() + 1
        labels[idxs[sub_labels == 1]] = new_id
        if len(np.unique(labels)) <= len(uniq):
            return labels  # cannot split further


def recursive_top_down_cluster(embeddings, k_per_level=(14, 7, 5, 4, 3),
                                min_size_per_level=(40, 8, 3, 2, 1),
                                min_children=3):
    """Returns (N, 5) integer label matrix. Ensures each parent has at least min_children
    children when len(parent_items) >= min_children. Otherwise items get label 0 to mark
    'no further split' (caller should treat 0 as no level emitted).
    """
    N = len(embeddings)
    labels_per_level = np.zeros((N, 5), dtype=int)
    root = np.arange(N)
    lab1 = _cluster_indices(embeddings[root], k_per_level[0])
    lab1 = _ensure_min_clusters(lab1, embeddings[root], k_per_level[0])
    labels_per_level[root, 0] = lab1

    def recurse(level, parent_idx):
        if level >= 5:
            return
        prev = labels_per_level[parent_idx, level-1]
        for prev_lbl in np.unique(prev):
            if prev_lbl == 0:
                continue
            sel = parent_idx[prev == prev_lbl]
            n = len(sel)
            if n < min_children:
                # Mark deeper levels as 0 (leaf)
                for d in range(level, 5):
                    labels_per_level[sel, d] = 0
                continue
            emb_sub = embeddings[sel]
            k = min(k_per_level[level], max(min_children, n // 2))
            k = max(k, min_children)
            k = min(k, n)
            lab = _cluster_indices(emb_sub, k)
            lab = _ensure_min_clusters(lab, emb_sub, min(min_children, n))
            labels_per_level[sel, level] = lab
            recurse(level + 1, sel)

    recurse(1, root)
    return labels_per_level
