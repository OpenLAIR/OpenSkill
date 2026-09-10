"""
Parallel TF-IDF Index Building Utilities

MapReduce approach:
1. chunk_documents: Split documents into chunks for parallel processing
2. map_index_chunk: Worker function - compute local TF and DF for a chunk
3. merge_partial_results: Merge local inverted indices and DFs
4. finalize_tfidf_scores: Apply global IDF to convert raw TF to TF-IDF
5. build_tfidf_index_parallel: Orchestrate the full parallel pipeline
"""

import math
import os
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field


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
    """Tokenize text into lowercase words, filtering stop words. Matches sequential.py exactly."""
    tokens = TOKEN_PATTERN.findall(text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def compute_term_frequencies(tokens):
    """Compute normalized TF: count(t) / total_tokens. Matches sequential.py exactly."""
    if not tokens:
        return {}
    counts = defaultdict(int)
    for token in tokens:
        counts[token] += 1
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


# ============================================================================
# Chunking
# ============================================================================

def chunk_documents(documents, chunk_size=500):
    """
    Split a list of documents into chunks of specified size.
    
    Args:
        documents: List of Document objects
        chunk_size: Number of documents per chunk
    
    Returns:
        List of chunks, where each chunk is a list of (doc_id, text) tuples
    """
    chunks = []
    for i in range(0, len(documents), chunk_size):
        chunk = []
        for doc in documents[i:i + chunk_size]:
            text = doc.title + " " + doc.content
            chunk.append((doc.doc_id, text))
        chunks.append(chunk)
    return chunks


# ============================================================================
# Map Phase (Worker Function)
# ============================================================================

def map_index_chunk(chunk):
    """
    Worker function: Process a chunk of documents.
    Computes local TF (normalized) and local DF for each document in the chunk.
    
    Args:
        chunk: List of (doc_id, text) tuples
    
    Returns:
        Tuple of:
        - local_tf: dict mapping doc_id -> {term: normalized_tf}
        - local_df: Counter mapping term -> number of docs containing term
        - local_vocab: set of all terms seen in this chunk
    """
    local_tf = {}
    local_df = Counter()
    local_vocab = set()
    
    for doc_id, text in chunk:
        tokens = tokenize(text)
        tf = compute_term_frequencies(tokens)
        local_tf[doc_id] = tf
        # Each term counted once per document for DF
        local_df.update(tf.keys())
        local_vocab.update(tf.keys())
    
    return local_tf, dict(local_df), local_vocab


# ============================================================================
# Reduce Phase (Merge)
# ============================================================================

def merge_partial_results(partial_results):
    """
    Merge results from all workers into global structures.
    
    Args:
        partial_results: List of (local_tf, local_df, local_vocab) tuples
    
    Returns:
        Tuple of:
        - all_doc_tf: dict mapping doc_id -> {term: normalized_tf}
        - global_df: dict mapping term -> total document frequency
        - vocabulary: set of all terms
    """
    all_doc_tf = {}
    global_df = Counter()
    vocabulary = set()
    
    for local_tf, local_df, local_vocab in partial_results:
        all_doc_tf.update(local_tf)
        global_df.update(local_df)
        vocabulary.update(local_vocab)
    
    return all_doc_tf, dict(global_df), vocabulary


# ============================================================================
# Finalize Phase (TF-IDF Scores)
# ============================================================================

def finalize_tfidf_scores(all_doc_tf, global_df, vocabulary, num_documents):
    """
    Convert raw TF values to TF-IDF scores using global DF.
    Build the inverted index, doc_vectors, and doc_norms.
    
    IDF formula (matches sequential.py): log(N / df) + 1
    TF-IDF = normalized_tf * idf
    
    Args:
        all_doc_tf: dict mapping doc_id -> {term: normalized_tf}
        global_df: dict mapping term -> document frequency
        vocabulary: set of all terms
        num_documents: total number of documents
    
    Returns:
        Tuple of (idf_scores, inverted_index, doc_vectors, doc_norms)
    """
    N = num_documents
    
    # Compute IDF: log(N / df) + 1
    idf_scores = {}
    for term in vocabulary:
        df = global_df.get(term, 0)
        if df > 0:
            idf_scores[term] = math.log(N / df) + 1
    
    # Build inverted index and doc vectors
    inverted_index = defaultdict(list)
    doc_vectors = {}
    doc_norms = {}
    
    for doc_id, tf_dict in all_doc_tf.items():
        doc_vector = {}
        norm_squared = 0.0
        for term, tf in tf_dict.items():
            idf = idf_scores.get(term, 0)
            tfidf = tf * idf
            doc_vector[term] = tfidf
            norm_squared += tfidf * tfidf
            inverted_index[term].append((doc_id, tfidf))
        doc_vectors[doc_id] = doc_vector
        doc_norms[doc_id] = math.sqrt(norm_squared)
    
    # Sort posting lists by score descending (matches sequential.py)
    final_inverted_index = {}
    for term in inverted_index:
        posting_list = inverted_index[term]
        posting_list.sort(key=lambda x: x[1], reverse=True)
        final_inverted_index[term] = posting_list
    
    return idf_scores, final_inverted_index, doc_vectors, doc_norms


# ============================================================================
# Main Parallel Index Building
# ============================================================================

def build_tfidf_index_parallel(documents, num_workers=None, chunk_size=500):
    """
    Build TF-IDF index in parallel using ProcessPoolExecutor.
    
    Uses MapReduce approach:
    1. Chunk documents
    2. Map: Each worker computes local TF and DF
    3. Reduce: Merge all partial results
    4. Finalize: Compute IDF and TF-IDF scores
    
    Args:
        documents: List of Document objects
        num_workers: Number of worker processes (default: cpu_count)
        chunk_size: Documents per chunk
    
    Returns:
        ParallelIndexingResult with TFIDFIndex and timing info
    """
    if num_workers is None:
        num_workers = os.cpu_count()
    
    start_time = time.perf_counter()
    
    # Step 1: Chunk documents
    chunks = chunk_documents(documents, chunk_size)
    
    # Step 2: Map phase - parallel processing
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        partial_results = list(executor.map(map_index_chunk, chunks))
    
    # Step 3: Reduce phase - merge results
    all_doc_tf, global_df, vocabulary = merge_partial_results(partial_results)
    
    # Step 4: Finalize - compute TF-IDF scores
    idf_scores, inverted_index, doc_vectors, doc_norms = finalize_tfidf_scores(
        all_doc_tf, global_df, vocabulary, len(documents)
    )
    
    # Build the TFIDFIndex object (same structure as sequential)
    # Import here to avoid circular imports - the actual TFIDFIndex is defined
    # in the main module
    index = {
        'num_documents': len(documents),
        'vocabulary': vocabulary,
        'document_frequencies': global_df,
        'idf': idf_scores,
        'inverted_index': inverted_index,
        'doc_vectors': doc_vectors,
        'doc_norms': doc_norms,
    }
    
    elapsed = time.perf_counter() - start_time
    
    return index, elapsed, len(documents), len(vocabulary)
