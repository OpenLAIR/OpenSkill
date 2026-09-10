# Domain Reference for evo-acopf-network-parser

**Responsibility**: All data ingestion, validation, and transformation from network.json into clean dictionaries/structures for the optimization model. No optimization logic.

**Key functions to implement**: parse_network_json, compute_branch_pi_params, aggregate_loads_by_bus, aggregate_shunts_by_bus, map_generators_to_buses, identify_reference_buses, get_branch_bus_mappings

---

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