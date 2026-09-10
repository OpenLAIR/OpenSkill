# Domain Reference for evo-wigner-csv-export

**Responsibility**: Generate phase-space grid arrays, compute the Wigner function using qutip.wigner with the clenshaw method, and save the resulting 2D array to CSV with proper formatting using numpy savetxt or pandas DataFrame.

**Key functions to implement**: compute_wigner_function, save_wigner_to_csv

---

## 6. Wigner Function Calculation in QuTiP 4.7.0


The Wigner function $W(x, p)$ is a quasi-probability distribution used to visualize quantum states in phase space [cite: 24]. Negative values in $W(x, p)$ are a strict indicator of non-classicality (quantum interference) [cite: 25, 26].

## 7. Saving Wigner Function Data as CSV


Exporting a 1000×1000 Wigner function matrix generates 1,000,000 float values.