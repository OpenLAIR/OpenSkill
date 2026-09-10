---
name: evo-defect-pipeline
description: End-to-end pipeline that reads test center log CSVs and product codebook files, orchestrates text normalization and fuzzy matching, and produces structured solution.json output.
---

# evo-defect-pipeline

Orchestration pipeline for defect text normalization.

## Key Functions

- `safe_read_csv(file_path)` - Read CSV with encoding fallbacks (utf-8, gbk, replace)
- `discover_codebooks(directory)` - Find codebook CSVs, map product_id to filepath
- `build_codebook_mapping(codebook_df)` - Build preprocessed label -> code dict
- `process_record(row, codebook_dict, standard_texts, threshold)` - Process single record
- `export_results_to_json(records, output_path)` - Write JSON with numpy-safe encoding
- `run_pipeline(data_dir, output_path, threshold)` - Full end-to-end pipeline

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-defect-pipeline/scripts')
from utils import run_pipeline
run_pipeline('/app/data', '/app/output/solution.json')
```
