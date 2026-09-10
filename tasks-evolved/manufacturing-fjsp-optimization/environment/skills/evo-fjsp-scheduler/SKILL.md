---
name: evo-fjsp-scheduler
description: Core FJSP scheduling engine with downtime-aware scheduling, greedy dispatching, repair, and SA optimization.
---
# evo-fjsp-scheduler

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-fjsp-scheduler/scripts')
from utils import (find_earliest_start, greedy_dispatching, repair_schedule,
    decode_schedule, simulated_annealing_fjsp, validate_policy_budgets)
```
