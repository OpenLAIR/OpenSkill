# DC Optimal Power Flow (DC-OPF) with Reserve Co-Optimization in Python: A Comprehensive Implementation Guide

**Key Points:**
- **Formulation:** DC-OPF simplifies the non-linear AC power flow equations into a set of linear equations by assuming flat voltage profiles, small angle differences, and neglecting reactive power [cite: 1, 2, 3]. Co-optimizing spinning reserves requires integrating reserve capacity requirements and coupling constraints directly into the objective function and feasible region [cite: 1, 4]. 
- **Data Parsing:** The MATPOWER format is a standard in power systems research [cite: 5, 6]. Parsing it in Python from JSON necessitates mapping non-sequential external bus numbers to zero-based internal indices to construct linear algebra matrices [cite: 7, 8].
- **Python Libraries:** Python offers robust modeling libraries. PuLP and Pyomo are excellent for strictly linear or mixed-integer programming, while CVXPY handles convex optimization, including quadratic costs [cite: 9, 10, 11]. 
- **Economic Extraction:** Locational Marginal Prices (LMPs) and Reserve Market Clearing Prices (MCPs) are mathematically equivalent to the dual variables (shadow prices) of the nodal power balance constraints and the system-wide reserve requirement constraint, respectively [cite: 3, 10]. 

**Understanding OPF and Reserve Co-Optimization:**
The Optimal Power Flow (OPF) problem seeks to dispatch generators to meet electrical demand at the lowest possible cost without violating the physical constraints of the transmission network [cite: 2]. Historically, energy and ancillary services (such as spinning reserves) were cleared in sequential markets. However, sequential clearing can lead to suboptimal dispatch and pricing. Co-optimization integrates energy dispatch and reserve procurement into a single mathematical problem. The "Standard Capacity Coupling" constraint ensures that a generator's energy dispatch plus its reserved capacity does not exceed its maximum physical output [cite: 3, 4, 12].

**Tooling and Environment:**
When solving optimization problems in Python, selecting the right library and solver is critical. PuLP provides a highly pythonic interface for linear programs and conveniently bundles the CBC solver [cite: 13, 14]. CVXPY offers powerful convex optimization capabilities, bundling solvers like OSQP and ECOS, which are useful if generator cost curves are formulated as continuous quadratic functions rather than piecewise linear approximations [cite: 9, 15]. Pyomo requires external solvers but offers unparalleled flexibility for massive, complex energy system models [cite: 11]. 

## Introduction to DC-OPF and Market Co-Optimization

The secure and economical operation of electrical power grids relies heavily on Mathematical Optimization. The Optimal Power Flow (OPF) problem, originally formulated by Carpentier in the 1960s, forms the backbone of modern wholesale electricity market clearing engines [cite: 2]. The full Alternating Current (AC) OPF is a non-convex, non-linear problem due to the sinusoidal nature of alternating current, voltage magnitude constraints, and reactive power flows [cite: 16, 17]. Because real-time electricity markets require rapid, reliable, and transparent pricing, system operators widely adopt the Direct Current Optimal Power Flow (DC-OPF) approximation [cite: 17].

The DC-OPF linearizes the power flow equations by making three fundamental assumptions:
1. All bus voltage magnitudes are perfectly flat at 1.0 per unit (p.u.).
2. The voltage angle difference between any two connected buses is extremely small, meaning \(\sin(\theta_i - \theta_j) \approx \theta_i - \theta_j\).
3. Reactive power flows and line resistances are negligible, meaning power flow is entirely governed by line reactance [cite: 1, 18, 19].

As grids transition toward higher penetrations of variable renewable energy sources, the need for robust ancillary services—specifically spinning reserves—has grown exponentially [cite: 1, 20]. Spinning reserve is synchronized generation capacity that can be rapidly deployed to counter unexpected generator contingencies or forecast errors [cite: 4]. Co-optimizing energy and reserves ensures that the cheapest units are not entirely maxed out for energy if their capacity is more valuable as a system-wide reserve [cite: 3, 21]. This report provides an exhaustive, end-to-end implementation guide for building reusable DC-OPF utility functions with reserve co-optimization in Python.

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

### 1. PuLP
PuLP is an intuitive API exclusively for linear and mixed-integer linear programming (MILP) [cite: 10, 13]. 
- **Bundled Solvers:** PuLP comes bundled with the COIN-OR CBC solver [cite: 13, 14]. This makes it extremely easy to use out-of-the-box on Ubuntu 24.04 via `pip install pulp`.
- **Pitfall - Dual Extraction:** By default, PuLP runs CBC with settings that obfuscate or fail to return dual variables (shadow prices) [cite: 36, 39]. To force PuLP to calculate and store duals, you *must* explicitly instruct the solver that the problem is a pure LP (not an MILP), and you must set `msg=0`.
- **API Call:** `prob.solve(PULP_CBC_CMD(msg=0, mip=False))` [cite: 39, 40, 41, 42]. Following this, the dual variable is accessed via `constraint_object.pi` [cite: 10, 36, 39].

