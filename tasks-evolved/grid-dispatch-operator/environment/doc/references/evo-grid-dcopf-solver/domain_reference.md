# Domain Reference for evo-grid-dcopf-solver

**Responsibility**: Mathematical formulation of the optimization problem (objective, constraints), solver invocation, and extraction of optimal decision variables (Pg, Rg, flows). Determines reserve requirement using standard capacity coupling (largest online generator).

**Key functions to implement**: formulate_dcopf_with_reserves, solve_dcopf_linprog, solve_dcopf_cvxpy, compute_reserve_requirement, linearize_quadratic_cost

---

## 4. DC-OPF with Spinning Reserves as a Linear Program


To build a reliable market dispatch, we embed reserve requirements directly into the OPF. This ensures the system does not schedule a cheap generator at 100% capacity for energy, leaving it unable to contribute to the spinning reserve pool [cite: 4, 22].

### 4.1. Decision Variables

For each generator $g \in \{0 \dots G-1\}$:
*   $P_{g}$: Active energy dispatch (MW).
*   $R_{g}$: Spinning reserve allocation (MW).
*   $\theta_{i}$: Voltage angle at each bus $i \in \{0 \dots N-1\}$.

*(Note: Depending on the formulation—B-theta vs. PTDF—$\theta$ variables may be eliminated, relying entirely on injection variables $P_g$ [cite: 2, 19]. Both will be discussed).*

### 4.2. Constraints Formulation

The complete Linear Program/Quadratic Program setup involves:

**1. Generation Limits:**
Generators cannot produce below their technical minimum or exceed their maximum. Crucially, the *sum* of energy dispatch and reserve allocation cannot exceed the unit's maximum capacity [cite: 4, 19].
\[ P_{min, g} \le P_{g} \le P_{max, g} \quad \forall g \]
\[ R_{g} \ge 0 \quad \forall g \]
\[ P_{g} + R_{g} \le P_{max, g} \quad \forall g \]

**2. System Power Balance (Nodal):**
At every bus $i$, generation minus demand equals the net power injected into the grid [cite: 2, 18].
\[ \sum_{g \in \text{Bus}_i} P_g - P_{d,i} = \sum_{j} B_{ij} \theta_j \quad \forall i \]

**3. Transmission Limits (Branch Flow):**
Flows must respect the thermal limits defined by `rateA`. If `rateA == 0`, the line is unconstrained (bounds are set to $-\infty, \infty$) [cite: 11, 12].
\[ -rateA_k \le \frac{\theta_{f, k} - \theta_{t, k}}{x_k} \le rateA_k \quad \forall k \]

**4. Spinning Reserve Requirement:**
The entire grid (or a specific area) must carry enough reserve to cover contingencies. The "standard capacity coupling" rule generally mandates that the total spinning reserve must equal or exceed the capacity of the largest single online generator (N-1 criterion) or a set percentage (e.g., 5% of total system load) [cite: 3, 4].
\[ \sum_{g} R_g \ge R_{req} \]

### 4.3. Objective Function

The objective is to minimize total generation cost and, optionally, reserve provision costs [cite: 4].
\[ \min \sum_{g} \left( c_{2,g} P_g^2 + c_{1,g} P_g + c_{0,g} \right) + \sum_g \left( c_{res, g} R_g \right) \]
If reserve costs are not explicitly defined in standard MATPOWER arrays, they can be treated as zero or a nominal small penalty to prioritize deploying reserves on the most efficient units [cite: 4, 23].

## 6. Python Implementation Solvers


To build reusable utility functions, developers must choose an appropriate solver. Standard libraries dictate two distinct paths depending on whether the generator cost model is linear (Model 1) or quadratic (Model 2).

### 6.1. Linear Programming with `scipy.optimize.linprog`


If generators possess piecewise linear costs (Model 1) or if quadratic curves are linearized into multiple segments, `scipy.optimize.linprog` provides a native, dependency-free optimization engine. 

**Signature:** `scipy.optimize.linprog(c, A_ub, b_ub, A_eq, b_eq, bounds, method='highs')`

To use this for reserve co-optimization, the variable vector $X$ is stacked as $[P_{g}, R_{g}, \theta]$. 

