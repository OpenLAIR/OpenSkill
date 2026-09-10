# Domain Reference for evo-nasa-budget-recovery

**Responsibility**: All domain-specific logic for recovering missing values: detecting sum relationships (row totals, column totals, cross-sheet totals), implementing constraint propagation to iteratively resolve unknowns, handling floating-point precision, inferring correct data types (int vs float), and orchestrating the full recovery pipeline from load to save.

**Key functions to implement**: detect_sum_relationships, detect_cross_sheet_relationships, recover_missing_values, run_recovery_pipeline

---

## 3. Analyzing Relationships in NASA Budget Excel Files


To build logic that recovers missing numbers, the program must understand the mathematical topography of the target document. NASA's Science Mission Directorate (SMD) and Earth Science Division (ESD) utilize strictly structured Excel templates for Senior Review budget proposals. Understanding these templates illuminates the programmatic patterns required for data recovery.

## 4. Numerical Computation Patterns for Data Recovery


Transforming the theoretical constraint propagation into programmatic execution requires specific heuristics for interpreting Excel layouts.

## 6. Working Code Examples: Complete Reusable Utility Module


The following section aggregates the research, logic, and edge-case mitigations into a complete, production-ready Python utility module. It contains all five requested functions, rigorously engineered for NASA-style financial workbooks.

```python
import math
from typing import List, Dict, Tuple, Any
from openpyxl import load_workbook
from openpyxl.workbook import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.packaging.extended import ExtendedProperties