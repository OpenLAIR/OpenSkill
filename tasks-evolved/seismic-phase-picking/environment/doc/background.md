# Comprehensive Guide to Seismic Phase Picking in Python Using the SeisBench Library

### Key Points
*   **SeisBench provides a unified API** for deep learning-based seismic phase picking, abstracting away complex data preparation and model architecture implementation. 
*   **Pretrained models** like PhaseNet, EQTransformer, and GPD are natively supported, with weights trained on massive global datasets (e.g., STEAD, INSTANCE, ETHZ, SCEDC).
*   **Data integration heavily relies on ObsPy.** While users may store data in raw NumPy `.npz` files, SeisBench models are optimized to ingest ObsPy `Stream` objects, which elegantly handle sliding windows, resampling, and channel ordering.
*   **Inference yields discrete picks or continuous probabilities.** The `classify()` method directly outputs discrete phase arrivals (P and S), while `annotate()` provides raw probability traces for custom peak extraction.

### Overview of Deep Learning in Seismology
The application of deep learning to seismology has revolutionized the extraction of seismic catalogs from continuous waveform data [cite: 1, 2]. Historically, analysts relied on short-term average/long-term average (STA/LTA) triggers and manual review. Today, convolutional neural networks (CNNs) and transformer architectures routinely outperform classical methods, particularly in low signal-to-noise ratio (SNR) environments [cite: 3]. The SeisBench framework serves as the standard computational bridge, allowing researchers to deploy state-of-the-art models without rebuilding architectures from scratch [cite: 4, 5].

### Report Scope and Methodology
This report addresses the comprehensive end-to-end pipeline for processing continuous seismic waveform data stored as NumPy `.npz` files. It details SeisBench installation, pretrained model loading, data conversion into ObsPy structures, resampling and sliding window mechanics, inference generation, and robust pick extraction. We also explore common pitfalls, such as channel ordering and data type mismatches, culminating in a complete, production-ready Python script.

---

## 1. SeisBench Installation and Imports

SeisBench is an open-source Python toolbox designed specifically for machine learning applications in seismology, significantly reducing the overhead required to train and apply deep learning algorithms [cite: 4, 6]. 

### Installation
The recommended and most stable method to install SeisBench is via the Python Package Index (PyPI). It is highly advisable to install the library within an isolated virtual environment (e.g., using `conda` or `venv`) to prevent dependency conflicts with other scientific libraries [cite: 6].

```bash
# Core installation
pip install seisbench
```

For the most up-to-date developmental features, installation from the source repository is also supported [cite: 6]:
```bash
git clone https://github.com/seisbench/seisbench.git
cd seisbench
pip install .
```

### Module Structure and Exact Import Paths
SeisBench is structured into three primary modules that govern the machine learning lifecycle: `data`, `models`, and `generate` [cite: 6, 7].

*   `seisbench.models`: Contains the neural network architectures, pre-trained weights, and the inference API (`annotate` and `classify`).
*   `seisbench.data`: Provides access to benchmark datasets (e.g., STEAD, ETHZ) and standardized loading utilities [cite: 6, 8].
*   `seisbench.generate`: Contains tools for building data generation pipelines, essentially bridging raw data and the models via augmentations and PyTorch `DataLoader` integrations [cite: 6, 9].

A standard import block for a phase-picking pipeline utilizing external `.npz` files typically requires SeisBench models, alongside ObsPy for data formatting, and NumPy/SciPy for array manipulation:

```python
import numpy as np
import pandas as pd
import seisbench.models as sbm
import seisbench.util as sbu
from obspy.core import Trace, Stream, UTCDateTime
```

The current stable version frequently updates its API to standardize model outputs. Notably, a recent major update synchronized the output structure of all SeisBench models, meaning legacy code relying on direct tensor manipulation from the models may need to be updated to use the modern `ClassifyOutput` structures [cite: 10].

---

## 2. Pretrained Models for Phase Picking

SeisBench provides a robust suite of deep learning models designed to detect seismic events and pick the precise arrival times of compressional (P) and shear (S) waves [cite: 11]. 

