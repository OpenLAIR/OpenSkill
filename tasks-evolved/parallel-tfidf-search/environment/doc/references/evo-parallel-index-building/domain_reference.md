# Domain Reference for evo-parallel-index-building

**Responsibility**: Document chunking, parallel map phase for local TF/DF computation, merging partial inverted indices and document frequencies using Counter.update() and defaultdict.extend(), and finalizing TF-IDF scores from raw counts.

**Key functions to implement**: chunk_documents, map_index_chunk, merge_partial_results, finalize_tfidf_scores, build_tfidf_index_parallel

---

## 1. Concurrency APIs: ProcessPoolExecutor and multiprocessing.Pool


Python provides two robust standard library modules for process-based parallelism: `multiprocessing` and `concurrent.futures`. While both spawn child processes to bypass the GIL [cite: 5], their APIs, internal mechanics, and optimal use cases differ significantly.

### 1.4 Code Example: Chunking and Mapping Documents


```python
import os
import math
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Pool

## 2. Parallelizing Inverted Index Construction


Constructing a TF-IDF inverted index requires determining the Document Frequency (DF) of every term in the corpus, calculating the Term Frequency (TF) for each document, and finally building a mapping of `term -> list[(doc_id, tf_idf_score)]`. 

Because DF requires global knowledge of the corpus, parallel indexing is structurally similar to a MapReduce job [cite: 2, 17].

### 2.1 The Two-Pass vs. Single-Pass Strategy


**Two-Pass Approach:**
1. **Pass 1 (DF Calculation):** Distribute document chunks to workers. Each worker calculates a local DF (using a `set` to ensure a document only counts a term once) and returns a partial DF dictionary. The main process merges these into a global DF.
2. **Pass 2 (TF-IDF & Local Index):** Pass the global DF to workers (via initializer). Distribute document chunks again. Workers calculate TF, compute the final TF-IDF using the global DF, and build a local inverted index. The main process merges local inverted indices into the final global index.

**Single-Pass Approach (Optimized):**
To avoid tokenizing the text twice, a more efficient single-pass (Map) followed by a heavy Reduce is preferred [cite: 3]:
1. **Map Phase:** Distribute document chunks. Each worker tokenizes the text, calculates local TF-counts, and tracks the local DF-counts. It returns a combined object containing the local inverted index (with raw TF counts) and the local DF counts.
2. **Reduce Phase (DF Merge):** The main process sums all local DF counts to form the global DF.
3. **Finalize Phase (TF-IDF Conversion):** The main process iterates over the merged global inverted index, applying the global DF to convert raw TF counts into final TF-IDF scores.

### 6.2 Chunk Size Optimization

The `chunksize` parameter dictates how many elements are batched into a single IPC transfer [cite: 7, 10]. 
- If `chunksize=1`, the IPC pipe is flooded with thousands of tiny serialized objects, causing massive blocking.
- If `chunksize` is too large (e.g., `total_docs / workers`), you risk uneven workload distribution (stragglers). If one worker receives slightly longer documents, the other workers finish early and sit idle while the pool waits for the straggler.
- **Rule of Thumb:** `chunksize = max(1, total_items // (workers * 4))`. This balances IPC efficiency with workload distribution.

## 7. TF-IDF Computation Details


Standard TF-IDF implementation details dictate the mathematical soundness of the search engine. Implementing a custom version necessitates mimicking or understanding standard frameworks like Scikit-Learn's `TfidfVectorizer` [cite: 38, 39].

## 10. Efficient Patterns for Merging Partial Results


The final step of parallel data processing—the reduction phase—runs linearly in the main process. If written inefficiently, it becomes an Amdahl's Law bottleneck.

### 10.1 Merging Inverted Indices

When combining partial inverted indices (`dict[term, list[tuple]]`), the fastest approach utilizes `collections.defaultdict(list)`.

```python
from collections import defaultdict

def fast_merge_indices(list_of_partial_indices):
    merged_index = defaultdict(list)
    # Iterate through each partial index
    for partial in list_of_partial_indices:
        for term, postings in partial.items():
            # Use extend() which is implemented in C and highly optimized
            merged_index[term].extend(postings)
    return merged_index
```
Avoid using list concatenation (`merged_index[term] += postings`) as it creates intermediate list objects in memory, increasing garbage collection overhead. `extend()` mutates the existing list in-place.

### 10.2 Merging Document Frequencies

As established in Section 2, the most optimized pattern for summing multiple `Counter` objects is looping over them and calling `update()` [cite: 19].

```python
from collections import Counter

def fast_merge_dfs(list_of_df_counters):
    global_df = Counter()
    for local_df in list_of_df_counters:
        global_df.update(local_df)
    return global_df
```
Using the bitwise OR operator `c = a | b` takes the maximum of counts rather than summing them, which is incorrect for DF [cite: 19]. The `sum(counters, Counter())` approach works but creates intermediary `Counter` objects during each addition step, resulting in $O(N^2)$ memory allocations, whereas iterative `.update()` is $O(N)$ and alters a single object in-place [cite: 20].