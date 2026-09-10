---
name: evo-fjsp-validator
description: Validates FJSP schedules for completeness, precedence, machine overlaps, downtime overlaps, eligibility.
---
# evo-fjsp-validator

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-fjsp-validator/scripts')
from utils import (validate_schedule, check_precedence, check_machine_overlaps,
    check_downtime_overlaps, check_eligibility_and_duration, calculate_makespan)
```