### Available Architectures
The three most prominent models for phase picking are:
1.  **PhaseNet**: A 1D U-Net architecture adapted for segmenting seismic time series into P-wave, S-wave, and noise probabilities [cite: 2]. It utilizes skip connections to maintain temporal resolution while extracting deep features [cite: 12].
2.  **EQTransformer (EQT)**: A complex architecture combining CNNs with attention mechanisms (Transformers) to capture long-term temporal dependencies [cite: 1].
3.  **Generalized Phase Detection (GPD)**: A simpler CNN operating on shorter time windows, effective but generally outperformed by PhaseNet and EQT in comprehensive benchmarks [cite: 13].

### Loading Pretrained Weights
Pretrained models are instantiated using the `from_pretrained()` method [cite: 14]. The exact model class names are `sbm.PhaseNet`, `sbm.EQTransformer`, and `sbm.GPD`.

```python
# Loading PhaseNet with weights trained on the original Northern California dataset
phasenet_model = sbm.PhaseNet.from_pretrained("original")

# Loading EQTransformer with weights from the STEAD dataset
eqt_model = sbm.EQTransformer.from_pretrained("stead")
```

Users can query available weights for a specific model using the `list_pretrained()` class method [cite: 15]. Options commonly available include:
*   `"original"`: The weights published by the authors of the algorithm (e.g., California data for PhaseNet) [cite: 15].
*   `"stead"`: Trained on the STanford EArthquake Dataset (STEAD), a massive, global, highly heterogeneous dataset.
*   `"instance"`: Trained on the Italian seismic network data [cite: 2].
*   `"ethz"`: Trained on regional data from Switzerland [cite: 8].
*   `"geofon"` and `"diting"`: Weights adapted for global broadband stations and the Chinese DiTing dataset, respectively [cite: 16].

**Generalization Performance**: Research indicates that models trained on highly diverse, large-scale datasets like STEAD generally exhibit the best transfer learning and out-of-domain generalization. For example, PhaseNet trained on STEAD frequently outperforms models trained on narrower datasets (like SCEDC) when applied to new, unseen networks, due to the diversity of noise profiles and tectonic settings in the training corpus [cite: 13].

### Input Shapes, Channels, and Window Lengths
Understanding the expected input tensors for these models is critical when processing raw numpy arrays:

*   **Sampling Rate**: Almost all standard models in SeisBench (PhaseNet, EQTransformer, GPD) natively expect data sampled at **100 Hz** [cite: 3, 7]. Providing data at different rates without resampling will lead to severe degradation in predictive accuracy because the convolutional filters are trained on specific temporal frequencies.
*   **Window Length**: 
    *   *PhaseNet* natively expects an input window of **3000 samples** (which equates to 30 seconds at 100 Hz) [cite: 1, 7].
    *   *EQTransformer* expects a longer input window of **6000 samples** (60 seconds at 100 Hz) to leverage long-term temporal dependencies [cite: 1].
*   **Channel Order and Shape**: Deep learning models generally expect a 3-component input in the shape of `(3, N)` where 3 is the channel dimension and N is the number of samples. The rigorously expected channel order is **Z, N, E** (Vertical, North, East) [cite: 8, 17]. Supplying data in E, N, Z order or failing to account for specific channel orientations can confuse the spatial convolutions, particularly for S-wave detection which relies heavily on horizontal particle motion.

---

## 3. Data Pipeline: Loading .npz Files and Preparing Input

If your continuous waveform data is stored in NumPy `.npz` files, it must be carefully preprocessed before being fed into SeisBench. Let us assume the `.npz` file contains the following structure:
*   `data`: An array of shape `(12000, 3)` representing 120 seconds of data.
*   `dt`: A float representing the sampling interval (e.g., `0.005` for 200 Hz).
*   `channels`: An array or list of strings like `["DPE", "DPN", "DPZ"]`.

