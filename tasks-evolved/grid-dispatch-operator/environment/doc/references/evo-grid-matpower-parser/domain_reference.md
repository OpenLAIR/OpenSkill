# Domain Reference for evo-grid-matpower-parser

**Responsibility**: All data ingestion from MATPOWER JSON: external-to-internal bus ID mapping, status filtering for generators and branches, susceptance matrix construction, PTDF computation, incidence matrices, and cost coefficient extraction with correct polynomial ordering.

**Key functions to implement**: load_matpower_json, build_bus_index_map, filter_active_components, build_susceptance_matrix, compute_ptdf, build_gen_bus_matrix, extract_gencost_coefficients

---

## 2. MATPOWER Case Format and JSON Structure


MATPOWER is a widely adopted standard for power system simulation data [cite: 6, 7]. When exported to JSON, a MATPOWER case is fundamentally a nested dictionary containing 2D arrays corresponding to the `bus`, `gen`, `branch`, and `gencost` data matrices [cite: 8, 9].

Because Python uses 0-based indexing (unlike MATLAB's 1-based indexing), extracting data requires shifting the standardized MATPOWER column indices down by one [cite: 10].

### 2.1. Bus Data Matrix

The `bus` matrix defines the topological nodes of the system and the fixed load demand [cite: 7, 11].
*   **0: `bus_i`** – Bus ID number (Integer)
*   **1: `type`** – Bus type (1 = PQ/load, 2 = PV/gen, 3 = Reference/slack, 4 = Isolated)
*   **2: `Pd`** – Active power demand (MW)
*   **3: `Qd`** – Reactive power demand (MVAr)
*   **4: `Gs`** – Shunt conductance (MW injected at V = 1.0 p.u.)
*   **5: `Bs`** – Shunt susceptance (MVAr injected at V = 1.0 p.u.)
*   **6: `area`** – Area number
*   **7: `Vm`** – Voltage magnitude (p.u.)
*   **8: `Va`** – Voltage angle (degrees)
*   **9: `baseKV`** – Base voltage (kV)
*   **10: `zone`** – Loss zone
*   **11: `Vmax`** – Maximum voltage magnitude (p.u.)
*   **12: `Vmin`** – Minimum voltage magnitude (p.u.)

### 2.2. Generator Data Matrix

The `gen` matrix outlines the physical limits and connectivity of generators [cite: 7, 11].
*   **0: `bus`** – Bus ID number to which the generator is connected
*   **1: `Pg`** – Active power output (MW) (Initial/Solved)
*   **2: `Qg`** – Reactive power output (MVAr)
*   **3: `Qmax`** – Maximum reactive power (MVAr)
*   **4: `Qmin`** – Minimum reactive power (MVAr)
*   **5: `Vg`** – Voltage magnitude setpoint (p.u.)
*   **6: `mBase`** – Total MVA base of the machine
*   **7: `status`** – Machine status (>0 is in-service/online; $\le 0$ is offline)
*   **8: `Pmax`** – Maximum active power output (MW)
*   **9: `Pmin`** – Minimum active power output (MW)

### 2.3. Branch Data Matrix

The `branch` matrix represents the transmission lines and transformers [cite: 7, 12].
*   **0: `fbus`** – "From" bus ID number
*   **1: `tbus`** – "To" bus ID number
*   **2: `r`** – Branch resistance (p.u.)
*   **3: `x`** – Branch reactance (p.u.)
*   **4: `b`** – Total line charging susceptance (p.u.)
*   **5: `rateA`** – MVA rating A (long-term rating). **Crucial note:** A value of 0 indicates an unlimited transmission capacity [cite: 7, 13].
*   **6: `rateB`** – MVA rating B (short-term rating)
*   **7: `rateC`** – MVA rating C (emergency rating)
*   **8: `ratio`** – Transformer off-nominal turns ratio (0 for standard transmission lines)
*   **9: `angle`** – Transformer phase shift angle (degrees)
*   **10: `status`** – Initial branch status (1 = in-service, 0 = out-of-service)
*   **11: `angmin`** – Minimum angle difference (degrees)
*   **12: `angmax`** – Maximum angle difference (degrees)

### 2.4. Generator Cost Matrix (`gencost`)

The `gencost` matrix formulates the objective function to minimize [cite: 6, 8].
*   **0: `model`** – Cost model (1 = piecewise linear, 2 = polynomial)
*   **1: `startup`** – Startup cost (US dollars)
*   **2: `shutdown`** – Shutdown cost (US dollars)
*   **3: `ncost`** – $n$, representing either the number of data points (if model=1) or the number of coefficients (if model=2)
*   **4 to $4+n-1$:** Cost coefficients or data points.
    *   **Coefficient Ordering (Model = 2):** MATPOWER orders polynomial coefficients from **highest degree to lowest degree** [cite: 14, 15]. For a quadratic cost function $c_2 P^2 + c_1 P + c_0$, `ncost` is 3. Column 4 is $c_2$, column 5 is $c_1$, and column 6 is $c_0$ [cite: 6, 14]. Note that MATPOWER automatically reduces the order if the highest degree coefficients are zero [cite: 14, 16].

### 2.5. Indexing and Topological Mapping

A severe pitfall in MATPOWER implementation is the disparity between explicit Bus IDs and contiguous matrix indices. Buses are often identified by non-contiguous integers (e.g., Bus 101, Bus 105) [cite: 1, 17].
1.  **Internal vs. External Numbering:** You must dynamically build a mapping dictionary that translates the MATPOWER external `bus_i` to a contiguous internal index $0 \dots N_{bus}-1$ [cite: 17].
2.  **Generator to Bus Mapping:** The value at `gen[i]` is the *external* Bus ID. It must be mapped to the internal 0-based index to construct generation-to-bus incidence matrices.
3.  **Status Filtering:** Any component (bus, gen, branch) with a `status` $\le 0$ must be rigorously excluded from all matrices and computations before building the model [cite: 1, 6].

## 3. DC Power Flow Formulation


The DC power flow simplifies the non-linear physical realities of AC networks under the assumptions that resistances are negligible ($r \approx 0$), voltages are constant ($1.0$ p.u.), and angle differences across branches are small enough that $\sin(\theta_{ij}) \approx \theta_{ij}$ [cite: 1, 18].

### 3.1. Building the Susceptance Matrix (B-bus)

The relation between active power injections and bus voltage angles is linear:
\[ P = B_{bus} \cdot \theta \]
where $P$ is the vector of net power injections (Generation - Demand) at each bus, $\theta$ is the vector of bus voltage phase angles, and $B_{bus}$ is the nodal susceptance matrix [cite: 2, 19].

To construct $B_{bus}$ in Python (for an $N \times N$ system):
1.  Calculate branch susceptance: $b_k = 1 / x_k$ for each branch $k$.
2.  Initialize an $N \times N$ matrix of zeros.
3.  For each branch $k$ connecting internal bus $i$ to bus $j$:
    *   Subtract $b_k$ from the off-diagonals: $B_{ij} \mathrel{-}= b_k$ and $B_{ji} \mathrel{-}= b_k$.
    *   Add $b_k$ to the diagonals: $B_{ii} \mathrel{+}= b_k$ and $B_{jj} \mathrel{+}= b_k$.

### 3.2. Reference (Slack) Bus Handling

Because power flow equations depend on angle *differences*, the $B_{bus}$ matrix is singular (rank deficient by 1) [cite: 2, 20]. To solve the system, a reference bus (slack bus) must be selected—usually the bus with `type == 3` [cite: 11, 20]. The angle at the slack bus is mathematically anchored to 0 radians. In computations requiring inversion of $B_{bus}$, the row and column corresponding to the slack bus must be temporarily removed, yielding the reduced, non-singular matrix $B_{red}$ [cite: 2, 20].

### 3.3. Branch Flow Calculations

Line flows are derived strictly from the angle differences:
\[ \text{flow}_{ij} = \frac{\theta_i - \theta_j}{x_{ij}} \]
In matrix form:
\[ F = D \cdot C_f^T \cdot \theta \]
where $F$ is the vector of branch flows, $D$ is a diagonal matrix containing branch susceptances ($1/x$), and $C_f$ is the branch-bus incidence matrix (with $+1$ at the "from" bus and $-1$ at the "to" bus) [cite: 2, 21].

## 5. Building the PTDF Matrix in Python


While the "B-theta" formulation incorporates $\theta$ variables directly into the solver, the PTDF (Power Transfer Distribution Factor) formulation is often preferred in market clearing because it eliminates $\theta$ entirely, mapping generation injections directly to line flows. This reduces the number of decision variables in the LP [cite: 19, 24].

### 5.1. Mathematical Definition of PTDF

The PTDF matrix defines the sensitivity of the real power flow on line $l$ to a 1 MW injection at bus $i$ (which is subsequently withdrawn at the slack bus) [cite: 2, 20].
\[ \text{PTDF} = D \cdot C_f^T \cdot B_{red}^{-1} \]
Where:
*   $D$ is an $L \times L$ diagonal matrix of branch susceptances ($1/x$).
*   $C_f$ is the $N \times L$ bus-branch incidence matrix [cite: 2, 21].
*   $B_{red}^{-1}$ is the inverted reduced susceptance matrix (with the slack row/column padded back with zeros) [cite: 2, 21].

Using PTDF, branch flows are computed directly from injections [cite: 2, 19]:
\[ F = \text{PTDF} \cdot (P_{gen} - P_{load}) \]
Transmission constraints become:
\[ -rateA \le \text{PTDF} \cdot P_{net} \le rateA \]

### 5.2. Python and NumPy Implementation

Here is a rigorous, vector-optimized implementation of PTDF calculation using NumPy [cite: 24, 25]:

```python
import numpy as np

def compute_ptdf(branch_f, branch_t, branch_x, n_buses, slack_bus):
    n_branches = len(branch_x)
    
    # 1. Build B-bus and Cf (Incidence Matrix)
    Bbus = np.zeros((n_buses, n_buses))
    Cf = np.zeros((n_branches, n_buses))
    D = np.diag(1.0 / branch_x)
    
    for k in range(n_branches):
        f = int(branch_f[k])
        t = int(branch_t[k])
        b_k = 1.0 / branch_x[k]
        
        # Incidence matrix
        Cf[k, f] = 1.0
        Cf[k, t] = -1.0
        
        # B-bus construction
        Bbus[f, f] += b_k
        Bbus[t, t] += b_k
        Bbus[f, t] -= b_k
        Bbus[t, f] -= b_k
        
    # 2. Reduce B-bus by removing the slack bus row and column
    mask = np.ones(n_buses, dtype=bool)
    mask[slack_bus] = False
    B_red = Bbus[mask][:, mask]
    
    # 3. Invert reduced B-bus
    B_red_inv = np.linalg.inv(B_red)
    
    # 4. Map back to full size (padded with zeros for the slack bus)
    B_inv_full = np.zeros((n_buses, n_buses))
    # Fill the non-slack indices with the inverted matrix
    idx = np.ix_(mask, mask)
    B_inv_full[idx] = B_red_inv
    
    # 5. Compute PTDF
    PTDF = D @ Cf @ B_inv_full
    
    return PTDF
```

## 8. Common Pitfalls in Implementation


Developing reusable DCOPF modules involves navigating highly specific data traps common in power system numerics.

1.  **Off-by-One and Missing Indices:** 
    Python arrays are strictly 0-indexed. Do not subtract 1 indiscriminately from bus numbers; use an index mapping dictionary `ext2int` [cite: 17, 29]. A common error is assuming generator $i$ is connected to bus $i$. Generator data matrix column 0 (`gen[:,0]`) dictates the exact external bus [cite: 7]. 
2.  **Inactive Components (`status = 0`):**
    MATPOWER files often leave out-of-service lines and generators in the array with `status = 0` [cite: 6, 7]. A failure to filter these out will result in lines passing flow that physically do not exist, or offline generators providing dispatch and reserves. Always pre-filter: `gen = gen[gen[:, 7] > 0]` and `branch = branch[branch[:, 10] > 0]` [cite: 1, 11].
3.  **Polynomial Ordering Confusion:**
    The coefficients in `gencost` for polynomial functions (model 2) follow highest order to lowest order [cite: 14, 15]. Assuming $c_0, c_1, c_2$ instead of $c_2, c_1, c_0$ will result in solving an inverse mathematical cost function, generating entirely incorrect, usually mathematically unbounded dispatch commands.
4.  **Matrix Singularities & The Slack Bus:**
    Attempting to invert the raw $B_{bus}$ matrix results in a singular matrix error `LinAlgError` because power flows depend on relative angle differences, rendering the system underdetermined [cite: 2]. The slack bus (defined dynamically via `bus[:, 1] == 3`) must be anchored (row/col removed) before any matrix inversion or LU factorization [cite: 11, 20].
5.  **Infeasible LP States:**
    If line limits are overly tight or generation is insufficient to meet demand + reserve, `scipy.linprog` will return `success: False` with an infeasible status. Robust utilities should catch this and retry the problem after incrementally relaxing $R_{req}$ (Reserve Requirement), prioritizing keeping the lights on over holding reserves.