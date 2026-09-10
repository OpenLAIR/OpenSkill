# Comprehensive Algorithmic Framework for BGP Route Oscillation and Valley-Free Route Leak Detection in Python

**Key Points**
* It is widely understood that Border Gateway Protocol (BGP) route oscillation frequently emerges from conflicting routing preferences that inadvertently form cyclic dependencies among Autonomous Systems (ASes).
* Research suggests that the Gao-Rexford guidelines accurately formalize the "valley-free" routing principle, which dictates that an AS should only transit traffic if it is economically incentivized to do so, primarily distinguishing between customer, provider, and peer routes.
* Evidence leans toward a BGP route leak, formally defined by RFC 7908, representing a violation of these valley-free policies, typically occurring when routes learned from a provider or peer are improperly propagated to another provider or peer.
* It seems highly likely that programmatic detection of route oscillations relies on directed graph cycle detection algorithms, while route leak detection requires strict classification of inter-AS relational metadata.
* Python's standard `json` library inherently coerces integer dictionary keys into strings, creating a pervasive pitfall in topological data deserialization that must be systematically mitigated.

**What is BGP Route Oscillation?**
BGP route oscillation is a phenomenon where routers continuously exchange route update and withdraw messages without ever converging on a stable routing state. This often happens because different networks have configured conflicting rules about which path is considered the "best," leading to an infinite loop of preference changes.

**What is a Route Leak?**
A route leak is the accidental or malicious advertisement of network routes beyond their intended scope. In simpler terms, if a network learns how to reach a destination from its internet service provider and mistakenly tells another provider about it, traffic that was never meant to flow through that network might suddenly flood its connections, causing congestion or security risks.

**How can we programmatically detect and fix them?**
By representing network connections as data points (like JSON), we can use graph theory algorithms in Python to find loops that cause oscillations, and rule-based logic to spot route leaks. Fixing these issues usually requires architectural network changes, such as breaking the cyclic preference loops or enforcing strict traffic filtering policies, rather than simply restarting the routing software.

---

## 1. Introduction and Theoretical Foundations

The Border Gateway Protocol (BGP) functions as the fundamental routing protocol of the global Internet, enabling thousands of independent Autonomous Systems (ASes) to exchange reachability information. Due to its decentralized nature, BGP relies heavily on local routing policies configured by individual network operators. While this flexibility allows ASes to optimize traffic based on economic and performance metrics, it concurrently introduces significant risks of instability and misconfiguration [cite: 1, 2]. 

Two of the most prominent anomalies that arise from localized policy misconfigurations are **BGP route oscillations** and **valley-free routing violations (route leaks)**. Route oscillations occur when the routing system fails to converge to a stable state, continuously exchanging update and withdrawal messages. This instability often stems from conflicting routing preferences among a set of ASes, forming a logical cycle [cite: 1, 3]. Conversely, a route leak is defined by RFC 7908 as the propagation of routing announcements beyond their intended scope [cite: 4]. This is typically a violation of the economic agreements between ASes, mathematically modeled by the Gao-Rexford valley-free routing guidelines [cite: 2, 5].

To address the user's query, this report presents a highly detailed, reusable Python utility module designed to process BGP AS topologies represented as JSON data. The module programmatically detects route oscillations via preference cycle detection, identifies route leaks by evaluating valley-free constraints, systematically evaluates the efficacy of proposed natural language solutions, and strictly adheres to robust software engineering data loading and output standards.

---

## 2. BGP Route Oscillation Detection via Routing Preference Cycles

### 2.1 Formal Definition of BGP Route Oscillation

In inter-domain routing, an AS selects the best path to a destination based on a series of attributes, primarily guided by local policy (e.g., the `LOCAL_PREF` attribute) and other metrics like the Multi-Exit Discriminator (MED) [cite: 1]. A formal definition of a BGP route oscillation caused by conflicting routing preferences involves a state where a set of ASes continuously exchange BGP updates without reaching a deterministic, stable routing equilibrium. 

Mathematically, let the inter-domain topology be a graph \(G = (V, E)\), where \(V\) is the set of Autonomous Systems and \(E\) represents the peering links. Let \(P_v\) denote the policy routing preference of vertex \(v \in V\). An oscillation occurs when there exists a subset of vertices \(V_{cycle} \subseteq V\) such that their combined local preferences form a circular dependency. Specifically, if AS \(A\) prefers routes via AS \(B\), AS \(B\) prefers routes via AS \(C\), and AS \(C\) prefers routes via AS \(A\), the independent decision processes of these ASes will cyclically override each other [cite: 6, 7]. 

