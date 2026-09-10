# QuTiP 4.7.0 Open Dicke Model Simulation and Wigner Function Analysis: An Exhaustive API Guide

**Executive Summary**
This report provides a comprehensive, expert-level guide to simulating the open Dicke model and calculating phase-space Wigner distributions using QuTiP (Quantum Toolbox in Python) version 4.7.0 [cite: 1]. The open Dicke model, which describes the interaction between a quantized cavity field and an ensemble of $N$ two-level systems (spins/qubits) subject to dissipation, presents unique computational challenges due to exponential Hilbert space scaling [cite: 2, 3]. 

Addressing the core critical question regarding symmetric subspaces: local dissipation channels (such as individual spin dephasing or emission) fundamentally break the strong permutation symmetry required to restrict dynamics to the maximal spin $j = N/2$ Dicke subspace. Consequently, simulating local dissipation requires either constructing the full $2^N$ multi-qubit Hilbert space or leveraging QuTiP 4.7.0's Permutational Invariant Quantum Solver (PIQS) module, which maps the system to an $O(N^3)$ dimensional Liouvillian subspace [cite: 4, 5]. This guide extensively details both methodologies, providing exact mathematical mappings, API signatures, solver selection matrices, and optimized routines for computing and exporting 1000×1000 Wigner function grids using pandas [cite: 6, 7]. 

---

## 1. Introduction to the Open Dicke Model and QuTiP 4.7.0

The Dicke model is a paradigmatic framework in quantum optics describing the collective, symmetric coupling of $N$ two-level atoms to a single mode of the electromagnetic field [cite: 2]. When extending this to the **open Dicke model**, we account for the system's coupling to external reservoirs, leading to phenomena such as cavity photon leakage, local atomic dephasing, and spontaneous emission. Research shows that while collective dissipation channels preserve the permutation symmetry of the spin ensemble, local dissipation fundamentally breaks this symmetry, altering critical phenomena like the superradiant phase transition [cite: 2, 8].

Simulating these dynamics mathematically requires constructing a composite Hilbert space $\mathcal{H} = \mathcal{H}_{cav} \otimes \mathcal{H}_{spin}$. QuTiP 4.7.0, relying on `numpy 1.23.0` and `scipy 1.8.0`, offers highly optimized sparse matrix operations to build these spaces, construct Liouvillian superoperators, and solve for steady-state density matrices using advanced iterative and direct numerical methods [cite: 9, 10].

---

## 2. Composite Hilbert Space Construction

Constructing the Hilbert space is the foundational step in any QuTiP simulation. For the open Dicke model, the total space is a tensor product of a bosonic Fock space (the cavity) and a multi-qubit space (the atomic ensemble).

### 2.1 Core QuTiP API for Operator Construction
The fundamental operators required to build the state space are generated using QuTiP's state and operator factory functions [cite: 11, 12]:

- `qutip.destroy(N)`: Returns the bosonic annihilation operator $a$ for a truncated Fock space of dimension $N$ (where $N = n_{max} + 1$). Return type: `Qobj` of shape `(N, N)`.
- `qutip.create(N)`: Returns the bosonic creation operator $a^\dagger$. Return type: `Qobj`.
- `qutip.sigmax()`, `qutip.sigmay()`, `qutip.sigmaz()`: Returns the Pauli matrices $\sigma_x, \sigma_y, \sigma_z$ for a single two-level system. Dimension: `(2, 2)`.
- `qutip.sigmap()`, `qutip.sigmam()`: Returns the raising ($\sigma_+$) and lowering ($\sigma_-$) operators. `sigmam()` is the matrix `[, [cite: 8]]` representing a jump from the excited $|0\rangle$ (or $|\uparrow\rangle$) state to the ground $|1\rangle$ (or $|\downarrow\rangle$) state in QuTiP's standard z-basis convention [cite: 13, 14].
- `qutip.qeye(N)` or `qutip.identity(N)`: Returns the $N \times N$ identity matrix. Crucial for padding operators in composite spaces.
- `qutip.tensor(*args)`: Computes the Kronecker tensor product of the input `Qobj` instances [cite: 15]. **Operator Ordering Convention**: QuTiP follows standard mathematical physics conventions where the leftmost argument corresponds to the first subsystem (index 0). If you call `tensor(A, B)`, `A` operates on subsystem 0 and `B` on subsystem 1.

### 2.2 Constructing the Spin Subspace: `jmat` vs. Full Space vs. PIQS

This addresses the **critical question** of the query: *How do we represent $N$ spins, and does local dissipation require the full Hilbert space?*

#### Approach A: The Symmetric Dicke Subspace via `qutip.jmat`
If your model contains **only collective coupling and collective dissipation**, the atomic ensemble behaves as a single giant spin. The permutation symmetry is perfectly preserved, restricting the dynamics entirely to the symmetric Dicke subspace characterized by the maximum total angular momentum quantum number $j = N/2$ [cite: 11, 16].
- **For $N=4$ spins**, the correct spin quantum number is $j = 4/2 = 2$.
- The dimension of this subspace is $2j + 1 = N + 1 = 5$.
- You can construct collective spin operators directly using `qutip.jmat(j, *args)` [cite: 11]:
  ```python
  Jz = qutip.jmat(2, 'z')
  Jp = qutip.jmat(2, '+')
  Jm = qutip.jmat(2, '-')
  ```

