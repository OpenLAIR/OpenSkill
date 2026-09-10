---
name: evo-output-serialization
description: Serializes egomotion labels to JSON with frame-interval keys and binary masks to NPZ in CSR sparse format using only NumPy.
---

# evo-output-serialization

Serializes analysis results to the required output formats.

## Key Functions

- `dense_to_csr_manual(dense_mask)` — Converts 2D bool array to CSR (data, indices, indptr)
- `save_csr_masks_npz(mask_list, output_file, shape)` — Saves masks to NPZ with CSR format
- `export_motion_labels_json(motion_results, output_path)` — Saves motion labels to JSON

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-output-serialization/scripts')
from utils import save_csr_masks_npz, export_motion_labels_json

# motion_results: list of (sample_idx_prev, sample_idx_curr, labels_list)
export_motion_labels_json(motion_results, '/root/pred_instructions.json')

# mask_list: list of boolean 2D arrays, shape: [H, W]
save_csr_masks_npz(mask_list, '/root/pred_dyn_masks.npz', shape=[H, W])
```

## CSR Format Details

For each frame i, stores:
- `f_{i}_data`: bool array of True values
- `f_{i}_indices`: int32 column indices of nonzero elements
- `f_{i}_indptr`: int32 array of length H+1 (row pointers)
- `shape`: [H, W] as int32 array

## JSON Format

```json
{
    "0->1": ["Pan Right"],
    "1->2": ["Stay"],
    ...
}
```
Keys are "sample_idx_prev->sample_idx_curr" (0-based sample indices).