### 2. Pyomo
Pyomo is a generalized algebraic modeling language. It scales incredibly well for massive network infrastructures and supports non-linear programming [cite: 11].
- **Bundled Solvers:** Pyomo does *not* bundle solvers [cite: 11]. On Ubuntu 24.04, you must install solvers at the system level: `sudo apt install glpk-utils coinor-cbc` [cite: 10].
- **Pitfall - Dual Extraction:** Pyomo does not return dual variables by default to save memory. You must declare a dual suffix before solving the model: `model.dual = Suffix(direction=Suffix.IMPORT)` [cite: 11, 43, 44, 45].
- **API Call:** After solving, LMPs are accessed via `model.dual[model.power_balance_constraint]` [cite: 45].

### 3. CVXPY
CVXPY is designed for convex optimization. It supports quadratic programming inherently, allowing you to use exact polynomial (Type 2) generator cost curves without piecewise linear approximations [cite: 9, 37].
- **Bundled Solvers:** CVXPY bundles OSQP, ECOS, and SCS [cite: 9, 15]. `pip install cvxpy` provides everything needed to solve a quadratic DC-OPF [cite: 46].
- **Pitfall - DCP Compliance:** CVXPY strictly enforces Disciplined Convex Programming (DCP) rules [cite: 38]. Expressions must explicitly preserve convexity. Multiplying parameters must be handled properly.
- **API Call:** `prob.solve()`. The dual is found via `constraint_object.dual_value` [cite: 9, 38, 47].

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

### 1. DC-OPF using PuLP

```python
import pulp
import numpy as np

def solve_dcopf_pulp(nb, ng, nl, Pmax, Pmin, Cost_energy, Cost_reserve, 
                     Load_P, PTDF, RateA, GenBus_Idx, Req_sys, ext2int, int2ext):
    
    # 1. Initialize Problem
    prob = pulp.LpProblem("DCOPF_Reserve_Cooptimization", pulp.LpMinimize)
    
    # 2. Decision Variables
    # Generators
    Pg = [pulp.LpVariable(f"Pg_{i}", lowBound=Pmin[i], upBound=Pmax[i], cat=pulp.LpContinuous) for i in range(ng)]
    Rg = [pulp.LpVariable(f"Rg_{i}", lowBound=0, cat=pulp.LpContinuous) for i in range(ng)]
    
    # 3. Objective Function
    total_cost = pulp.lpSum([Pg[i] * Cost_energy[i] + Rg[i] * Cost_reserve[i] for i in range(ng)])
    prob += total_cost, "Total_Cost"
    
    # 4. Constraints
    # Standard Capacity Coupling
    for i in range(ng):
        prob += Pg[i] + Rg[i] <= Pmax[i], f"Capacity_Coupling_Gen_{i}"
        
    # System Reserve Requirement
    reserve_req_constraint = pulp.lpSum(Rg) >= Req_sys
    prob += reserve_req_constraint, "System_Reserve_Requirement"
    
    # Power Balance and Line Flows via PTDF
    # Net injection per bus = Sum of generation at bus - Load at bus
    P_inj = []
    for i in range(nb):
        gen_at_bus = pulp.lpSum([Pg[g] for g in range(ng) if GenBus_Idx[g] == i])
        P_inj.append(gen_at_bus - Load_P[i])
        
    # System power balance (lossless DC OPF)
    system_balance = pulp.lpSum(P_inj) == 0
    prob += system_balance, "System_Power_Balance"
    
    # Line Thermal Limits using PTDF: F_l = Sum(PTDF_l,b * P_inj_b)
    # Note: Power balance per bus is implicitly handled by PTDF, but to extract nodal LMPs 
    # directly using the PTDF formulation in an LP, we usually define virtual nodal balance variables
    # Alternatively, the B-theta formulation directly provides nodal LMPs easily.
    # To get LMPs from PTDF, we enforce nodal balance explicitly:
    
    bus_balance_constraints = []
    for i in range(nb):
        # We enforce that the net injection variable equals the physical reality
        # In a strict PTDF, nodal balance is system_balance + PTDF limits.
        # To get exact LMPs, a B-theta formulation is computationally cleaner to extract nodal duals.
        pass

    for l in range(nl):
        if RateA[l] > 0: # 0 means unconstrained in MATPOWER
            line_flow = pulp.lpSum([PTDF[l, b] * P_inj[b] for b in range(nb)])
            prob += line_flow <= RateA[l], f"Thermal_Limit_Forward_{l}"
            prob += line_flow >= -RateA[l], f"Thermal_Limit_Reverse_{l}"

    # 5. Solve the problem
    # CRITICAL: mip=False must be set to retrieve dual variables (pi)
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0, mip=False))
    
    if pulp.LpStatus[status] != 'Optimal':
        raise ValueError("Optimal solution not found.")
        
    # 6. Extract Results
    Pg_vals = [pulp.value(var) for var in Pg]
    Rg_vals = [pulp.value(var) for var in Rg]
    
    # Extract Reserve MCP
    reserve_mcp = reserve_req_constraint.pi
    
    # Identify Binding Constraints
    binding_lines = []
    for l in range(nl):
        if RateA[l] > 0:
            fwd_c = prob.constraints[f"Thermal_Limit_Forward_{l}"]
            rev_c = prob.constraints[f"Thermal_Limit_Reverse_{l}"]
            if abs(fwd_c.slack) <= 1e-4 or abs(rev_c.slack) <= 1e-4:
                binding_lines.append(l)
                
    return Pg_vals, Rg_vals, reserve_mcp, binding_lines
```