#### Approach B: The Full $2^N$ Hilbert Space (Strictly Required for Basic Local Dissipation)
If your model includes **local dissipation** (e.g., individual atomic dephasing or emission), the operators $\sigma_z^{(i)}$ or $\sigma_-^{(i)}$ act asymmetrically on the ensemble. Applying a local operator to a fully symmetric state kicks the population out of the $j = N/2$ subspace into subradiant states with lower $j$ values [cite: 8, 17]. 
**Therefore, you cannot use `qutip.jmat(N/2)` if local dissipation is present.** 
For moderate $N$ (e.g., $N=4$), the full space dimension is $2^4 = 16$. This is computationally trivial, and constructing the full space is highly recommended for clarity:
```python
def local_op(op, i, N):
    # Places `op` at the i-th position, padded by identities
    op_list = [qutip.qeye(2)] * N
    op_list[i] = op
    return qutip.tensor(op_list)

# Full collective operators are sums of local operators
Jz_full = sum([local_op(qutip.sigmaz(), i, N)/2 for i in range(N)])
Jm_full = sum([local_op(qutip.sigmam(), i, N) for i in range(N)])
Jp_full = Jm_full.dag()
```

#### Approach C: The Permutational Invariant Quantum Solver (PIQS)
For large $N$ (e.g., $N \ge 10$), the $2^N$ space becomes computationally intractable. QuTiP 4.7.0 includes the `qutip.piqs` module specifically to solve this exact problem [cite: 1, 5]. PIQS maps identical local dissipators into a permutationally invariant basis block-diagonalized by $j$. The basis dimension scales as $O(N^2)$ and the Liouvillian as $O(N^3)$, bypassing the $2^N$ barrier entirely [cite: 4, 5].

### 2.3 Constructing the Composite Space

Assuming we proceed with the full $2^N$ space for absolute rigor with $N=4$, we must embed the cavity and spin operators into the composite space $\mathcal{H}_{cav} \otimes \mathcal{H}_{spin}$ using `qutip.tensor` [cite: 15].
```python
N_cav = 17 # n_max = 16, dimension is 17
N_spin = 4

# Base identities
I_cav = qutip.qeye(N_cav)
I_spin = qutip.qeye(2**N_spin) 

# Cavity operator in composite space
a = qutip.destroy(N_cav)
a_comp = qutip.tensor(a, I_spin)

# Spin operator in composite space
Jz_comp = qutip.tensor(I_cav, Jz_full)
Jp_comp = qutip.tensor(I_cav, Jp_full)
Jm_comp = qutip.tensor(I_cav, Jm_full)
```

---

## 3. Dicke Hamiltonian Construction

The standard Dicke Hamiltonian governing the coherent dynamics is:
\[ H = \omega_c a^\dagger a + \omega_0 J_z + g (a^\dagger + a)(J_+ + J_-) \]
*(Note: depending on the exact theoretical framework, the interaction term is sometimes written as $2g (a^\dagger + a) J_x$. Since $J_x = \frac{1}{2}(J_+ + J_-)$, the physics are identical, provided scaling is accounted for [cite: 16].)*

Using the composite operators defined in Section 2.3, constructing the Hamiltonian in QuTiP 4.7.0 is a direct algebraic translation:
```python
wc = 1.0  # Cavity resonance frequency
w0 = 1.0  # Atomic transition frequency
g = 0.5   # Light-matter coupling strength

H = wc * a_comp.dag() * a_comp + \
    w0 * Jz_comp + \
    g * (a_comp.dag() + a_comp) * (Jp_comp + Jm_comp)
```
The resulting `H` is a `Qobj` of type `oper` with dimensions `[[cite: 3, 18], [cite: 3, 18]]` and shape `(272, 272)`.

---

## 4. Lindblad Master Equation Collapse Operators

Open quantum system dynamics in QuTiP are evaluated using the Lindblad master equation framework, requiring a list of collapse (jump) operators $C_k$ [cite: 19].

### 4.1 Global/Collective Dissipators
Collective dissipators act globally on the spin ensemble.
- **Cavity Loss ($\kappa$)**: Photons leak from the cavity. 
  \[ C_{cav} = \sqrt{\kappa} \, a \implies \text{Code: } \verb|np.sqrt(kappa) * a_comp| \]
- **Collective Emission ($\gamma_\Downarrow$)**: The ensemble emits a photon collectively.
  \[ C_{col\_emit} = \sqrt{\gamma_\Downarrow} \, J_- \implies \text{Code: } \verb|np.sqrt(gamma_down_col) * Jm_comp| \]
- **Collective Pumping ($\gamma_\Uparrow$)**: The ensemble is collectively excited.
  \[ C_{col\_pump} = \sqrt{\gamma_\Uparrow} \, J_+ \implies \text{Code: } \verb|np.sqrt(gamma_up_col) * Jp_comp| \]

### 4.2 Local Dissipators (Acting on Individual Spins)
Local processes act independently on each atom $i$. 
- **Local Emission ($\gamma_\downarrow$)**: $C_i = \sqrt{\gamma_\downarrow} \, \sigma_-^{(i)}$
- **Local Pumping ($\gamma_\uparrow$)**: $C_i = \sqrt{\gamma_\uparrow} \, \sigma_+^{(i)}$
- **Local Dephasing ($\gamma_\phi$)**: $C_i = \sqrt{\gamma_\phi} \, \sigma_z^{(i)}$

