"""
utils.py - DOT visualization generator for dialogue graphs.

Generates Graphviz DOT files from parsed dialogue graph structures
using the graphviz 0.20.3 Python API.
"""

import graphviz
from typing import Dict, Any

__all__ = ["generate_dot", "escape_label", "style_node"]


def escape_label(text: str) -> str:
    """Safely escape text for DOT labels using graphviz.escape()."""
    if not text:
        return ""
    return graphviz.escape(text)


def style_node(node_type: str) -> Dict[str, str]:
    """Return DOT styling attributes based on node type."""
    if node_type == "choice":
        return {"shape": "diamond", "style": "filled", "fillcolor": "lightyellow"}
    elif node_type == "terminal":
        return {"shape": "doubleoctagon", "style": "filled", "fillcolor": "lightgray"}
    else:  # line
        return {"shape": "box", "style": "rounded"}


def generate_dot(graph: Dict[str, Any], output_path: str) -> None:
    """
    Generates a Graphviz DOT source file from the dialogue graph.

    Args:
        graph: The structured dialogue graph with nodes and edges.
        output_path: File path to save the DOT source.
    """
    dot = graphviz.Digraph(name="DialogueGraph", strict=False)
    dot.attr(rankdir="TB")

    # Add nodes
    for node in graph.get("nodes", []):
        n_id = node["id"]
        label_parts = []
        if node.get("speaker"):
            label_parts.append(f"{node['speaker']}:")
        if node.get("text"):
            label_parts.append(node["text"])
        label = " ".join(label_parts) if label_parts else n_id
        safe_label = escape_label(label)
        attrs = style_node(node.get("type", "line"))
        dot.node(n_id, label=safe_label, **attrs)

    # Add edges
    for edge in graph.get("edges", []):
        edge_label = escape_label(edge.get("text", ""))
        dot.edge(edge["from"], edge["to"], label=edge_label)

    # Save DOT source file (no rendering)
    dot.save(filename=output_path)
