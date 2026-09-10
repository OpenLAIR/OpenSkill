# Skill Creation Plan

**Task**: Unify hierarchical product category taxonomies from Amazon, Facebook, and Google Shopping into a single 5-level taxonomy via offline semantic clustering.

**Rationale**: The task splits naturally into data ingestion/normalization, semantic embedding + hierarchical clustering, and cluster naming/output formatting. Three skills keep each concern self-contained without overlap.

**Number of skills**: 3

---

## Skill 1: evo-taxonomy-data-pipeline

**Description**: Load, normalize, and output e-commerce category taxonomy data using Pandas 2.2.0-safe patterns. Use when ingesting source CSVs (Amazon/Facebook/Google), splitting hierarchical paths, deduplicating, and writing the final unified taxonomy CSVs.

**Responsibility**: CSV I/O, schema normalization across the three platforms, path splitting, text cleanup, deduplication, and writing final output files (unified_taxonomy_full.csv and unified_taxonomy_hierarchy.csv).

**Key functions**: `load_source_csvs`, `normalize_category_paths`, `split_hierarchy_columns`, `write_unified_outputs`, `compute_source_entropy`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-taxonomy-data-pipeline/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-semantic-hierarchical-clustering

**Description**: Generate sentence embeddings for category strings and build a balanced 5-level hierarchy via recursive top-down agglomerative clustering. Use when needing offline semantic embeddings and SciPy/Sklearn-based hierarchical clustering with size constraints.

**Responsibility**: Offline embedding generation using sentence-transformers 2.5.1, condensed distance matrix computation, recursive top-down clustering with min/max children constraints to produce strictly nested 5-level cluster IDs.

**Key functions**: `generate_normalized_embeddings`, `compute_condensed_distance`, `recursive_top_down_cluster`, `extract_flat_clusters`, `enforce_size_balance`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-semantic-hierarchical-clustering/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-cluster-naming

**Description**: Assign human-readable, non-overlapping representative names to clusters using centroid-nearest selection and TF-IDF, with sibling Jaccard-overlap checks. Use when labeling clustered taxonomy nodes with concise multi-word names.

**Responsibility**: Cluster naming via centroid proximity and TF-IDF top n-grams, enforcement of '<5 words' and ' | ' separator formatting, parent-child name overlap avoidance, and sibling distinctness via Jaccard overlap thresholds.

**Key functions**: `compute_centroid_name`, `extract_tfidf_top_terms`, `format_category_label`, `check_sibling_overlap`, `deduplicate_parent_child_names`

**Depends on**: evo-semantic-hierarchical-clustering


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-cluster-naming/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