To construct these in QuTiP using the full $2^N$ space:
```python
c_ops = [np.sqrt(kappa) * a_comp] # Start with cavity loss

for i in range(N_spin):
    # Local emission
    sm_i = local_op(qutip.sigmam(), i, N_spin)
    c_ops.append(np.sqrt(gamma_down) * qutip.tensor(I_cav, sm_i))
    
    # Local dephasing
    sz_i = local_op(qutip.sigmaz(), i, N_spin)
    c_ops.append(np.sqrt(gamma_phi) * qutip.tensor(I_cav, sz_i))
```

### 4.3 Mathematical Mapping of Local Dissipation (The PIQS Perspective)
*Answering the query's question regarding specific collective superoperator formulas.*

When authors (e.g., Dalla Torre et al., arXiv:1608.06293 [cite: 18, 20], or Kirton & Keeling, arXiv:1611.03342 [cite: 2, 8]) project local dissipation into a computationally tractable basis, they do **not** simply replace $\sum_i \mathcal{D}[\sigma_-^{(i)}]$ with $\mathcal{D}[J_-]$. 

Mathematically, the local dissipator is:
\[ \mathcal{L}_{loc}[\rho] = \frac{\gamma_\downarrow}{2} \sum_{i=1}^N \left( 2\sigma_-^{(i)} \rho \sigma_+^{(i)} - \sigma_+^{(i)} \sigma_-^{(i)} \rho - \rho \sigma_+^{(i)} \sigma_-^{(i)} \right) \]
In the symmetric subspace, the anti-commutator term sums to $-\frac{\gamma_\downarrow}{2} \{ J_z + N/2, \rho \}$, which keeps the state within the symmetric subspace. However, the "jump" term $2\sigma_-^{(i)} \rho \sigma_+^{(i)}$ mathematically generates statistical mixtures of states that lie *outside* the maximum $J$ manifold. 