### Transposing and Channel Ordering
The model expects `(3, N)` while the data is `(N, 3)`. Furthermore, the channels `["DPE", "DPN", "DPZ"]` represent East, North, and Vertical components. We must transpose the array and reorder the channels to **Z, N, E**.

```python
import numpy as np

# 1. Load the .npz file
file_data = np.load("waveform_data.npz")
raw_array = file_data["data"]  # Shape: (12000, 3)
dt = file_data["dt"]           # e.g., 0.005 (200 Hz)
channels = file_data["channels"] # e.g., ["DPE", "DPN", "DPZ"]

# 2. Transpose to (3, N)
transposed_array = raw_array.T  # Shape becomes (3, 12000)

# 3. Identify and sort to Z, N, E
# Create a mapping of the current indices
chan_list = list(channels)
z_idx = chan_list.index("DPZ")
n_idx = chan_list.index("DPN")
e_idx = chan_list.index("DPE")

# Reorder array to Z, N, E
zne_array = transposed_array[[z_idx, n_idx, e_idx], :]
```

### Resampling
If `dt = 0.005`, the sampling rate is 200 Hz. SeisBench models expect 100 Hz. We must resample the array. While `scipy.signal.resample` can be used on raw numpy arrays, the seismological gold standard for avoiding aliasing and handling metadata is to leverage **ObsPy**. Furthermore, SeisBench models are natively designed to ingest ObsPy `Stream` objects, which makes conversion to ObsPy highly beneficial. 

By wrapping the NumPy array in an ObsPy stream, we can utilize `stream.resample(100.0)` which safely applies an anti-aliasing lowpass filter before decimation [cite: 18, 19].

### Handling Sliding Windows
The loaded data contains 12,000 samples (which at 100 Hz will become 120 seconds). PhaseNet expects 30 seconds (3000 samples). **You do not need to manually slice your NumPy array.** 
When a SeisBench model is passed an ObsPy `Stream` via the `annotate()` or `classify()` methods, it automatically manages a sliding window approach internally [cite: 15]. The model will chop the continuous stream into appropriate lengths (e.g., 3000 samples), predict on each window, handle overlaps using a defined stacking mechanism (e.g., maximum probability across overlapping predictions), and seamlessly merge the results back into a continuous output [cite: 15].

---

## 4. ObsPy Integration: Bridging NumPy and SeisBench

To utilize the automatic preprocessing, sliding windows, and post-processing of SeisBench, the ideal approach is to convert the `(3, N)` NumPy array into an ObsPy `Stream` object [cite: 1]. 

### Constructing obspy.Trace and obspy.Stream
An ObsPy `Stream` is a collection of `Trace` objects. Each `Trace` contains a 1D NumPy array representing a single channel, accompanied by a `stats` dictionary [cite: 18, 20].

To ensure SeisBench's `annotate()` and `classify()` work flawlessly, the `stats` dictionary must at minimum contain:
*   `network`, `station`, `location`, `channel`
*   `starttime` (as an `obspy.UTCDateTime` object)
*   `sampling_rate` (derived from `1.0 / dt`)

```python
from obspy.core import Trace, Stream, UTCDateTime

# Assuming zne_array is shape (3, N) at 200 Hz
sampling_rate = 1.0 / dt
start_time = UTCDateTime("2023-01-01T00:00:00.000000Z")
network, station, location = "XX", "STA01", ""

# Map to standard Z, N, E channel codes (e.g., DPZ, DPN, DPE)
mapped_channels = ["DPZ", "DPN", "DPE"]

traces = []
for i, chan_code in enumerate(mapped_channels):
    stats = {
        "network": network,
        "station": station,
        "location": location,
        "channel": chan_code,
        "starttime": start_time,
        "sampling_rate": sampling_rate
    }
    # Create Trace; ensure data is float32, as deep learning models expect floats
    tr = Trace(data=zne_array[i, :].astype(np.float32), header=stats)
    traces.append(tr)

# Assemble the Stream
stream = Stream(traces=traces)

# Now, we use ObsPy to safely resample to the model's expected 100 Hz
stream.resample(100.0)
```

