# Domain Reference for evo-bgp-anomaly-detection

**Responsibility**: Implement DFS-based cycle detection on the routing preference graph to find oscillation cycles, and apply Gao-Rexford valley-free rules to route events to classify route leaks. Produces deterministically ordered cycle lists and standardized leak report objects.

**Key functions to implement**: detect_preference_cycle, check_route_leak, detect_route_leaks

---

## 2. BGP Route Oscillation Detection via Routing Preference Cycles



### 2.1 Formal Definition of BGP Route Oscillation


In inter-domain routing, an AS selects the best path to a destination based on a series of attributes, primarily guided by local policy (e.g., the `LOCAL_PREF` attribute) and other metrics like the Multi-Exit Discriminator (MED) [cite: 1]. A formal definition of a BGP route oscillation caused by conflicting routing preferences involves a state where a set of ASes continuously exchange BGP updates without reaching a deterministic, stable routing equilibrium. 

Mathematically, let the inter-domain topology be a graph \(G = (V, E)\), where \(V\) is the set of Autonomous Systems and \(E\) represents the peering links. Let \(P_v\) denote the policy routing preference of vertex \(v \in V\). An oscillation occurs when there exists a subset of vertices \(V_{cycle} \subseteq V\) such that their combined local preferences form a circular dependency. Specifically, if AS \(A\) prefers routes via AS \(B\), AS \(B\) prefers routes via AS \(C\), and AS \(C\) prefers routes via AS \(A\), the independent decision processes of these ASes will cyclically override each other [cite: 6, 7]. 

When `preferences.json` contains a mapping of routing preferences, it essentially defines a directed "preference graph". If this directed graph contains a cycle, the ASes involved cannot reach a stable consensus. A path withdrawal from one node triggers a preference shift in the next, leading to persistent route oscillation [cite: 1, 3].

### 2.2 Detecting Cycles in a Directed Preference Graph


To detect these oscillations, we must identify cycles in the directed preference graph. In this specific scenario, each AS has a single `prefer_via` neighbor, meaning the out-degree of every vertex in the preference graph is at most 1. Such a graph is known as a **functional graph**.

To detect a cycle in a functional graph, we can utilize a Depth-First Search (DFS) algorithm with path tracking, or Floyd’s Tortoise and Hare algorithm. For the Python implementation, a DFS-based approach that maintains a record of visited nodes and the current traversal stack (the recursion path) is optimal.

### 2.4 Python Implementation of Route Oscillation Detection


Below is the implementation logic encapsulated in a Python method.

```python
def detect_preference_cycle(preferences: dict) -> list:
    """
    Detects a cycle in a BGP routing preference graph.
    
    Args:
        preferences (dict): A dictionary where keys are ASNs and values 
                            are dicts containing 'prefer_via' ASN.
                            Example: {65002: {"prefer_via": 65003}, 65003: {"prefer_via": 65002}}
                            
    Returns:
        list: A deterministically ordered list of ASNs forming the cycle, or empty list if no cycle.
    """
    visited = set()
    
    for start_node in preferences.keys():
        if start_node in visited:
            continue
            
        current_path = []
        current_node = start_node
        
        while current_node is not None:
            if current_node in current_path:
                # Cycle detected
                cycle_start_index = current_path.index(current_node)
                cycle = current_path[cycle_start_index:]
                
                # To ensure deterministic output, we can rotate the cycle so the smallest ASN is first
                min_index = cycle.index(min(cycle))
                deterministic_cycle = cycle[min_index:] + cycle[:min_index]
                return deterministic_cycle
                
            if current_node in visited:
                # Reached a previously explored node that did not lead to a cycle in this path
                break
                
            current_path.append(current_node)
            visited.add(current_node)
            
            # Get next node
            node_data = preferences.get(current_node, {})
            current_node = node_data.get("prefer_via")
            
    return []
```

---

## 3. BGP Valley-Free Routing and Route Leak Detection



### 3.1 The Valley-Free Routing Principle (Gao-Rexford)


The Internet is an agglomeration of ASes bound by commercial relationships. These relationships are predominantly defined as:
1. **Customer-to-Provider (C2P)**: The customer pays the provider for transit to the rest of the Internet.
2. **Provider-to-Customer (P2C)**: The inverse of C2P.
3. **Peer-to-Peer (P2P)**: Two ASes agree to exchange traffic between their respective customers free of charge to save on transit costs.

