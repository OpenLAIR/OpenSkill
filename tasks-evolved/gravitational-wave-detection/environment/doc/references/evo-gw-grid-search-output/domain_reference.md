# Domain Reference for evo-gw-grid-search-output

**Responsibility**: Manages the grid search loop over mass1, mass2 (10-40 solar masses, integer steps) and three approximants, calls the matched filter engine for each combination, tracks the maximum SNR and corresponding total mass per approximant, handles exceptions gracefully, performs memory cleanup between iterations, and writes the results CSV to /root/detection_results.csv in the required format.

**Key functions to implement**: run_grid_search, extract_best_per_approximant, write_detection_results_csv

---

## 6. Common Pitfalls and Version-Specific Issues in PyCBC 2.8.5


When building robust pipelines in PyCBC, several subtle issues can trigger silent logical errors or hard crashes [cite: 4, 12].

## 8. Output Formatting: Aggregating a Grid Search


When deploying a matched-filter pipeline over a grid of component masses (e.g., scanning $M_1$ and $M_2$ from 10 to 40 solar masses), Pandas is the most robust tool for aggregation and export.

Below is an exemplary block of code demonstrating how to loop over parameters, correctly calculate the `total_mass`, format the results into a DataFrame, and save to CSV.

```python
import pandas as pd
import numpy as np