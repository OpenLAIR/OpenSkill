# Domain Reference for evo-dialogue-parser

**Responsibility**: Text parsing via regex, graph data structure construction, node type classification, implicit node generation, graph validation (BFS reachability, edge target existence), and JSON serialization

**Key functions to implement**: parse_script, validate_graph, save_json, synthesize_implicit_nodes

---

## 1. Text Parsing Patterns for Dialogue Scripts


The initial phase of constructing a dialogue utility module involves the lexical analysis of a formatted text string. Dialogue scripts typically employ custom syntax rules designed for human readability, which must be systematically deconstructed into abstract syntax trees or immediate graph objects.

### 1.1 Regular Expression (Regex) Fundamentals in Python


The Python standard library `re` module is the primary vehicle for text extraction. When dealing with multi-line text files containing dialogue, two compilation flags are of paramount importance: `re.MULTILINE` and `re.DOTALL` [cite: 1]. By default, the special character `^` matches the start of the string, and `$` matches the end of the string; however, `re.MULTILINE` modifies this behavior so that `^` and `$` match the start and end of *each individual line* within the string [cite: 1]. Similarly, the `.` character typically matches any character except a newline, but applying `re.DOTALL` forces it to match newlines as well, which is necessary when capturing multi-line dialogue [cite: 1, 2].

Furthermore, the dichotomy between greedy and lazy matching is a frequent source of logic errors in regex parsing. A greedy quantifier like `.*` will consume as much text as possible, potentially swallowing subsequent delimiters or entire blocks of text [cite: 1, 3]. Conversely, a lazy (or non-greedy) quantifier like `.*?` consumes the minimum amount of characters required to satisfy the pattern [cite: 4].

### 1.2 Formulating Patterns for Script Elements


A custom dialogue script typically consists of three primary components: node delimiters, speaker lines, and choice lines.

### 1.3 Pitfalls in Multi-line Text Parsing


Parsing structured text in Python introduces several insidious edge cases:
1.  **Dangling Whitespace**: A line written as `Player: Hello -> End   ` contains hidden trailing spaces. Using `\s*$` ensures the target group `(?P<target>\S+)` does not erroneously include these trailing spaces.
2.  **Greedy vs. Lazy Matching in Dialogue**: If a user writes `Player: I said "yes" -> Target`, a greedy `.*` might behave unpredictably if multiple arrows `->` exist on a single line. The lazy modifier `.*?` strictly binds the capture to the nearest logical delimiter [cite: 4].
3.  **Cross-Platform Line Endings**: Windows uses `\r\n` while Unix uses `\n`. Opening files using universal newline mode (e.g., `open('file.txt', 'r', encoding='utf-8')`) allows Python to normalize these automatically, alleviating regex failures [cite: 3].

---

## 2. Graph Data Structure for Dialogue Trees


A conversational sequence is topologically isomorphic to a Directed Graph \(G = (V, E)\), where \(V\) is the set of Nodes (representing discrete states of dialogue or player choice) and \(E\) is the set of Edges (representing the transitions between these states).

### 2.1 JSON Schema Representation


To facilitate programmatic ingestion by game engines (e.g., Unity, Godot, Unreal), the graph must be translated into a standardized JSON structure. A canonical dictionary representation involves explicit node and edge arrays:

```json
{
  "nodes": [
    {
      "id": "IntroNode",
      "text": "Greetings, traveler.",
      "speaker": "NPC",
      "type": "line"
    },
    {
      "id": "ChoiceNode",
      "text": "What will you do?",
      "speaker": "NPC",
      "type": "choice"
    }
  ],
  "edges": [
    {
      "from": "IntroNode",
      "to": "ChoiceNode",
      "text": "",
      "tag": null
    },
    {
      "from": "ChoiceNode",
      "to": "CombatNode",
      "text": "I will fight you!",
      "tag": "Attack"
    }
  ]
}
```

### 2.2 Differentiating Node Types


The parsing logic must strictly differentiate between "line" nodes and "choice" nodes based on their contents:
*   **Line Node**: Contains a single `Speaker: ... -> Target` sequence. The node itself holds the speaker and the text. The outgoing edge connects to the target, with an empty string for the edge `text`.
*   **Choice Node**: Serves as a branching junction. The text associated with a Choice Node should conceptually reflect the dialogue immediately preceding the choices (if any) or simply act as a silent hub. The actual options presented to the user (`1. Choice A`, `2. Choice B`) are mapped to the **edges**. The edge's `text` property holds the choice text, and the edge's `tag` property holds any mechanical tags (`[Lie]`, `[Attack]`).

### 2.3 Handling Terminal and Implicit Nodes


A common edge case in dialogue authoring is pointing an arrow to a target (e.g., `-> End`) without explicitly creating an `[End]` node definition in the script. 
If an edge targets a node identifier that is absent from the parsed `[NodeName]` array, the parser must algorithmically synthesize an **implicit leaf node**.

```python
def synthesize_implicit_nodes(nodes_dict: dict, edges_list: list):
    """
    Scans edge targets and generates implicit terminal nodes 
    if they do not explicitly exist in the graph.
    """
    for edge in edges_list:
        target = edge["to"]
        if target not in nodes_dict:
            # Create a silent terminal node
            nodes_dict[target] = {
                "id": target,
                "text": f"[{target}]",
                "speaker": "System",
                "type": "terminal"
            }
```
In this paradigm, terminal nodes have an in-degree > 0 and an out-degree of 0. Multiple disparate paths converging on the same "End" node is perfectly valid (a directed acyclic graph, or DAG, characteristic).

