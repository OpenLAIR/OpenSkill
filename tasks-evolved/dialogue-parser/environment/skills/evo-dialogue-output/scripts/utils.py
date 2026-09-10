import json
from typing import Dict, Any
from graphviz import Digraph

def export_json(graph_data: Dict[str, Any], file_path: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

def export_dot(graph_data: Dict[str, Any], file_path: str):
    dot = Digraph(name="DialogueFlow", engine="dot")
    dot.attr(rankdir="TB")
    for node in graph_data["nodes"]:
        nid = node["id"]
        lbl = node["speaker"] + "\\n" + node["text"]
        if node["type"] == "choice":
            dot.node(nid, label=lbl, shape="diamond", style="filled", fillcolor="lightblue")
        else:
            dot.node(nid, label=lbl, shape="box", style="filled", fillcolor="whitesmoke")
    for edge in graph_data["edges"]:
        dot.edge(edge["from"], edge["to"], label=edge.get("text", ""))
    dot.save(filename=file_path)

def generate_dot_visualization(graph_data: Dict[str, Any], file_path: str):
    export_dot(graph_data, file_path)