*(Note: Extracting exact nodal LMPs using a pure PTDF formulation requires multiplying the system energy balance dual by the transmission congestion components derived from binding line duals. If exact nodal LMPs are required natively from the constraint objects, the B-theta formulation is vastly superior for extraction).*

### 2. DC-OPF using CVXPY (With B-Theta for direct LMP Extraction)

To demonstrate how LMPs are natively extracted via dual variables on nodal power balance, we switch to the B-Theta formulation using CVXPY.

```python
import cvxpy as cp
import numpy as np

def solve_dcopf_cvxpy(nb, ng, nl, Pmax, Pmin, Cost_energy_c1, Cost_energy_c2, Cost_reserve, 
                      Load_P, Bbus, Bbranch, A, RateA, GenBus_Idx, Req_sys):
    
    # Variables
    Pg = cp.Variable(ng)
    Rg = cp.Variable(ng)
    Theta = cp.Variable(nb)
    
    # Generator mappings
    # Create a matrix C_g of size (nb, ng) mapping generators to buses
    C_g = np.zeros((nb, ng))
    for i, b_idx in enumerate(GenBus_Idx):
        C_g[b_idx, i] = 1
        
    # Objective (Quadratic cost allowed)
    # Cost = c2*P^2 + c1*P + reserve_cost
    cost = cp.sum(cp.multiply(Cost_energy_c2, cp.square(Pg)) + 
                  cp.multiply(Cost_energy_c1, Pg) + 
                  cp.multiply(Cost_reserve, Rg))
    objective = cp.Minimize(cost)
    
    # Constraints
    constraints = []
    
    # 1. Standard Capacity Coupling & Bounds
    constraints.append(Pg + Rg <= Pmax)
    constraints.append(Pg >= Pmin)
    constraints.append(Rg >= 0)
    
    # 2. System Reserve Requirement
    reserve_req = cp.sum(Rg) >= Req_sys
    constraints.append(reserve_req)
    
    # 3. Nodal Power Balance (P_gen - P_load = Bbus * Theta)
    P_inj = C_g @ Pg - Load_P
    power_balance = (P_inj == Bbus @ Theta)
    constraints.append(power_balance)
    
    # 4. Slack Bus
    slack_bus = 0
    constraints.append(Theta[slack_bus] == 0)
    
    # 5. Thermal Line Limits
    Flow = Bbranch @ A @ Theta
    for l in range(nl):
        if RateA[l] > 0:
            constraints.append(Flow[l] <= RateA[l])
            constraints.append(Flow[l] >= -RateA[l])
            
    # Solve Problem
    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.OSQP)
    
    if prob.status not in ["optimal", "optimal_inaccurate"]:
        raise Exception("Solver failed to find optimal solution")
        
    # Extract Values
    Pg_opt = Pg.value
    Rg_opt = Rg.value
    
    # Extract LMPs (Dual variables of power balance constraint)
    # The dual value of the equality constraint yields the nodal LMPs
    LMPs = power_balance.dual_value
    
    # Extract Reserve Market Clearing Price
    Reserve_MCP = reserve_req.dual_value
    
    # Binding Lines
    binding_lines = []
    Flow_opt = Flow.value
    for l in range(nl):
        if RateA[l] > 0:
            if abs(abs(Flow_opt[l]) - RateA[l]) < 1e-4:
                binding_lines.append(l)
                
    return Pg_opt, Rg_opt, LMPs, Reserve_MCP, binding_lines
```

### 3. DC-OPF using Pyomo

Pyomo enables declarative modeling. Remembering to activate the `Suffix` to extract LMPs is crucial [cite: 11, 44, 45].

