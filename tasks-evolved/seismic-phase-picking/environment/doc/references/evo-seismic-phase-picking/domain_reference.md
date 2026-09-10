# Domain Reference for evo-seismic-phase-picking

**Responsibility**: Model loading, inference execution, pick extraction from model output, index conversion from resampled to original coordinates, and CSV output generation

**Key functions to implement**: load_phasenet_model, run_phase_picking, extract_picks_to_dataframe, convert_pick_to_original_index, process_all_traces_to_csv

---

## 1. SeisBench Installation and Imports


SeisBench is an open-source Python toolbox designed specifically for machine learning applications in seismology, significantly reducing the overhead required to train and apply deep learning algorithms [cite: 4, 6].

### Installation

The recommended and most stable method to install SeisBench is via the Python Package Index (PyPI). It is highly advisable to install the library within an isolated virtual environment (e.g., using `conda` or `venv`) to prevent dependency conflicts with other scientific libraries [cite: 6].

```bash

## 2. Pretrained Models for Phase Picking


SeisBench provides a robust suite of deep learning models designed to detect seismic events and pick the precise arrival times of compressional (P) and shear (S) waves [cite: 11].

## 5. Running Inference with SeisBench Models


SeisBench provides a dual-tiered API for running inferences: `model.annotate()` for continuous probability traces, and `model.classify()` for extracted, discrete event picks [cite: 11, 15].

## 6. Pick Extraction from Model Output


Converting deep learning probabilities to exact timestamps is a sensitive task.

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