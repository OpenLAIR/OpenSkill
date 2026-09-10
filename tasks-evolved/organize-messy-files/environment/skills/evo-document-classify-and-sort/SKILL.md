---
name: evo-document-classify-and-sort
description: Classifies document text into 5 categories (LLM, trapped_ion_and_qc, black_hole, DNA, music_history) using weighted keyword matching, then moves files into folders.
---
# evo-document-classify-and-sort

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-document-classify-and-sort/scripts')
sys.path.insert(0, '/app/environment/skills/evo-document-text-extraction/scripts')
from utils import extract_text
import importlib
classify_mod = importlib.import_module('utils')
# Better approach:
sys.path.insert(0, '/app/environment/skills/evo-document-classify-and-sort/scripts')
from utils import classify_document, create_category_folders, sort_files_into_folders
```

## Key Functions
- `classify_document(text)` - returns category string
- `create_category_folders(base_dir)` - creates 5 folders
- `sort_files_into_folders(source_dir, dest_base_dir, extract_fn)` - full pipeline
- `get_category_keywords()` - returns keyword dictionaries