```python
from pyomo.environ import *

def solve_dcopf_pyomo(nb, ng, nl, Pmax, Pmin, Cost_energy, Cost_reserve, 
                      Load_P, Bbus, Bbranch, A, RateA, GenBus_Idx, Req_sys):
    
    model = ConcreteModel()
    
    # Activate dual extraction
    model.dual = Suffix(direction=Suffix.IMPORT)
    
    # Sets
    model.Buses = RangeSet(0, nb - 1)
    model.Gens = RangeSet(0, ng - 1)
    model.Lines = RangeSet(0, nl - 1)
    
    # Variables
    def pg_bounds(m, i): return (Pmin[i], Pmax[i])
    model.Pg = Var(model.Gens, bounds=pg_bounds)
    model.Rg = Var(model.Gens, within=NonNegativeReals)
    model.Theta = Var(model.Buses)
    
    # Objective
    def obj_rule(m):
        return sum(m.Pg[i] * Cost_energy[i] + m.Rg[i] * Cost_reserve[i] for i in m.Gens)
    model.Cost = Objective(rule=obj_rule, sense=minimize)
    
    # Constraints
    # Capacity Coupling
    def cap_coupling_rule(m, i):
        return m.Pg[i] + m.Rg[i] <= Pmax[i]
    model.CapCoupling = Constraint(model.Gens, rule=cap_coupling_rule)
    
    # Reserve Requirement
    def res_req_rule(m):
        return sum(m.Rg[i] for i in m.Gens) >= Req_sys
    model.ReserveReq = Constraint(rule=res_req_rule)
    
    # Power Balance
    def power_balance_rule(m, b):
        gen_inj = sum(m.Pg[i] for i in m.Gens if GenBus_Idx[i] == b)
        net_inj = gen_inj - Load_P[b]
        flow_out = sum(Bbus[b, j] * m.Theta[j] for j in m.Buses)
        return net_inj == flow_out
    model.PowerBalance = Constraint(model.Buses, rule=power_balance_rule)
    
    # Slack Bus
    model.Slack = Constraint(expr=model.Theta == 0)
    
    # Thermal Limits
    model.ThermalLimits = ConstraintList()
    for l in range(nl):
        if RateA[l] > 0:
            # Flow = b_l * (Theta_from - Theta_to)
            # Extracted via Bbranch @ A @ Theta
            flow_expr = sum(Bbranch[l, l] * A[l, b] * model.Theta[b] for b in model.Buses)
            model.ThermalLimits.add(flow_expr <= RateA[l])
            model.ThermalLimits.add(flow_expr >= -RateA[l])
            
    # Solve
    opt = SolverFactory('glpk')
    results = opt.solve(model, tee=False)
    
    # Extract Results
    Pg_opt = [value(model.Pg[i]) for i in model.Gens]
    LMPs = [model.dual[model.PowerBalance[b]] for b in model.Buses]
    Reserve_MCP = model.dual[model.ReserveReq]
    
    return Pg_opt, LMPs, Reserve_MCP
```

## Output Formatting

After solving the model, formatting the data back into a structured JSON for downstream UI plotting or further microgrid analysis is essential. To prevent non-serializable objects (like numpy floats), convert them to native Python floats.

```python
import json

def export_results(Pg_opt, Rg_opt, LMPs, Reserve_MCP, binding_lines, int2ext, filename="opf_results.json"):
    
    # Convert numpy types to native Python types
    LMPs_dict = {str(int2ext[b]): round(float(LMPs[b]), 4) for b in range(len(LMPs))}
    Pg_list = [round(float(p), 4) for p in Pg_opt]
    Rg_list = [round(float(r), 4) for r in Rg_opt]
    
    output_data = {
        "market_clearing": {
            "reserve_mcp_usd_mw": round(float(Reserve_MCP), 4),
            "locational_marginal_prices": LMPs_dict
        },
        "dispatch": {
            "generation_mw": Pg_list,
            "spinning_reserve_mw": Rg_list
        },
        "network": {
            "binding_transmission_lines": [int(l) for l in binding_lines]
        }
    }
    
    with open(filename, 'w') as f:
        json.dump(output_data, f, indent=4)
```

## Conclusion

Building a reusable utility module in Python for DC-OPF and spinning reserve co-optimization provides immense flexibility for power system analysis. Parsing the MATPOWER JSON standard requires careful mapping of external bus identifiers to sequential 0-based arrays to accurately construct linear algebra models. Utilizing Python’s robust optimization libraries—whether PuLP for simple mixed-integer LP with CBC, CVXPY for strictly disciplined convex quadratic cost curves, or Pyomo for immense structural models—allows for direct implementation of standard capacity coupling. Importantly, researchers must be acutely aware of solver-specific configurations, such as overriding PuLP's `mip` parameter to `False` or explicitly requesting Pyomo’s `Suffix(direction=Suffix.IMPORT)`, to extract critical economic market signals like the Reserve Market Clearing Price and Locational Marginal Prices.

