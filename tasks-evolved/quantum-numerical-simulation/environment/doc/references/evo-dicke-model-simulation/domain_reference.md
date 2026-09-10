# Domain Reference for evo-dicke-model-simulation

**Responsibility**: Construct composite Hilbert space operators (cavity + N qubits), build the Dicke Hamiltonian, assemble collapse operator lists for arbitrary combinations of local and collective dissipation channels, solve for steady state using QuTiP's steadystate solver, and return the reduced cavity density matrix.

**Key functions to implement**: build_local_spin_op, build_collective_spin_ops, build_dicke_hamiltonian, build_collapse_operators, solve_steady_state, get_cavity_state

---

## 2. Composite Hilbert Space Construction


Constructing the Hilbert space is the foundational step in any QuTiP simulation. For the open Dicke model, the total space is a tensor product of a bosonic Fock space (the cavity) and a multi-qubit space (the atomic ensemble).

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

## 4. Liouvillian Construction and Steady State Solver


The steady state of the open system satisfies $\dot{\rho}_{ss} = \mathcal{L}\rho_{ss} = 0$, where $\mathcal{L}$ is the Liouvillian superoperator [cite: 9, 21].

## 5. Partial Trace to Get Cavity Reduced Density Matrix


To evaluate properties of the cavity field (such as the Wigner function), we must trace out the spin degrees of freedom [cite: 22].

In QuTiP 4.7.0, the `Qobj.ptrace(sel)` method is used to perform the partial trace [cite: 15, 23].
- **Indexing Convention**: The indices correspond to the order in which the composite space was constructed using `qutip.tensor`.
- Since we built our operators as `qutip.tensor(Cavity, Spin)`, the cavity is at index `0` and the spin is at index `1`.
- To keep the cavity and trace out the spin, pass `0` to `ptrace`.

```python

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