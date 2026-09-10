---
name: evo-scala-tokenizer-generator
description: Generates complete Scala 2.13 Tokenizer.scala from Python Tokenizer.py translation.
---
# evo-scala-tokenizer-generator
Produces /root/Tokenizer.scala with all classes/traits translated from Python.

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-scala-tokenizer-generator/scripts')
from generate import generate_scala_file
generate_scala_file('/root/Tokenizer.scala')
```
