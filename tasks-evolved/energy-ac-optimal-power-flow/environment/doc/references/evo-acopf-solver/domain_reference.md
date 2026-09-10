# Domain Reference for evo-acopf-solver

**Responsibility**: Constructing the Pyomo ConcreteModel with all ACOPF variables, constraints, expressions, and objective; configuring and invoking IPOPT; returning the solved model and solver results. No data parsing or report formatting.

**Key functions to implement**: install_solver, build_acopf_model, solve_acopf, build_and_solve_acopf

---

## Python Libraries for ACOPF Formulations


The ecosystem for power system optimization in Python has evolved significantly. While specialized tools exist, solving the ACOPF from scratch requires an Algebraic Modeling Language (AML) coupled with a robust continuous nonlinear programming (NLP) solver. 

**Pyomo for Optimization Modeling**
Pyomo is a highly capable Python-based AML that allows users to construct structured optimization problems using exact algebraic expressions [cite: 1]. Unlike matrix-based environments (such as MATLAB), Pyomo models are defined object-oriented, utilizing Sets, Parameters, Variables, and Constraints [cite: 1]. For ACOPF, Pyomo excels because it natively handles the complex nonlinear equations (sines, cosines, and quadratic terms) required for polar coordinate power flow formulations [cite: 2, 3]. Pyomo does not inherently understand complex numbers; therefore, the user must decompose all complex power and voltage equations into their explicit real and imaginary components [cite: 4].

**IPOPT Solver Interface**
IPOPT (Interior Point OPTimizer) is the industry-standard open-source solver for large-scale, non-convex NLPs [cite: 4, 5]. It utilizes a primal-dual interior-point algorithm with a filter line-search method. Pyomo interfaces with IPOPT through the Advanced Modeling for Power Systems (AMPL) solver interface, invoked via `pyo.SolverFactory('ipopt')` [cite: 6]. 
Crucial solver options for ACOPF convergence include:
*   `tol`: Convergence tolerance (typically $10^{-4}$ or $10^{-6}$ for ACOPF) [cite: 7].
*   `max_iter`: Maximum iterations (usually 3000+ for large grids).
*   `linear_solver`: The underlying linear algebra suite. While `mumps` is the default open-source option, compiling IPOPT with the HSL library (`ma27` or `ma57`) significantly improves performance and numeric stability on large networks [cite: 1, 8].

**Alternatives: PowerModels.jl and Pandapower**
While Pyomo is excellent for custom constraints, Julia's **PowerModels.jl** is widely considered the state-of-the-art for benchmarked OPF formulations (including SDP and SOCP relaxations) [cite: 9, 10, 11]. It can be called from Python via `juliacall`, though this introduces inter-language overhead.
Alternatively, **pandapower** is a Python-native power system analysis tool built heavily on PYPOWER (a Python port of Matpower) [cite: 12, 13]. Pandapower provides a simplified API for grid modeling and includes an `runopp()` function to execute ACOPF utilizing an internal interior-point method or external interfaces to PowerModels.jl [cite: 14, 15].

## Mathematical Formulation in Polar Coordinates


Pyomo requires analytical algebraic constraints. The polar coordinate formulation leverages voltage magnitudes ($v$) and voltage phase angles ($\theta$) [cite: 4].

### Branch Power Flow Expressions

Following the standard Matpower asymmetric $\Pi$-section model, an ideal transformer with a complex tap ratio $T = \tau e^{j \theta_{shift}}$ is placed at the "from" end of the branch [cite: 18, 19, 21]. 
Let $i$ be the from-bus and $j$ be the to-bus. The complex power injected into the branch from bus $i$ is $S_{ij} = P_{ij} + jQ_{ij}$, and from bus $j$ is $S_{ji} = P_{ji} + jQ_{ji}$.
Using algebraic expansion of $S = V I^*$, we obtain the explicit real and imaginary power flows [cite: 22]:

**Active Power Flow ($P$):**
$$P_{ij} = \frac{v_i^2}{\tau^2} g_{ij} - \frac{v_i v_j}{\tau} \left[ g_{ij} \cos(\theta_i - \theta_j - \theta_{shift}) + b_{ij} \sin(\theta_i - \theta_j - \theta_{shift}) \right]$$
$$P_{ji} = v_j^2 g_{ij} - \frac{v_i v_j}{\tau} \left[ g_{ij} \cos(\theta_j - \theta_i + \theta_{shift}) + b_{ij} \sin(\theta_j - \theta_i + \theta_{shift}) \right]$$

