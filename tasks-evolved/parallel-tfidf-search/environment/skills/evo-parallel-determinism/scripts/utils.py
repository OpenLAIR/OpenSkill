"""
Parallel Determinism Utilities

Ensures parallel TF-IDF results are identical to sequential baseline.
Handles:
- Floating-point ordering (sort terms before accumulation)
- Tie-breaking in result sorting
- Pickling compatibility (module-level definitions)
- Safe multiprocessing context selection
"""

import multiprocessing
import sys


def deterministic_score_accumulation(query_vector, doc_vector):
    """
    Compute dot product with deterministic term ordering.
    
    Floating-point addition is not associative: (a+b)+c != a+(b+c).
    To ensure identical results to sequential, iterate over query_vector
    terms in the SAME order as the sequential version.
    
    The sequential version iterates: 
        sum(query_vector.get(term, 0) * doc_vector.get(term, 0) for term in query_vector)
    This iterates in dict insertion order, which is deterministic in Python 3.7+.
    
    For parallel safety, we replicate this exact iteration pattern.
    
    Args:
        query_vector: dict of term -> tfidf score for query
        doc_vector: dict of term -> tfidf score for document
    
    Returns:
        float: dot product
    """
    return sum(
        query_vector.get(term, 0) * doc_vector.get(term, 0)
        for term in query_vector
    )


def stable_sort_results(results):
    """
    Sort search results with deterministic tie-breaking.
    
    When scores are identical, sort by doc_id ascending to ensure
    consistent ordering regardless of parallel execution order.
    
    The sequential version uses heapq.nlargest with key=lambda x: x[1],
    which uses Python's Timsort (stable sort). For identical scores,
    the original insertion order is preserved.
    
    To match this exactly in parallel, we must ensure candidates are
    processed in the same order.
    
    Args:
        results: List of (doc_id, score) tuples
    
    Returns:
        Sorted list with scores descending, ties broken by doc_id ascending
    """
    # heapq.nlargest with key=x[1] preserves insertion order for ties
    # For parallel determinism, we use stable sort matching sequential behavior
    return sorted(results, key=lambda x: (-x[1], x[0]))


def get_safe_mp_context():
    """
    Get a safe multiprocessing context.
    
    On Linux, 'fork' is fast (copy-on-write) but unsafe with threads.
    'spawn' is safe but slower (pickles everything).
    
    For this use case, we use 'fork' on Linux for performance
    (since we control the environment and don't use threads),
    and 'spawn' elsewhere.
    
    Returns:
        multiprocessing context object
    """
    if sys.platform == 'linux':
        # fork is faster on Linux - copy-on-write for read-only data
        return multiprocessing.get_context('fork')
    else:
        return multiprocessing.get_context('spawn')
