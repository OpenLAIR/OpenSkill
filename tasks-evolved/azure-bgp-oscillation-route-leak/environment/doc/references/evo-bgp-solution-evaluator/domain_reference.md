# Domain Reference for evo-bgp-solution-evaluator

**Responsibility**: Use regex pattern matching to classify each proposed solution as resolving oscillation (breaks preference cycle or disables peering link), resolving route leaks (enforces export/ingress filtering, community tagging, routing intent, or disables peering), or neither. Assemble the complete oscillation_report.json output with all required fields.

**Key functions to implement**: evaluate_solution, evaluate_all_solutions, generate_oscillation_report, save_report

---

## 4. Solution Evaluation Logic


Once oscillations and leaks are identified, automated systems often receive a list of remediation proposals (solutions) described in natural language text. The goal is to programmatically evaluate whether each solution effectively resolves the identified oscillation or route leak.

### 4.1 Resolution Effectiveness Criteria


**Oscillation Resolution**: 
An oscillation is resolved *only* if the underlying routing preference cycle is broken [cite: 14, 15]. Solutions that achieve this include:
* **Modifying Preferences**: Changing the `prefer_via` or local preference metric explicitly (e.g., "stop preferring routes via").
* **Link Disablement/Teardown**: Completely removing the peering session that forms the cycle path (e.g., "disable hub peering", "shutdown bgp neighbor").

**Route Leak Resolution**: 
A route leak is resolved if the configuration prevents the offending AS from exporting the restricted routes (learned from providers/peers) to other restricted destinations [cite: 12, 13, 14]. Effective solutions include:
* **Export Policies**: "Configure export policy... to block announcing provider routes".
* **Ingress Filtering**: "Enable ingress filtering... to reject routes with provider ASN in AS_PATH".
* **Community-based Filtering**: "Enforce no-export of provider routes... by bgp community".
* **Architectural Shifts**: "Enable Virtual WAN hub routing intent" which overrides raw BGP propagation with centralized, safe routing abstractions.
* **Link Disablement**: "disable hub peering", completely neutralizing the avenue of the leak.

**Purely Operational Configurations**:
Solutions that adjust timers (Keepalive, Hold-time), flap dampening, soft-reconfiguration, Maximum-Prefix limits, or restart BGP do **not** fix the logical errors in policy [cite: 14, 16]. Therefore, they resolve neither oscillations nor leaks.

### 4.2 Python Pattern Matching Implementation


To classify these solutions programmatically, we employ regular expressions (`re` module) to search for specific key phrases indicating the mechanical intent of the text.

```python
import re

def evaluate_solutions(solutions: list) -> dict:
    """
    Evaluates a list of solution text descriptions to determine if they resolve 
    BGP route oscillations and/or route leaks.
    
    Args:
        solutions (list): List of string descriptions of proposed solutions.
        
    Returns:
        dict: Mapping of solution string to their resolution capabilities.
    """
    results = {}
    
    # Oscillation resolving keywords: modifying preference, disabling peers
    oscillation_patterns = [
        r"stop preferring",
        r"update routing preference",
        r"disable hub peering",
        r"shutdown (bgp)? neighbor",
        r"break.*cycle"
    ]
    
    # Route leak resolving keywords: strict filtering, disable peers, architectural enforcement
    leak_patterns = [
        r"export policy.*block",
        r"ingress filtering.*reject",
        r"no-export",
        r"disable hub peering",
        r"routing intent",
        r"route policy.*filter"
    ]
    
    osc_regex = re.compile('|'.join(oscillation_patterns), re.IGNORECASE)
    leak_regex = re.compile('|'.join(leak_patterns), re.IGNORECASE)
    
    for sol in solutions:
        osc_resolved = bool(osc_regex.search(sol))
        leak_resolved = bool(leak_regex.search(sol))
        
        results[sol] = {
            "oscillation_resolved": osc_resolved,
            "route_leak_resolved": leak_resolved
        }
        
    return results
```

---

## 6. Output Format Specification


The utility module must synthesize the detections and evaluations into a strictly defined JSON payload. The resulting `/app/output/oscillation_report.json` must adhere to the following schema [cite: 14]:

* `oscillation_detected` (bool): `true` if a cycle is found, `false` otherwise.
* `oscillation_cycle` (list of integers): The deterministically ordered list of ASNs in the cycle. Empty list `[]` if false.
* `affected_ases` (list of integers): The identical list/set as the cycle.
* `route_leak_detected` (bool): `true` if at least one route leak is detected.
* `route_leaks` (list of objects): A list containing the standard route leak report dictionaries. Empty list `[]` if false.
* `solution_results` (dict): A dictionary mapping the string text of the solution to an object containing boolean values for `oscillation_resolved` and `route_leak_resolved`.

Example schema expected:
```json
{
  "oscillation_detected": true,
  "oscillation_cycle": ,
  "affected_ases": ,
  "route_leak_detected": true,
  "route_leaks": [
    {
      "leaker_as": 65002,
      "source_as": 65001,
      "destination_as": 65003,
      "source_type": "provider",
      "destination_type": "peer"
    }
  ],
  "solution_results": {
    "Configure export policy on vhubvnet1 to block announcing provider routes to peer": {
      "oscillation_resolved": false,
      "route_leak_resolved": true
    },
    "disable hub peering between vhubvnet1 and vhubvnet2": {
      "oscillation_resolved": true,
      "route_leak_resolved": true
    }
  }
}
```

---

## 7. Common Pitfalls and Edge Cases to Avoid


1. **Integer vs String ASN Keys**: As extensively detailed in Section 5.2, failing to cast string JSON keys back to integer ASNs is the single most common cause of runtime errors in BGP processing logic [cite: 17, 18, 19, 20]. The `object_hook` approach provides an elegant, scalable safeguard.
2. **Deterministic Ordering of Cycle Output**: If a cycle is `A -> B -> C -> A`, depending on which node the loop starts, the output might be `[B, C, A]` or `[C, A, B]`. For programmatic evaluation (and unit testing), the module must guarantee deterministic output. This is accomplished by finding the minimum ASN in the cycle and shifting the array so it begins with that minimum value (as shown in the provided `detect_preference_cycle` function).
3. **Empty Data Structures**: When no oscillations or leaks are found, the output JSON must strictly output `false` for the detection booleans, and empty lists `[]` for the arrays. It should not omit the keys from the JSON object. Omitting keys breaks downstream consumers expecting a consistent schema.
4. **Regex Sensitivity**: When using natural language processing to evaluate solutions, ensure all regex matching uses `re.IGNORECASE`. Operator logs and configuration descriptions frequently fluctuate in capitalization (e.g., "BGP" vs "bgp").

---