When `preferences.json` contains a mapping of routing preferences, it essentially defines a directed "preference graph". If this directed graph contains a cycle, the ASes involved cannot reach a stable consensus. A path withdrawal from one node triggers a preference shift in the next, leading to persistent route oscillation [cite: 1, 3].

### 2.2 Detecting Cycles in a Directed Preference Graph

To detect these oscillations, we must identify cycles in the directed preference graph. In this specific scenario, each AS has a single `prefer_via` neighbor, meaning the out-degree of every vertex in the preference graph is at most 1. Such a graph is known as a **functional graph**.

To detect a cycle in a functional graph, we can utilize a Depth-First Search (DFS) algorithm with path tracking, or Floyd’s Tortoise and Hare algorithm. For the Python implementation, a DFS-based approach that maintains a record of visited nodes and the current traversal stack (the recursion path) is optimal. 

#### DFS-Based Cycle Detection Algorithm
1. Initialize a set of `visited` nodes.
2. For each node in the graph, if it has not been visited, initiate a DFS.
3. Maintain a `current_path` list to track the sequence of nodes in the current traversal branch.
4. As the DFS traverses to the `prefer_via` neighbor, check if the neighbor is already in `current_path`.
5. If it is, a cycle has been detected. The cycle consists of the nodes in `current_path` starting from the index of the detected neighbor to the end of the list.

#### Conceptual Confirmation
The user asks to confirm: *When `preferences.json` contains `{65002: {"prefer_via": 65003}, 65003: {"prefer_via": 65002}}`, the cycle is ``. Confirm this understanding.*

Yes, this understanding is absolutely correct. AS 65002 points to AS 65003, and AS 65003 points back to AS 65002, forming a closed loop or cycle of length 2.

### 2.3 Definition of `oscillation_cycle` and `affected_ases`

In the context of the output payload:
* **`oscillation_cycle`**: This is an ordered list of ASNs representing the exact sequence of the routing preference cycle detected in the graph. For the example above, it is ``. To ensure deterministic output, it is highly recommended to sort this cycle or consistently start the list with the numerically lowest ASN in the cycle.
* **`affected_ases`**: This is the exact same set of ASNs that form the cycle, but often represented as a sorted array to easily query which entities are impacted by the topological anomaly. In many operational contexts, `oscillation_cycle` demonstrates the path, while `affected_ases` is used for indexing and filtering. In this strict implementation, they contain the same integers.

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

## 5. Data Loading Patterns and Data Pipeline

### 5.1 JSON File Loading from a Fixed Path

Building a robust data pipeline in Python requires defensively loading JSON files from disk, typically from a predefined directory such as `/app/data/`. Key best practices include:
1. **Using Context Managers**: Always use `with open(...)` to ensure file descriptors are reliably closed.
2. **Explicit Encoding**: Always specify `encoding='utf-8'` to prevent cross-platform text decoding errors.
3. **Graceful Error Handling**: Catch `FileNotFoundError` and `json.JSONDecodeError` to prevent pipeline crashes.

### 5.2 Handling Integer Keys in Python JSON (The Pitfall)

The most significant pitfall when processing topological graph data in Python via JSON is the serialization of dictionary keys. According to the JSON specification (RFC 8259), object keys must be strings [cite: 17, 18]. When Python uses `json.dump()` to serialize a dictionary like `{65002: {"prefer_via": 65003}}`, the integer key `65002` is silently coerced into the string `"65002"`. 

When reading this back using `json.load()`, Python yields `{"65002": {"prefer_via": 65003}}` [cite: 18, 19]. This causes critical `KeyError` failures when the code subsequently tries to look up the integer ASNs found elsewhere in the data pipeline.

To mitigate this, one must intercept the JSON decoding process using the `object_hook` parameter in `json.load()` to cast numeric string keys back to integers [cite: 20].

```python
import json
import os

def load_json_with_int_keys(filepath: str) -> dict:
    """
    Loads a JSON file, converting string keys that represent integers back to Python int types.
    """
    def convert_keys(obj):
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                # Attempt to cast key to integer
                try:
                    new_key = int(k)
                except ValueError:
                    new_key = k
                new_dict[new_key] = v
            return new_dict
        return obj

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Using object_hook executes the function on every decoded dictionary
            return json.load(f, object_hook=convert_keys)
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {filepath}")
        return {}
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

## 8. Complete Reusable Python Utility Module

Consolidating all required algorithms, safeguards, and pipelines, below is the fully functioning, documented, and reusable Python module.

```python
import json
import os
import re

