---
name: evo-azure-bgp-oscillation-route-leak
description: Analyzes Azure Virtual WAN multi-hub BGP topologies to detect route oscillation (preference cycles) and valley-free route leak violations (Gao-Rexford model), then evaluates proposed solutions against domain-specific resolution criteria.
---

# BGP Route Oscillation and Route Leak Analyzer for Azure Virtual WAN

Detects BGP route oscillation and valley-free route leak violations in Azure Virtual WAN multi-hub topologies, then evaluates whether proposed solutions resolve each issue.

## Domain Knowledge

### Oscillation Detection (Preference Cycle)
A BGP oscillation occurs when ASes form a mutual routing preference cycle: e.g., AS A prefers routes via AS B, while AS B prefers routes via AS A. The preference graph is a directed functional graph (out-degree ≤ 1 per node). A cycle of any length causes persistent non-convergence. Detection uses DFS-based traversal with path tracking.

**Output**: `oscillation_cycle` and `affected_ases` are deterministically ordered (rotated so the smallest ASN appears first).

### Route Leak Detection (Gao-Rexford Valley-Free Model)
Under the Gao-Rexford valley-free routing principle (RFC 7908):
- **Customer-learned** routes → may export to anyone (customers, peers, providers)
- **Peer-learned** routes → may export to **customers ONLY**
- **Provider-learned** routes → may export to **customers ONLY**

A **route leak** = exporting peer-learned or provider-learned routes to a peer or provider.

### Solution Evaluation Rules

**Fixes OSCILLATION:**
1. Explicitly stop one cycle participant from preferring the other (`stop preferring routes via`)
2. Route preference hierarchy that deprioritizes peer routes (breaks cycle edge)
3. Export policy filtering peer-learned routes between cycle participants
4. Data-plane override: UDR or Routing Intent

**Fixes ROUTE LEAK:**
1. Export policy blocking provider-learned routes to peers (source-side)
2. BGP community no-export on provider routes (source-side)
3. Ingress filtering rejecting routes with provider AS in path (receiver-side)
4. RPKI origin validation (receiver-side)
5. Data-plane override: UDR or Routing Intent

**Fixes BOTH:** UDR and Routing Intent (forwarding layer overrides)

**Fixes NEITHER:**
- Timer tuning (keepalive/holdtime), route dampening, ECMP, max-prefix limits
- Waiting for convergence, restarting BGP, prefix-list filtering
- Generic AS-PATH/MED heuristics, generic route maps without specific config
- Disabling BGP sessions / shutting down peering / removing gateways (connectivity destruction — not acceptable)

**KEY DISTINCTION:** Filtering **provider-learned** routes fixes LEAKS but NOT oscillation. Filtering **peer-learned** routes fixes OSCILLATION but NOT leaks.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-azure-bgp-oscillation-route-leak/scripts')
from utils import generate_report

report = generate_report(data_dir='/app/data/', output_dir='/app/output/')
```

## Scripts
- `scripts/utils.py` — All utility functions for data loading, detection, evaluation, and report generation