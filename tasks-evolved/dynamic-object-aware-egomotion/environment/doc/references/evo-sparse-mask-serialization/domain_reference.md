# Domain Reference for evo-sparse-mask-serialization

**Responsibility**: Dense-to-CSR conversion using np.nonzero and np.bincount/cumsum, NPZ archive creation with proper key naming, JSON output formatting for frame interval to motion label mapping

**Key functions to implement**: dense_to_csr_numpy, save_sparse_masks_npz, save_motion_labels_json

---

## 4. Pure NumPy Sparse CSR Matrix Storage Format


Dense binary masks of high-resolution video require immense disk space. A 1080p boolean mask consumes ~2 MB per frame. Since moving objects typically occupy a fraction of the frame, compressing this data is highly advantageous. Without utilizing the `scipy.sparse` library, we can manually implement the Compressed Sparse Row (CSR) format using pure NumPy.

## 5. JSON Output Formatting


JSON (`json.dump`) provides an interoperable format to document camera motion logic. A structured dictionary mapping transitions between frames to identified motions promotes downstream parsing.

```python
import json

motion_labels = {
    "0->1": ["Pan Left", "Dolly In"],
    "1->2": ["Stay"],
    "2->3": ["Tilt Down", "Roll Clockwise"]
}

with open("motion_analysis.json", "w") as f:
    json.dump(motion_labels, f, indent=4)
```

---