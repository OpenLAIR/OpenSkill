# Comprehensive Guide to Solving AC Optimal Power Flow (ACOPF) in Python

**Key Points:**
*   The AC Optimal Power Flow (ACOPF) problem is a fundamental, non-convex, nonlinear programming (NLP) challenge in power systems engineering, aiming to find the most cost-effective generation dispatch while satisfying strict physical and operational grid constraints.
*   **Pyomo** combined with the **IPOPT** solver represents the gold standard for custom, open-source ACOPF modeling in Python, offering unparalleled flexibility compared to pre-packaged tools.
*   Power systems data is frequently exchanged in **PowerModels.jl/Matpower JSON format**, utilizing a per-unit system based on a reference MVA base (typically 100 MVA). 
*   Accurate mathematical formulation of branch flows must account for the standard $\Pi$-section model, inclusive of complex off-nominal transformer tap ratios and phase shifters.
*   For users prioritizing rapid development over deep mathematical customization, **pandapower** provides a robust, higher-level alternative utilizing internal interior-point solvers or PowerModels interfaces.

Solving the AC Optimal Power Flow (ACOPF) problem involves calculating the optimal active and reactive power generation to satisfy demand at minimum cost, subject to the nonlinear physical laws governing alternating current networks (Kirchhoff's laws) and equipment limitations. For a layman, it is akin to finding the cheapest way to pump water through a complex network of pipes without exceeding the pressure limits of any single pipe, while accounting for the fact that water flow dynamics interact in complex, non-linear ways. This report provides an exhaustive, academic-grade guide to building a reusable, large-scale ACOPF framework in Python using Pyomo, parsing network data, formulating exact mathematical constraints, extracting results, and avoiding common domain-specific pitfalls.

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

## Parsing Network Data in JSON Format

Network data provided in `network.json` typically adheres to the data schema popularized by Matpower and PowerModels.jl [cite: 7, 16]. All electrical parameters are scaled to a per-unit (p.u.) system based on a system-wide `baseMVA` to prevent numerical conditioning issues during optimization [cite: 17].

### JSON Structure Breakdown
*   **System Base**: `baseMVA` (float, typically 100.0). All MW/MVAr values are divided by this number [cite: 7].
*   **Buses** (`"bus"` dict): Contains `vmin` and `vmax` (voltage bounds, e.g., 0.95 to 1.05 p.u.), `va` (initial angle), `vm` (initial magnitude), and `bus_type` (1=PQ/Load, 2=PV/Gen, 3=Reference/Slack) [cite: 16, 18, 19].
*   **Generators** (`"gen"` dict): Contains `pmin`, `pmax`, `qmin`, `qmax` bounds. Cost functions are defined via polynomial coefficients, typically under a `cost` array: $[c_2, c_1, c_0]$ representing $c_2 P^2 + c_1 P + c_0$ [cite: 16, 20].
*   **Branches** (`"branch"` dict): Represent lines and transformers. Includes series resistance `br_r`, series reactance `br_x`, total line charging susceptance `b_fr` and `b_to` (often split equally). Transformer parameters include `tap` (magnitude) and `shift` (angle in radians or degrees) [cite: 16]. Thermal limits are denoted by `rate_a` (in MVA).
*   **Loads and Shunts** (`"load"`, `"shunt"` dicts): Loads have active `pd` and reactive `qd` demand. Shunts have conductance `gs` and susceptance `bs` [cite: 16].

### Python Parsing Implementation
To construct the constraints, we must map these parameters into branch $\Pi$-section equivalents. The series admittance is $y_{ij} = \frac{1}{r + jx} = g_{ij} + j b_{ij}$.

```python
import json
import math

def parse_network_json(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    baseMVA = data.get('baseMVA', 100.0)
    buses = data.get('bus', {})
    gens = data.get('gen', {})
    branches = data.get('branch', {})
    loads = data.get('load', {})
    shunts = data.get('shunt', {})
    
    # Process branches into Pi-model parameters
    branch_params = {}
    for br_id, br in branches.items():
        r = br['br_r']
        x = br['br_x']
        # Series admittance y = 1 / (r + jx)
        z_mag2 = r**2 + x**2
        g_ij = r / z_mag2
        b_ij = -x / z_mag2
        
        # Shunt charging (divided between from and to)
        b_fr = br.get('b_fr', 0.0)
        b_to = br.get('b_to', 0.0)
        
        # Transformer tap and phase shift
        # Matpower default tap is 1.0; 0.0 also implies 1.0 natively.
        tap = br.get('tap', 1.0)
        if tap == 0.0: tap = 1.0
        shift = br.get('shift', 0.0) # Assume radians. If degrees, math.radians()
        
        branch_params[br_id] = {
            'f_bus': str(br['f_bus']),
            't_bus': str(br['t_bus']),
            'g': g_ij,
            'b': b_ij,
            'b_fr': b_fr,
            'b_to': b_to,
            'tap': tap,
            'shift': shift,
            'rate_a': br.get('rate_a', None),
            'angmin': br.get('angmin', -math.pi/2),
            'angmax': br.get('angmax', math.pi/2)
        }
        
    return baseMVA, buses, gens, branch_params, loads, shunts
```

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

## Post-Solve Calculations

Once the NLP converges optimally, system analysis variables must be extracted and validated. `pyo.value()` calculates the numeric floating-point value of any variable or expression evaluated at the solved state.

**1. Extracting Branch Flows and Loading Percentages**
Branch loading is evaluated as apparent power flow relative to the branch's MVA thermal limit.
```python
import pandas as pd

branch_data = []
for br in model.BRANCHES:
    limit = branches[br]['rate_a']
    # Evaluate Pyomo expressions
    p_f = pyo.value(model.P_fr[br])
    q_f = pyo.value(model.Q_fr[br])
    p_t = pyo.value(model.P_to[br])
    q_t = pyo.value(model.Q_to[br])
    
    s_fr = math.sqrt(p_f**2 + q_f**2)
    s_to = math.sqrt(p_t**2 + q_t**2)
    
    loading_pct = 0.0
    if limit is not None and limit > 0:
        max_flow = max(s_fr, s_to)
        loading_pct = (max_flow / limit) * 100
        
    branch_data.append({
        'Branch': br,
        'P_fr (MW)': p_f * baseMVA,
        'Q_fr (MVAr)': q_f * baseMVA,
        'Loss_P (MW)': (p_f + p_t) * baseMVA,
        'Loading %': loading_pct
    })

df_branches = pd.DataFrame(branch_data).sort_values(by='Loading %', ascending=False)
print("Most heavily loaded branches:")
print(df_branches.head())
```

**2. Calculating Total System Losses**
Active system losses can be evaluated physically by summing the injected minus extracted branch power, or mathematically by summing total generation minus load [cite: 7, 23].
```python
total_gen_p = sum(pyo.value(model.pg[g]) for g in model.GENS) * baseMVA
total_load_p = sum(l['pd'] for l in loads.values()) * baseMVA
total_loss_p = total_gen_p - total_load_p
print(f"Total Active System Losses: {total_loss_p:.2f} MW")
```

**3. Power Balance Mismatches**
A fundamental post-processing check calculates power mismatches to ensure no numerical leakage exists in the equations. Evaluating `m.bal_P[i].body` and subtracting `m.bal_P[i].upper` should yield a value bounded within the solver's tolerance $\epsilon$.

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
# 1. Install Pyomo and the IDAES environment package
pip install pyomo idaes-pse

# 2. Download the pre-compiled IPOPT and exact solver extensions
idaes get-extensions

# 3. Add the IDAES binary path to the system execution path
export PATH=$PATH:$HOME/.idaes/bin
```
When `idaes get-extensions` is called, it downloads IPOPT statically linked with the HSL linear solvers (`ma27`), negating the need for system-level `apt-get` dependencies or manual compilation, and ensuring robust ACOPF scaling out of the box [cite: 8].

Alternative methods include:
*   `conda install -c conda-forge ipopt`: Very reliable if Miniconda is available in the image [cite: 28].
*   `apt-get install coinor-libipopt-dev ipopt`: Pulls standard repository binaries. Often lacks optimized HSL linear solvers (defaults to MUMPS) which can cause Pyomo ACOPF to stall on networks exceeding ~5,000 buses.

## Alternative Approach using Pandapower

If engineering requirements favor ease of use over deep mathematical customizations, **pandapower** represents an industry-standard alternative capable of running ACOPF out of the box [cite: 12, 14]. Under the hood, pandapower converts its DataFrames to PYPOWER components and solves the problem using PYPOWER's interior-point solver (PIPS) [cite: 5, 13, 14].

**Building and Solving the Network:**
```python
import pandapower as pp

# 1. Initialize empty network
net = pp.create_empty_network()

# 2. Add elements
b1 = pp.create_bus(net, vn_kv=110., min_vm_pu=0.95, max_vm_pu=1.05)
b2 = pp.create_bus(net, vn_kv=110., min_vm_pu=0.95, max_vm_pu=1.05)
pp.create_ext_grid(net, bus=b1, min_p_mw=-1000, max_p_mw=1000, min_q_mvar=-500, max_q_mvar=500)

g1 = pp.create_gen(net, bus=b2, p_mw=50, min_p_mw=10, max_p_mw=100, min_q_mvar=-20, max_q_mvar=20, controllable=True)
pp.create_load(net, bus=b2, p_mw=80, q_mvar=20)
pp.create_line(net, from_bus=b1, to_bus=b2, length_km=10, std_type="149-AL1/24-ST1A", max_i_ka=0.5)

# 3. Define polynomial costs for the generator (c2, c1, c0)
# Note: Pandapower costs evaluate active power (P in MW) natively.
pp.create_polynomial_cost(net, element=g1, element_type="gen", coefficients=[0.1, 20.0, 0.0])

# 4. Run AC Optimal Power Flow
pp.runopp(net, verbose=True)

# 5. Extract Results
print("Generation Dispatch (MW):")
print(net.res_gen)
print("Line Loadings (%):")
print(net.res_line.loading_percent)
```

**Pandapower Capabilities and Limitations:**
Pandapower natively enforces network equations, thermal line limits (in MVA or maximum current `max_i_ka` [cite: 29]), and node voltage bounds [cite: 30]. Furthermore, polynomial cost functions for active power can hold any order, but costs applied to reactive power can strictly only be quadratic, linear, or constant [cite: 30]. While incredibly useful, pandapower does not provide the ease of injecting customized arbitrary algebraic constraints (such as transient stability proxy margins) that Pyomo affords natively [cite: 2, 30].

**Sources:**
1. [jump.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuGpx25_ST8u3KTdxSCspTdLrKE5mFAVxqkRpPVCTQNc1nZzn_4b9BMYd03-0qdpUWlDUpgWB42s0YtENvMn8l2J-Py0XvPKc58lqWlbnkRoaolx2Gi9KXX0Qf1isiLLB1zoq2ffPtME4cdMojMWyFhIN2)
2. [latimerent.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHd6JrJnfXNYR64G2kzF2_fpQ0STa7in0DqGCf5P761cFwWX-icli137OXnpK6OcXgUel2wC599PnrvAercljKSlkCPPn6g7LxfNWEvlh1mGPPtpDhH-Zf5uAAMas2Hv1_t5cTThfjOA-d_GVoRuSRBy3Lv1Y3v_XzdBU7tKOTMgzcoJ4lTjYc4BCnhK8I=)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGsYsYu9feEOcRLDxfOwH5AtFGWU5kyzURoFCmGBgmEsOH1ogV8R11VE8sM2XgC6EigIJVbKQBGnZo5SMhRu5MjBWW5hz-UEMo4vdI7FJg7G2wEyFQKiuA=)
4. [informs.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHBlfuIRgx6kVuJEp0we_Dh93bgTHfIlVnHBiKZ--IUqpPBOOP1GXBnsMYpL0rmm_hNgdkf-QTbw_39C_kqEVsbrEHpDLyiaz-T18YQHxB5QePOQ477KmmYFVDxePWS_0gjZ3TfZdXEkS2klUOE8Iw=)
5. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSUcqlAIDrXm4Ya9KGg9GnpldbGPzmutfPDrMjuthJwJFgPF6B69C2Cq-_b4SmF9scYdDesOkPVsr4NkpkLTixkBZO4joy4Jhii8pKVtAIS9Wj6jIZey1w8ss6_r9DmItbmCxGBJ9v72r4oWArMFfYYxxouZ51yx8BcOEEtgLkhYHL4Y9r3rW-wWNYnn1enH6axBZNrqXSKPtwAg81hnQuvqAc0QZzU1EZN-lqJx0O12E=)
6. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHsq4K6D5JqUZ_JkMCkpFKdT18GidgAlZ4mXVBm6JBp8HsEluX32uV8QseUTZmrZwpCo2t__p71RcQmw_jKdb674zCv7S7Q0uyLM5no2SgpVprKdh2DVTswUJH2TZWe0yTskpglQb2aWxfqIyUzGINCipn0tg2ow6E9Z2-08GnE8RU1OLmEh-s91HiKIzo81Q==)
7. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFLFN3zTc0szDWn4xgWK0N4Vmjkv8qKhzQNVy3X1Yp-8S8biyHUfiJMG_XdKFguUIDf4a9O2vhYsqSPe75lSSoextMxdOK5JYuQ4PxZ0MgHxFcwPW4v7nhCdQ==)
8. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7pV0GLwauFiPff3vkqJ-PN1YKgpkgbkNGst9Wxhj4TXOKuCwIXBD-D1mRCNx1MrwkJcHYp6k3RKsdp0fNMGHfF2NWRywI2FOKqVWZAxFqQA-bDr7ZMnM9vaWNE6whPlZYdpy0X0lnh2KKysyn97ag9kkdCdIEU-d6jpSpiwzAy85FsgG2EU_6)
9. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3f2w9yRr1ldRFEyBzuOJ6NsRP3ovz0-vaUnDlphb-paPbo4Wgyqro5CXQgX04SOjcjA-4Ak3ge4AeK3S_P3rbFIzm3ed1vYlF67IAhaFYFAnmL8RYjku-DGq8zEWQNQ==)
10. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqEcUAKL0w_A2U1ejJHX4b3lVJuvlNayExTJsvtXuBZC7R_NSVMueWWje439hWlSJb62t4LHDnCM_vatKJje8GJESzEIBbQcKr92WhCp-syt6JSUNU99TGeTO3PxkT3FiboDTf_BBx_2TtNQ738BHs5li5L6rAg4TvwBkd-R5sZR45XIfrCqg67kgLYksmfJhHUqGGSAlki_4P47VLB3fVoynqyF_reHoM2w6HfXkvfFRdwfVVS3Q=)
11. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGfQYxFMZyEXZRDQrt6PYocRS56bKAPJPB98eD8ukWLypmUNzPCwmejvYLsLFizvcBFVDyRwHRLYAgW8eysOV1a4CK7lNlJfc6gxQKylI3edJaNDFgO8dntFg==)
12. [uark.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoFS2j0JaOg1cK5KTvaGcLnDWJAOKJ8rPfsOp1XuasBKw_A8Zr585HBYXa46bdpaMpj_gQaQHfcMcuZ8aBJPuxTtkTVJ1sOHnDhwL5ihquNI8AQQM4a4wka-Ogxb1SDD7ISzQJLFtK1iIWA0IKvGybaoWgQ-33jubpYeW3d6BMpf9l3Aul5YROVL2AGahMOqUYB7u2gZyOhIDLSO8cS-yVe8V3Vvm7o8XDiNw=)
13. [epn.edu.ec](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnfHPBxCcqGT3w3XJLvMrLaVi-ubfaBLNcElcqMmqQMKt8cQ5HMFTrk4nZ3sOydJDlVhenDFK7onBA7m8ZrE_6zmScs-ZVrV8uSyipFbU-Kc9GWjCH8qqmRLus8TB2bF7RcnWC7ziwZVRP0t-r8g0SxpClnqb7T_PglA==)
14. [electrisim.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFGV3N0Mw11PMuB1jmagJawJffGZvezrPiVoQQEQ40mNpLyGq88WH7oPc5y7y-pbIpMfO3SbViv1mz6ZlaKMgNAial4-5R0ACp3orAGjHx9kNDBwas8e1HZhAs=)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_Q1Kn4hhqvccUCDFwu3reROchFyV-BnQgWc_RUmhSYJsZIFBAD1lssZnoPxuaJuJ83Gox8fB2hxX3kmdTkhnramj8aX5xlrxDRIKe4zwmrqV4EDPl9KDVv9VpagrabSjuz1rJMP9sRg9oaDj57awNargsdARu)
16. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_721nzYaWTLjbU0J5x5Byi1CcyHBDCGWU1hLulFSO5RGadhMM3ny69e43QZSWSsJ0Ih90TA3MXmqHfFGS7tgbK6R5KTSLDCe0DKOZ9uCdp6Hg6PCw6wz4cjJAdWnBf9u3vQ8rHLWs5SL5OMZNfTbSJLSlwTM=)
17. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwWJ22ueIvRX2-RWzY3W6JSKqm1SQiF8AJWGzIsk9gPEqIGXefI8xtXdEHjMpoznQCOZOVtP2Rmy7JT_0-6lX27gxzi7HvFbLnsXDla-2WWKQ9f2xSxspBzu1obbGUn1eo4jTGTW3zdMCZV2CTWtYUje1GPdc=)
18. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgD7IZRjl66LbTRmB_Vf5UsDdCMOKFdSoe5X3yYrM5tPcdzGnItPov_95DGso1HGEC3ZQH-z_NPvlsIEOSjBGXtlIDv7iKiU5rql6UgfttRbsMWy875yfxvr7LIP4p71jzYzZCCiPa)
19. [matpower.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFd0wOC7tlQ0APUfygECiy498Ns7agvdGJqbHV3w9jmeX6Deb630CMGQ9bV0JXhILBXG1C5DEr9uI85dnC-b7PHHuXWNigQnrV69nOsBuO19srFFuPx-IZf6EjxRukqlpiCEnaqu1v2)
20. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHV4EmVzj4FlfDm39lepyRq_3irIThYnhlBcfo4g8H8YiBeK1c6n6HDeWL2bOyo8Hpi_w31kZKgkZ8eq3nodW5g_C_BX8s77iaNJ5l9HDlT0sVcG3_2AeBax-i3PA9PEveBsyPZnBhAFHYIvI1NiWk=)
21. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHbhS2QleVwAeQ5A3OrBp7dmGs2U72_b0HTJ10XjR85Lqa-qCdoiWqFQINTS-MFdfyPaQdc-FrRAyd-q7PQNAeJJnCiLDcJf7-pQaBoAzBHUBntmBeTzA==)
22. [gpatsakis.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFT1UjBsVJN5cqOgupzbxs3kizsIUfYZAwM1efm-MF2y977Clmb2rRQ7IdgrDkucXaSY5LP7gaAu4Q_jdo0G0IZJvKt5VvRbIYtMMSmOTgoljW5mamdgVioB2heOV3uv0U=)
23. [ieee.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEr2rIZrI4-pH4s7q1b44_E4fiP23kee-1SZkKiNzoE8lIIaaup3lwNoLPhV_9i7tkqcDhqeCp3jxtsYRIxw84yiW-9IX6CEUjuxQGSM3HA_IELCOswwZo1f8K2OJnJ8kv93GXXvjKxUqFwy8kL7bCDfjNy)
24. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPZ6P0cLy39Bor6qlK_JO9MZ6sSbJ4_zvt_pS8ZWKm6RiIrYmyaRke_QdrLQ74QOb62kmSHCuwyH3_QjADxP57lVBXGMINZ80vT3AeibwwGS_jUfE6Ag25iiISLVM=)
25. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbZ9iDNLIXak7p5ie3UimRW6YAH5WIQApxNDCX7rW1D19tkCybtT8GcUpXHHzTAc0UgI_JHIj907bcQmlwnu6o_6k9596LmrKM7KleOTd5Sw0y8g6lDfuxSJClNzh_d8170c7EABGS1X_vG-3k2YXj_Vbqb7FL5Hs_8Q==)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGo0Mqk8EeeMkxePoIVPxlXU6Nyt12L0dXTWP_g2jZOuii8neV6h5P8lZWX1n3aiTIPVor98dzysjQHpOg9yE7EdGyMcz0jIqQpGd2CyLWtAX7_NvJe3zDtWk558gW_47FN8cPIGW6NBAdXts7c7L3y_bVcjb9DFJBuQejXKX5Y7j62b8XlN2_t)
27. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNnrkjMzs_FYvfc2Lq68Bug8RrH1FZVKxoPZYp_PlvmX0j1my-zCPoC74SbgT3J1IKhcTcKuWTo5AYog52XXyRHn0J9jXygCqAsVUJSCiLOz81-rmJNZxqBw==)
28. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGk_U8JD1m_-A0JcNkPtmxnEhX66UtDQhOlo5jWRgyB0OrQ95CE_ha_Dr4PVT7P746nelLTyszZSUMUOyHs6UOcKz8YIhMHOtDAkM4zzLOhxJVT3s58Ptl_BLunsogTZCoStqw_jnQiqNskTT-RcnrNrCdtuRl6BceGUHDvmgjZnHNblKtzm-ac6qC9jhaUBwrmNVE=)
29. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKPw9LWOzLKRtjJ88k-hcLO3_YLhF9pj2HJB2V_vbR83ASynr7buJea7wDpeM4M4QTBQfLapHH1bmN3I4SMt5yXgDtd25ELNzlZORgosNVFw3NgrEm7LvA5MIyKyv49A94)
30. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQELY56jGNdPDauwV1mt5OEY37ziUjDeST236gVo2bYkdZuy_hBQ_lxxhqgV7AI91mkgZJrculo9x1gZr535tZrf_vr5rnc9rFljrz2-62CsZ6ASo0pFS0S89ejQgZpfcHQgd4u7KFlXpevvfyUV_lIM9Tps_Q==)
