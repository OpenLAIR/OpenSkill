# Domain Reference for evo-output-serialization

**Responsibility**: Manual dense-to-CSR conversion using NumPy, NPZ file writing with compressed sparse masks, JSON export with interval-keyed motion labels.

**Key functions to implement**: dense_to_csr_manual, save_csr_masks_npz, export_motion_labels_json

---

## 4. Manual Construction of SciPy Sparse CSR Matrices


When packaging constraints forbid the use of external dependencies like `scipy`, utilizing its highly efficient Compressed Sparse Row (CSR) matrix format requires a manual implementation using base NumPy arrays [cite: 26, 27]. CSR is an optimized memory representation for matrices where the vast majority of elements are zero (e.g., binary segmentation masks) [cite: 27, 28].

### 4.1 Theory of the CSR Format


A CSR matrix of shape $(H, W)$ is fully defined by three 1-dimensional arrays [cite: 26, 27]:
1.  **`data`**: Contains all non-zero values of the dense array, read row-by-row (top to bottom, left to right). For a boolean mask, this is an array of `True` values [cite: 29, 30].
2.  **`indices`**: Contains the column indices corresponding to each element in the `data` array [cite: 26, 27, 29]. Length matches `data`.
3.  **`indptr`**: The "Index Pointer" array. It defines the starting index within the `data` and `indices` arrays for each row [cite: 27, 29]. Its length is strictly $H + 1$ (number of rows plus one) [cite: 26, 27, 29]. The values of the $i$-th row are stored in `data[indptr[i]:indptr[i+1]]` [cite: 26, 27, 28]. The very first element is always 0, and the last element equals the total number of non-zero elements (length of `data`) [cite: 27, 29].

### 4.2 Algorithm for Manual NumPy Conversion


To convert a 2D dense boolean NumPy array `dense_mask` into these three arrays efficiently without looping over Python iterables:

```python
import numpy as np

def dense_to_csr_manual(dense_mask):
    """
    Convert a 2D boolean NumPy array to CSR components manually.
    """
    # 1. Identify non-zero elements
    # np.where returns a tuple: (row_indices, col_indices)
    rows, cols = np.where(dense_mask)
    
    # 2. Data array: all non-zero values (all True for a binary mask)
    data = np.ones(len(rows), dtype=bool)
    
    # 3. Indices array: just the column indices of the non-zero elements
    indices = cols.astype(np.int32)
    
    # 4. Indptr array: count of non-zeros per row
    # np.bincount counts occurrences of each row index.
    # We must provide minlength to account for completely empty trailing rows.
    row_counts = np.bincount(rows, minlength=dense_mask.shape)
    
    # indptr is the cumulative sum of row counts, prepended with a 0
    indptr = np.zeros(dense_mask.shape + 1, dtype=np.int32)
    indptr[1:] = np.cumsum(row_counts)
    
    return data, indices, indptr
```

### 4.3 Serialization to NPZ Format


Once the mask for a given frame `i` is transformed into the CSR components, it should be serialized to disk using `np.savez_compressed()`. This saves multiple arrays into a single zipped binary file. 

```python
def save_csr_masks(mask_list, output_file, shape):
    """
    Saves a list of boolean masks to an NPZ file utilizing CSR structure.
    """
    save_dict = {'shape': np.array(shape, dtype=np.int32)}
    
    for i, mask in enumerate(mask_list):
        data, indices, indptr = dense_to_csr_manual(mask)
        save_dict[f'f_{i}_data'] = data
        save_dict[f'f_{i}_indices'] = indices
        save_dict[f'f_{i}_indptr'] = indptr
        
    np.savez_compressed(output_file, **save_dict)
```

## 5. Structuring Motion Outputs in JSON


The egomotion analysis operates between pairs of consecutive sampled frames. Therefore, the outputs are inherently interval-based. Writing these sequence intervals to JSON requires standard string manipulation to format the keys as `"start->end"` intervals. In a zero-based index logic, the movement extracted between the very first sample and the second sample will be keyed `"0->1"`.

```python
import json

def export_motion_to_json(motion_results, output_path):
    """
    motion_results: List of tuples (frame_idx_prev, frame_idx_curr, labels_list)
    """
    json_dict = {}
    
    for (prev_idx, curr_idx, labels) in motion_results:
        key = f"{prev_idx}->{curr_idx}"
        json_dict[key] = labels
        
    with open(output_path, 'w') as f:
        json.dump(json_dict, f, indent=4)
```

To reduce payload size, temporal smoothing or interval compression can be applied. If frame $0 \rightarrow 1$ is `["Pan Left"]` and frame $1 \rightarrow 2$ is `["Pan Left"]`, they can be compressed to `"0->2": ["Pan Left"]` [cite: 18].