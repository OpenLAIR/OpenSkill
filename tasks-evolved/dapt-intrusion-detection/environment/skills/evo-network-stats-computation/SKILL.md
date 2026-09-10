---
name: evo-network-stats-computation
description: Computes all network statistics from extracted packet features and writes to CSV.
---
# evo-network-stats-computation
## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-network-stats-computation/scripts')
from utils import (compute_protocol_counts, compute_time_stats, compute_ppm_buckets,
    compute_size_stats, compute_shannon_entropy, compute_graph_metrics,
    compute_iat_metrics, compute_pcr_metrics, compute_flow_metrics,
    determine_analysis_flags, write_stats_csv)
```
