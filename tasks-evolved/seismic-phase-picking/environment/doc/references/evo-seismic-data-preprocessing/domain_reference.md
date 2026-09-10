# Domain Reference for evo-seismic-data-preprocessing

**Responsibility**: All data I/O from .npz files and transformation into properly formatted ObsPy Stream objects with correct channel ordering, sampling rate, and data types

**Key functions to implement**: load_npz_trace, build_obspy_stream, identify_channel_order, preprocess_stream

---

## 3. Data Pipeline: Loading .npz Files and Preparing Input


If your continuous waveform data is stored in NumPy `.npz` files, it must be carefully preprocessed before being fed into SeisBench. Let us assume the `.npz` file contains the following structure:
*   `data`: An array of shape `(12000, 3)` representing 120 seconds of data.
*   `dt`: A float representing the sampling interval (e.g., `0.005` for 200 Hz).
*   `channels`: An array or list of strings like `["DPE", "DPN", "DPZ"]`.

## 4. ObsPy Integration: Bridging NumPy and SeisBench


To utilize the automatic preprocessing, sliding windows, and post-processing of SeisBench, the ideal approach is to convert the `(3, N)` NumPy array into an ObsPy `Stream` object [cite: 1].

## 7. Common Pitfalls


1.  **Channel Ordering Mismatches**: Supplying East, North, Vertical instead of Vertical, North, East (Z, N, E) is the most frequent silent error [cite: 17]. While a 1D CNN might still detect P-waves (since they appear strongly on all components), S-wave accuracy will plummet because the model's filters are spatially tuned to expect horizontal shear energy on the 2nd and 3rd input channels. Ensure ObsPy traces have channel codes correctly ending in Z, N, and E [cite: 8, 15].
2.  **Integer vs. Float Data Types**: Raw NumPy `.npz` data is frequently stored as `int32` (raw digitizer counts). PyTorch and SeisBench models expect `float32` tensors [cite: 7]. When constructing ObsPy traces, explicit conversion using `.astype(np.float32)` is mandatory to prevent PyTorch crashes.
3.  **Data Normalization**: You generally **do not** need to apply min-max or zero-mean/unit-variance normalization to the data manually before passing it to `annotate()` or `classify()`. SeisBench models and their PyTorch implementations include data normalization as an internal, built-in preprocessing layer applied to individual sliding windows on the fly [cite: 7]. Detrending the data (removing the mean) is, however, highly recommended.
4.  **Hardware Acceleration (GPU vs CPU)**: Model inference on CPU is painfully slow for large datasets. You must explicitly move the SeisBench model to the GPU. Use `model.to_preferred_device(verbose=True)`. If you wish to force CPU inference for memory reasons, you can use `model.cpu()` as it inherits from standard PyTorch modules [cite: 10, 15].
5.  **Memory Issues with Batch Processing**: If you process 100 files simultaneously by appending them all into a massive ObsPy `Stream` and passing it to `.classify()`, you may trigger a CUDA Out of Memory (OOM) error. The `batch_size` argument in `classify()` controls the tensor batching, but iterating through your `.npz` files in a loop and saving individual CSVs is more robust than holding gigabytes of characteristic functions in RAM [cite: 21].
6.  **Missing Channels**: If an `.npz` file only contains Z and N components, standard 3-component PhaseNet will throw an error. In operational scenarios, you must inject arrays of zeros for missing components, or utilize specialized models designed for 1-component or missing-data environments.

---