Lixin Gao and Jennifer Rexford formalized the routing policies derived from these economic realities into the **Gao-Rexford guidelines**, which ensure BGP stability [cite: 2, 5]. The cornerstone of these guidelines is the **valley-free routing principle**. 

The principle states that an AS path is only valid (valley-free) if it follows a specific sequence of edges. An AS will only transit traffic if it receives financial compensation [cite: 8, 9]. Therefore:
* A route learned from a **customer** can be advertised to **anyone** (providers, peers, or other customers).
* A route learned from a **provider** should only be advertised to **customers**. It must *never* be advertised to another provider or a peer.
* A route learned from a **peer** should only be advertised to **customers**. It must *never* be advertised to a provider or another peer.

Visualizing the path hierarchically, traffic can flow "up" (C2P), "across" (P2P, at most once), and "down" (P2C). It cannot go down into a valley and come back up, hence "valley-free" [cite: 5, 9, 10].

### 3.2 Definition and Detection of a Route Leak


According to IETF RFC 7908, a BGP route leak is "the propagation of routing announcement(s) beyond their intended scope" [cite: 4, 11]. In practice, this almost universally manifests as a violation of the valley-free routing principle [cite: 12].

Based on the RFC 7908 classification and valley-free constraints, we can explicitly classify a route advertisement as a leak by examining the `source_type` (where the route came from) and the `destination_type` (where it is being sent). 

The detection logic for an AS forwarding a route is strictly:
* If `source_type` == "provider" and `destination_type` == "peer" \(\rightarrow\) **Route Leak** (Type 3 in RFC 7908) [cite: 4, 13].
* If `source_type` == "provider" and `destination_type` == "provider" \(\rightarrow\) **Route Leak** (Type 1 or Multihomed Customer leak) [cite: 4].
* If `source_type` == "peer" and `destination_type` == "peer" \(\rightarrow\) **Route Leak** (Type 2 Lateral Leak) [cite: 4].
* If `source_type` == "peer" and `destination_type` == "provider" \(\rightarrow\) **Route Leak** (Type 4) [cite: 4].

### 3.3 Python Implementation for Classifying Route Events


Given an array of route events with the structure `{advertiser_asn, source_asn, destination_asn, source_type, destination_type}`, we iterate through and apply the valley-free heuristic.

```python
def check_route_leak(event: dict) -> bool:
    """
    Evaluates a single BGP route advertisement event against valley-free constraints.
    
    Args:
        event (dict): Must contain 'source_type' and 'destination_type'.
                      Valid types are 'provider', 'peer', 'customer'.
                      
    Returns:
        bool: True if the event is a route leak, False otherwise.
    """
    src_type = event.get("source_type")
    dst_type = event.get("destination_type")
    
    # A route learned from a provider or peer cannot be sent to a provider or peer.
    restricted_sources = {"provider", "peer"}
    restricted_destinations = {"provider", "peer"}
    
    if src_type in restricted_sources and dst_type in restricted_destinations:
        return True
        
    return False

def detect_route_leaks(route_events: list) -> list:
    """
    Filters a list of route events to find all route leaks.
    
    Args:
        route_events (list): List of dictionaries representing route advertisements.
        
    Returns:
        list: A list of standardized route leak dictionaries.
    """
    leaks = []
    for event in route_events:
        if check_route_leak(event):
            # Format the output exactly to the standard
            leak_report = {
                "leaker_as": event.get("advertiser_asn"),
                "source_as": event.get("source_asn"),
                "destination_as": event.get("destination_asn"),
                "source_type": event.get("source_type"),
                "destination_type": event.get("destination_type")
            }
            leaks.append(leak_report)
    return leaks
```

### 3.4 Standard Format for Reporting Route Leaks


The industry and analytical standard for reporting these events in a structured JSON schema, as requested, requires exactly five fields [cite: 14]:
* `leaker_as` (int): The ASN that improperly propagated the route.
* `source_as` (int): The ASN from which the leaker learned the route.
* `destination_as` (int): The ASN to which the leaker incorrectly advertised the route.
* `source_type` (str): The relationship type of the source (e.g., "provider").
* `destination_type` (str): The relationship type of the destination (e.g., "peer").

---