By ensuring the channels end in `Z`, `N`, and `E`, SeisBench will automatically detect the component order during the `annotate()` phase [cite: 15].

---

## 5. Running Inference with SeisBench Models

SeisBench provides a dual-tiered API for running inferences: `model.annotate()` for continuous probability traces, and `model.classify()` for extracted, discrete event picks [cite: 11, 15]. 

### The `annotate()` API
`model.annotate(stream)` takes an ObsPy `Stream` and returns a new ObsPy `Stream` containing the characteristic functions (probability curves) for each output class (typically P-wave, S-wave, and Noise) [cite: 15]. 

*   **Input**: Accepts an ObsPy `Stream`.
*   **Parameters**:
    *   `overlap`: Defines the overlap between sliding windows. Can be defined as a fraction (e.g., `0.25`) or in samples. Higher overlaps decrease edge effects but increase compute time [cite: 10].
    *   `batch_size`: Number of windows processed simultaneously. Increase this if GPU memory permits [cite: 21].
    *   `blinding`: Number of samples at the edges of the window to ignore during merging, useful for preventing edge artifacts in convolutional padding [cite: 21].
*   **Output Format**: A `Stream` where the `.data` payload contains values between 0.0 and 1.0 (probabilities), and the channel names are renamed to `PhaseNet_P`, `PhaseNet_S`, etc. [cite: 15].

### The `classify()` API
For most catalog-building workflows, `model.classify(stream)` is superior. It internally calls `annotate()`, but then subsequently runs peak-finding algorithms on the probability traces to return discrete timestamps and metadata for the picks [cite: 15].

```python
# Move model to GPU if available (essential for batch processing)
phasenet_model.to_preferred_device(verbose=True)

# Run discrete classification
classify_out = phasenet_model.classify(
    stream, 
    P_threshold=0.3, 
    S_threshold=0.3, 
    overlap=0.25, 
    batch_size=256
)
```

The output of `classify()` is a `ClassifyOutput` object [cite: 17, 22]. This container standardizes outputs across models. Its primary attribute is `.picks`, which is a `PickList` object—an iterable containing metadata for every detected phase.

---

## 6. Pick Extraction from Model Output

Converting deep learning probabilities to exact timestamps is a sensitive task.

### Probability Thresholds
Models like PhaseNet output a probability score representing the model's confidence that a given sample is the true onset of a phase [cite: 15]. 
*   **Optimal Thresholds**: While `0.5` is the mathematical center point, empirical applications of SeisBench models often utilize lower thresholds, ranging from **`0.1` to `0.3`**, paired with strict phase association tools later in the pipeline [cite: 13, 21]. A threshold of `P_threshold=0.3` and `S_threshold=0.3` provides an excellent balance between recall and precision, accommodating overlapping events and varying noise conditions [cite: 13, 21].

### Using `ClassifyOutput` and `PickList`
When using `model.classify()`, SeisBench handles the peak-picking using SciPy internally. The returned `ClassifyOutput.picks` (`PickList`) contains objects with fields such as `trace_id`, `start_time`, `peak_value` (confidence), and `phase` [cite: 17].

To extract this into a usable format, SeisBench provides an extremely convenient utility: `to_dataframe()` [cite: 17, 22].

```python
# Assuming classify_out is the output of model.classify(stream)
picks_list = classify_out.picks

# Convert directly to a Pandas DataFrame
picks_df = picks_list.to_dataframe()

# View the DataFrame
print(picks_df[['trace_id', 'start_time', 'peak_value', 'phase']])
```

### Addressing Resampling in Output Indices
If you need the raw array indices of the pick relative to your *original* 12000-sample array (at 200 Hz), relying strictly on time is the safest approach. Because ObsPy maintains absolute UTC timing, the `start_time` output by `classify()` (which operates on the 100 Hz data) maps flawlessly back to the original continuous time framework.

