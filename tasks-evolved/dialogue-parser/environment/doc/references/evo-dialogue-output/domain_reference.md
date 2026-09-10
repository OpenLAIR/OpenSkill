# Domain Reference for evo-dialogue-output

**Responsibility**: JSON serialization with proper encoding (ensure_ascii=False, indent, utf-8), Graphviz DOT file generation using the graphviz Python library (Digraph, node/edge creation, save()), visual differentiation of node types (choice vs line)

**Key functions to implement**: export_json, export_dot, generate_dot_visualization

---

## 4. Graphviz DOT Visualization (Version 0.20.3)


To visually audit dialogue flows, the `graphviz` Python package translates our hierarchical structures into the `DOT` graph description language. Version 0.20.3 of the package provides a highly refined object-oriented API wrapping the Graphviz C libraries [cite: 3, 4].

## 6. JSON Module Serialization and Encoding


To persist the intermediate graph as a JSON file, the Python standard library's `json` module is utilized. It performs "serialization," translating Python dictionaries into JSON-formatted string streams [cite: 13, 14].

## 7. Complete Utility Module Implementation


Below is the assembled, fully functional Python utility module. It integrates text parsing, JSON schema synthesis, structural validation, Graphviz DOT generation, and UTF-8 JSON serialization into a reusable application.

```python
"""
dialogue_parser.py
A comprehensive utility for parsing, validating, and visualizing non-linear dialogue.
Dependencies: 
  - Python 3.9+
  - graphviz (pip install graphviz) - Requires Graphviz binaries installed on system
"""

import re
import json
import os
from typing import List, Dict, Any, Optional
from collections import defaultdict, deque