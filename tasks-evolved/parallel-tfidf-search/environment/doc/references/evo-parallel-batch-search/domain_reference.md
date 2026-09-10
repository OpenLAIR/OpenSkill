# Domain Reference for evo-parallel-batch-search

**Responsibility**: Worker initializer setup for sharing large index data, parallel query dispatch using ProcessPoolExecutor or multiprocessing.Pool with initializer/initargs, per-query search logic in workers, and result collection.

**Key functions to implement**: init_search_worker, worker_search_query, batch_search_parallel

---

## 3. Parallelizing Batch Query Search


Once the TF-IDF index is constructed, executing a batch of thousands of queries sequentially is inefficient. Parallelizing the query search involves dispatching queries to worker processes, where each worker compares the query against the global inverted index to calculate cosine similarities.

The paramount challenge here is **sharing the index**. The inverted index for a large corpus can easily consume gigabytes of RAM.

### 3.1 Passing the Index: Approaches and Trade-offs


**1. Passing as an Argument (Serialization via Pickle)**
If you pass the `index` as an argument to `pool.map(search, queries, index)`, the `multiprocessing` module will serialize the entire index into bytes using `pickle`, send it over a pipe, and deserialize it in every worker process for every task [cite: 4]. 
- **Trade-offs:** Catastrophic performance degradation. The overhead of pickling and transferring gigabytes of data will take longer than the search itself [cite: 21].

**2. Utilizing `multiprocessing.shared_memory`**
Python 3.8 introduced the `multiprocessing.shared_memory` module, which allows true POSIX-style shared memory blocks across processes [cite: 22]. 
- **Trade-offs:** `SharedMemory` only supports raw bytes, primitive types via `struct`, or a `ShareableList` containing basic types [cite: 22, 23]. Sharing a complex nested Python dictionary (like an inverted index) requires flattening the data structure into numerical arrays (e.g., using NumPy and memory-mapped files) or using third-party wrappers like `shared-memory-dict`, which internally still use pickling for complex objects [cite: 23, 24]. This approach demands a complete rewrite of the search engine's data structures.

**3. Fork Semantics (Inherited Memory)**
On POSIX systems (Linux), the default start method for multiprocessing historically was `fork` [cite: 5, 25]. When a process is forked, the OS utilizes a copy-on-write mechanism. The child processes inherit the memory layout of the parent instantly, without any copying or pickling [cite: 26, 27].
- **Trade-offs:** Extremely fast and memory-efficient for read-only data. However, `fork` without `exec` is fundamentally broken when the parent process utilizes multi-threading (e.g., via NumPy, gRPC, macOS system libraries) [cite: 28]. It causes severe, silent deadlocks [cite: 4]. Consequently, Python 3.14 changes the POSIX default to `forkserver` or `spawn` [cite: 5, 25], and macOS has defaulted to `spawn` since Python 3.8 [cite: 5]. Relying on `fork` is an anti-pattern for cross-platform, modern Python applications.

**4. The Worker Initializer Pattern (Best Practice)**
When using the safe `spawn` start method, a new Python interpreter is started. To share a large index efficiently without passing it via tasks, you must load or pass the index into the worker's memory space *exactly once* upon creation [cite: 9]. This is done using the `initializer` argument [cite: 6, 13].

---

## 4. The Worker Initializer Pattern


The initializer pattern leverages module-level global variables within the worker process. Because each worker runs in a separate memory space (especially under `spawn`), writing to a global variable in the worker does not cause race conditions with the parent or other workers [cite: 29].

### 4.1 Exact Code Pattern for Initializer


When defining the initializer, you pass the large shared object (or a path to load it) via `initargs`. Note a crucial Python syntax requirement: `initargs` must be a tuple. If passing a single dictionary, it must be formatted as `(my_dict,)` to prevent Python from unpacking the dictionary keys as individual positional arguments [cite: 16, 30].

```python
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

## 6. Performance Considerations and Scaling


Achieving a theoretical linear speedup (e.g., 4x speedup on 4 workers) is practically impossible due to Amdahl's Law and multiprocessing overheads. Realistically, aiming for a 1.5x to 2.5x speedup on 4 workers is a successful implementation.

### 6.1 Understanding Overhead

- **Process Creation:** Spawning a new Python interpreter (under `spawn`) takes roughly 50-100ms. If you create a pool for a task that takes 200ms, parallelization hurts performance [cite: 6, 37].
- **Pickling/IPC:** Every argument and return value sent between processes is pickled, written to a pipe, read from the pipe, and unpickled [cite: 21]. For massive text strings or large lists, this overhead can dominate CPU time.

### 6.3 ProcessPoolExecutor vs. multiprocessing.Pool

`ProcessPoolExecutor` relies heavily on creating `Future` objects for every submitted task. When using `submit()`, the instantiation and tracking of futures adds significant overhead. Tests show `Pool.map` or `Pool.apply_async` can occasionally outperform `ProcessPoolExecutor` for extremely high-frequency, low-latency tasks due to lighter internal machinery [cite: 11]. However, `ProcessPoolExecutor.map` optimizes this by chunking iterables and bypassing individual future tracking, achieving parity with `Pool.map` [cite: 10, 12].