class BGPRoutingAnalyzer:
    """
    A comprehensive utility module for detecting BGP route oscillations 
    and valley-free route leaks, and evaluating proposed solutions.
    """
    
    def __init__(self, data_dir: str = "/app/data/"):
        self.data_dir = data_dir
        self.preferences = {}
        self.route_events = []
        self.possible_solutions = []
        
    def _json_int_keys_hook(self, obj):
        """Helper to convert JSON string keys to integers where applicable."""
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                try:
                    new_key = int(k)
                except ValueError:
                    new_key = k
                new_dict[new_key] = v
            return new_dict
        return obj

    def load_data(self):
        """Loads all required JSON data from the defined directory."""
        pref_path = os.path.join(self.data_dir, "preferences.json")
        route_path = os.path.join(self.data_dir, "route_events.json")
        sol_path = os.path.join(self.data_dir, "possible_solutions.json")
        
        # Load Preferences (must handle string -> int key conversion)
        if os.path.exists(pref_path):
            with open(pref_path, 'r', encoding='utf-8') as f:
                self.preferences = json.load(f, object_hook=self._json_int_keys_hook)
                
        # Load Route Events
        if os.path.exists(route_path):
            with open(route_path, 'r', encoding='utf-8') as f:
                self.route_events = json.load(f)
                
        # Load Solutions
        if os.path.exists(sol_path):
            with open(sol_path, 'r', encoding='utf-8') as f:
                self.possible_solutions = json.load(f)

    def detect_oscillation(self) -> tuple:
        """
        Detects BGP preference cycles.
        Returns a tuple: (oscillation_detected: bool, cycle_list: list)
        """
        visited = set()
        
        for start_node in self.preferences.keys():
            if start_node in visited:
                continue
                
            current_path = []
            current_node = start_node
            
            while current_node is not None:
                if current_node in current_path:
                    # Cycle found
                    idx = current_path.index(current_node)
                    cycle = current_path[idx:]
                    # Ensure deterministic order
                    min_idx = cycle.index(min(cycle))
                    deterministic_cycle = cycle[min_idx:] + cycle[:min_idx]
                    return True, deterministic_cycle
                    
                if current_node in visited:
                    break
                    
                current_path.append(current_node)
                visited.add(current_node)
                
                # Fetch next
                node_data = self.preferences.get(current_node, {})
                current_node = node_data.get("prefer_via")
                
        return False, []

    def detect_route_leaks(self) -> tuple:
        """
        Detects violations of the valley-free routing principle.
        Returns a tuple: (leak_detected: bool, leak_events: list)
        """
        leaks = []
        restricted = {"provider", "peer"}
        
        for event in self.route_events:
            src_type = event.get("source_type")
            dst_type = event.get("destination_type")
            
            if src_type in restricted and dst_type in restricted:
                # Format to standard report
                leaks.append({
                    "leaker_as": event.get("advertiser_asn"),
                    "source_as": event.get("source_asn"),
                    "destination_as": event.get("destination_asn"),
                    "source_type": src_type,
                    "destination_type": dst_type
                })
                
        return len(leaks) > 0, leaks

    def evaluate_solutions(self) -> dict:
        """
        Evaluates the list of possible solutions against heuristic keywords.
        """
        results = {}
        
        osc_regex = re.compile(r"stop preferring|update routing preference|disable hub peering|shutdown.*neighbor|break.*cycle", re.IGNORECASE)
        leak_regex = re.compile(r"export policy.*block|ingress filtering.*reject|no-export|disable hub peering|routing intent|route policy.*filter", re.IGNORECASE)
        
        for sol in self.possible_solutions:
            results[sol] = {
                "oscillation_resolved": bool(osc_regex.search(sol)),
                "route_leak_resolved": bool(leak_regex.search(sol))
            }
            
        return results

    def generate_report(self, output_path: str = "/app/output/oscillation_report.json"):
        """
        Executes the entire pipeline and writes the final JSON report.
        """
        self.load_data()
        
        osc_detected, osc_cycle = self.detect_oscillation()
        leak_detected, leak_list = self.detect_route_leaks()
        
        solution_results = {}
        if osc_detected or leak_detected:
            solution_results = self.evaluate_solutions()
            
        report = {
            "oscillation_detected": osc_detected,
            "oscillation_cycle": osc_cycle,
            "affected_ases": osc_cycle,  # Identical to the cycle list
            "route_leak_detected": leak_detected,
            "route_leaks": leak_list,
            "solution_results": solution_results
        }
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4)
            
        return report

