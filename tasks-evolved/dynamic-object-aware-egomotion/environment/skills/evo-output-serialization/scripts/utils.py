import numpy as np
import json


def dense_to_csr_manual(dense_mask):
    """
    Convert a 2D boolean NumPy array to CSR components manually (no scipy).
    
    Returns:
        data: 1D bool array of True values (length = number of nonzero elements)
        indices: 1D int32 array of column indices for each nonzero element
        indptr: 1D int32 array of length H+1, row pointers
    """
    H = dense_mask.shape[0]
    
    # Find nonzero elements
    rows, cols = np.where(dense_mask)
    
    # Data: all True for binary mask
    data = np.ones(len(rows), dtype=bool)
    
    # Indices: column indices
    indices = cols.astype(np.int32)
    
    # Indptr: cumulative count of nonzeros per row
    if len(rows) > 0:
        row_counts = np.bincount(rows, minlength=H)
    else:
        row_counts = np.zeros(H, dtype=np.int32)
    
    indptr = np.zeros(H + 1, dtype=np.int32)
    indptr[1:] = np.cumsum(row_counts)
    
    return data, indices, indptr


def save_csr_masks_npz(mask_list, output_file, shape):
    """
    Save a list of boolean masks to NPZ file in CSR sparse format.
    
    Args:
        mask_list: list of 2D boolean numpy arrays
        output_file: path to output .npz file
        shape: [H, W] resolution of the masks
    """
    save_dict = {'shape': np.array(shape, dtype=np.int32)}
    
    for i, mask in enumerate(mask_list):
        data, indices, indptr = dense_to_csr_manual(mask)
        save_dict[f'f_{i}_data'] = data
        save_dict[f'f_{i}_indices'] = indices
        save_dict[f'f_{i}_indptr'] = indptr
    
    np.savez_compressed(output_file, **save_dict)


def export_motion_labels_json(motion_results, output_path):
    """
    Export motion labels to JSON with frame-interval keys.
    
    Args:
        motion_results: list of (sample_idx_prev, sample_idx_curr, labels_list)
        output_path: path to output .json file
    """
    json_dict = {}
    
    for (prev_idx, curr_idx, labels) in motion_results:
        key = f"{prev_idx}->{curr_idx}"
        json_dict[key] = labels
    
    with open(output_path, 'w') as f:
        json.dump(json_dict, f, indent=4)
