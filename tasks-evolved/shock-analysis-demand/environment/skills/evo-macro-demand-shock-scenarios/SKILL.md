---
name: evo-macro-demand-shock-scenarios
description: Builds demand-side investment shock model on NA sheet with bell-shaped spending, currency conversion, deflation, import adjustment, multiplier. Creates 3 scenarios.
---

# evo-macro-demand-shock-scenarios

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-macro-demand-shock-scenarios/scripts')
from utils import create_scenario_tables, recalculate_workbook

create_scenario_tables(wb)
wb.save('test - demand.xlsx')
recalculate_workbook('test - demand.xlsx')
```

## Bell Shape: [2%,7%,15%,22%,24%,18%,9%,3%]
## Exchange Rate: 2.746 GEL/USD
## Scenarios: 1(mult=0.8,theta=SUT), 2(mult=1.0,theta=SUT), 3(mult=0.8,theta=0.5)
