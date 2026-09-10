# Domain Reference for evo-market-report

**Responsibility**: Scenario comparison logic, impact analysis computation, JSON report assembly and serialization with correct field names, types, and structure.

**Key functions to implement**: compute_impact_analysis, find_top_lmp_drops, check_congestion_relieved, build_report_json, export_report

---

## Extracting Economic Signals (LMP and MCP)


**Locational Marginal Prices (LMPs):**
The LMP at a node represents the cost to serve one additional MW of load at that specific node [cite: 3, 36]. In linear programming, this is perfectly encapsulated by the dual variable (or shadow price/Lagrange multiplier) of the nodal power balance equality constraint [cite: 10, 36, 37]. 

**Market Clearing Price for Reserves (MCP):**
The reserve MCP is the marginal cost of procuring one additional MW of spinning reserve system-wide. This is the dual variable of the system reserve requirement constraint $\sum R_g \geq Req_{sys}$ [cite: 3, 10].

**Sign Conventions:**
When querying solvers for dual variables, the sign of the dual is heavily dependent on how the constraint is formulated (i.e., $LHS \leq RHS$ versus $LHS \geq RHS$, or standard equality $LHS - RHS = 0$) [cite: 38]. 
- If power balance is written as `Generation - Load - Flow == 0`, adding 1 unit of load shifts the balance, and the solver returns the dual. Depending on the solver (CBC vs GLPK vs OSQP), you may need to multiply the returned dual by $-1$ or $1 / baseMVA$ if equations were in p.u. [cite: 10, 38]. CVXPY standardizes duals well, but PuLP's CBC duals might require negating if formulated as $injections = 0$ [cite: 39].

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