To get the index in the original array:
```python
original_start_utc = UTCDateTime("2023-01-01T00:00:00.000000Z")
original_sampling_rate = 200.0

picks_df["original_index"] = ((picks_df["start_time"] - original_start_utc) * original_sampling_rate).astype(int)
```
This safely bypasses the complexities of manual sampling rate conversion and eliminates index drift.

### Multiple Picks per Trace
Because `classify()` uses sliding windows and Scipy's `find_peaks` over continuous probability curves, it naturally handles multiple events within a single 120-second array. The resulting `PickList` simply appends each detected peak over the specified threshold, making it highly robust to earthquake swarms or aftershocks [cite: 22, 23].

---

## 7. Common Pitfalls

1.  **Channel Ordering Mismatches**: Supplying East, North, Vertical instead of Vertical, North, East (Z, N, E) is the most frequent silent error [cite: 17]. While a 1D CNN might still detect P-waves (since they appear strongly on all components), S-wave accuracy will plummet because the model's filters are spatially tuned to expect horizontal shear energy on the 2nd and 3rd input channels. Ensure ObsPy traces have channel codes correctly ending in Z, N, and E [cite: 8, 15].
2.  **Integer vs. Float Data Types**: Raw NumPy `.npz` data is frequently stored as `int32` (raw digitizer counts). PyTorch and SeisBench models expect `float32` tensors [cite: 7]. When constructing ObsPy traces, explicit conversion using `.astype(np.float32)` is mandatory to prevent PyTorch crashes.
3.  **Data Normalization**: You generally **do not** need to apply min-max or zero-mean/unit-variance normalization to the data manually before passing it to `annotate()` or `classify()`. SeisBench models and their PyTorch implementations include data normalization as an internal, built-in preprocessing layer applied to individual sliding windows on the fly [cite: 7]. Detrending the data (removing the mean) is, however, highly recommended.
4.  **Hardware Acceleration (GPU vs CPU)**: Model inference on CPU is painfully slow for large datasets. You must explicitly move the SeisBench model to the GPU. Use `model.to_preferred_device(verbose=True)`. If you wish to force CPU inference for memory reasons, you can use `model.cpu()` as it inherits from standard PyTorch modules [cite: 10, 15].
5.  **Memory Issues with Batch Processing**: If you process 100 files simultaneously by appending them all into a massive ObsPy `Stream` and passing it to `.classify()`, you may trigger a CUDA Out of Memory (OOM) error. The `batch_size` argument in `classify()` controls the tensor batching, but iterating through your `.npz` files in a loop and saving individual CSVs is more robust than holding gigabytes of characteristic functions in RAM [cite: 21].
6.  **Missing Channels**: If an `.npz` file only contains Z and N components, standard 3-component PhaseNet will throw an error. In operational scenarios, you must inject arrays of zeros for missing components, or utilize specialized models designed for 1-component or missing-data environments.

---

## 8. Working End-to-End Code Example

The following script encapsulates the entire pipeline: reading a NumPy `.npz` file, reshaping, resampling, pushing through an ObsPy Stream into SeisBench's PhaseNet, and extracting precise event indices to a CSV file.

