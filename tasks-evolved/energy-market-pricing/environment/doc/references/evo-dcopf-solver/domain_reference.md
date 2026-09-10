# Domain Reference for evo-dcopf-solver

**Responsibility**: Optimization model construction (objective, constraints: power balance, thermal limits, capacity coupling, reserve requirement), solving, dual variable extraction for LMPs and reserve MCP, and identifying binding lines.

**Key functions to implement**: solve_dcopf_with_reserves, extract_lmps, extract_reserve_mcp, identify_binding_lines, compute_total_cost

---

## Introduction to DC-OPF and Market Co-Optimization


The secure and economical operation of electrical power grids relies heavily on Mathematical Optimization. The Optimal Power Flow (OPF) problem, originally formulated by Carpentier in the 1960s, forms the backbone of modern wholesale electricity market clearing engines [cite: 2]. The full Alternating Current (AC) OPF is a non-convex, non-linear problem due to the sinusoidal nature of alternating current, voltage magnitude constraints, and reactive power flows [cite: 16, 17]. Because real-time electricity markets require rapid, reliable, and transparent pricing, system operators widely adopt the Direct Current Optimal Power Flow (DC-OPF) approximation [cite: 17].

The DC-OPF linearizes the power flow equations by making three fundamental assumptions:
1. All bus voltage magnitudes are perfectly flat at 1.0 per unit (p.u.).
2. The voltage angle difference between any two connected buses is extremely small, meaning \(\sin(\theta_i - \theta_j) \approx \theta_i - \theta_j\).
3. Reactive power flows and line resistances are negligible, meaning power flow is entirely governed by line reactance [cite: 1, 18, 19].

As grids transition toward higher penetrations of variable renewable energy sources, the need for robust ancillary services—specifically spinning reserves—has grown exponentially [cite: 1, 20]. Spinning reserve is synchronized generation capacity that can be rapidly deployed to counter unexpected generator contingencies or forecast errors [cite: 4]. Co-optimizing energy and reserves ensures that the cheapest units are not entirely maxed out for energy if their capacity is more valuable as a system-wide reserve [cite: 3, 21]. This report provides an exhaustive, end-to-end implementation guide for building reusable DC-OPF utility functions with reserve co-optimization in Python.

## Mathematical Formulation of DC-OPF with Spinning Reserves


The problem is structured to minimize the total generation cost plus the cost of providing reserves, subject to nodal power balance, generation limits, branch limits, and system-wide reserve requirements.

### Standard Capacity Coupling

In a reserve co-optimized market, a generator sells two products: energy ($P_g$) and spinning reserve ($R_g$). The "Standard Capacity Coupling" formulation enforces that the generator's energy provision plus its reserve buffer cannot exceed its physical maximum capacity ($P_{max}$) [cite: 4, 12, 29]:
\[ P_g + R_g \leq P_{max} \]
Additionally, a generator cannot provide reserves if it is offline, and minimum bounds must be respected:
\[ P_{min} \leq P_g \leq P_{max} \]
\[ 0 \leq R_g \leq R_{max} \]

The system spinning reserve requirement ($Req_{sys}$) is typically set as a deterministic rule, such as 10% of total load demand or the capacity of the largest single generator online (N-1 security criterion) [cite: 4, 20]. The global constraint is:
\[ \sum_{g} R_g \geq Req_{sys} \]

### Matrix Constructions for Network Flows

There are two dominant ways to model transmission line flows in DC-OPF: the B-theta formulation and the Power Transfer Distribution Factor (PTDF) formulation [cite: 30, 31].

**1. B-Theta Formulation:**
Flows are determined by the voltage angle ($\theta$) at each node.
- $\mathbf{A} \in \mathbb{R}^{N_l \times N_b}$: The branch incidence matrix, mapping lines to buses [cite: 32]. $A_{l, f} = 1$ and $A_{l, t} = -1$.
- $\mathbf{B}_{branch} \in \mathbb{R}^{N_l \times N_l}$: Diagonal matrix of line susceptances $b_l = 1 / x_l$ [cite: 19].
- $\mathbf{B}_{bus} \in \mathbb{R}^{N_b \times N_b}$: The nodal susceptance matrix [cite: 19, 33], mathematically $\mathbf{B}_{bus} = \mathbf{A}^T \mathbf{B}_{branch} \mathbf{A}$.

Line flow $F_l$:
\[ F = \mathbf{B}_{branch} \mathbf{A} \theta \]

