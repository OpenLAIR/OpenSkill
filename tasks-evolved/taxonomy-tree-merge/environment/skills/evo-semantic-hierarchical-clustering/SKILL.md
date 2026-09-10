---
name: evo-semantic-hierarchical-clustering
description: Generate sentence embeddings and build a balanced 5-level hierarchy via recursive top-down clustering.
---

# Semantic Hierarchical Clustering

## Usage
```python
import sys; sys.path.insert(0, '/app/environment/skills/evo-semantic-hierarchical-clustering/scripts')
from cluster_utils import generate_normalized_embeddings, recursive_top_down_cluster
embeds = generate_normalized_embeddings(list_of_strings)
label_matrix = recursive_top_down_cluster(embeds, k_per_level=[14, 8, 6, 5, 4])
```