```python
import numpy as np
import pandas as pd
import obspy
from obspy.core import Trace, Stream, UTCDateTime
import seisbench.models as sbm
import os

def process_seismic_npz(npz_path, output_csv):
    """
    Load an npz file, run SeisBench PhaseNet picking, and export to CSV.
    Assumes .npz structure: 'data' (N, 3), 'dt' (float), 'channels' (list of strings).
    """
    print(f"Loading data from {npz_path}...")
    
    # 1. Load Data
    # For demonstration, let's create a dummy .npz file structure if it doesn't exist
    if not os.path.exists(npz_path):
        dummy_data = np.random.randn(12000, 3) * 100  # 12000 samples, 3 channels
        np.savez(npz_path, data=dummy_data, dt=0.005, channels=["DPE", "DPN", "DPZ"])
    
    file_data = np.load(npz_path)
    raw_array = file_data["data"]    # Shape: (N, 3)
    dt = file_data["dt"]             # e.g., 0.005
    channels = list(file_data["channels"])
    
    # 2. Data Formatting & Channel Reordering to Z, N, E
    # Transpose to (3, N)
    transposed_array = raw_array.T
    
    # Map indices
    try:
        z_idx = channels.index("DPZ")
        n_idx = channels.index("DPN")
        e_idx = channels.index("DPE")
    except ValueError as e:
        raise ValueError("Channels must contain DPZ, DPN, DPE.") from e
    
    zne_array = transposed_array[[z_idx, n_idx, e_idx], :]
    
    # 3. ObsPy Stream Integration
    print("Building ObsPy Stream and resampling...")
    original_rate = 1.0 / dt
    target_rate = 100.0  # Required by SeisBench PhaseNet
    start_time = UTCDateTime("2023-01-01T00:00:00.000000Z")
    
    traces = []
    # Loop over Z, N, E order
    for i, chan_code in enumerate(["DPZ", "DPN", "DPE"]):
        stats = {
            "network": "XX",
            "station": "STA",
            "location": "00",
            "channel": chan_code,
            "starttime": start_time,
            "sampling_rate": original_rate
        }
        # Explicit conversion to float32 is critical for PyTorch models
        tr = Trace(data=zne_array[i, :].astype(np.float32), header=stats)
        traces.append(tr)
        
    stream = Stream(traces=traces)
    
    # Detrend data before resampling (best practice in seismology)
    stream.detrend("demean")
    
    # Resample to 100 Hz for PhaseNet
    if original_rate != target_rate:
        stream.resample(target_rate)
        
    # 4. Load SeisBench Model
    print("Loading Pretrained PhaseNet model...")
    model = sbm.PhaseNet.from_pretrained("stead") # Highly generalized weights
    model.to_preferred_device(verbose=True)       # Use GPU if available
    
    # 5. Run Inference
    print("Running classification inference (sliding window approach)...")
    # Using sensible thresholds of 0.3 for both P and S arrivals
    classify_out = model.classify(
        stream,
        P_threshold=0.3,
        S_threshold=0.3,
        overlap=0.25,      # 25% window overlap to prevent edge issues
        batch_size=64      # Lower batch size for safety on average hardware
    )
    
    # 6. Extract Picks & Convert Indices
    print("Extracting picks...")
    pick_list = classify_out.picks
    
    if len(pick_list) == 0:
        print("No picks detected over the specified threshold.")
        return
        
    # Leverage SeisBench's built in dataframe converter
    picks_df = pick_list.to_dataframe()
    
    # Map the detected UTC time back to the absolute index in the ORIGINAL 200 Hz array
    # original_start_utc + (index / original_rate) = pick_time
    picks_df["original_index"] = ((picks_df["start_time"] - start_time) * original_rate).astype(int)
    picks_df["resampled_index"] = ((picks_df["start_time"] - start_time) * target_rate).astype(int)
    
    # Keep only relevant columns for clean output
    out_df = picks_df[["trace_id", "phase", "start_time", "peak_value", "original_index", "resampled_index"]]
    
    # 7. Output to CSV
    out_df.to_csv(output_csv, index=False)
    print(f"Successfully processed {len(out_df)} picks. Saved to {output_csv}")
    print(out_df)

if __name__ == "__main__":
    process_seismic_npz("test_waveform.npz", "picks_output.csv")
```