**2. PTDF Formulation:**
The PTDF matrix $\mathbf{H} \in \mathbb{R}^{N_l \times N_b}$ maps nodal net power injections directly to line flows without requiring voltage angles as decision variables [cite: 30, 31, 32]. This is highly advantageous for reducing the state space in linear programming.
\[ F = \mathbf{H} P_{inj} \]
Where $P_{inj} = P_{gen} - P_{load}$.

To calculate PTDF in Python via numpy/scipy [cite: 31, 34, 35]:
1. Select a slack bus (reference bus).
2. Remove the row and column corresponding to the slack bus from $\mathbf{B}_{bus}$ to create a non-singular matrix $\tilde{\mathbf{B}}_{bus}$.
3. Invert $\tilde{\mathbf{B}}_{bus}$.
4. Expand the inverted matrix back to $N_b \times N_b$ by inserting zeros for the slack bus row and column (creating the pseudo-inverse $\mathbf{B}_{bus}^{+}$) [cite: 32].
5. Compute PTDF: $\mathbf{H} = \mathbf{B}_{branch} \mathbf{A} \mathbf{B}_{bus}^{+}$ [cite: 31].

```python
import numpy as np

def compute_matrices(bus_data, branch_data, ext2int, slack_ext):
    nb = len(bus_data)
    nl = len(branch_data)
    
    A = np.zeros((nl, nb))
    Bbranch = np.zeros((nl, nl))
    
    for i, branch in enumerate(branch_data):
        if branch[cite: 28] == 0: # BR_STATUS out of service
            continue
        
        f_idx = ext2int[int(branch)]
        t_idx = ext2int[int(branch[cite: 1])]
        x = branch[cite: 21]
        b = 1.0 / x if x != 0 else 0
        
        A[i, f_idx] = 1
        A[i, t_idx] = -1
        Bbranch[i, i] = b
        
    Bbus = A.T @ Bbranch @ A
    
    # Compute PTDF
    slack_idx = ext2int[slack_ext]
    Bbus_noslack = np.delete(np.delete(Bbus, slack_idx, 0), slack_idx, 1)
    Bbus_inv = np.linalg.inv(Bbus_noslack)
    
    X = np.zeros((nb, nb))
    idx = np.ones(nb, dtype=bool)
    idx[slack_idx] = False
    X[np.ix_(idx, idx)] = Bbus_inv
    
    PTDF = Bbranch @ A @ X
    return A, Bbranch, Bbus, PTDF
```

## Extracting Economic Signals (LMP and MCP)


**Locational Marginal Prices (LMPs):**
The LMP at a node represents the cost to serve one additional MW of load at that specific node [cite: 3, 36]. In linear programming, this is perfectly encapsulated by the dual variable (or shadow price/Lagrange multiplier) of the nodal power balance equality constraint [cite: 10, 36, 37]. 

**Market Clearing Price for Reserves (MCP):**
The reserve MCP is the marginal cost of procuring one additional MW of spinning reserve system-wide. This is the dual variable of the system reserve requirement constraint $\sum R_g \geq Req_{sys}$ [cite: 3, 10].

**Sign Conventions:**
When querying solvers for dual variables, the sign of the dual is heavily dependent on how the constraint is formulated (i.e., $LHS \leq RHS$ versus $LHS \geq RHS$, or standard equality $LHS - RHS = 0$) [cite: 38]. 
- If power balance is written as `Generation - Load - Flow == 0`, adding 1 unit of load shifts the balance, and the solver returns the dual. Depending on the solver (CBC vs GLPK vs OSQP), you may need to multiply the returned dual by $-1$ or $1 / baseMVA$ if equations were in p.u. [cite: 10, 38]. CVXPY standardizes duals well, but PuLP's CBC duals might require negating if formulated as $injections = 0$ [cite: 39].

## Optimization Frameworks in Python


Python possesses a rich ecosystem for operations research. Here we compare the three requested libraries and discuss their pitfalls.

## Implementation Guides and Working Code


Below are comprehensive implementations for formulating the DC-OPF with reserve co-optimization. The generator limits, capacities, and costs are parsed from the matrices described earlier.

We assume the following pre-processed NumPy arrays:
- `Pmax`, `Pmin`: Arrays of length $N_g$ (MW).
- `Cost_energy`: Linear cost coefficient for energy ($/MW).
- `Cost_reserve`: Linear cost coefficient for reserve availability ($/MW).
- `Load_P`: Array of length $N_b$ (MW).
- `PTDF`: The $N_l \times N_b$ mapping matrix.
- `RateA`: Array of length $N_l$ containing branch thermal limits (MW). Unconstrained lines have a dummy high value.
- `GenBus_Idx`: Array mapping generator index to internal bus index.
- `Req_sys`: Scalar MW requirement.