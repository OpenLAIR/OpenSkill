# Domain Reference for evo-grid-report-generator

**Responsibility**: All post-optimization computations: line flow calculation from PTDF and optimal injections, loading percentage computation (handling rateA=0), operating margin calculation, total cost/load/generation/reserve aggregation, and JSON report serialization.

**Key functions to implement**: compute_line_flows, compute_line_loading_pct, find_top_loaded_lines, compute_operating_margin, compute_total_cost, generate_report_json

---

## 7. Post-Processing and Reporting Computations


Once the solver converges, generating a structured dispatch report requires contextualizing the variable outputs against system limits.

### 7.1. Computing Line Loading Percentages

Transmission loading provides grid operators with awareness of congestion severity. 
The absolute real power flow in MW is extracted using the solved phase angles $\theta_{opt}$:
\[ \text{Flow}_k = \left| \frac{\theta_{opt, f} - \theta_{opt, t}}{x_k} \right| \times \text{baseMVA} \]
If a PTDF formulation was used, the flows are:
\[ \text{Flow}_k = |(\text{PTDF} \cdot P_{net, opt})_k| \times \text{baseMVA} \]

**Handling `rateA == 0`:** 
In MATPOWER, `rateA = 0` means unlimited [cite: 7, 11]. When generating loading percentages, code logic must explicitly bypass these lines to prevent division-by-zero exceptions or false 0% metrics.
```python
loading_pct = []
for k in range(n_branch):
    if rateA[k] > 0:
        pct = (abs(flow_mw[k]) / rateA[k]) * 100
    else:
        pct = None # or 0.0, denoting unconstrained
    loading_pct.append(pct)
```

### 7.2. Operating Margin Calculation

The *Remaining Operating Margin* dictates how much generation could theoretically be summoned beyond the already committed energy and reserved thresholds. It provides a measure of overall system resilience.
It is calculated strictly over generators that are currently online (`status > 0`) [cite: 1, 6].
\[ \text{Operating Margin} = \sum_{g \in \text{online}} (P_{max, g} - P_{opt, g} - R_{opt, g}) \]
This metric represents purely uncommitted, physically connected rotational mass capacity that is completely unburdened by market clearing assignments.