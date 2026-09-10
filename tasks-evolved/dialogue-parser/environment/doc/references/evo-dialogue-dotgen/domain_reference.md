# Domain Reference for evo-dialogue-dotgen

**Responsibility**: DOT file generation using graphviz Python API, label escaping with graphviz.escape(), visual styling of nodes and edges, and saving DOT source files without rendering

**Key functions to implement**: generate_dot, escape_label, style_node

---

## 3. Python `graphviz` Version 0.20.3 API


The `graphviz` package version 0.20.3 provides a robust, pure-Python interface for compiling and manipulating DOT language specifications [cite: 5, 6, 7].

### 3.1 Object Instantiation and Core Methods


The `graphviz.Digraph` object is utilized for directed graphs [cite: 8]. Its exact instantiation allows for naming, commenting, and formatting:

```python
import graphviz

### 3.2 Escaping Labels and Special Characters


A crucial pitfall in `graphviz` involves rendering arbitrary user text strings. The DOT language reserves specific characters (such as `<` and `>`) for HTML-like labels, and treats backslashes `\` as escape operators [cite: 8]. Prior to version 0.18, handling these was inconsistent, but version 0.20.3 relies heavily on standardizing backslash behaviors and escaping HTML tags [cite: 6, 7]. 

To safely utilize arbitrary text in node or edge labels, one must strictly employ `graphviz.escape()` [cite: 8]. This method suppresses the DOT engine's special interpretation of sequences like `\n` or `\N` (which usually expands to the node's name) [cite: 9].

```python
user_input = 'NPC: Here is a "quote", and a <bracket>.'
safe_label = graphviz.escape(user_input)

### 3.3 Exporting DOT Source (`save` vs `render`)


A fundamental requirement of the prompt is extracting a `.dot` source file *without* incurring the overhead of invoking the external Graphviz `dot` executable to render a PNG or SVG. 

In version 0.20.3, the `render()` method is strictly purposed for executing the external engine and producing visual output [cite: 6]. To exclusively output the raw DOT text to a specific path, the `save()` method must be invoked [cite: 7]. The `save()` method was distinctly split from `render(dry=True)` in recent versions to prevent semantic overlaps [cite: 6].

```python

## 7. Python Module Structure for Reusable Skills


An effectively structured Python utility module enforces encapsulation, clear access boundaries (`__all__`), and rigorous type hinting to facilitate IDE intelligence and prevent invocation errors.