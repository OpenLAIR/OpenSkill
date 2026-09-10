# Skill Creation Plan

**Task**: Parallelize a sequential TF-IDF search engine using Python multiprocessing, implementing parallel index building and parallel batch query search with correctness guarantees and performance targets.

**Rationale**: The task has two distinct parallelization targets (index building and batch search) that share common multiprocessing patterns but have fundamentally different computational structures. Index building is a MapReduce problem (chunk, compute local TF/DF, merge), while batch search requires distributing a large read-only index to workers via the initializer pattern. A third concern is ensuring result determinism. These map cleanly to 3 skills.

**Number of skills**: 3

---

## Skill 1: evo-parallel-index-building

**Description**: Provides utilities for parallelizing TF-IDF inverted index construction using a MapReduce approach: chunking documents, computing local TF and DF in worker processes, merging partial results, and finalizing TF-IDF scores with global DF.

**Responsibility**: Document chunking, parallel map phase for local TF/DF computation, merging partial inverted indices and document frequencies using Counter.update() and defaultdict.extend(), and finalizing TF-IDF scores from raw counts.

**Key functions**: `chunk_documents`, `map_index_chunk`, `merge_partial_results`, `finalize_tfidf_scores`, `build_tfidf_index_parallel`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-parallel-index-building/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-parallel-batch-search

**Description**: Provides utilities for parallelizing batch query search over a pre-built TF-IDF index, using the worker initializer pattern to efficiently share the read-only index across worker processes without repeated pickling.

**Responsibility**: Worker initializer setup for sharing large index data, parallel query dispatch using ProcessPoolExecutor or multiprocessing.Pool with initializer/initargs, per-query search logic in workers, and result collection.

**Key functions**: `init_search_worker`, `worker_search_query`, `batch_search_parallel`

**Depends on**: evo-parallel-index-building


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-parallel-batch-search/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-parallel-determinism

**Description**: Provides patterns and utilities to ensure parallel TF-IDF results are identical to the sequential baseline, addressing floating-point ordering, dictionary/set ordering, tie-breaking, and pickling compatibility.

**Responsibility**: Deterministic score accumulation order, tie-breaking in result sorting, ensuring NamedTuples/dataclasses are module-level picklable, handling spawn vs fork context selection, and __name__ guards.

**Key functions**: `deterministic_score_accumulation`, `stable_sort_results`, `get_safe_mp_context`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-parallel-determinism/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
