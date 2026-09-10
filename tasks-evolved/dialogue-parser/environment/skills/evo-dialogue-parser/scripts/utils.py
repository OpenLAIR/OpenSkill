import re
from typing import List, Dict, Any
from collections import defaultdict, deque

HEADER_PATTERN = re.compile(r"^\[(?P<id>[a-zA-Z0-9_]+)\]\s*$")
SPEAKER_PATTERN = re.compile(
    r"^(?P<speaker>[^:]+?):\s*(?P<text>.*?)\s*(?:->\s*(?P<target>[a-zA-Z0-9_]+))?\s*$"
)
CHOICE_PATTERN = re.compile(
    r"^(?P<number>\d+)\.\s*(?:\[(?P<tag>[^\]]+)\]\s*)?(?P<text>.*?)\s*->\s*(?P<target>[a-zA-Z0-9_]+)\s*$"
)

def parse_dialogue_text(script_text: str) -> List[Dict[str, Any]]:
    lines = script_text.strip().split("\n")
    sections = []
    current = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        hm = HEADER_PATTERN.match(line)
        if hm:
            if current:
                sections.append(current)
            current = {"id": hm.group("id"), "lines": [], "choices": []}
            continue
        if not current:
            continue
        cm = CHOICE_PATTERN.match(line)
        if cm:
            current["choices"].append(cm.groupdict())
            continue
        sm = SPEAKER_PATTERN.match(line)
        if sm:
            d = sm.groupdict()
            if d["text"] or d["target"]:
                current["lines"].append(d)
            continue
        current["lines"].append({"speaker": "Narrator", "text": line, "target": None})
    if current:
        sections.append(current)
    return sections

def build_json_graph(sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes = []
    edges = []
    for sec in sections:
        nid = sec["id"]
        is_choice = len(sec["choices"]) > 0
        ntype = "choice" if is_choice else "line"
        nspeaker = "Narrator"
        ntext = ""
        if sec["lines"]:
            lead = sec["lines"][0]
            nspeaker = lead.get("speaker") or "Narrator"
            ntext = lead.get("text", "")
            if not is_choice and lead.get("target"):
                edges.append({"from": nid, "to": lead["target"], "text": ""})
        if is_choice:
            for ch in sec["choices"]:
                etxt = ch.get("text", "").strip()
                if ch.get("tag"):
                    etxt = "[" + ch["tag"] + "] " + etxt
                edges.append({"from": nid, "to": ch["target"], "text": etxt})
        nodes.append({"id": nid, "type": ntype, "speaker": nspeaker, "text": ntext.strip()})
    return {"nodes": nodes, "edges": edges}

def validate_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    if not graph["nodes"]:
        return {"valid": False, "errors": ["Empty graph"]}
    node_ids = {n["id"] for n in graph["nodes"]}
    start = graph["nodes"][0]["id"]
    adj = defaultdict(list)
    errors = []
    for e in graph["edges"]:
        adj[e["from"]].append(e["to"])
        if e["to"] not in node_ids and e["to"] != "End":
            errors.append(f"Dangling: {e['from']} -> {e['to']}")
    visited = set()
    queue = deque([start])
    while queue:
        c = queue.popleft()
        if c not in visited:
            visited.add(c)
            for nb in adj[c]:
                if nb not in visited and nb in node_ids:
                    queue.append(nb)
    unreachable = node_ids - visited
    warnings = []
    if unreachable:
        warnings.append(f"Unreachable: {unreachable}")
    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

def parse_script(script_text: str) -> Dict[str, Any]:
    sections = parse_dialogue_text(script_text)
    graph = build_json_graph(sections)
    validation = validate_graph(graph)
    return graph
