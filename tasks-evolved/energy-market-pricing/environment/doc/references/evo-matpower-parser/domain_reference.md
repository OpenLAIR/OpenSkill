# Domain Reference for evo-matpower-parser

**Responsibility**: All data ingestion from MATPOWER JSON, bus index mapping, network matrix construction (A, Bbranch, Bbus, PTDF), branch modification utilities, and generator cost parsing (polynomial and piecewise linear).

**Key functions to implement**: load_matpower_json, create_bus_mappings, parse_generators, parse_branches, parse_gencost, compute_network_matrices, modify_branch_rate, find_slack_bus

---

## MATPOWER Data Structure and JSON Parsing


MATPOWER is the undisputed academic standard for storing and sharing power system network data [cite: 5, 6]. A MATPOWER case struct conventionally contains the following primary matrices: `bus`, `gen`, `branch`, and `gencost` [cite: 6, 22]. When serialized into a JSON format, these matrices are represented as nested lists or arrays.

### Exact Structure of MATPOWER JSON

A MATPOWER JSON file typically mirrors the MATLAB struct. The keys in the JSON dictionary correspond to the matrices:
```json
{
    "baseMVA": 100.0,
    "bus": [
        [1, 3, 0.0, 0.0, 0.0, 0.0, 1, 1.0, 0.0, 345.0, 1, 1.05, 0.95],
        ...
    ],
    "gen": [
        [1, 23.0, 0.0, 150.0, -20.0, 1.0, 100.0, 1, 250.0, 10.0, ...],
        ...
    ],
    "branch": [
        [1, 2, 0.002, 0.02, 0.0, 200.0, 200.0, 200.0, 0.0, 0.0, 1, ...],
        ...
    ],
    "gencost": [
        [2, 0.0, 0.0, 3, 0.01, 20.0, 100.0],
        ...
    ]
}
```

### Column Indices for Data Matrices

To parse this data in Python, you must rely on the standardized column indices defined by MATPOWER [cite: 22, 23]. 

**Bus Data (`bus`):**
- `0`: **BUS_I** - Bus number (positive integer, non-sequential) [cite: 6, 22].
- `1`: **BUS_TYPE** - 1 = PQ (load), 2 = PV (generator), 3 = REF (slack/reference), 4 = isolated [cite: 22].
- `2`: **PD** - Real power demand (MW) [cite: 22].
- `3`: **QD** - Reactive power demand (MVAr) [cite: 22].

**Generator Data (`gen`):**
- `0`: **GEN_BUS** - The bus number the generator is attached to [cite: 22].
- `1`: **PG** - Real power output initial condition (MW) [cite: 22].
- `7`: **GEN_STATUS** - 1 = in service, 0 = out of service [cite: 22].
- `8`: **PMAX** - Maximum real power output (MW) [cite: 22].
- `9`: **PMIN** - Minimum real power output (MW) [cite: 22].

**Branch Data (`branch`):**
- `0`: **F_BUS** - From bus number [cite: 5, 22].
- `1`: **T_BUS** - To bus number [cite: 5, 22].
- `2`: **BR_R** - Resistance (p.u.) [cite: 22].
- `3`: **BR_X** - Reactance (p.u.) [cite: 22].
- `5`: **RATE_A** - Long-term thermal rating (MVA/MW) [cite: 5, 22].
- `10`: **BR_STATUS** - 1 = in service, 0 = out of service [cite: 5].

**Generator Cost Data (`gencost`):**
- `0`: **MODEL** - Cost model: 1 = piecewise linear, 2 = polynomial [cite: 5, 22, 24].
- `1`: **STARTUP** - Startup cost ($) [cite: 5, 24].
- `2`: **SHUTDOWN** - Shutdown cost ($) [cite: 5, 24].
- `3`: **NCOST** - Number of data points (for piecewise) or coefficients (for polynomial) [cite: 22, 24].
- `4+`: **COST** - Parameters defining the cost function [cite: 24].

### Parsing Generator Cost Functions

The `gencost` matrix handles both polynomial (type 2) and piecewise linear (type 1) cost functions [cite: 22, 25, 26]. 
- **Type 2 (Polynomial):** If `MODEL == 2`, `NCOST` indicates the number of coefficients. For a quadratic curve ($Cost = c_2 P^2 + c_1 P + c_0$), `NCOST = 3`. The coefficients start at index 4 in descending order of the polynomial degree ($c_2, c_1, c_0$) [cite: 22, 24, 27].
- **Type 1 (Piecewise Linear):** If `MODEL == 1`, `NCOST` indicates the number of coordinate pairs $(P, Cost)$. The parameters at index 4 and beyond alternate as $p_1, f_1, p_2, f_2, \dots, p_n, f_n$ [cite: 22, 24].

*Pitfall:* In strictly linear formulations (like PuLP), quadratic polynomial costs must be artificially linearized into piecewise segments. Alternatively, utilizing a solver via CVXPY allows native implementation of quadratic objectives.

## MATPOWER Bus Numbering, Indexing, and MW Base Conventions



### Internal vs. External Bus Indexing

A common and fatal pitfall in parsing MATPOWER data is assuming that bus numbers are sequential (e.g., 1, 2, 3...) [cite: 28]. In reality, MATPOWER external bus numbers can be sparse and arbitrary (e.g., 10, 24, 1501). However, to construct linear algebra matrices like the admittance matrix ($Y_{bus}$ or $B_{bus}$), you need continuous, 0-based indices corresponding to the dimensions of a NumPy array [cite: 7, 8]. 

You must create mapping dictionaries: `ext2int` (external to internal) and `int2ext` (internal to external).
```python
def create_bus_mappings(bus_data):
    ext2int = {}
    int2ext = {}
    for internal_idx, row in enumerate(bus_data):
        external_bus_id = int(row)
        ext2int[external_bus_id] = internal_idx
        int2ext[internal_idx] = external_bus_id
    return ext2int, int2ext
```

### Modifying Specific Branches

To locate a specific transmission line between two buses (e.g., from Bus 64 to Bus 1501) and modify its `rateA` limit:
```python
def modify_branch_rate(branch_data, f_bus_ext, t_bus_ext, new_rate):
    for branch in branch_data:
        if int(branch) == f_bus_ext and int(branch[cite: 1]) == t_bus_ext:
            branch[cite: 2] = new_rate # RATE_A index
            break
    return branch_data
```

### BaseMVA and Sign Conventions

The MATPOWER `baseMVA` is typically 100 MVA [cite: 6, 7]. In the DC-OPF framework, reactive power ($Q$) is completely ignored, and voltages are assumed to be 1.0 p.u. [cite: 1, 18]. Therefore, Apparent Power (MVA) is equivalent to Real Power (MW) [cite: 6]. 
Branch thermal limits (`rateA`) are provided in MVA, which translates directly to MW for inequality constraints. If `rateA == 0`, the transmission line is considered unconstrained (infinite thermal capacity) [cite: 5]. 

All per-unit (p.u.) conversions for the power flow matrix require utilizing `baseMVA`:
- $P_{pu} = P_{MW} / baseMVA$
- $B_{branch}$ reactance values are already in per-unit [cite: 22].

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