**Reactive Power Flow ($Q$):**
$$Q_{ij} = -\frac{v_i^2}{\tau^2} (b_{ij} + b_{fr}) - \frac{v_i v_j}{\tau} \left[ g_{ij} \sin(\theta_i - \theta_j - \theta_{shift}) - b_{ij} \cos(\theta_i - \theta_j - \theta_{shift}) \right]$$
$$Q_{ji} = -v_j^2 (b_{ij} + b_{to}) - \frac{v_i v_j}{\tau} \left[ g_{ij} \sin(\theta_j - \theta_i + \theta_{shift}) - b_{ij} \cos(\theta_j - \theta_i + \theta_{shift}) \right]$$

### Nodal Power Balance Constraints

At each bus $i$, the sum of generation minus the sum of demand minus the power absorbed by local shunts must equal the sum of power flowing out of the bus into connected branches [cite: 23].

$$ \sum_{k \in \mathcal{G}_i} P_{g,k} - \sum_{k \in \mathcal{L}_i} P_{d,k} - v_i^2 G_{s,i} = \sum_{(i,j) \in \mathcal{E}} P_{ij} + \sum_{(j,i) \in \mathcal{E}} P_{ji} $$
$$ \sum_{k \in \mathcal{G}_i} Q_{g,k} - \sum_{k \in \mathcal{L}_i} Q_{d,k} + v_i^2 B_{s,i} = \sum_{(i,j) \in \mathcal{E}} Q_{ij} + \sum_{(j,i) \in \mathcal{E}} Q_{ji} $$

### Thermal and Angle Constraints

Thermal limits constrain the apparent power (MVA) across a branch [cite: 4]. To avoid the non-differentiability of the square root at zero, the constraint is formulated as a squared limit:
$$ P_{ij}^2 + Q_{ij}^2 \le (S_{ij}^{max})^2 \quad \text{and} \quad P_{ji}^2 + Q_{ji}^2 \le (S_{ji}^{max})^2 $$
Voltage angle differences across branches must also be bounded to ensure steady-state stability:
$$ \theta_{min} \le \theta_i - \theta_j \le \theta_{max} $$
Furthermore, the reference bus $ref$ requires $\theta_{ref} = 0$.

### Objective Function

The goal is to minimize total generation cost. If cost coefficients $[c_2, c_1, c_0]$ are given for a polynomial function based on per-unit active power $P_g$, the objective is [cite: 16]:
$$ \min \sum_{k \in \mathcal{G}} \left( c_2 P_{g,k}^2 + c_1 P_{g,k} + c_0 \right) $$

## Working Pyomo ACOPF Code Example


The following script is a complete, runnable Pyomo implementation encapsulating the mathematics defined above. It assumes data structures parsed by the earlier JSON utility.

