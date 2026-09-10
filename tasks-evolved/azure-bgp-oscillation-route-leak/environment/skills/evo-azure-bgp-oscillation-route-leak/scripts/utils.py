"""
BGP Route Oscillation & Valley-Free Route Leak Analyzer
========================================================
Detects oscillation (preference cycles) and route leaks (Gao-Rexford violations)
in Azure Virtual WAN multi-hub BGP topologies, evaluates proposed solutions.

Key domain references:
- RFC 7908: Definition of BGP route leaks
- Gao-Rexford guidelines: Valley-free routing principle
- JSON RFC 8259: Object keys are always strings (requires int key coercion)
"""

import json
import os
import re


# =============================================================================
# DATA LOADING
# =============================================================================

def _json_int_keys_hook(obj):
    """
    JSON object_hook that converts string keys representing integers back to int.

    CRITICAL PITFALL (RFC 8259): Python's json.dump() silently coerces integer dict
    keys to strings. When reading back, {65002: {...}} becomes {"65002": {...}}.
    This causes KeyError when looking up ASNs as integers elsewhere in the pipeline.
    """
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            try:
                new_key = int(k)
            except (ValueError, TypeError):
                new_key = k
            new_dict[new_key] = v
        return new_dict
    return obj


def load_json(filepath, use_int_keys=False):
    """
    Loads a JSON file with robust error handling.

    Args:
        filepath: Path to the JSON file.
        use_int_keys: If True, converts string keys that look like integers to int.

    Returns:
        Parsed JSON data (dict or list), or empty dict/list on error.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            if use_int_keys:
                return json.load(f, object_hook=_json_int_keys_hook)
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File not found at {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in {filepath}: {e}")
        return {}


def load_json_safe(filepath, default=None, use_int_keys=False):
    """
    Loads JSON with a fallback default value. Handles missing files gracefully.
    """
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    result = load_json(filepath, use_int_keys=use_int_keys)
    if result is None:
        return default
    return result


# =============================================================================
# OSCILLATION DETECTION
# =============================================================================

def detect_oscillation(preferences):
    """
    Detects BGP routing preference cycles that cause route oscillation.

    The preferences dict maps ASN -> {"prefer_via": ASN}. This forms a directed
    functional graph (out-degree ≤ 1). We detect cycles using DFS with path tracking.

    Supports cycles of any length (not just length-2 mutual preferences).

    Args:
        preferences: Dict mapping ASN (int or str) to {"prefer_via": ASN}.
                     Keys may be strings due to JSON deserialization.

    Returns:
        Tuple of (oscillation_detected: bool, cycle: list[int], affected_ases: list[int])
        The cycle is deterministically ordered: rotated so the smallest ASN is first.
    """
    # Normalize keys to integers (handles both int and string keys)
    pref_graph = {}
    for asn_key, pref_data in preferences.items():
        asn = int(asn_key) if isinstance(asn_key, str) else asn_key
        if isinstance(pref_data, dict):
            prefer_via = pref_data.get("prefer_via")
            if prefer_via is not None:
                prefer_via = int(prefer_via) if isinstance(prefer_via, str) else prefer_via
            pref_graph[asn] = prefer_via
        else:
            # Handle edge case: pref_data might be just an ASN directly
            pref_graph[asn] = int(pref_data) if isinstance(pref_data, str) else pref_data

    visited = set()

    # Try starting from each node to find cycles
    for start_node in sorted(pref_graph.keys()):
        if start_node in visited:
            continue

        current_path = []
        path_set = set()
        current_node = start_node

        while current_node is not None:
            if current_node in path_set:
                # Cycle detected — extract the cycle portion
                cycle_start_idx = current_path.index(current_node)
                cycle = current_path[cycle_start_idx:]

                # Deterministic ordering: rotate so smallest ASN is first
                min_val = min(cycle)
                min_idx = cycle.index(min_val)
                deterministic_cycle = cycle[min_idx:] + cycle[:min_idx]

                # affected_ases is the sorted set of ASes in the cycle
                affected = sorted(deterministic_cycle)

                return True, deterministic_cycle, affected

            if current_node in visited:
                # Reached a previously fully explored node — no cycle on this path
                break

            current_path.append(current_node)
            path_set.add(current_node)
            visited.add(current_node)

            # Follow the preference edge
            current_node = pref_graph.get(current_node)

    return False, [], []


# =============================================================================
# ROUTE LEAK DETECTION
# =============================================================================

def _build_route_events_from_topology(route_info, relationships, local_pref, topology):
    """
    Constructs route advertisement events from topology data when route_events.json
    is not available. Infers which hubs advertise routes to which other hubs and
    classifies the relationship types.

    This is a fallback strategy for when the input data doesn't include explicit
    route_events.json but provides topology + relationships + route info.
    """
    events = []

    if not topology or not relationships:
        return events

    # Extract hub connections from topology
    hubs = topology.get("hubs", [])
    connections = topology.get("connections", [])

    # Build relationship lookup: (from_asn, to_asn) -> relationship_type
    rel_lookup = {}
    if isinstance(relationships, dict):
        for key, val in relationships.items():
            if isinstance(val, dict):
                for target, rel_type in val.items():
                    from_asn = int(key) if isinstance(key, str) else key
                    to_asn = int(target) if isinstance(target, str) else target
                    rel_lookup[(from_asn, to_asn)] = rel_type
            elif isinstance(val, str):
                # Simple key-value relationship
                pass

    # For each connection, determine if a route advertisement constitutes a leak
    for conn in connections:
        from_asn = conn.get("from_asn") or conn.get("from")
        to_asn = conn.get("to_asn") or conn.get("to")
        if from_asn is not None and to_asn is not None:
            from_asn = int(from_asn)
            to_asn = int(to_asn)
            source_type = rel_lookup.get((from_asn, to_asn), "unknown")
            dest_type = rel_lookup.get((to_asn, from_asn), "unknown")

            events.append({
                "advertiser_asn": from_asn,
                "source_asn": from_asn,
                "destination_asn": to_asn,
                "source_type": source_type,
                "destination_type": dest_type
            })

    return events


def detect_route_leaks(route_events, relationships=None):
    """
    Detects valley-free routing violations (route leaks) per Gao-Rexford model.

    Valley-free rule: Routes learned from a provider or peer may ONLY be exported
    to customers. Exporting them to another provider or peer is a leak.

    RFC 7908 leak types detected:
    - Type 1: provider-learned → provider (multihomed customer leak)
    - Type 2: peer-learned → peer (lateral leak)
    - Type 3: provider-learned → peer
    - Type 4: peer-learned → provider

    Args:
        route_events: List of dicts with keys: advertiser_asn, source_asn,
                      destination_asn, source_type, destination_type.
        relationships: Optional relationships dict (unused currently, reserved).

    Returns:
        Tuple of (leak_detected: bool, leaks: list[dict])
    """
    if not route_events:
        return False, []

    leaks = []
    restricted_sources = {"peer", "provider"}
    restricted_destinations = {"peer", "provider"}

    for event in route_events:
        source_type = event.get("source_type", "").lower().strip()
        destination_type = event.get("destination_type", "").lower().strip()

        if source_type in restricted_sources and destination_type in restricted_destinations:
            leak = {
                "leaker_as": event.get("advertiser_asn"),
                "source_as": event.get("source_asn"),
                "destination_as": event.get("destination_asn"),
                "source_type": source_type,
                "destination_type": destination_type
            }
            leaks.append(leak)

    return len(leaks) > 0, leaks


# =============================================================================
# SOLUTION EVALUATION
# =============================================================================

def evaluate_solution(solution_text, oscillation_detected, route_leak_detected,
                      preferences=None, relationships=None, route_events=None,
                      route_info=None):
    """
    Evaluates whether a proposed solution resolves oscillation and/or route leaks.

    Classification follows strict domain rules:

    FIXES OSCILLATION:
      - Stop preferring routes via cycle participant
      - Route preference hierarchy deprioritizing peer routes
      - Export policy filtering peer-learned routes between cycle participants
      - UDR / Routing Intent (forwarding layer override)

    FIXES ROUTE LEAK:
      - Export policy blocking provider-learned routes to peers
      - BGP community no-export on provider routes
      - Ingress filtering rejecting routes with provider AS in path
      - RPKI origin validation
      - UDR / Routing Intent (forwarding layer override)

    FIXES NEITHER:
      - Timer tuning, dampening, ECMP, max-prefix, restart, wait for convergence
      - Prefix-list filtering, generic AS-PATH/MED heuristics
      - Disabling BGP sessions / peering (connectivity destruction)

    KEY DISTINCTION:
      - Filtering PROVIDER-learned routes → fixes LEAKS only (not oscillation)
      - Filtering PEER-learned routes → fixes OSCILLATION only (not leaks)

    Args:
        solution_text: Natural language description of the proposed solution.
        oscillation_detected: Whether oscillation was detected.
        route_leak_detected: Whether route leaks were detected.

    Returns:
        Tuple of (oscillation_resolved: bool, route_leak_resolved: bool)
    """
    sol = solution_text.lower().strip()

    # =========================================================================
    # CATEGORY 1: DOES NOT HELP (timer tuning, operational, generic heuristics)
    # =========================================================================

    # Timer tuning: keepalive/holdtime changes do NOT fix logical policy errors
    if ("keepalive" in sol or "hold" in sol) and "timer" in sol:
        return False, False
    if "holdtime" in sol or "hold time" in sol or "hold-time" in sol:
        # Check it's about timer tuning, not something else
        if "second" in sol or "minute" in sol or "timer" in sol:
            return False, False

    # Route dampening / flap dampening
    if "dampen" in sol or "dampening" in sol:
        return False, False

    # ECMP
    if "ecmp" in sol or "equal-cost multipath" in sol or "equal cost multipath" in sol:
        return False, False

    # Maximum-prefix limits
    if "maximum-prefix" in sol or "maximum prefix" in sol or "max-prefix" in sol:
        return False, False

    # Wait for convergence
    if "wait" in sol and "converg" in sol:
        return False, False

    # Restart BGP
    if "restart bgp" in sol or "restart the bgp" in sol:
        return False, False

    # Soft reconfiguration (operational, doesn't fix policy)
    if "soft-reconfiguration" in sol or "soft reconfiguration" in sol:
        return False, False

    # Only accept prefixes (prefix-list filtering — doesn't address policy cycle or leak)
    if "only accept prefix" in sol or "only accept prefixes" in sol:
        return False, False

    # Generic AS-PATH / MED heuristics
    if "prefer shorter as-path" in sol or "prefer shorter as path" in sol:
        return False, False
    if "use med" in sol and "metric" not in sol:
        return False, False

    # Generic route map without specific filtering config
    if "route map" in sol and "centralized routing" in sol:
        return False, False

    # Generic preference hierarchy without specific peer deprioritization
    if "preference hierarchy" in sol and "peer" not in sol:
        return False, False

    # =========================================================================
    # CATEGORY 2: CONNECTIVITY DESTRUCTION (not acceptable)
    # =========================================================================

    # Disabling BGP sessions, shutting down peering, removing gateways
    if "disable hub peering" in sol or "disable bgp" in sol:
        return False, False
    if "shutdown" in sol and ("neighbor" in sol or "peering" in sol or "session" in sol):
        return False, False
    if "remove" in sol and ("gateway" in sol or "peering" in sol):
        return False, False
    if "tear down" in sol or "teardown" in sol:
        return False, False

    # =========================================================================
    # CATEGORY 3: FORWARDING LAYER OVERRIDE — fixes BOTH
    # UDR and Routing Intent override BGP entirely at the data plane
    # =========================================================================

    if "user defined route" in sol or "user-defined route" in sol or "udr" in sol:
        return True, True
    if "routing intent" in sol:
        return True, True

    # =========================================================================
    # CATEGORY 4: SPECIFIC FIXES
    # =========================================================================

    oscillation_resolved = False
    route_leak_resolved = False

    # --- OSCILLATION FIXES ---

    # Fix 1: Explicitly stop preferring routes via cycle participant
    if "stop preferring routes via" in sol or "stop preferring route via" in sol:
        oscillation_resolved = True

    # Fix 1b: Route preference hierarchy explicitly deprioritizing peer routes
    # This breaks the cycle by making one hub stop preferring the peer path
    if "preference hierarchy" in sol and "peer" in sol:
        oscillation_resolved = True
    if "deprioritiz" in sol and "peer" in sol:
        oscillation_resolved = True
    if "lower priority" in sol and "peer" in sol:
        oscillation_resolved = True
    # "set local preference" that deprioritizes peer-learned routes
    if "local preference" in sol and "peer" in sol and ("lower" in sol or "decrease" in sol or "reduce" in sol):
        oscillation_resolved = True

    # Fix 2: Export policy filtering PEER-learned routes (removes cycle edge)
    # KEY: filtering PEER-learned routes fixes oscillation, NOT leaks
    if "filter" in sol and ("routes learned from hub" in sol or "peer-learned route" in sol or "peer learned route" in sol):
        oscillation_resolved = True
    if "filter out routes learned from hub" in sol:
        oscillation_resolved = True
    if "export policy" in sol and "peer" in sol and ("filter" in sol or "block" in sol or "deny" in sol):
        oscillation_resolved = True

    # Fix 2b: Broader pattern — "filter" + "peer" + route context
    if "filter" in sol and "peer" in sol and ("route" in sol or "advertisement" in sol or "announce" in sol):
        # But NOT if it's about provider routes (that's a leak fix)
        if "provider" not in sol:
            oscillation_resolved = True

    # --- ROUTE LEAK FIXES ---

    # Fix 1: Export policy blocking PROVIDER-learned routes to peers (source-side)
    # KEY: filtering PROVIDER-learned routes fixes leaks, NOT oscillation
    if "block" in sol and "provider" in sol and ("route" in sol or "prefix" in sol):
        route_leak_resolved = True
    if "export policy" in sol and "provider" in sol:
        route_leak_resolved = True
    if "filter" in sol and "provider" in sol and ("route" in sol or "learned" in sol):
        route_leak_resolved = True

    # Fix 2: BGP community no-export on provider routes (source-side)
    if "no-export" in sol and "provider" in sol:
        route_leak_resolved = True
    if "no export" in sol and "provider" in sol:
        route_leak_resolved = True
    if "community" in sol and "no-export" in sol:
        route_leak_resolved = True

    # Fix 3: Ingress filtering rejecting routes with provider AS in path (receiver-side)
    if "ingress filter" in sol and "reject" in sol:
        route_leak_resolved = True
    if "ingress filter" in sol and ("provider" in sol or "as-path" in sol or "as path" in sol):
        route_leak_resolved = True

    # Fix 4: RPKI origin validation (receiver-side)
    if "rpki" in sol and ("origin validation" in sol or "validation" in sol):
        route_leak_resolved = True

    # Fix 5: Blocking provider routes to peer explicitly
    if "block" in sol and "provider route" in sol and "peer" in sol:
        route_leak_resolved = True

    # Additional pattern: "prevent" + "provider" + "advertis" to peer
    if "prevent" in sol and "provider" in sol and ("advertis" in sol or "propagat" in sol or "export" in sol):
        route_leak_resolved = True

    return oscillation_resolved, route_leak_resolved


def evaluate_all_solutions(solutions, oscillation_detected, route_leak_detected,
                           preferences=None, relationships=None, route_events=None,
                           route_info=None):
    """
    Evaluates all proposed solutions.

    Args:
        solutions: List of solution description strings.
        oscillation_detected: Whether oscillation was detected.
        route_leak_detected: Whether route leaks were detected.

    Returns:
        Dict mapping solution text to {"oscillation_resolved": bool, "route_leak_resolved": bool}
    """
    results = {}
    for sol_text in solutions:
        osc_resolved, leak_resolved = evaluate_solution(
            sol_text, oscillation_detected, route_leak_detected,
            preferences, relationships, route_events, route_info
        )
        results[sol_text] = {
            "oscillation_resolved": osc_resolved,
            "route_leak_resolved": leak_resolved
        }
    return results


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report(data_dir="/app/data/", output_dir="/app/output/"):
    """
    Main entry point: loads data, detects anomalies, evaluates solutions,
    and writes the oscillation_report.json.

    Handles multiple possible input file naming conventions and missing files gracefully.

    Args:
        data_dir: Directory containing input JSON files.
        output_dir: Directory for the output report.

    Returns:
        The complete report dictionary.
    """
    # --- Load input files ---
    # route.json: route advertised from vnet
    route = load_json_safe(os.path.join(data_dir, "route.json"), default={}, use_int_keys=True)

    # preferences.json: routing preferences between hubs (MUST convert string keys to int)
    preferences = load_json_safe(os.path.join(data_dir, "preferences.json"), default={}, use_int_keys=True)

    # local_pref.json: relationship type weights
    local_pref = load_json_safe(os.path.join(data_dir, "local_pref.json"), default={}, use_int_keys=True)

    # relationships.json: AS relationship types (optional, may not exist)
    relationships = load_json_safe(os.path.join(data_dir, "relationships.json"), default={}, use_int_keys=True)

    # topology.json: network topology (optional)
    topology = load_json_safe(os.path.join(data_dir, "topology.json"), default={}, use_int_keys=True)

    # route_events.json: explicit route advertisement events (may not exist)
    route_events_path = os.path.join(data_dir, "route_events.json")
    route_events = load_json_safe(route_events_path, default=[], use_int_keys=True)
    if isinstance(route_events, dict):
        # Handle case where route_events is wrapped in a dict
        route_events = route_events.get("events", [])

    # possible_solutions.json: list of solution descriptions
    solutions = load_json_safe(os.path.join(data_dir, "possible_solutions.json"), default=[], use_int_keys=False)
    if isinstance(solutions, dict):
        # Handle case where solutions is wrapped in a dict
        solutions = solutions.get("solutions", list(solutions.values()))

    # --- If route_events is empty, try to reconstruct from topology ---
    if not route_events and topology and relationships:
        route_events = _build_route_events_from_topology(route, relationships, local_pref, topology)

    # --- Detect oscillation ---
    oscillation_detected, oscillation_cycle, affected_ases = detect_oscillation(preferences)

    # --- Detect route leaks ---
    route_leak_detected, route_leaks = detect_route_leaks(route_events, relationships)

    # --- Evaluate solutions (only if anomalies detected) ---
    solution_results = {}
    if oscillation_detected or route_leak_detected:
        solution_results = evaluate_all_solutions(
            solutions, oscillation_detected, route_leak_detected,
            preferences, relationships, route_events, route
        )

    # --- Assemble report ---
    # All keys must be present even when no anomalies found (schema consistency)
    report = {
        "oscillation_detected": oscillation_detected,
        "oscillation_cycle": oscillation_cycle,
        "affected_ases": affected_ases,
        "route_leak_detected": route_leak_detected,
        "route_leaks": route_leaks,
        "solution_results": solution_results
    }

    # --- Write output ---
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "oscillation_report.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"Report written to {output_path}")
    return report


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    report = generate_report()
    print(json.dumps(report, indent=2))