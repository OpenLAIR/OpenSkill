---
name: evo-wigner-csv-export
description: Computes the Wigner function of a bosonic density matrix on a specified phase-space grid using QuTiP and exports the result as a CSV file.
---

# evo-wigner-csv-export

Computes Wigner functions on phase-space grids and exports to CSV.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-wigner-csv-export/scripts')
from utils import compute_wigner_function, save_wigner_to_csv

# Compute Wigner function on 1000x1000 grid over [-6,6]
W, xvec, yvec = compute_wigner_function(rho_cavity, n_points=1000)

# Save to CSV
save_wigner_to_csv(W, xvec, yvec, '1.csv')
```

## Key Functions

- `compute_wigner_function(rho_cavity, xvec=None, yvec=None, x_range=(-6,6), y_range=(-6,6), n_points=1000)`: Compute Wigner function using clenshaw method
- `save_wigner_to_csv(W, xvec, yvec, filename, float_format='%.6f')`: Save Wigner function as CSV with p index and x columns