```python
import pyomo.environ as pyo
import math

def build_and_solve_acopf(baseMVA, buses, gens, branches, loads, shunts):
    model = pyo.ConcreteModel()
    
    # ---- SETS ----
    model.BUSES = pyo.Set(initialize=buses.keys())
    model.GENS = pyo.Set(initialize=gens.keys())
    model.BRANCHES = pyo.Set(initialize=branches.keys())
    
    # Mapping sets for buses
    gen_at_bus = {b: [] for b in buses}
    for g_id, g in gens.items():
        gen_at_bus[str(g['gen_bus'])].append(g_id)
        
    load_at_bus = {b: {'pd': 0.0, 'qd': 0.0} for b in buses}
    for l_id, l in loads.items():
        bus_id = str(l['load_bus'])
        load_at_bus[bus_id]['pd'] += l['pd']
        load_at_bus[bus_id]['qd'] += l['qd']
        
    shunt_at_bus = {b: {'gs': 0.0, 'bs': 0.0} for b in buses}
    for s_id, s in shunts.items():
        bus_id = str(s['shunt_bus'])
        shunt_at_bus[bus_id]['gs'] += s['gs']
        shunt_at_bus[bus_id]['bs'] += s['bs']
        
    branch_from = {b: [] for b in buses}
    branch_to = {b: [] for b in buses}
    for br_id, br in branches.items():
        branch_from[br['f_bus']].append(br_id)
        branch_to[br['t_bus']].append(br_id)

    # ---- VARIABLES ----
    # Voltage Magnitude and Angle
    def vm_bounds(m, i):
        return (buses[i]['vmin'], buses[i]['vmax'])
    model.vm = pyo.Var(model.BUSES, bounds=vm_bounds, initialize=1.0)
    
    model.va = pyo.Var(model.BUSES, initialize=0.0)
    
    # Active and Reactive Generation
    def pg_bounds(m, g):
        return (gens[g]['pmin'], gens[g]['pmax'])
    def qg_bounds(m, g):
        return (gens[g]['qmin'], gens[g]['qmax'])
    
    model.pg = pyo.Var(model.GENS, bounds=pg_bounds, initialize=0.0)
    model.qg = pyo.Var(model.GENS, bounds=qg_bounds, initialize=0.0)
    
    # ---- EXPRESSIONS FOR BRANCH FLOWS ----
    def p_from_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, tap, shift = b['g'], b['b'], b['tap'], b['shift']
        return (m.vm[f]**2 / tap**2) * g - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.cos(m.va[f] - m.va[t] - shift) + b_ij * pyo.sin(m.va[f] - m.va[t] - shift))
    model.P_fr = pyo.Expression(model.BRANCHES, rule=p_from_rule)

    def p_to_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, tap, shift = b['g'], b['b'], b['tap'], b['shift']
        return m.vm[t]**2 * g - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.cos(m.va[t] - m.va[f] + shift) + b_ij * pyo.sin(m.va[t] - m.va[f] + shift))
    model.P_to = pyo.Expression(model.BRANCHES, rule=p_to_rule)

    def q_from_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, b_fr, tap, shift = b['g'], b['b'], b['b_fr'], b['tap'], b['shift']
        return -(m.vm[f]**2 / tap**2) * (b_ij + b_fr) - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.sin(m.va[f] - m.va[t] - shift) - b_ij * pyo.cos(m.va[f] - m.va[t] - shift))
    model.Q_fr = pyo.Expression(model.BRANCHES, rule=q_from_rule)

    def q_to_rule(m, br):
        b = branches[br]
        f, t = b['f_bus'], b['t_bus']
        g, b_ij, b_to, tap, shift = b['g'], b['b'], b['b_to'], b['tap'], b['shift']
        return -m.vm[t]**2 * (b_ij + b_to) - (m.vm[f] * m.vm[t] / tap) * \
               (g * pyo.sin(m.va[t] - m.va[f] + shift) - b_ij * pyo.cos(m.va[t] - m.va[f] + shift))
    model.Q_to = pyo.Expression(model.BRANCHES, rule=q_to_rule)

    # ---- CONSTRAINTS ----
    # 1. Power Balance
    def p_balance_rule(m, i):
        p_gen = sum(m.pg[g] for g in gen_at_bus[i])
        p_load = load_at_bus[i]['pd']
        p_shunt = m.vm[i]**2 * shunt_at_bus[i]['gs']
        p_flow = sum(m.P_fr[br] for br in branch_from[i]) + sum(m.P_to[br] for br in branch_to[i])
        return p_gen - p_load - p_shunt == p_flow
    model.bal_P = pyo.Constraint(model.BUSES, rule=p_balance_rule)

    def q_balance_rule(m, i):
        q_gen = sum(m.qg[g] for g in gen_at_bus[i])
        q_load = load_at_bus[i]['qd']
        q_shunt = -m.vm[i]**2 * shunt_at_bus[i]['bs'] # Note the minus sign for capacitive injection
        q_flow = sum(m.Q_fr[br] for br in branch_from[i]) + sum(m.Q_to[br] for br in branch_to[i])
        return q_gen - q_load - q_shunt == q_flow
    model.bal_Q = pyo.Constraint(model.BUSES, rule=q_balance_rule)

    # 2. Thermal Limits
    def thermal_fr_rule(m, br):
        limit = branches[br]['rate_a']
        if limit is None or limit == 0.0:
            return pyo.Constraint.Skip
        return m.P_fr[br]**2 + m.Q_fr[br]**2 <= limit**2
    model.limit_fr = pyo.Constraint(model.BRANCHES, rule=thermal_fr_rule)

    def thermal_to_rule(m, br):
        limit = branches[br]['rate_a']
        if limit is None or limit == 0.0:
            return pyo.Constraint.Skip
        return m.P_to[br]**2 + m.Q_to[br]**2 <= limit**2
    model.limit_to = pyo.Constraint(model.BRANCHES, rule=thermal_to_rule)

    # 3. Angle Limits
    def ang_diff_rule(m, br):
        f, t = branches[br]['f_bus'], branches[br]['t_bus']
        return pyo.inequality(branches[br]['angmin'], m.va[f] - m.va[t], branches[br]['angmax'])
    model.ang_diff = pyo.Constraint(model.BRANCHES, rule=ang_diff_rule)

    # 4. Reference Bus
    def ref_bus_rule(m, i):
        if buses[i]['bus_type'] == 3:
            return m.va[i] == 0.0
        return pyo.Constraint.Skip
    model.ref_bus = pyo.Constraint(model.BUSES, rule=ref_bus_rule)

    # ---- OBJECTIVE ----
    def obj_rule(m):
        cost = 0.0
        for g_id, g in gens.items():
            c = g['cost'] # assuming [c2, c1, c0] structure
            if len(c) == 3:
                cost += c*(m.pg[g_id]**2) + c[cite: 8]*m.pg[g_id] + c[cite: 24]
            elif len(c) == 2:
                cost += c*m.pg[g_id] + c[cite: 8]
        return cost
    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    # ---- SOLVE ----
    solver = pyo.SolverFactory('ipopt')
    solver.options['tol'] = 1e-6
    solver.options['max_iter'] = 3000
    # Optional: solver.options['linear_solver'] = 'ma27' # Recommended if HSL is installed
    
    results = solver.solve(model, tee=True)
    return model, results
```