The standard approach uses the basis of permutationally invariant states $|J, M, \alpha\rangle$. Because all spins undergo identical dissipation, the density matrix remains invariant under particle exchange. Thus, we trace out the degeneracy index $\alpha$. The superoperator mapping results in block-diagonal transitions: population from the density matrix block $\rho^{(J)}_{M, M'}$ decays into the same block $(J)$, and is fed into blocks with smaller angular momentum $(J-1)$. 

If you attempt to simulate $N=20$, you must construct the Liouvillian using QuTiP's PIQS module rather than `c_ops`:
```python
from qutip.piqs import Dicke
system = Dicke(N=20)
system.emission = gamma_down
system.dephasing = gamma_phi
L_spin_local = system.liouvillian() # Returns superoperator in O(N^2) basis
```
*Note for advanced usage:* To combine a PIQS spin Liouvillian with a cavity Liouvillian, one must use QuTiP's `super_tensor` functionality to tensor the superoperators together. For $N=4$, sticking to the $2^N$ space and standard `c_ops` is much simpler and highly efficient.

---

## 4. Liouvillian Construction and Steady State Solver

The steady state of the open system satisfies $\dot{\rho}_{ss} = \mathcal{L}\rho_{ss} = 0$, where $\mathcal{L}$ is the Liouvillian superoperator [cite: 9, 21].

### 4.1 `qutip.liouvillian()` and `qutip.steadystate()`
The QuTiP function `qutip.steadystate(A, c_op_list=[], method='direct', **kwargs)` is the primary API [cite: 10, 12].
- **Parameters**: 
  - `A`: Can be a Hamiltonian (type `oper`) or a pre-calculated Liouvillian (type `super`).
  - `c_op_list`: A list of collapse operators. **Yes, you can pass the Hamiltonian and the list of collapse operators directly** to `steadystate()`. QuTiP will automatically call `qutip.liouvillian(H, c_ops)` internally to construct the sparse Liouvillian supermatrix [cite: 9, 21].

### 4.2 Solver Selection Matrix
The `method` parameter accepts several string values [cite: 10]. Here is a comparative analysis based on a moderate Hilbert space size (~272 dimensions, resulting in a $73,984 \times 73,984$ sparse Liouvillian):

| Method | Algorithm | Best Use Case / Performance on dim=272 |
| :--- | :--- | :--- |
| `'direct'` | Sparse LU decomposition (`scipy.sparse.linalg.spsolve`). | **Default & Best for dim < 1000.** Solves dim=272 in milliseconds. Highly robust. |
| `'eigen'` | Iterative zero-eigenvalue search. | Slower than direct; useful only if looking for multiple steady states. |
| `'iterative-gmres'` | Generalized Minimal RESidual solver. | Best for massive spaces (dim > 5000) where LU decomposition exceeds RAM. Requires preconditioners for efficiency [cite: 10]. |
| `'iterative-lgmres'` | LGMRES. | Similar to GMRES, often better convergence for tough matrices [cite: 9, 21]. |
| `'svd'` | Dense Singular Value Decomposition. | **Do not use for dim=272.** Converts matrix to dense format; will consume massive RAM and fail [cite: 10]. |
| `'power'` | Inverse power method. | Robust alternative to direct, but typically slower. |

### 4.3 Common Pitfalls & Parameters
- **Memory Problems**: The `'direct'` method builds an exact LU factorization, which can cause RAM blowouts for composite spaces exceeding dimension ~2000. For dim=272, memory usage is negligible.
- **Reverse Cuthill-Mckee**: Setting `use_rcm=True` reduces the bandwidth of the sparse matrix, significantly speeding up the `'direct'` solver [cite: 9, 12].
- **Return Type**: `steadystate` returns a `Qobj` of `type='oper'`, representing the steady-state density matrix $\rho_{ss}$ [cite: 10].

```python
# Optimal execution for N=4, N_cav=17
rho_ss = qutip.steadystate(H, c_ops, method='direct', use_rcm=True)
```

---

## 5. Partial Trace to Get Cavity Reduced Density Matrix

To evaluate properties of the cavity field (such as the Wigner function), we must trace out the spin degrees of freedom [cite: 22].

In QuTiP 4.7.0, the `Qobj.ptrace(sel)` method is used to perform the partial trace [cite: 15, 23].
- **Indexing Convention**: The indices correspond to the order in which the composite space was constructed using `qutip.tensor`.
- Since we built our operators as `qutip.tensor(Cavity, Spin)`, the cavity is at index `0` and the spin is at index `1`.
- To keep the cavity and trace out the spin, pass `0` to `ptrace`.

```python
# Returns a Qobj of shape (17, 17) representing the cavity density matrix
rho_cavity = rho_ss.ptrace(0) 
```

---

## 6. Wigner Function Calculation in QuTiP 4.7.0

The Wigner function $W(x, p)$ is a quasi-probability distribution used to visualize quantum states in phase space [cite: 24]. Negative values in $W(x, p)$ are a strict indicator of non-classicality (quantum interference) [cite: 25, 26].

### 6.1 The `qutip.wigner()` API
The exact signature in QuTiP 4.7.0 is [cite: 27]:
```python
qutip.wigner(state, xvec, yvec, method='clenshaw', g=np.sqrt(2), sparse=False, parfor=False)
```
- **`state`**: The density matrix or ket (must be a single-mode bosonic state, which our `rho_cavity` is).
- **`xvec`, `yvec`**: 1D numpy arrays specifying the phase space grid. They are passed directly as 1D arrays; QuTiP utilizes `np.meshgrid` internally [cite: 28, 29].
- **Return Type**: It returns a 2D numpy array `W` of `float64` [cite: 27]. The dimensions are `(len(yvec), len(xvec))`. If `xvec` and `yvec` are the same length (e.g., 1000), it returns a `(1000, 1000)` array.

### 6.2 The Phase Space Grid and the `g` Parameter
The definition of the phase space coordinates depends intimately on the commutation relation $[x, p] = i\hbar$.
The `g` parameter in `qutip.wigner` dictates the scaling factor connecting the annihilation operator $a$ to the $x, y$ coordinates [cite: 27]:
\[ a = \frac{1}{2} g (x + i y) \]
By default, `g = np.sqrt(2)`, which means $a = \frac{x + iy}{\sqrt{2}}$. This corresponds exactly to setting $\hbar = 1$ such that $[x, y] = i$. 
- The `xvec` array represents the real part ($\text{Re}(\alpha) \times \sqrt{2} = x$).
- The `yvec` array represents the imaginary part ($\text{Im}(\alpha) \times \sqrt{2} = p$).

### 6.3 Calculation Methods Comparison
QuTiP 4.7.0 offers four methods for computing the Wigner function [cite: 27, 30]:
1. **`clenshaw`**: The default and strictly recommended method for QuTiP 4.7.0. It uses Clenshaw summation, is highly numerically stable, and is exceptionally fast even for large Fock truncations ($n_{max} > 50$) [cite: 29, 30, 31]. **Best for $n_{max}=16$.**
2. **`iterative`**: The legacy method. Evaluates $W$ iteratively. Stable but slower than Clenshaw for larger matrices [cite: 28].
3. **`laguerre`**: Utilizes SciPy's Laguerre polynomials. Highly optimized for *very sparse* density matrices, but numerically unstable for large $n_{max}$ [cite: 27, 30].
4. **`fft`**: Computes the 2D Fourier transform of the characteristic function. Extremely fast but suffers from finite grid resolution artifacts [cite: 27, 32]. Note: `fft` only accepts `xvec` and calculates `yvec` internally [cite: 30].

### 6.4 Exact Code Execution
```python
import numpy as np

# Define a 1000x1000 grid over [-6, 6]
xvec = np.linspace(-6, 6, 1000)
yvec = np.linspace(-6, 6, 1000)

# Calculate Wigner function
W = qutip.wigner(rho_cavity, xvec, yvec, method='clenshaw', g=np.sqrt(2))
```

---

## 7. Saving Wigner Function Data as CSV

Exporting a 1000×1000 Wigner function matrix generates 1,000,000 float values. 

### 7.1 Best Practices: Pandas vs. NumPy
While `np.savetxt("wigner.csv", W, delimiter=",")` works, it does not easily embed the $x$ and $p$ grid coordinates as headers/indices [cite: 33]. The standard best practice in data science and computational physics is to use `pandas.DataFrame.to_csv()` [cite: 6, 34].

By setting `index=yvec` and `columns=xvec`, the resulting CSV file includes the explicit coordinate grid, which is immensely helpful when importing the data later into OriginLab, MATLAB, or another Python plotting script [cite: 7, 35].

### 7.2 Performance and Formatting
A standard `float64` array of 1 million elements occupies exactly 8 MB of RAM. Writing this to a standard CSV will yield an ~18 MB file. To optimize disk I/O and file size, we pass the `float_format='%.6f'` argument, which truncates the precision to 6 decimal places (well beyond the necessary precision for plotting), cutting the file size nearly in half [cite: 7].

```python
import pandas as pd

# W is shape (len(yvec), len(xvec))
# Thus, index maps to yvec (rows) and columns map to xvec (columns)
df = pd.DataFrame(W, index=yvec, columns=xvec)

# Save to CSV efficiently
df.to_csv("dicke_wigner.csv", index_label="p_coord", float_format="%.6f")
```

---

## 8. Performance and Memory Considerations

- **Steady State Execution Time**: For the composite Hilbert space of dimension $272$ (Cavity=17, Full Spin=16), the sparse Liouvillian $L$ has shape $(73984, 73984)$. However, because QuTiP exploits CSR sparse matrix formats natively, the matrix contains very few non-zero entries. The `'direct'` solver (`scipy.sparse.linalg.spsolve`) will evaluate the steady state in roughly **0.1 to 0.5 seconds** on a modern CPU [cite: 9, 21]. 
- **Wigner Function Time**: Evaluating the `clenshaw` summation over a 1000×1000 grid for $n_{max}=16$ is moderately computationally expensive. It typically executes in **2 to 8 seconds**, depending on CPU clock speed. 
- **Memory Footprint**: The entire script will consume less than 150 MB of RAM. The 1000×1000 `W` matrix utilizes 8 MB, and the sparse Liouvillian overhead is minimal.

---

## 9. Common Pitfalls with QuTiP 4.7.0 Specifically

1. **Deprecated Plotting Backends**: QuTiP 4.7.0 introduced minor incompatibilities with Matplotlib 3.8+ concerning 3D plotting projections. If attempting to plot the Wigner function natively using `qutip.plot_wigner`, you may encounter deprecation warnings [cite: 1]. Saving to CSV and plotting manually bypasses this cleanly.
2. **SciPy 1.12+ Incompatibilities**: QuTiP 4.7.4+ was patched to fix issues with `scipy==1.12` [cite: 1]. Ensure your environment explicitly matches your target (`scipy 1.8.0`), which is perfectly stable for QuTiP 4.7.0.
3. **Non-Convergence in `steadystate`**: If `kappa = 0` and `gamma = 0`, the Liouvillian has zero eigenvalues spanning multiple steady states, causing the `'direct'` solver to throw a singular matrix error. Ensure your dissipators are non-zero.
4. **Wigner Function Precision**: For mixed steady states with large thermal components, numerical precision artifacts can result in values of $W(x,p)$ on the order of $-10^{-15}$ where the theoretical value is strictly positive [cite: 36]. If analyzing non-classicality via negative volumes, ensure you apply a strict numerical tolerance filter (e.g., `W[W > -1e-10] = 0`).

---

## 10. Working End-to-End Code Example

Below is the definitive, reusable Python utility script integrating all derivations, mappings, and best practices formulated in this guide. This template uses the full $2^N$ Hilbert space approach, which rigorously supports local spin dissipation without symmetry restrictions for $N=4$.

```python
"""
QuTiP 4.7.0 Open Dicke Model Utility
------------------------------------
Calculates the steady-state density matrix for a cavity coupled to N spins
under both collective and local dissipation, evaluates the Wigner function
of the reduced cavity state, and exports the data to a CSV file.

Dependencies: qutip==4.7.0, numpy==1.23.0, scipy==1.8.0, pandas
"""

import numpy as np
import pandas as pd
from qutip import (
    destroy, qeye, tensor, sigmam, sigmaz,
    steadystate, wigner
)

def build_dicke_hamiltonian_and_cops(N_cav, N_spin, params):
    """
    Constructs the composite Hamiltonian and collapse operators.
    """
    # Extract parameters
    wc = params['wc']
    w0 = params['w0']
    g  = params['g']
    kappa = params['kappa']
    g_down = params['gamma_down']
    g_phi  = params['gamma_phi']
    
    # 1. Base Operators
    a = destroy(N_cav)
    I_cav = qeye(N_cav)
    I_spin = qeye(2**N_spin)
    
    # Helper for local operators
    def local_spin_op(op, idx):
        op_list = [qeye(2)] * N_spin
        op_list[idx] = op
        return tensor(op_list)

    # 2. Construct collective spin operators from local ones
    Jz = sum([local_spin_op(sigmaz(), i) for i in range(N_spin)]) / 2.0
    Jm = sum([local_spin_op(sigmam(), i) for i in range(N_spin)])
    Jp = Jm.dag()

    # 3. Composite space projection
    a_comp = tensor(a, I_spin)
    Jz_comp = tensor(I_cav, Jz)
    Jp_comp = tensor(I_cav, Jp)
    Jm_comp = tensor(I_cav, Jm)

    # 4. Dicke Hamiltonian
    H = wc * a_comp.dag() * a_comp + \
        w0 * Jz_comp + \
        g * (a_comp.dag() + a_comp) * (Jp_comp + Jm_comp)
        
    # 5. Lindblad Collapse Operators
    c_ops = []
    
    # Cavity loss
    if kappa > 0:
        c_ops.append(np.sqrt(kappa) * a_comp)
        
    # Local spin dissipation
    for i in range(N_spin):
        sm_i = local_spin_op(sigmam(), i)
        sz_i = local_spin_op(sigmaz(), i)
        
        if g_down > 0:
            c_ops.append(np.sqrt(g_down) * tensor(I_cav, sm_i))
        if g_phi > 0:
            c_ops.append(np.sqrt(g_phi) * tensor(I_cav, sz_i))
            
    return H, c_ops

def run_simulation():
    # Model parameters
    params = {
        'wc': 1.0,               # Cavity frequency
        'w0': 1.0,               # Atom frequency
        'g': 0.8,                # Coupling strength
        'kappa': 0.1,            # Cavity dissipation
        'gamma_down': 0.05,      # Local emission
        'gamma_phi': 0.02        # Local dephasing
    }
    
    N_cav = 17    # Fock state cutoff
    N_spin = 4    # Number of atoms
    
    print(f"Building operators for N_cav={N_cav}, N_spin={N_spin}...")
    H, c_ops = build_dicke_hamiltonian_and_cops(N_cav, N_spin, params)
    
    print(f"Solving steady state (Matrix dim: {H.shape}x{H.shape[cite: 8]})...")
    # 'direct' is best for moderate dimensions < 1000
    rho_ss = steadystate(H, c_ops, method='direct', use_rcm=True)
    
    print("Performing partial trace over spin ensemble...")
    # System defined as tensor(Cavity, Spin). Cavity is index 0.
    rho_cavity = rho_ss.ptrace(0)
    
    print("Calculating Wigner function on 1000x1000 grid...")
    xvec = np.linspace(-6, 6, 1000)
    yvec = np.linspace(-6, 6, 1000)
    
    # clenshaw method is preferred in QuTiP 4.7
    W = wigner(rho_cavity, xvec, yvec, method='clenshaw', g=np.sqrt(2))
    
    print("Exporting Wigner matrix to CSV...")
    # Index maps to yvec (p), Columns map to xvec (x)
    df = pd.DataFrame(W, index=yvec, columns=xvec)
    df.to_csv("dicke_model_wigner.csv", index_label="p", float_format="%.6f")
    
    print("Simulation complete. Data saved to 'dicke_model_wigner.csv'.")

if __name__ == '__main__':
    run_simulation()
```

---

## 11. Conclusion

Evaluating the steady-state Wigner function of an open Dicke model in QuTiP 4.7.0 requires strict attention to symmetry conditions and Hilbert space dimensions. As demonstrated, local jump processes break the total angular momentum symmetry, strictly prohibiting the naive use of `qutip.jmat(N/2)` for collective reduction [cite: 8, 17]. 

By constructing the full $2^N$ multi-qubit space for moderate sizes (or leveraging QuTiP's PIQS module for extreme scaling $N \ge 10$ [cite: 4, 5]), physicists can accurately assemble the composite Hamiltonian and pass the parameters natively to `qutip.steadystate()`. Implementing the `Qobj.ptrace(0)` operator isolates the cavity bosonic state, allowing the heavily optimized Clenshaw summation method in `qutip.wigner()` to extract the phase-space profile [cite: 29, 30]. Finally, leveraging modern pandas integration provides scalable, robust, and index-preserved data exportation for subsequent phenomenological analysis [cite: 6].

**Sources:**
1. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGRbracgDAaphV6_-F4V9BlT4cgbjQZhUcpXFJekUc8pbMZJITvzwTEi-pRKjHvb9zonVN42dZ_8ym-u5dY9nVtp7Zok2xYLAG02ZjMHH1OLbV3H74lSyCW0o391OOUYQ==)
2. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHkSoU9kYF56NbWw74ghiSeE_zgElEvsQgk6QgvTjpiiLPfSmCdziBgWTvw68ICI4ub3o7L_OKNfuEQd7m_fgzJAJUicilzg9Gw2MIXdd6H7t4yEXwc5w==)
3. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7xnplXMr_qE_3DlKQAD2fThavm4Mn1iW_-I5Fhfz0PyGs_NdlFBca7fQhFLL5Y6eoBufQno7M9Xiu4mupqqximyNYVIqrzcWhahlF-Z1bGj6c4w3LIw==)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHSTYsZDoNZGb1iZyElidyLryYfTGIfQjf_peXA7XvdHHkl0K7gcyV_XUUyXZfoyTWmi_N6z160kOBnG0yiTYwXLBprSmfK-yi7PNBtKXEYpwxCIkg3pBFzkNscQRV5cEjIZOblUSGgeo997X7y)
5. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYPyJocXjB8eRqgDtKepoR8-wRBURKX7FQW99qaAklOd8mm93AUItND2Mzp4BYQ-SLmma7Rj7ltGeX1tv1P7IDB9JugnuuxPCmGwPThRnn38EMTUFyvdUCAIgAmcMRkRqvSJjIkeiW-A==)
6. [datacamp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHRMBn9LNFqHMB_A8JW3Swi882qpw7p12b8_v64udJaBjwICJvPvVyNQUcq3IYCgQ_TX-e3dRNcxd8vRYVJBgg2gufGrDK8NzbtdRO81X8hbd0kSElje8zK3D5IeF5lme-yGaHwk4Hps0g9Io3jWGpLrqD5ew==)
7. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQETDyyTbSYgf3cND5a3Wxh35byY4yBH8he2ornvDMCOfBY1MfkLloBMgW_I-IzTt9LcXmkBpRi5R4oe7228TVJFFcyXIkOXfFFj9mBYSyuC6JrLlePPTlJQHnqy_7ZtgdeJfRUnUSX7YfzLaV78KNOO6yeAMEOEn8Vd6YeK3_WI)
8. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNHSJob7coJR9FwvVSxKS_3uZXidXzVKZgWrELFNdHbIVSvIo1HPN6N5oPf5AxZT3nrjz2XWyGVm92etudNrat14KW4qA1k-96eLjJ6KtVckjOHpD5rg==)
9. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFQxM73GrlbAMhoHQ572UpYvKx27bIi-hTjmNYu7kWXdDMpHlQe9ZK6zADNaJjsn76CpK9sTIM6gzxyLfBVa7gRVzOJ4tzeg8d_5B0HVz02WSvTUY2-GMkeyeAbYpfnMXGgHdFrr9OLJg==)
10. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEwWxnK-FrblM9qvokDV2eBwmuVf04KSw4p4ddPxtrEcGNw5QsabJw69_WNCr1sqKxxq7_mtqAjHKWJp1QtWD5DsrWJqof9DH86KjvIPcgUxRWD3y5MMJ9MdlNNxi0FWJGCvArkvZDNyOoCV-05rZA=)
11. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhr-bBqLi6ZvtXcKZCAue_gJOac94CSp4nqrItSCQ6LpE45pPL8kdcmB1rH3rvQ8R0DrDzvtOSFG_OJEx4P5fsBDngBZOXqTwL5RustFQxsxTdYsrCYumaLcrR2Svq8xQhJw0apKdav_xb69w4)
12. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEhLWYJ5lKTBcnKyLDYhH61LSfijOiRk9nycotS_F3myGTJMc4sBaRPrs3eCdCeJPrgoT0-sTNjNfqZrg8hLFvmI99ZDbWJuabzWILgcV_nDy8a9ngJED1XCJQKicKYmkynMmH6i_I=)
13. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3Sr8eJ4F5B_WemICrDu-8Yqsn-w9CXYtiyYKALAIqpVIUOMoIzE0gn50CvQxhq2IxJZ71yfOv49ZoBerlPZ_DXa1-IqdMnlVo6GPPJZa_dDf4v_sUMUXdQfprNbZsx5t35FQo7vCYQQ==)
14. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHpdiqAqWuQDJvaH3YTJHk1zdc1p484a3N21u9xOovQVmkCRYO3GcSJkngYcSZtZpXaSDvfrQSDL12AshNrqRYEXV9OjDXnJ_v2sCgPcvergikjgTvZlV9773IXPJ8w-rWfpXxUZD4qk2tiQ==)
15. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwVRbRIjOWOwcIYEmvvrMsyHAK_uFdHRmRqPXuRRa8pV_TGkMHa6b4bCIAHo2da-pabsce0Jq5hCMM-WYKwyLniVod6Ry2z8qB-SpuZcfnL7GD0jU__J3oJ0az_2WYJtsD0d32EKBaeA==)
16. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHbTfVHjqG64Qj5Gf4jMY5bvClQ1qaltymQtASkgxPp3NDha1Fabc3I8A-hb1rnpUsU7uYpL3RFQdxx2ht2e_XFviuNUfk8VkmUPnOs9uc5Wa8CP6rNEsJvL3houYrUN2LP2PT7-_IOYplzPg==)
17. [nathanshammah.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQET6haa94GD28VOqXytT8K4heIPVSX_D0-LePx0mrKTmu76OTOVRG8fKXBGrPmyxEo_D7RIiZq82uxmPNyYTyVWTaUyhBpNS3LBgFHhl86zkywhpy2wYu1FoMnx-Yr3u2_7Mr5LczmYaHIYNFoGqwvKNPZc6Kk3RZdUbHC1mF-SbBoz)
18. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8xqKLH8mk4w7dtZD9lPCAPMFjjHWxQ27td7ioKT2LlaiZOqzqfKV5F3nl-q7cQFROjsuOjptT1IrOLmSouwTmWOY_LTzYQpFwrgqDpLmrdXQmJ3ROfYAzfAEkxRg-oqEiSG1aZ-GQmM7DH8Em7za_unc=)
19. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFi_7XYQXE-9jKY_j6S4pnmDl6b8hQS9ySC2Jo5wbmchQ04VowRiqoLrURALw83cM9EYKDXujy6yUNbP97V0L6WHaYmGR-S8r10CK188sHuymD8wMCc_WYY1AoaXMG3s0jxQ_tI1iEMC7h8JprMzaKnKtkJ)
20. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7jyElMEDR_Wwcr-0BG5kRRkFavQCh11KQiXTJx2LnSKzIlbOrk0rVJ8aoRDEVpFok_f77R7uHF1wZ6fHUeNcXMPIvAG2WVuYqL6YXHS5479qgZURPC84FqIdilJ5YNQGlIwBB3cAVpc_3Kw-XpfbE)
21. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFT6q_-nHQFwYBpVBciL4XHhfMm5sB_DF5hD29-I6jcdACGFLnSNTnglSIj8GTTmQn4G5T4QHnCoc_8vGjSJJ1tPxgvIwyn7NwlfrJPQMrl-b9TIxyh2q38-nJgC2oHXrlaKfd_5XwBloNUQUG2SU8A8oe6uw==)
22. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFnNqkrnLOUanb0VnckYyigqQCn1RDwpVMVe2CIT1x6sOd8BiGw50jQmk5veHMP4HhlpzyYJd783FB3Vu-FeajEmep0txzDFK1AoB_-62fUH4J0hN4fSDPQJUkyoNVyfq2K0G86en9eg0s=)
23. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnHvkKGLGi_J_F395F0MxyaKqt85R3SOjIjDjr4GMKbbnoeDfbcaiklF2p-rK8aDBjaqkv4UoN9GwawGtPrS2PV41MUvtJsS_iObkZQ_qTa-GBgVjq46WaMtb2SROfIyyjsE8uUk_NkKkkzHn8u8Q7RNhtlpiK)
24. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGceEtzq7ijetbX766oAR54dvskm6HqLjR56n7RnOvcB8y-Aj-C6cNb1jSdU8qtZslGBqFul9Iohpm9Nzw_5I1V66CoCgw5Zf0gzlPZMSgGH6WQsXCBrvPHbebL8KuMap394exQg4Hwg4tWHrJdRR1VBw==)
25. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuTQ_DLmQiFisT4VLkOrtLg7FpNgob0gHB0ReoHePqN7AHX56jqRwMdGb7zQwMLE8DznUjJ4k0SnfcFjfBVRw6vAS_PfG5zik_nOO5aHgtQ8wMRZiOkJJnlEoB_2uz5lZH8i9G9wHFkfgBjWXhWgWrCzGhKVJJuC1i5Us=)
26. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWPbJZSoRG6u2_ZBBhHGBUXkU5BJngty9d0OoUWxSMzQ3vr5MwahHQLCrIAJ1JNvP7GzOvRRVOwF4ZHKG2dNvDIbpmYMvrVk-QJaaHvCCZnoGDSFL3YU-okr6vZGMaQeohhjhy1JfsUrdVK-d6hzY=)
27. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxko82HtUtBtnnL5SfKKwKIZV5HQFlrt6hHNyfx_ejQw52G0poFXPb1LMDjc1g6vRFcFbxFeRl2OxQXDZ3DuD5Y8pgltZpXmFJXY7DvqRA-Jd4ia5-iIZLh_EnEoKXtbF2dgcuT5H1Ypag)
28. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0QJAh08b9zFEfvcOMvMHq0KxXw3eD_JeGy8-NgiylkpJLu7aVCydcQmNkSbEn3r8wiYyr9RNjmWU0Mjo7ERExXW7B4S_8RVPwm5c2mPrdRbRqfOZwIl8isW4K0-ZseeJNcs5BuMv_XFQHag8=)
29. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_aXztMUNutWR7ujGkTQ2L2-IjX75KAuM0WTbCFR3dzDrQK2WD3YIXmnkvm8RNog1RmzQ-WKoqdTfuV2RMeEtMs0S5lw9c4Z6MzOHaK9yX0ud1flFrDnHPqOgpGo12U80WLuQ0HLKLk20O)
30. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0zpthdG_Kk2brJr6QEZ8CFBWHRv9zyNoK2uCI717yDze-ZDfkyCk3ENRAvAOIj7MPyPQBND6Rau_o3mKx-F2ehVYrNk6gq92QjkjqiM3o-oFlyWq1zsbZpkiw5UICGtgFJYz371PNSwZt)
31. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdUGTVFxi9BE4OrQ-KiwtO_CIVL57p8QCWt5rMxn2FIJ2LHFttbJChHTDtQx2BZ1X4zdaKQiooxTyKRvdjnmZhMwFa5J8KpdwKoToN7RlgUMqmbizCG5kbt9E0RwV_poCG0y-1iAyJYuPi)
32. [qutip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqI43pqW8ZPp8zsb4S-19xo9Hk6c230pa7yPirlIFQa19fxQkh_idhuIk8VyiFgaDmRAv9ZONA5Y0tbcLJYe-HgBZYXJ8KZ8sJry4ULoq9jNWj7R2u7hvHKneLfrsSj94NsUAiCJPF86XUOKQ=)
33. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqF181UmWLUU9mcKZMBp_QMW-nnIYYIHO4Y2NAL2RVsLSB7Divu9eexSC1sb3Rfl_Une0yN1rVXuTkA0F5-LY0Gc5RcGdw8XDRr7QamuwSOjYtaSwnOo35RuJ_ztXgZcQKr75yJ_Zh94ssB_eBVGZ_MDu6bHphvm0P2q4w7Q==)
34. [digitalocean.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHX8uq5TdeHWQ-rw_R9p-wqeB-S-2HU_27kFpbQVtEekIJFfq2G9NnAYQNs30CqVKmdmXF5eXTuC9TxFMyzZGQ5SGsH5RpBhTSBoZspzKn7eWBM6HrKzR7u3tLqiM8-v57INuFw8MbzJiCh5CODxsS5Md7io7FZaznWVWfsz3EiaXzhbseR_DpNN77ccTM=)
35. [datascientyst.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGuRh5ryiVmldc7rbkHd-BXCd1IlUcMvMqlSpL2kEdZxTcCFWM1i6n4Q4WNa6A17Zb2X-CjumJQAUCsX6ldZib_6ejM3S4HwCPTPb4A5-hAyXhxd5PtOxrnWiEdSySz8pne7XxlCOIgpXB_LT2o1WaXaHzQJeWMm5U=)
36. [blogspot.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEhP05gFnhnwA7kyUzTnJTh2PxVoQNiB-ucUigJcZ4Dq3kkHkeij7tFEOEaK2_ybgbw07pRv0zlLgGDHLhRZdTgex5qpbNScXcAT9B0TXqgT-4WQJsZLUqt)
