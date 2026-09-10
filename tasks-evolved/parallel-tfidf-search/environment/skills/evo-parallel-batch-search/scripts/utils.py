"""
Parallel Batch Search Utilities

Uses the worker initializer pattern to share the read-only TF-IDF index
across worker processes without repeated pickling.

Key functions:
- init_search_worker: Initializer that sets global index in worker memory
- worker_search_query: Per-query search function using global index
- batch_search_parallel: Orchestrate parallel batch search
"""

import math
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from heapq import nlargest


# ============================================================================
# Constants (must match sequential.py exactly)
# ============================================================================

STOP_WORDS = frozenset([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "the", "this", "but", "they",
    "have", "had", "what", "when", "where", "who", "which", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "not", "only", "same", "so", "than", "too",
    "very", "just", "can", "should", "now", "or", "if", "then",
    "because", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "again", "further", "once",
    "here", "there", "any", "do", "does", "did", "doing", "would",
    "could", "might", "must", "shall", "may", "been", "being", "am",
])

TOKEN_PATTERN = re.compile(r"\b[a-zA-Z]{2,}\b")


def tokenize(text):
    """Tokenize text - matches sequential.py exactly."""
    tokens = TOKEN_PATTERN.findall(text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def compute_term_frequencies(tokens):
    """Compute normalized TF - matches sequential.py exactly."""
    if not tokens:
        return {}
    counts = defaultdict(int)
    for token in tokens:
        counts[token] += 1
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


# ============================================================================
# Worker Initializer Pattern - Module-level globals
# ============================================================================

_WORKER_INDEX = None
_WORKER_DOCUMENTS = None
_WORKER_TOP_K = None


def init_search_worker(index_data, documents_data, top_k):
    """
    Initializer function executed once per worker at startup.
    Sets module-level global variables in the worker's memory space.
    
    This avoids pickling the large index for every query task.
    The index is pickled only once per worker during pool creation.
    
    Args:
        index_data: The TFIDFIndex object (or dict with same fields)
        documents_data: Optional list of documents for title lookup (or None)
        top_k: Number of top results to return
    """
    global _WORKER_INDEX, _WORKER_DOCUMENTS, _WORKER_TOP_K
    _WORKER_INDEX = index_data
    _WORKER_DOCUMENTS = documents_data
    _WORKER_TOP_K = top_k


def worker_search_query(query):
    """
    Per-query search function that runs in a worker process.
    Uses the global index set by init_search_worker.
    
    This function replicates the exact logic of search_sequential
    from sequential.py to ensure identical results.
    
    Args:
        query: Search query string
    
    Returns:
        List of (doc_id, score, title) tuples
    """
    index = _WORKER_INDEX
    documents = _WORKER_DOCUMENTS
    top_k = _WORKER_TOP_K
    
    # Tokenize query
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    
    # Compute query TF
    query_tf = compute_term_frequencies(query_tokens)
    
    # Access index fields - support both dict and object access
    if isinstance(index, dict):
        idf = index['idf']
        inverted_index = index['inverted_index']
        doc_vectors = index['doc_vectors']
        doc_norms = index['doc_norms']
    else:
        idf = index.idf
        inverted_index = index.inverted_index
        doc_vectors = index.doc_vectors
        doc_norms = index.doc_norms
    
    # Compute query TF-IDF vector
    query_vector = {}
    query_norm_squared = 0.0
    for term, tf in query_tf.items():
        if term in idf:
            tfidf = tf * idf[term]
            query_vector[term] = tfidf
            query_norm_squared += tfidf * tfidf
    
    if not query_vector:
        return []
    
    query_norm = math.sqrt(query_norm_squared)
    
    # Find candidate documents
    candidate_docs = set()
    for term in query_vector:
        if term in inverted_index:
            for doc_id, _ in inverted_index[term]:
                candidate_docs.add(doc_id)
    
    # Compute cosine similarity for each candidate
    scores = []
    for doc_id in candidate_docs:
        doc_vector = doc_vectors.get(doc_id, {})
        doc_norm = doc_norms.get(doc_id, 0)
        
        if doc_norm == 0:
            continue
        
        # Dot product - iterate over query_vector terms (same order as sequential)
        dot_product = sum(
            query_vector.get(term, 0) * doc_vector.get(term, 0)
            for term in query_vector
        )
        
        similarity = dot_product / (query_norm * doc_norm)
        scores.append((doc_id, similarity))
    
    # Get top-k results using nlargest (matches sequential.py)
    top_results = nlargest(top_k, scores, key=lambda x: x[1])
    
    # Build result tuples
    doc_titles = {d.doc_id: d.title for d in documents} if documents else {}
    results = []
    for doc_id, score in top_results:
        title = doc_titles.get(doc_id, f"Document {doc_id}")
        results.append((doc_id, score, title))
    
    return results


def batch_search_parallel(queries, index, top_k=10, num_workers=None, documents=None):
    """
    Execute batch query search in parallel using ProcessPoolExecutor
    with the worker initializer pattern.
    
    Args:
        queries: List of query strings
        index: TFIDFIndex object (or dict with same fields)
        top_k: Number of top results per query
        num_workers: Number of worker processes (default: cpu_count)
        documents: Optional list of Document objects for title lookup
    
    Returns:
        Tuple of (results_list, elapsed_time)
        where results_list is List[List[(doc_id, score, title)]]
    """
    if num_workers is None:
        num_workers = os.cpu_count()
    
    start_time = time.perf_counter()
    
    # Calculate optimal chunksize for IPC efficiency
    chunksize = max(1, len(queries) // (num_workers * 4))
    
    with ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=init_search_worker,
        initargs=(index, documents, top_k)
    ) as executor:
        results = list(executor.map(worker_search_query, queries, chunksize=chunksize))
    
    elapsed = time.perf_counter() - start_time
    
    return results, elapsed