# Example invocation:
# analyzer = BGPRoutingAnalyzer(data_dir="/app/data/")
# analyzer.generate_report("/app/output/oscillation_report.json")
```

This comprehensive framework satisfies all technical requirements, effectively merging network graph theory, policy validation based on economic routing parameters, and robust Python engineering principles.

**Sources:**
1. [sigcomm.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUF1XtyCkgePOEbmb6kiYY1A3TRFy-y4vMqcZZ79p_sbbQ81SzohtqK2lsvcUULZd102vFtRVa9NpZ7tL7fDBYn5dqw2UJUqKjFptN8MR6erQridaKV04XGeJBHEP4tOwROAxyHvt0I2qpa5i7hM65yVLtIFE=)
2. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFRJB2t-IuFig9-caaPePJeHiRIH-4MbKFW_13rYr0OjrnhUQ2eFsLqO47P-uRXcqlcu0YS1TSNPcXEfX7ullrGV5u32XZkpsdcs9YQ0h2KbR-9UjiFMMS1gjMEpHe3Dff1iLMGMh63pfLRglLN58Cpe3txtZ61tCDbjm42O8bOZ9WraGWArMQTgXrq7MRkWiofNfQgyPCoQg5AoZs=)
3. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqO9sB5MykY8noUApN-7y9BR5Sv28M6ZeXEaFPoY8qzOjVuzjqBu2nYwDdt5dDtq5xcqMZoOIYUxcgKxHvvtXBDWx5xQ3xIQ0QbKA5OHazPCLJ9nRba7S91E7Q9Zk5NS8Z5B4-7xoBQCqqqegQhvLNZprrOi-1My3Dra80r7zAIlAUEghbPTa8AF2PIw==)
4. [ietf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWpkOxfWzIXkf9TF56vTKIrjsk7q2aWsFnxZi2ZmLHOnG6556DUVpqBUIV8AI7n12lv55ZMDwn-FbrzVli5uvuTL4PR9fv5tm70o2urPkkU6nMkjTNdEBTahaPOJV2vuKtZdU=)
5. [sidnlabs.nl](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVDqT7WTavtbdfX9bR1vcD50ElPY-dVDz2_O0Fga4bxyQWjS7JH7zVRdFqz4OXpOScIEF4fKTyeA4mek6WvXn3jUvPpp5Y6T3GVFFwnY2VQyrRMjEXW60SqE1XUivIAfDK8EJ2eJZZlgfG-C-J-DlNpmeXtT2NnVjYhwqiD8QsUoi3HFjq1hmjkDEDXeF4ld0X5JQihu_E_NVOKlFDbisytwsAX-m3Lkp8wAd7foD6NF2Z_fzxOqFh0Io=)
6. [cuhk.edu.hk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_930ZWeItHiUNK_R5TF3p40uzqjFghSBIXGokuowLcQge-9OEPd_jRUaT1o3P-_hFhKHJzLuwUdSFyrVa9Ta-SJTDALs6V7y7FP89wixT0XADg988M7_exXCpHNIRGADXAA==)
7. [cuhk.edu.hk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFHnCbeB269hndK-vsuutTnpFf69ScqqhNJulxYoPKeLg-KtLnnzehLazqLUemkdu2QOOnAgFUee7Pi-wDe7VUWmWeAbipxTJDZvSW5ao_LKPdUXD5gvSHO2CZ4-rNKM9AqOTRT-ZmR6UyjvoM-P6z8TB8tdbM=)
8. [mislove.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXtD7Ud8YE7AOUivCjq5ZKO8f2Co-ZzGHJlUTAmq-DkA54bWSmAw804iCIO7RZmaQUYDTT7sbZIJZI-URRTLaVu3tDk-fsFX4_bZAzthMiK4nAnDXzvjQs4cxTWLDzOAriAg_lBEkK7na_pTH1Vj30U__9CabsQJU=)
9. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGI_M6BnoN7r6LBVcz5O_mxvJ6y-FF8_O84Zq_LOQcYjhuLK90uErKiSqAFvio8sETn_TSoti5K1CXJTmU2EhUwAopSSkacELEj0Og7DjzxkPyQ4fReyareLB8Yxt1ccThVjt5_cN9Db8sR8ElZBvFbMBYQx1U6f6HZYZUx9FwqJ2SO1rI8WO2JoDSvNS80A5WMtjJ_kCHEG6uc7pTV0g324lox21nRyLfqWvHry4pmWFvFlYmKIYNO_e0=)
10. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFt9br_cgSsPyItXgxQDYq-Ujfzh43kZwqFaETGoiT3KCZZPhp4Yt3z4ruhznMzTBQg2CT4GZ6g7ZCtKYT_grZV67h2wcgk5JfeUOschX3Rvnfv7A4yNWQ83eN4URMqZaVrX5-8uGZWbbc0pNCcUyG1ytEvrugHUCfuscIihDFFC6z8h2k1DW0t14fMM8re2t2PcoXiFQtLmdtZ)
11. [thousandeyes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXaAeT3sHwT88hW_0CxDhFiuQtoNurlo-G7dC5lkfInc32Qt_ljHcJC8aFBagmXJaKmt10QNsw0MXILq87wsfVMkk3ugQQ2eT8Xh39_paAuDQwZ0wocWiM2cCXQpHM69ZCMbTOZ9zGx8WqMWzGdbEKQIWs)
12. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaepYYcHAmIYYEwFT_JNvOa_K1ZeeXOUHfURdUW9oNEbJGwN_7xh9VzTtoQLO3rBH9Shy28m9Yx89NWGdR4MIVvmj2sU1e1W5w8sMsjZwY3Fily5SpZaqtBenQhZgEVLyEJKJZ8CYT1cZE14viet6OVdgVem9B2NW8gpUu89NBVuCYtfje_9qdTRFewp-oBERgAHEBjY6kGxvLytE-gmLrgg==)
13. [networklessons.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHu4N0FzcgkWEeAYf4WJNP7i_SQUuZBt3UEruk9McDAdkznGyq25fU4d8v8y4o-41AQX1xnzIu_M7I4GWZaf0J_L-XvRtXw_U67XhuI0ac1R9ciGcJJ7zrGQTtZR4fXnTFt_hWmtlc=)
15. [ietf.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwrA3tStUYQAp-ljfk9r5xOuLk7GbniJk-HbvFxce2ILP2oZCnL-EAYGNi8U0Mt9H6SxmZ3phiT34p_RJrWA-YaPtVu6nD2W9WcUdgIgDCnMrbk064kt7ePx_GaNSmkz5DngfqHBB_4yaUDCGwwpM5k5KMU52pLyPXglRmte0HEGLA)
16. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpp2IRxEDP7NlnOCtv481nz2t6xXHrLwNTp2ddQNFTdcAeJyMVCY9C_PgMyUAR9CEt_1P870VOFjU4xrKW5vHZdJwYzG5NBH1xySmzOs2COYEwmZzHnhb88StfH7GXIfB425vVEKuDZ5CgV43KcNFYfak_fT1J7j4L7mjyL1xSutddhWhNQFbPSQ==)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVv2AODhicc29gbhClIuP9XjGH76WT-QXLY8D8oXrlVpIREhu19JJ5SBulGVf7Y0oHlCZWtmd7sQ-GMIM7E9zL5sjRKvrkny0kE6vVEyfwETgzpu-J667jQ2ASa8u19F-WD9BP3xQd-fKPRMP6qtI29-y8L_ii4XNUjtXVXzv508tma-2BpXfSsGnIFmHjrVQb5OxHiMmmHVpDH14ylufp4vrL-d7TqcScizk=)
18. [realpython.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEszkdZZESB8RWNN8MFN455g57-qk4K2gbKZJmoDHgNM9KjLWOZYtF2VgBbcng_1QHlHDq-UYLDjuCIVa7xXPO9iIVc8ADGvRou8hnyUbJEAKuC9tmNujd8Vw==)
19. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuclrjr4h-Z44SlM77dbB1Wy3J51JmPE1tYhqySqxtj2Yy3Gs3aAATYE6EIRc3KjKwyoykuSdoqlh0JQ9nPZnMKnauVVApOMCzX4cJXcAyNsIjwveEzM-y7qFMkbvkUa0Wk4EQiiND7F_ODV3hZitvefajtFpz4yaMpXERDWJBvkrOQV5bjJ0NPA==)
20. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEwgKlawiyyPrSGZb-WAJe_svfINw9JI7WYt6D0nZENjv9eCoUC9frHdJD14aSY1EAKdnKjdb7Jr2C0uguEaYNpkEv7__OxPMTw7_yzMgzYvEln_7Y-rmPEmN3rkgAOg5x2hwtwDALWnIjK-YmcIilM4bs3JFnUmiRVE7-X70zh0kLxrAphsVxiR9k=)