## Common Pitfalls in ACOPF Modeling


**1. The Per-Unit System and Base MVA Conversions**
The most frequent error in Python ACOPF stems from failing to strictly separate the `baseMVA` scaling. In `network.json`, limits (`pmin`, `rate_a`) and system injections (`pd`) are often already in per-unit [cite: 7]. Ensure that optimization variable bounds match the provided units. Cost results, dispatch tracking, and loss reporting must be multiplied by `baseMVA` at the reporting stage [cite: 15, 17].

**2. Generator Cost Coefficients Base**
In JSON exports from PowerModels.jl, the mathematical format of polynomial costs must be carefully scrutinized [cite: 7, 16]. A cost coefficient $c_2$ designed for a MW-based solver behaves differently in a per-unit solver. Often, PowerModels scales the cost polynomial so it can be evaluated directly on the per-unit variable. For instance, if the original objective was $C(P) = a P^2 + b P + c$ where $P$ is in MW, the per-unit cost parameters supplied in the array will represent $a \cdot (\text{baseMVA})^2$, $b \cdot (\text{baseMVA})$, and $c$ [cite: 17, 20]. Verify whether `ncost` is 2 (linear) or 3 (quadratic) to index the coefficients dynamically [cite: 25].

**3. Transformer Taps and Asymmetry**
As shown in the Matpower $\Pi$-section derivation [cite: 19, 21], the ideal transformer is strictly located at the "from" end of the line. The complex tap $T_{ij} = \tau e^{j \theta_{shift}}$ is not symmetric. A failure to position $\tau^2$ and the $\theta_{shift}$ terms accurately in the $P_{ij}$ and $P_{ji}$ equations guarantees infeasible power flows [cite: 4, 18].

**4. Handling Unconstrained Branches**
Branches missing `rate_a` or having a `0.0` value must be explicitly ignored when building Pyomo constraints. Adding an inequality constraint `X <= 0.0` or `X <= None` will crash the solver or erroneously block all power flow [cite: 26]. 

**5. Initialization and Convergence Problems**
ACOPF is a highly non-convex problem. A "flat start" ($v=1.0, \theta=0.0$) may occasionally fail for stressed networks due to saddle points or initial matrix singularity [cite: 5, 27]. If IPOPT diverges ("Restoration Failed"), passing a converged DC-OPF solution as an initial warm start for Pyomo variables often solves the problem.

## Installing IPOPT on Ubuntu without Root Compilation


Setting up Pyomo alongside IPOPT on a bare Ubuntu 24.04 environment (such as a Docker container) historically posed challenges due to Fortran compiler dependencies. The most reliable method today utilizes the prebuilt binaries distributed by the IDAES project [cite: 8, 24].

In a Docker environment with only `pip` available, execute:
```bash