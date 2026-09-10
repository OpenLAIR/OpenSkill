# Domain Reference for evo-acopf-report-generator

**Responsibility**: All post-solve extraction, unit conversion (per-unit to physical), feasibility checking, most-loaded-branch identification, summary statistics computation, and JSON report file generation.

**Key functions to implement**: extract_generator_results, extract_bus_results, compute_branch_flows_and_loading, compute_feasibility_check, compute_summary_statistics, generate_report_json

---

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