**Sources:**
1. [core.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlfbmI-IaVgC7A7_VEHBbOa2SQLcQDbdShn5FncKy_pZkh0KdSp-vmSR1311TYiyrpAe4h-a5jftrRn8zAdHO_ZFXy80VpfVNw7Y9meZDHUxUg7QWbXTKktF49fa1Jww==)
2. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEsKhcosFbxt6tSxi0cpv3CO1PnnUNEkuhbVkFfHkhEci_LTLhJ5Nfdlnx8UiX14-X2oUZl5DgkdpYqeWgPPepU14UlYrz1xQWSHgetPNecy0cD7dduBm3CJMxtC2668DJi5Q==)
3. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQENdmfami98iq5a1lM1UISchdEyy92bUm9yAFOgIcdILT4RgrMQo1C2LKMgLYfdKpRSHUnTdJit9VigrVBGTYG8HmZUuEV-CNa8ETTVlMcfjkrIcuB3VhgvJw==)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlJdDsx8fWQcX2U2QZTnUhZmFSf78wz8YoIo6aq2NOV5xl89YzReVYq6utipm_1p_xMaVESDlhWRJM_zIKI4WjmZwX84rrRnZ9-qNVe1SAQ3_d3QHDAE8=)
5. [helmholtz.software](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDUJdm5OewLqwGkpGdmRo5MaJxej7vPfuL8c3Pffhj-JGM3gjjPRgGSGi4RCogHhw9dyEN31-11gi_JARCdTLGgWgF_e_gIRIXvxz1wrOebTZU0lJjTA6ykAXctU99L_VT27I=)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHaQBHc3DZ6ZMGkMzCa2wRswWu1Rz0JyxlkJWFu4xd8ZqUL206PS5iuYLkz0xkxGYmA78LlMVymCbDR2VKr85YklNGykHMCu-FiqsN3e6usIVGhqetd5tBTB_NYw==)
7. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHQs1fr8cr315y5_ep_hfrvr-5hSFOoA9IOAFvDq76BDAGrvzA3HtVRxQhFAwslU8_NrVIvCFQyNxTJG65YtvGr6DJqu7NyQ9mMGX1ktlFROM2u_ywonAbWse-TGfA9UD32XAFT6Xo12aVHopWLqkCZ9qFtzvRi60F6vtm8D75NPNQqTVY1WvsNlfT1qpPoeN5NtJxZIQcdDFCqpL8IuHlJXA==)
8. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmNmJ_G2k-xkVwreIXvztlpXRxT-coL-kAmpqaj3vWhBibu2XQDDYFSiwguPPSujliFdc2Q8enULEI6aDt94-XQc93Ohd7WWUHRBdhhPxNUK3mJMVf3yWsFPS8sUqFVpSZzPcBfCrwd1T7iDIshFZccnGHQuFhC5zAsYkJaem_aAWc)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHbfEw510pgKBNNJu_RuArOg5BUvcMiXBEN1LEjBOE0ZDbpArruE0Frj3WUhOd55uc4BgAbm6iHgwnaQVEtZumDy65lF905vggILGG7ESz-qJy4adrXwIBmnxObiSZ1PdBsys37mlQ4F4pH4gkmvHFAVbjpoMfV-yX91wwz_GYTa0E)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjeHT4HqvPHAj6w_PLGYLgAfowBo_OaHU7NwHjsgxE0usffREG3AxzLFkRl9GzzGtz-Se7-ZkgS-qfAHajFTz9A85KPexJsTi-rkUO5DX35MrW6p0XxNf4vlt2MkALK1H3nURD2Q==)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEY0kuS_h-gK4xLDbwjiai6V1cyGX4vvvMBcD1EMJ1Hur8qaygSC09QUUZ2lHzfKQu9Vs5Fg_kgeHBnUHlRPlPOEzYa-rGXDTE5A1kO8wprmPgIH5RhKZCG5v7IikcuNq7-PHwhfHMPsgMagl3b0_YthSleeBbD7zqW7LY=)
12. [ieee.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqfoi02Me50BnwctLp3ePx6QLffb-qGdD4K18ehNJiltEpBn4VTMEe3T37_4sHlcuAocs5uJ2qUIRI2JSOxGAySzvrYaTQhe8g4Ct-oyujU4HeN8OnZCAv7lovOc4376iHgAMsilfcTGST7XLbMWMVWLTeBw==)
13. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEaj3waz6IFmXNGuU-TJqK9YkenrdBOxPqldCeorQ8YQMXZnlarQM_ZtcRcQyRPrpbkeb-NU29YANkd1WpJ9asHK3o23KK9oYa8tNdYgPAR2VzWTon5zhdryT_BUxjCR-B-VPeal3BkoQ==)
14. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqb8KorkufKHaOdSDKHWXhoZVUH8h-kMFCe2AtFmscRWZ_eEC8Zt-SN-ug9tWRt9pJzEmw_cmZBQgnOuAIA9iNDKjQ3RWCqlxjHKuOAayGrVHYjT_1rjFLyiG0iYOVbPq0DTpL8lF5LwH6tznPdg==)
15. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEoOBsVHBe9tWRdXiyDgi5JFherqGHDbrNKCqF6gebCqV0crhDXEkJB6zgMhhbyxFcN2A43KD_1qJv6o_oIO-qkPWCESzVEGGtWHyI2VbQJUOJH_4j34KEZIfDq_rAidLRJFctiXFiWCB8cLz4H0H4ShB2DMBesYYOCRM35CFPfhTg5dexCl3zg_H5GtFbM9RH44ZHkL_Go4so=)
16. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEFji9Lcfbm9z4hzAFZ8rCbyibl3Ll98xcwbX4l9rpwCCKrCUAjJ7y-ED-djUmDjLhqSw5utROMmbCcXNFNLpR4nUiFgAQcf71AEBiQ4pPn9RQ1579eHbBTfcSX5giJK4wz)
17. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjM5wmYK73Qvoc5BSmjh6g-Sp3SnPDObiOPP1V_81IQStGAx3Zp0OYxcw6pokwutmzIaj0lpymxoOt14LghDmOakgiE13eU2Sg_dTJrZT17D-3UBMmzdmguHqMQHjwpMekyOSjNmjFI6p7et87uFn53v-vNu8kUq68zl21nSo=)
18. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZibYR6X2-wGm2hHceLm8O45S7xaum2daos258VGDtC9raYz0AQVP9nPe76FKuY9yZn4BuCo-1Otd_YZW5k1ywocUGU1ROVyUrMooLxAfzGJCcgHmQup0IMmgg2Xxxtpl8-ckbtGCrLMoWRtqEf_qeijmnn4LO_xe7iMxxQHv8AJqEU4Y_)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGZWcTno7JI_mLcenhV3M-K6A3F2b49Ntu6PEM7YWVrhyDTxZcpQ-iwCIVimYPaSLhUqFli_Th_3hvZQFSSt7T0PlxPuWv67_73JJ8N8GBna4HJDe5nnqk19AENeTtUEocq7NOx06XWRWajYtbwnNYpWkt93RVH2SH3o8mAjm9V)
20. [academia.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGsatmAHMysPNrwC0epmssyBG54_UPwzOd9G9Qh8IyYRz0WwF2PqRlW-OCJ4VnGOELxOunmJcmzNPm_8n6cmEdlpFL1-uvbexuMD9S3i3jy_fG6ZThiv_gxr1THIxEhMCQ0I8Rq-b5NC1pkNKU=)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1NWn9L0JWPRqpvLP8olOp4XuoTm4Jk7MHjGysgn4fbCPcy-0fvzHcPGfmKyZqIHJhBxzK0Z9x1X4vIHFd82-ki8aRx7Ehk23vfQkdGcFeAOzMT_r5AT5_gGI8-uyJiA==)
22. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQETHlmsf6PEaKHuQMTfEFaM8z5JW0Bb1DZa-3OdkkioOsc0YxRcRGU4yLMh8IrJ8bnOEiILJTMGolg-FkZPPdRRY1KBzbWS1zng8t6fH8YqctWdD9hP21EWVGLZXc0IopE_DtgrdFOMsHLkH7VAThOyTwROaHzpvsgmmu1EowXbxBoz0wMSRhM=)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGg78I_w8hVvg3RcDI088iAJANqbeKE7JMXSxlypEW7YswDNbCbsVT2sIFc5068npBroSVh4IDr_meFnTuw_aJx-sYR7I4zBhZazLkUHtM1M0cwlhOTwpsqufUsSfC17M_VEFW0jWAx)
