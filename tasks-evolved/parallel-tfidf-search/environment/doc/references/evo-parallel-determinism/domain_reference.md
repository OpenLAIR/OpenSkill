# Domain Reference for evo-parallel-determinism

**Responsibility**: Deterministic score accumulation order, tie-breaking in result sorting, ensuring NamedTuples/dataclasses are module-level picklable, handling spawn vs fork context selection, and __name__ guards.

**Key functions to implement**: deterministic_score_accumulation, stable_sort_results, get_safe_mp_context

---

## 5. Ensuring Identical Results to Sequential Version


When parallelizing numerical pipelines, ensuring strict determinism (identical results to a single-threaded run) is notoriously difficult due to edge cases in data structures and floating-point math.

### 5.1 Floating-Point Non-Determinism

Floating-point addition is commutative ($a+b = b+a$) but **not** strictly associative ($(a+b)+c \neq a+(b+c)$) due to precision truncation [cite: 33]. 
In a sequential engine, document scores are accumulated in a specific order based on iterating through query terms. If a parallel engine splits a query across multiple workers or processes documents in different batches, the additions occur in a different order, leading to minute differences in the final cosine similarity score (e.g., `0.9999999999999998` vs `1.0`) [cite: 33].
- **Mitigation:** Sort query terms before processing them, ensuring the addition sequence for TF-IDF scores is rigorously identical regardless of the parallel chunking strategy.

### 5.2 Dictionary Ordering

Historically, Python dictionaries did not preserve insertion order, relying on non-deterministic hash seeds (`PYTHONHASHSEED`) [cite: 34, 35]. While Python 3.7+ guarantees dictionary insertion order, sets (`set()`) remain entirely unordered and non-deterministic [cite: 35].
If your sequential engine iterates over a `set` of terms to build a vector, the order will vary across parallel worker runs.
- **Mitigation:** Always convert sets to sorted lists before iterating over them if order impacts mathematical accumulation.

### 5.3 Tie-Breaking Logic

When sorting similarity scores (`results.sort(key=lambda x: x[cite: 11], reverse=True)`), documents with identical scores may appear in different orders depending on how Python's Timsort encounters them. In parallel architectures, partial results might be merged in arbitrary order (especially if using `imap_unordered` or varying map completion times) [cite: 36].
- **Mitigation:** Implement strict tie-breaking by sorting on both the score (descending) and the Document ID (ascending): 
  `results.sort(key=lambda x: (-x[cite: 11], x))`

---

## 8. NamedTuple and Dataclass Patterns for IPC


For cleaner code, developers often use `collections.namedtuple` or `dataclasses` to represent data like `SearchResult` or `ParallelIndexingResult` [cite: 44].

### 8.1 Pickling Requirements

A critical rule of the `pickle` module (which powers multiprocessing IPC) is that it only serializes the *data* inside an object, coupled with a string reference to the object's class [cite: 45, 46]. It does not serialize the class definition itself.
Therefore, the class must be importable at the top level of a module in the receiving process [cite: 46].

**Common Pitfall:** Defining a `namedtuple` inside a function or a dynamic scope.
```python

## 9. Common Pitfalls in Python Multiprocessing


Deploying multiprocessing pipelines into production introduces subtle failure modes that can silently stall pipelines or cause memory out-of-bounds errors [cite: 4].

### 9.2 Objects that Aren't Picklable

Lambdas, generators, inner functions, and file handles cannot be natively pickled [cite: 4].
*Solution:* Avoid passing complex closure logic to workers. Use top-level functions or `functools.partial`. If complex objects are strictly necessary, third-party libraries like `dill` or `cloudpickle` can replace the standard `pickle` [cite: 4].