**Objective Vector $c$:**
For a linear cost $c_1 P_g + c_0$, the vector $c$ simply maps $c_1$ to the $P_g$ indices. The constant $c_0$ is ignored by the solver and added manually to the final cost. The $R_g$ and $\theta$ indices in $c$ are set to 0.

**Constraint Matrices:**
1.  **$A_{eq}, b_{eq}$:** The nodal balance equations $P_{net} = B_{bus} \theta$ map into $A_{eq}$ by placing the generation-bus mapping matrix on the $P_g$ columns, and $-B_{bus}$ on the $\theta$ columns.
2.  **$A_{ub}, b_{ub}$:** 
    *   Transmission limits: $B_{branch} \theta \le rateA$ and $-B_{branch} \theta \le rateA$.
    *   Reserve constraints: $P_g + R_g \le P_{max}$ is encoded by placing 1s in the corresponding columns for $P_g$ and $R_g$.
    *   System Reserve: $\sum -R_g \le -R_{req}$ (SciPy requires $\le$, so multiply by $-1$).

### 6.2. Handling Quadratic Costs in SciPy

If `gencost` defines polynomial Model 2 ($c_2 P^2 + c_1 P + c_0$), `linprog` cannot solve it natively. `scipy.optimize.minimize` can handle non-linear objectives via the `SLSQP` or `trust-constr` methods, but it scales extremely poorly for systems with $>100$ buses due to dense Jacobian approximations.

**Piecewise Linear Approximation (PWL):**
The preferred pure-SciPy strategy is PWL approximation [cite: 26]. A quadratic curve is sampled at $k$ break-points. Instead of variables $P_g$, you introduce auxiliary variables for the power dispatched in each segment, bounded by the width of the segment, with linear costs corresponding to the slope of that segment [cite: 6].

### 6.3. The Optimal Approach: CVXPY Implementation


For authentic, large-scale implementation of MATPOWER data containing quadratic costs, **CVXPY** is universally recommended in power systems research [cite: 22, 27]. It parses convex optimization problems cleanly and interfaces with high-performance solvers like OSQP or Clarabel (both installed by default) [cite: 27, 28].

**CVXPY Installation:**
```bash
pip install cvxpy
```
*Note: See Section 9 regarding Ubuntu 24.04 pip warnings.*

**CVXPY Working Example for DCOPF with Reserves:**
```python
import numpy as np
import cvxpy as cp

def solve_dcopf_reserves(P_min, P_max, Pd, Bbus, PTDF, rateA, c2, c1, c0, R_req):
    n_gen = len(P_max)
    n_bus = len(Pd)
    n_branch = len(rateA)
    
    # Decision Variables
    Pg = cp.Variable(n_gen)
    Rg = cp.Variable(n_gen)
    
    # Objective: Minimize generation cost
    cost = cp.sum(cp.multiply(c2, cp.square(Pg)) + cp.multiply(c1, Pg) + c0)
    objective = cp.Minimize(cost)
    
    # Constraints list
    constraints = []
    
    # 1. Generator Limits & Reserve Headroom
    constraints += [Pg >= P_min]
    constraints += [Pg <= P_max]
    constraints += [Rg >= 0]
    constraints += [Pg + Rg <= P_max]
    
    # 2. Total Reserve Requirement
    constraints += [cp.sum(Rg) >= R_req]
    
    # 3. Power Balance (Assumes Gen 0 is at Bus 0 for simplicity in this snippet)
    # Real implementation requires a mapping matrix Gen_to_Bus
    Gen_to_Bus = np.eye(n_bus) # Placeholder
    P_net = Gen_to_Bus @ Pg - Pd
    constraints += [cp.sum(P_net) == 0] # Total Gen = Total Load
    
    # 4. Transmission Limits using PTDF
    flows = PTDF @ P_net
    for k in range(n_branch):
        if rateA[k] > 0: # Ignore unlimited branches
            constraints += [flows[k] <= rateA[k]]
            constraints += [flows[k] >= -rateA[k]]
            
    # Solve
    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.OSQP)
    
    return Pg.value, Rg.value, prob.value
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

## 9. Environment Setup in Ubuntu 24.04


A severe roadblock for modern Python developers on Ubuntu 24.04 (and Debian 12) is the integration of **PEP 668**, which marks the system Python environment as an "externally-managed-environment" [cite: 30, 31].