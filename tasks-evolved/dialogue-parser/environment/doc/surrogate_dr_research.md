To verify the dialogue parser without relying on the implementation itself, we establish the following verification anchors, invariants, and cross-validation strategies.

### 1. Independently Computable Reference Values
For the provided `script.txt` snippet, we can derive the expected structure of the first two nodes manually to serve as a "Gold Standard" fragment for assertions.

**Input Fragment:**
```
[Start]
Narrator: The tavern door creaks open. -> TavernEntry

[TavernEntry]
Narrator: Three figures catch your eye. -> TavernChoice
```

**Derivation Chain:**
1.  **Node 1 (Start):**
    *   `id`: "Start"
    *   `type`: "line"
    *   `speaker`: "Narrator"
    *   `text`: "The tavern door creaks open. Smoke and laughter fill the air."
2.  **Edge 1:**
    *   `from`: "Start"
    *   `to`: "TavernEntry"
    *   `text`: "" (Implicit transition)

**Pytest Assertion:**
```python
def test_node_start_integrity(parsed_data):
    start_node = next(n for n in parsed_data['nodes'] if n['id'] == 'Start')
    assert start_node['speaker'] == 'Narrator'
    assert "tavern door" in start_node['text']
```

### 2. Dataset-Level Statistical Invariants
These invariants must hold true regardless of the parsing logic, derived from the graph theory requirements of the task.

*   **Reachability Invariant:** Every node ID present in the `edges` list (as a `to` value) must exist in the `nodes` list, with the exception of a terminal node (e.g., "End" or nodes with no outgoing edges).
    *   *Assertion:* `set(e['to'] for e in edges) - set(n['id'] for n in nodes) <= {"End"}`
*   **Connectivity Invariant:** The number of unique nodes reachable from `[Start]` via Breadth-First Search (BFS) must equal the total number of nodes in the graph (assuming a single connected component).
*   **Edge Cardinality:** The number of edges must be $\ge$ the number of nodes minus 1 (for a connected tree/graph).

### 3. Cross-Validation Approaches
To verify the JSON output independently, use the `networkx` library to validate the graph topology. This is a standard, non-custom tool that acts as an oracle for graph properties.

**Cross-Validation Code:**
```python
import networkx as nx
import json

def verify_graph_structure(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    G = nx.DiGraph()
    for edge in data['edges']:
        G.add_edge(edge['from'], edge['to'])
        
    # Verify no dead ends (except terminal)
    for node in G.nodes():
        if G.out_degree(node) == 0 and node != "End":
            raise ValueError(f"Node {node} is a dangling leaf!")
            
    # Verify all nodes are reachable from Start
    assert nx.has_path(G, "Start", "End")
```

### 4. Benchmarks and Reference Implementations
The dialogue structure follows a **Finite State Machine (FSM)** pattern. You can use the following standard FSM validation rules as test oracles:

*   **DOT Syntax Validation:** Use the `graphviz` command-line tool (installed in the Dockerfile) to validate the generated `.dot` file. If `dot -Tpng /app/dialogue.dot -o /dev/null` returns a non-zero exit code, the syntax is invalid.
*   **Reference Logic:** The structure is a **Directed Acyclic Graph (DAG)** or a **Cyclic Graph** (if loops like `TavernChoice` $\to$ `ObserveRoom` $\to$ `ObserveChoice` $\to$ `TavernChoice` exist).
    *   *Test Oracle:* A script that parses the `script.txt` using a simple `re` pattern to count `[` occurrences should match the `len(nodes)` in the JSON output.

**Pytest Assertion for Node Count:**
```python
def test_node_count_consistency(script_path, parsed_data):
    with open(script_path, 'r') as f:
        content = f.read()
    # Count occurrences of [NodeName]
    expected_count = len(re.findall(r'^\[([^\]]+)\]', content, re.MULTILINE))
    assert len(parsed_data['nodes']) == expected_count
```