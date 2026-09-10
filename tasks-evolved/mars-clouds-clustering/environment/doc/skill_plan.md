# Skill Creation Plan

**Task**: Optimize DBSCAN hyperparameters over a grid search to cluster Mars cloud annotations, evaluate via greedy matching against expert labels, and identify Pareto-optimal configurations balancing F1 score and delta.

**Rationale**: The task has three distinct functional domains: (1) core clustering and evaluation logic (DBSCAN with custom metric, centroid computation, greedy matching, F1/delta scoring), (2) parallel grid search orchestration over the hyperparameter space with proper averaging logic, and (3) Pareto frontier extraction and formatted output. Separating these concerns allows clean, testable modules.

**Number of skills**: 3

---

## Skill 1: evo-mars-clustering-eval

**Description**: Core clustering and evaluation utilities: custom weighted Euclidean DBSCAN clustering, centroid computation, greedy bipartite matching, and per-image F1/delta scoring.

**Responsibility**: Implements the custom distance metric, runs DBSCAN with precomputed distance matrices on a single image's citizen science points, computes cluster centroids, performs greedy matching against expert points (max distance 100px), and returns F1 score and delta (average matched distance) for that image.

**Key functions**: `weighted_euclidean_pairwise`, `compute_precomputed_distance_matrix`, `run_dbscan_and_get_centroids`, `greedy_match`, `score_image`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-mars-clustering-eval/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-mars-grid-search

**Description**: Parallel grid search over DBSCAN hyperparameters (min_samples, epsilon, shape_weight), aggregating per-image F1 and delta scores across the full dataset with proper averaging semantics (all expert images, NaN delta handling).

**Responsibility**: Loads CSV data, defines the hyperparameter grid, orchestrates parallel evaluation using joblib, loops over all unique expert images for each hyperparameter combo, aggregates F1 (including zeros) and delta (excluding NaNs), filters results to F1 > 0.5, and produces the full results DataFrame.

**Key functions**: `load_data`, `evaluate_hyperparameter_combo`, `run_grid_search`, `filter_results`

**Depends on**: evo-mars-clustering-eval


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-mars-grid-search/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-mars-pareto-output

**Description**: Computes the Pareto frontier from grid search results (maximize F1, minimize delta) and writes the formatted CSV output.

**Responsibility**: Takes the filtered grid search results DataFrame, applies paretoset to identify Pareto-optimal points with sense=['max', 'min'] for F1 and delta respectively, formats and rounds columns per specification, and writes /root/pareto_frontier.csv.

**Key functions**: `compute_pareto_frontier`, `format_and_save_pareto_csv`

**Depends on**: evo-mars-grid-search


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-mars-pareto-output/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