---

## 4. JSON Output Serialization in Python


Transforming the nested dictionary mapping into a physical `.json` file requires utilizing the `json` module with explicit parameterization to prevent data corruption or serialization errors.

### 4.1 Serialization Best Practices


When calling `json.dump()`, the following parameters dictate best practices for structural graph data:
*   `indent=2` or `indent=4`: Enhances human readability, allowing level designers to manually audit the node hierarchy in text editors.
*   `ensure_ascii=False`: By default, the `json` module escapes all non-ASCII characters into `\uXXXX` sequences. Since dialogue scripts often include non-English scripts, accented characters, or emojis, `ensure_ascii=False` is mandatory to output raw UTF-8 glyphs.
*   `encoding='utf-8'`: The file object must be opened utilizing explicit UTF-8 encoding. Failure to do so defaults to the system's locale (e.g., `cp1252` on Windows), resulting in immediate `UnicodeEncodeError` exceptions.

```python
import json

def save_json(graph: dict, output_path: str):
    """
    Serializes a graph dictionary into a structured JSON file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(
            graph, 
            f, 
            indent=4, 
            ensure_ascii=False
        )
```

### 4.2 Potential Pitfalls


The most prominent pitfall during graph serialization involves attempting to encode custom objects (e.g., node object instances or sets) rather than basic data types (strings, ints, lists, dicts). Graph cycles (e.g., Node A points to Node B, Node B points to Node A) are not inherently fatal to JSON serializers as long as the references are topological (strings holding IDs) rather than direct object memory references. The string-based adjacency list format completely sidesteps maximum recursion depth errors.

---

## 5. Graph Validation Algorithms


Ensuring structural integrity through topological validation protects runtime environments from logical exceptions such as orphaned nodes or non-existent pointer targets.

### 5.1 Reachability Using Breadth-First Search (BFS)


To determine if all nodes are reachable from the starting node (typically the first defined `[NodeName]`), a Breadth-First Search (BFS) algorithm implemented via `collections.deque` offers an \(O(|V| + |E|)\) time complexity validation.

```python
from collections import deque
from typing import List, Dict, Set

def validate_graph(graph: dict) -> bool:
    """
    Validates graph reachability and constraint compliance using BFS.
    """
    nodes_list: List[Dict] = graph.get("nodes", [])
    edges_list: List[Dict] = graph.get("edges", [])
    
    if not nodes_list:
        return True # An empty graph is trivially valid
        
    # 1. Map nodes by ID for O(1) lookup
    node_map = {n["id"]: n for n in nodes_list}
    
    # 2. Build adjacency list for O(1) edge retrieval
    adjacency_list: Dict[str, List[str]] = {n_id: [] for n_id in node_map}
    for edge in edges_list:
        origin = edge["from"]
        target = edge["to"]
        
        # Constraint validation: Ensure edge target exists
        if target not in node_map:
            raise ValueError(f"Edge from '{origin}' points to non-existent node '{target}'")
            
        if origin in adjacency_list:
            adjacency_list[origin].append(target)
            
    # 3. BFS Execution from root node (index 0)
    root_node_id = nodes_list["id"]
    visited: Set[str] = set()
    queue = deque([root_node_id])
    
    while queue:
        current = queue.popleft()
        if current not in visited:
            visited.add(current)
            for neighbor in adjacency_list.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)
                    
    # 4. Detect unreachable orphaned nodes
    unreachable = set(node_map.keys()) - visited
    if unreachable:
        print(f"Warning: The following nodes are unreachable from root: {unreachable}")
        return False
        
    return True
```

### 5.2 Evaluating Circular References


Circular references (e.g., a choice leading back to a previous interrogation hub) are frequently intentional in game design to allow for exhaustive dialogue exploration. The BFS algorithm handles these implicitly by verifying the node's presence within the `visited` set before queuing, effectively preventing infinite looping. Therefore, circularity is not treated as a structural invalidity unless a strict Directed Acyclic Graph (DAG) constraint is a specified project requirement.

---

## 6. Edge Cases and Pitfalls for Dialogue Parsing


The implementation must be highly resilient against the chaotic realities of human-authored text scripts.

### 6.1 Nodes with Homogeneous Contents

*   **Choice-Only Nodes**: A script section may contain only choices (e.g., following a global narrative event). In this scenario, the `text` parameter of the node can be derived from the section header (the NodeName itself) or explicitly left blank. 
*   **Line-Only Nodes**: These are purely sequential events. The script dictates an immediate progression. The edge connecting to the next node will have a null/empty `text` field.

### 6.2 Tag Processing in Choices

Tags embedded in brackets such as `1. [Intimidation] Attack the guard -> Combat` dictate specific gameplay skill checks. Extracting this requires the non-capturing group in our regex: `(?:\[(?P<tag>[^\]]+)\])?`. Whether to strip the tag from the text or preserve it depends on the engine integration. Best practice is to extract the tag into a discrete property (`"tag": "Intimidation"`) and sanitize the `text` string to purely contain the spoken/presented dialog (`"text": "Attack the guard"`).

### 6.3 Spaces and Special Formatting in Arrows

Authors frequently deviate from strict formatting, writing sequences like `->Target`, `->  Target  `, or `-> [Target]`. Using `\s*->\s*(?P<target>\S+)` handles variable spacing. If targets contain embedded spaces, the pattern must be modified to `(?P<target>.+?)`, though node IDs with spaces often generate hash-mapping complications and should ideally be restricted to alphanumeric constraints `\w+`.

---