**Sources:**
1. [core.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEsCjuKuPHtY_FHT3hv2WjJ0QZBV3mUYq4z3v8OxKnJjORVblZqiefgfrgUl2uZ6zkH78w1VjFmghqkLt8-Xm1FmRD5cNuTqZZsCD69AyHiESVV9eyQzMIOR0dp633eHaOBMQ==)
2. [uconn.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxAyM8LpM1WQ34bgmBAgLsnga37MPnt8RvM8E0HFzYt8hqaoaVyrNYIV72dCgk0J9wJkhSGkxI-n2Nu1WpX9mtohogkzLhgdHbh3avR8FgtC6hS5eJw-AwFtB-_OU0NXB7fY7CNLYU1rfNpjCUN1Q__ScObLtnTu2Ksu787Yz2T1LYpFgFq2AvVLBUgodpTK7ruJP8uo5Ie7qb4udKwKJdoTKj9Z6A3Wt_oB0yC1EzYjOAyDJHtYQYQRzOyqz2RDtJlUlAN6z5zqvCzOLffd-r_rVApsGUhgiVx6IytLXVFAsIphQr4Slt4EtCvlIMTWJ9BnQluE6t26nLNFcf4hZeH4jxQ9ajdCRC2GdqRg==)
3. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGDlsI5Onx3UjdrBluNSOG9Q39D492xsxNaHAlHN31SHE5H8cvyf2Y6QCMM7DRvVU_9qRm6qJotZ43C5OumBRbz3iOn-Dz58cAQgK2DqWpDRt8BhIBt-V7AABt-Yk8=)
4. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0nKr-Np2p5jyxv7H2uSQHJpgkwU-L_W0iQk-NeAN1_jwea7TYDtT14p5h9BJWa5w4cKj2VUqdiaCVzUhEhq4DIqolq7iXYFZMQoiEKJ1vp9c0u-u0W90uTnvIAg==)
5. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYJ0lfu_WIwRQbnWgC15MeTFp0TyvnTNJ49NRQ2EVUGV0AU5UOGGqTLdOIampeghcQISyXjnydWjMSGY_bi-s9_LHydmyglpZoI76cUdwAuAAaIHjaCQ7VagHmxQrb65sGMJgs0KowJT4X3s7m-efJ4SY=)
6. [matpower.app](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGdrlI-VsytWJeCoYeT1_qQ7cyhDfGAyvzSivMB_BBxxNSn7LKgW9SEY-Xy-_wvX4aprqncOUVshSMRSkran9PdRiiUEyA_oG21JmbnbghrgRz6Xm8TxqgV5SBGRZS3FnY72af03Edcm_ltvm5B)
7. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHhWABsBALSc_Krw-aYqu-f-J8Z0OfzjfpepIIufIVJKZwFDDi11mXxA5kAO4QsRwxFMMK1dlU3uVilKOZSi41ZU_Q0Rir471pUkY44ncrkTO2MJfP8vRLe5xNwscCpI-TRIg==)
8. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdF_6qqjEWst6-mjdALJxxIP4-BduUVFfCJsnKo0YdV-qoG4_Cr6XvXfquEskdUjj5bTfTd_4F_AynSaS6OL9VVj9_-5SpD_FRhJpc9PR9XKwIls2LSBgt8Iz0WlVzSXlrKlNIVQTHuu9NzPw3XCtVOfxTSAWS8j08206mR7XEMb1cZg==)
9. [cvxpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHq1upnqLs0EOrhkrUeUI_8-RO5A07O_NqMqsdXQWs79yQdT1o67hGrZuoeqf2XT50YwSG8CxeL8x74FxhhzKDjgzbX6QCvEbKhYAjdaJkqwsI9YwOp2Z-D80I7_5DRcwwsctPclDTAL4kh6L1T1QoZc444)
10. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgHDuh19i2Zv6AJAhiQCdGuzCwcexE9E-KNXb7qAQaJ61Llq5flrhi-3Lk6XCKuK4OEqFvl15-7qUzhyyRoQ9C_yy3UHMQt3HCDNyTk8Qd-zmbgzgtR8PlD5hKNizomfbbPHzk4NOWDR4eMKxqpB-Jr_e6qRF6KPp2hdjiz2d4NPh2AtW7CpV16I9Acfof8A==)
11. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEH7aOndR7PdE84qhTQt9qRtaF5KZtsyjivDAtq5FXFrF9GtF79lModfUEiERoUlMZd4t5_0rEVbx2jBd6DdjERxSY_HxWWmltMwF7l8l2gQc2KbIAaXZ5NC3CCoRziRwkaUnOp8KwKWTxWO9XXl5z6og5VcB6Oxa-es-2LUFIudPZog3dnp78ZFmySOPw=)
12. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-1OjJ-_IgCOsUY9e9JetXBLeGkfLF-5-jp-yOtulSCNmswL8OtmRN_NOmHMxhfk48yB67eIaAdMc7ppSBIw6IjFZKJ5uSaUhCR15P0iJYETkEQsvK6ZWP4fHIT4ZZqVcLaAzcXqD3H5DqWtBRalzI9IR-5s0mO6wasEah2OVZhm3AP8d03Ax1QUVpG10CvPg0r7qCa2lPr5NCJEzxM4Hk)
13. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQExEqyBs_jRGjA5LpWwO7EUkH6L71qWONzKfUS3y1oiPxNSevqcUybvuYjzRr3eeYAst6fPx3XotVsu1whCozeaCoGoktSThPJjfF8yzteKajuvFQ==)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHD3EPFJf13wRaszSzCOXCO_O6VBUxqSo1KViZIYN8Z4E7iXg74I7ct6-0H5ymQqpEiSgvr_0R0zgIIgcALM1RBjdV0CMC4JRvkDHRsaVb_w_yxYCGQ0zxuEglM0l4tCiGmzlMukaZhsan_vvo53X8rcJ9-eIte5RIGNHUOfeHD8M3aMMuPcLEdAYc6_KYOfX-A_8vx4-0=)
15. [cvxpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEvF6p7tx4aTvB0z6SpW3Sp21QW8a1B4Yu-cl-IJsU16r7OqFwu5C2P47V2ub84ZNcMlf_G_jq5acpAS6pG-YX6hLldlRXXKw9OAV6f3yLlSFYhpKy6xhDOOn2q9I3V5Oa2ZZZGZlHyKil38B35QyTHCW7N)
16. [nrel.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQES8650CTnFSyDjuF1ggUIyi5j3JS6oiHhbBnba2ZeJjo4BjEALz2nBqhD2SyH5Aw3Cgg1e_DHDGR9wOqM4t1hW-GI5UFg3IQJ07PYrBcwe2aCYMFNwQe_RtM0yK5TvimcbVA==)
17. [uvic.ca](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBALGAkslMgwUnwbuv3stnXokVQ1pYahT-VDF-4uEaDVWB2Lyk_VODNExERMTODNwS6wnMFEvjCyYSME49ndFdBpPw6rl5vkFjzLuF8zGy6o3KGMRnCBGd6JM8Y9PpFaGdpRKu51mcFn26q3N1IPCl8_2WMEztdpmrysvXCb050QLIdNXD3q7yJd8ElKBoBFPoKKAxZOr3Xu9-Cw==)
18. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFWpfkP5sXlboCJHtryM-GhQrhEc3tfz09_cdRqYL8wKsajIEZYlzNI0GMm_GDTB1lxVecRODZbdpVcTZw_qeKqS-FGguTV9PlGaLxrYK-4-f-_ekkTAxQZ3pL-4esnxRvrKYALcROtda43If8gHwfOpwr1FA==)
19. [uni-due.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXft0f4gQH2yXz55Uyc4kQmyCAqi60zxxMn8Dd0bYhOXRXDhc0JmcPa2_FSFgQW5CZz7_j_LfXkFXxlGdU-mvrZEC3tNNRV1Ttw_01dBuEu2sV6OvwGCLprT89smEm3BoRnjKBNzKeppLnJgUXUqP8ib2Howhw2_pHt8uhU40_3iiZN8fKFMl1ioRtdB1koFUtyh0vUxgr3HJCwAhA-so=)
20. [slideserve.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGNpd6tNRkBCPi-NShLnsbyYY_rAJC7fisTOxpZu2SQctPtkBHL5pkrRrPGFMyqv7mKBbHtK_zO-zXLhyAP4YdB6KdbUZEM2AlXy1MuL-d6BMKdHPiKmFQXHkH8Afh7GhOGA6Dbjz4QIB7wLmGdryfNHiTMwMr_Ld__YlioCgmDRRMkuAZ_qyZ6a88=)
21. [uminho.pt](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEJaAdXmKOW_0N6RFV55_t2g8gyNKZpqx9p_elXF7PuBLIRXlUWLvbCIwFd2a_LcWh0dcbVwEZC32pfgkE_LXAHRN-i828gH4EX3RE_lsMUKEXvPvlYgFcZkvbNOjDw30CPYS7udU_hc0BLOGDGhGc-tJk1-sMMr_pqNCYNydF5f_4SnpcfxTb-rw-BKg==)
22. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJ5iMewDpgBnC5wiTYzOZsO3t-Z6-dxsEbNGCFDUU6h-gB7sJ0h_hVwbe3bfxhBiZVqKtZ8bUQMzIG-7tPwMzDwcuY4GDQqe3LALn8_bfSypw7L0qL0cXlobIyycmgd5uoq5y1BeXf48Y3XHcgMw==)
23. [ed.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEUg783n_KdUvFSTVIgGVW0eeKSzEXQFAyD0fs-dC8JCYJMhL92tFi_WjHMOy-YpBUBXbsK_93BI41csGB4ww0OsUyHc8Us1dr_usWNfNpylVvUpXPPWC1IoRi1DGc-B4XQ6Zu0s6fuuUHnWDZUcTVARZKVH4lX)
24. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNQ_NdX_BjNWJyR-cflxnVfDFTJullbga_LOGV4as1PQIw2JkE1_cCBf9EAczwKKS12p9oaRUDFDFLNEgDcgXd9aX7u_ElUL6dr8Y934Tg2tAGN-rdLFZarZBMLmxWv2GRQ7_ezNTc-YFw6YiL7JmV)
25. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHZl5hFjoanTwg-O06EbFd0P7mjG26EVWDTGUxHd6IWAnS_u9ixVcBGUj2W4_iFybckBIb7L0LSzKW4g3jPhs4EVervaojcnYI-p6O3E5M3uaExv4_nfKQu_O2Za9ynwS46u9NGKIR-kDZcQ==)
26. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFk-6QcA7FBnUIJZ4_IHHQr4VIK1HdXL1GhuvAC32wRFcSZrbiy4qlz_CxjWNw_b4fec-kf8ZnjQe7TX9le-BsLPfQYOyAf0jcy8yE5u-ZFas7LZebmCIxFaXIxZzd-tEWfFjYS01Q9JLvwukXKX6nLqjVe-MPP1OEn)
27. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9OGYXbk6Ki5F9USTonQWBHMXQH92e23MAkssHc6Mau7YHD87-FEmObQ0GuQa1YEa87RI6mPCUzvpYXmjvogjZByG5BEtPOtwqTbYFYdHLx7l7x6E9vnGF5qbbPiC9kO0T0yoLi-YaDue0wewHsJTr_mIYu3XfienH)
28. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFE3BErUmj1_yaku1P8wtHcjNU8hlps9NVbRiVVnWAAyVW04bv_r3CDTeuqhUq8w5D7gzKKeIn9oi2_RoLpBwU07ulMK-09lr6TMch5fhEUcVSI5X6MaPm22PZCQYhobEc1ciF_wVDbtPD0rA==)
30. [pypsa.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgLKKWPUCpS8gNjAS7gGvcjKhdJL0kypKPQ-FuaFIew96FPfZaXZIhWRWereyW-r7TAMX2C0ATVzYRsnJGCVVwNw2CiZepd7sx8VpAKCrddUxe7SMdjMCirQCmiWKmiaqDh2nF80Mdhq7Bid0rOYJxjmULuCjq8LP8toexWuQ_0doSoHk=)
31. [tu-dresden.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAQGEyr9gUnf0JVEZRYCjYJ-GCTegd0tI9aYqT3_0N4PWfs5cY15xtnTAv1-j2ggV_0Om8VPsaiEOvIVWV1z6MXmsWGVzO9H5jzS9ecA0zJZLjZHG1ZwjC7a_umLBzl3_scuhAqdgXw6UBPwChzw0n69KfcB_6ZztKHou6mXmbI8wvSoCKvO9mlBc6plSX-vf-WDhtCd6tn1Qt-iCE1tx8Fe6qWF2-BQAJ2fPEvpTVSbuDS__8JRLtPnE0F0U9EHWdcxauqUu_L5grtrqbdKLSx7yo7xYKMUDbW4rOib69vKIVBxD0kr7EXA==)
32. [ieee.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFeuzbs-jx2hl-8rG-jKsgZgg8ty0kQm5JLjqdkdw4Wszw0RdY05hjRo8ef39g61apLpxHuQC8_dCOWUZH6stQIS6iSTWj7L-RkmUX-QVI6DmqtBvxbLu--C8qPTB93gB9WSIR_LPzcLGGTxx5kbw==)
33. [dlr.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE1fbWOHdwIxNqWHtg3vZeX7NYW5o4aqMS46fyU7WLHBTGzkJwKEStiHl1MpWjtz-_qol2qC4MSE0Xwqh2r1-XuazR9d1WjBPMXwkCpWPKFFeNJpCPTayNZfkghbktGrt1G3kbvHs_GWlUApAk=)
34. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTBumPXP31pnXHOakSnWDiXaKsQckiNZyL1q2Lmpm6icTPFI-5te7C3uCZNtsFlQTV5dGOraxpEBxJfT1vt4Sqls0tcVQC30mv0r1dLL-0EANLff8rDjCsITO3d-aSgVmUo8lV6sNy2x0O)
35. [mspass.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9Cg_QHXLQ6coTV1UnwIz-tS9Luf_pGxwQl0P63IVP5LVnjb6Fj_Ks9yFP3YHJ23IzPP54-GYykP4IW5ILtByZJULfiLq5pf5igSqFJ60arGgdbPC4htKSYrJ73xJwzaerQ8lK-X1oPN-YYYEbcw1Uz9k=)
36. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFu6XfY5mKVTdZijpeAM9YA7tFAMdTdaqX96YEJYtLyspxquqYiY8ek467ErSX28qt_FyGJwn2pQVBGGu9t5CyG7SRWoRfJaI45V1ABPcpLGb0dbTEgOAgxAOtn8067_nPvVgF_cLiHoWKv4mV5nw==)
37. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFv95e1iUa-qLVcBo2XlLTXz6KPuViYNkBrexBQC8rtMrNmMVFJDmlRWIDP7vQP7Yowk2vzXhbA8JBN5ChedBDYIN51wIgOiFoGHz686L6U_NQZBdn-x06wHXXX2Wvaz11no3F9QJWk_6vV7v-NUrUxZlYSgq5dGuAZJwRZJhYSldUSYyAnMaoJv8aJ1UQmG--5K8kbPHRSXruJTybJsodvTt1cmCQGjb8tax95jI3swo5tCpzZnLoYQA==)
38. [cvxpy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFI5ICZ159C3xYkVcStoOingyBa6wPCKFYpxGRjdwTEqHb9RxFXYwau0i-Lw3HTmm-Wdrq-_i2FphmMSgai0E3qaKY6gnAMVnaVuxQQVO80ZnMRlzphNySRPi_y_pqhzV6CkbeQX2h_0KPSwrLUThU=)
39. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHd0z-PVrvNQznM0GbcnGZS_4w299JIawHzvXu5GBlkxh7620QFXoyhYgasoBrRVrWF824IZBBto9vSOh1oaHL37tx15o-4L1r-hX3tt5f0zfor7zfq_hAUvW70eCj0QTHqelRTZP8jxWODGRAT6wyJtVkx6ZQrGGYbe0h1CSkrI64=)
40. [thegeeksdiary.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEqWNOoVkjClWYzF1jTSQH2mFwIEdj5MAzdFO_mzRNt5f9Bs_wS3x7jmUsvr1_4xYwJAk1Qf4JM241jF9LI5Q9BlQaPO-3uukto5NGCmu7v-gfK2ixmrBOIeyI7BOOeGUR6Nl349QepLaOM01dS0WP9CKgsASNSGNMKS4h2Sx52kiVbqTCk6lPOQA==)
41. [qiita.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9Dl3wd5S9uyk7jwIgegYALJxUm3CXoDse1QDWfltA6axMRVi_lwYhXCGLqJSymEdq-tEJg2U7eSOh9KrgiaWFI2IWVyn_ZlTCPCcTRpSe7O6fJcmnepC2DJWWAhPm7S1vCjcB_0Fe3zkgbaTHGg==)
42. [unipi.gr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFjpA--TwETDrxrT8hk31MU56NkCHmFj1ccaFj1FD541uXpALYsoiIkwiU13dRVT_XAi8_trmzcrtYEOi0eK-ZlNDNfMQFvCmCB0f7ef3wcGE9fV7gFrIfPevn55f73-V9lg5PHciwVspFpfGxfIFDA0VuVO3h-BILbT14Kc75zwJ_nTCUXIYcCy7U-zsANOE-Uuig6GPq4M1owtk8=)
43. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxFBFYXwzjTuCvJFF0YTygigzMTSDGCwABhaZX-nZVTFhmwi0IafdgH3F8TvkSmxhesDIo6Fc7tqP5lOaJwkFryn8-hYurv2MqsRYhEZxjLPYjVLrNeMZb_EiwznakgkoMA1apsmB2jjLxXOW3SLlljGMTINGLN5Bkg--V8i3mPqy6fig=)
44. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwMhCr3RtZ1mwmOlUH5CqVvfiN-veLTEyILWvEXWz5xX1PqflM_RYJvGqg-WMGSnVgod07yzIeng7IkMfa5DSfH0FHc8OGrcvLzZ_MG5krZHfcjTkzvr8IkuLxrASkXlbb7ILNvQ8IWhGneMwwYhKm5NGZlERiR59__mvH1uzmGoBR7SHmktwc)
45. [constructor.university](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZVUt3gARtWii3yKnt4bU712-l7sUFm-78j9zG8DzudmbzV3oYSiIyiUviC4xniENNw8IFDk_lvxUzMz4dgSv90cG-4_MyhiGFaEdsTrUJQrWbZ6_MwtV4GXh84Se4al2zdLgE8bYkPZhU1M8pRmHpfuwyTY8OCBck_OfKrCRaE7H59O2RhzphNRn1TSElAgpZY4uBWPNJyCvpC0Fq9Hu6PoyR0RuhDIEgiQyoWFh9)
46. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHRIw51Pr3HWxZreNXqTmUn51lN0Gvk5UG2DCBcixaRLYiaWbuRiiOHPHjPq26eppK9Avwpus_veUWV6JkAhY6CwMVG2KWwO6fR1ZAXA3Gr62_anuwC4_UiwdZW28cIbAfNqIsWufUlEO3SJTaSEyA1jRqjK1BQ)
47. [cvxgrp.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF0FfIJAn-wQDek9GfO4teyj0tGZriGAk3f8yaCJttkjkYqiR39UFeFOJ_a35wyH9s-SLyLNlirYbSKmTQ7H3H2tGzF_YCU2o4FOuecQi5p4IuDLD3lOFkf0cQHGQVfm1dCS2VwXF-o9H-crvcnExF443yUmL-sK7Wd5_6lXOQCghn1VwvR)
