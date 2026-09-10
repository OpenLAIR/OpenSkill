# Comprehensive Guide to Gravitational Wave Matched Filtering with PyCBC 2.8.5

**Key Points**
*   **Data Reading**: `pycbc.frame.read_frame()` allows direct extraction of strain data from standard `.gwf` files. Omitting time bounds reads the entire file automatically [cite: 1, 2].
*   **Pre-Conditioning**: LIGO data requires strict conditioning: high-pass filtering (typically at 15–20 Hz) to remove seismic noise, resampling, and aggressive edge cropping to eliminate filter wraparound artifacts [cite: 3, 4, 5].
*   **PSD Estimation**: For real detector noise, empirical Power Spectral Density (PSD) estimation using Welch's method (standard 4-second segments) is mandatory. The PSD must be interpolated to the data's frequency resolution and time-truncated using `inverse_spectrum_truncation` [cite: 5, 6, 7].
*   **Waveform Templates**: PyCBC generates theoretical models using `get_td_waveform` or `get_fd_waveform`. Approximants like `IMRPhenomD` and `SEOBNRv4_opt` are ideal for full inspiral-merger-ringdown phases, whereas `TaylorT4` is restricted to the inspiral regime [cite: 8, 9, 10].
*   **Matched Filtering**: The `matched_filter` function returns a complex Signal-to-Noise Ratio (SNR) time series. Identifying the peak requires extracting the absolute magnitude and cropping out extensive edge artifacts (e.g., 8 seconds from the start, 4 seconds from the end) [cite: 4, 11].
*   **Pitfalls**: Time-domain templates must be explicitly resized to match the data length and cyclically shifted to align the merger peak; failure to do so will offset the SNR timestamp or raise errors [cite: 4, 7, 12].

**Matched Filtering Overview**
Matched filtering is the statistically optimal algorithm for detecting known signals buried in stationary Gaussian noise. In gravitational-wave astronomy, this technique involves correlating a theoretical template of a compact binary coalescence (CBC) against the noisy detector strain data, weighted by the noise floor's spectral characteristics (the PSD) [cite: 13, 14].

**The PyCBC Framework**
PyCBC is the primary open-source software suite utilized by the LIGO-Virgo-KAGRA (LVK) collaboration to conduct matched-filter searches. Version 2.8.5 provides robust Python wrappers around the core C-based LALSuite libraries, offering highly optimized routines for Fourier transforms, time-series manipulation, and waveform generation [cite: 15, 16, 17].

## 1. Reading GWF Frame Files with PyCBC

The standard data format for gravitational-wave observatories is the Gravitational-Wave Frame (GWF) file. These files containerize time-stamped strain data alongside auxiliary channels and data-quality flags [cite: 18, 19]. PyCBC provides a streamlined API to read these files directly into memory as `TimeSeries` objects.

### Function Signature and Parameters
The core utility for local frame reading is `pycbc.frame.read_frame()`. The precise function signature is:
```python
pycbc.frame.read_frame(location, channels, start_time=None, end_time=None, duration=None, check_integrity=False, sieve=None)
```
*   `location` (str): The file path to the `.gwf` frame file (or a frame cache) [cite: 1, 2].
*   `channels` (str or list): The specific data channel to extract, such as `'H1:GWOSC-16KHZ_R1_STRAIN'` [cite: 2, 18, 20].
*   `start_time` and `end_time` (int or float): The GPS timestamps defining the segment of data to read [cite: 1, 2].

### Behavior with Unspecified Bounds
If `start_time` and `end_time` are omitted (or set to `None`), `read_frame()` will default to reading the entire contiguous block of data available within the specified GWF file [cite: 2]. 

### Determining the Available Time Range
When confronted with a GWF file of unknown bounds, you can read the entire file into memory and programmatically inspect the resulting `TimeSeries` properties to determine the valid GPS time range. The `TimeSeries` object possesses `.start_time` and `.end_time` attributes that return precise `LIGOTimeGPS` objects.

### Code Example: Reading a GWF File
```python
from pycbc.frame import read_frame

# Define file path and channel
gwf_file = "H-H1_GWOSC_O2_4KHZ_R1-1181155328-4096.gwf"
channel_name = "H1:GWOSC-4KHZ_R1_STRAIN"

# Approach A: Reading the entire file to determine the range
ts_full = read_frame(gwf_file, channel_name)
available_start = ts_full.start_time
available_end = ts_full.end_time
print(f"File contains data from GPS {available_start} to {available_end}")

# Approach B: Reading a specific 32-second segment
start_gps = 1181155328
end_gps = 1181155360
strain_data = read_frame(gwf_file, channel_name, start_time=start_gps, end_time=end_gps)

# The return type is a pycbc.types.timeseries.TimeSeries object
print(type(strain_data)) 
```
*Note on return types: If a single string is passed to `channels`, it returns a single `TimeSeries`. If a list of strings is passed, it returns a list of `TimeSeries` objects corresponding to each channel [cite: 2].*

## 2. Data Conditioning for Matched Filtering in PyCBC

Raw strain data from ground-based interferometers is dominated by extreme low-frequency noise (such as seismic activity and suspension thermal noise) and sharp spectral lines. Attempting to matched-filter unconditioned data will severely compromise the numerical stability of the Fast Fourier Transforms (FFTs) and pollute the SNR output. Therefore, a strict data conditioning pipeline is required [cite: 3, 5, 20].

### Highpass Filtering
The first step is to suppress the overwhelmingly loud, uncalibrated low-frequency noise using a high-pass filter. In PyCBC, this is typically done using `pycbc.filter.highpass()` or the `TimeSeries.highpass_fir()` method [cite: 3, 5, 15]. 
*   **Standard Cutoff Frequency**: For LIGO data, the standard cutoff frequency is between **15 Hz and 20 Hz** [cite: 3, 4, 5, 13]. Frequencies below 15 Hz consist of seismic wall noise that cannot be calibrated accurately and will swamp higher-frequency astrophysical signals [cite: 3].

### Resampling
LIGO data is frequently distributed at a high sampling rate of 16384 Hz. To drastically reduce computational cost and memory overhead during template generation and FFTs, the data is usually downsampled [cite: 5, 20]. 
*   **Standard Resampling Rate**: 4096 Hz or 2048 Hz is standard for CBC searches [cite: 3, 5, 15, 20]. You can use `TimeSeries.resample(delta_t)` or `pycbc.filter.resample_to_delta_t()` [cite: 5].

### Cropping Filter Artifacts
Applying FIR highpass and anti-aliasing filters to a time series inevitably introduces filter "wraparound" artifacts at the boundaries. Because Fourier-based filters assume the data is cyclical, the sudden discontinuities at the start and end of the segment cause severe ringing [cite: 5, 6, 7]. 
*   **Standard Crop Amount**: It is mandatory to use the `TimeSeries.crop()` method to sever the corrupted edges. The standard practice is to remove **2 to 4 seconds** from both the beginning and the end of the time series immediately after highpassing and resampling [cite: 4, 5, 6].

### PSD Estimation and Inverse Spectrum Truncation
Optimal matched filtering requires weighting the frequency bins by the noise amplitude, effectively whitening the data [cite: 6, 13, 21]. 
1.  **Computing the PSD**: The `TimeSeries.psd(seg_len, seg_stride)` method invokes Welch's method to estimate the PSD [cite: 3, 6, 7]. 
    *   **Standard Welch Segment Length**: A segment length of **4 seconds** is the community standard [cite: 3, 6, 7, 21]. A 4-second segment provides a frequency resolution of \(0.25\) Hz, which is fine enough to resolve narrow spectral lines (like 60 Hz power mains) without suffering from excessive variance. The `seg_stride` is usually half the segment length (2 seconds) to provide 50% overlap [cite: 3].
2.  **Interpolation**: The PSD computed via Welch's method over 4-second segments has `delta_f = 0.25 Hz`. However, your overall data segment might be 32 seconds long (`delta_f = 1/32 Hz`). You must interpolate the PSD to match the data's frequency resolution using `pycbc.psd.interpolate()` [cite: 6, 7, 22].
3.  **Inverse Spectrum Truncation**: When the data is divided by the PSD in the frequency domain, it is mathematically equivalent to convolving the data with the inverse Fourier transform of the PSD in the time domain. If the PSD contains sharp features, its time-domain impulse response will be infinitely long, causing filter wraparound that corrupts the entire data segment. The `pycbc.psd.inverse_spectrum_truncation()` function forcibly truncates the time-domain equivalent of `1/PSD` to a specified maximum length (typically 4 seconds) [cite: 6, 7, 23].

### Complete Conditioning Pipeline Code
```python
from pycbc.filter import highpass, resample_to_delta_t
from pycbc.psd import interpolate, inverse_spectrum_truncation

def condition_data(strain_ts):
    # 1. Highpass filter at 15 Hz to remove seismic noise
    conditioned = highpass(strain_ts, 15.0)
    
    # 2. Resample to 2048 Hz to save computation time
    conditioned = resample_to_delta_t(conditioned, 1.0/2048)
    
    # 3. Crop 2 seconds from both ends to remove FIR filter wraparound
    conditioned = conditioned.crop(2, 2)
    
    # 4. Estimate PSD using Welch's method with a 4-second segment length
    # Overlap stride defaults to 50% (2 seconds) if not explicitly set
    psd = conditioned.psd(4)
    
    # 5. Interpolate PSD to match the fine frequency resolution of the data
    psd = interpolate(psd, conditioned.delta_f)
    
    # 6. Apply Inverse Spectrum Truncation
    # Truncate the filter length to 4 seconds. Frequencies below 15Hz are ignored.
    max_filter_len = int(4 * conditioned.sample_rate)
    psd = inverse_spectrum_truncation(psd, 
                                      max_filter_len, 
                                      low_frequency_cutoff=15.0)
    
    return conditioned, psd
```

## 3. Generating Waveform Templates with PyCBC

To perform matched filtering, we must generate theoretical waveform templates corresponding to expected astrophysical signals [cite: 3, 13]. PyCBC provides standard interfaces: `pycbc.waveform.get_td_waveform()` for time-domain generation and `get_fd_waveform()` for frequency-domain generation [cite: 3, 9, 10, 15].

### Approximants: SEOBNRv4_opt, IMRPhenomD, and TaylorT4
*   **SEOBNRv4_opt**: A highly optimized Time-Domain Effective-One-Body approximant. It models the full inspiral, merger, and ringdown (IMR) phases for aligned-spin binary black holes [cite: 8, 9, 24]. It is highly accurate but more computationally expensive than phenomenological models.
*   **IMRPhenomD**: A Frequency-Domain phenomenological model. It also captures the full IMR phases [cite: 3, 8, 15]. Because it is natively formulated in the frequency domain, it is exceptionally fast. Note: While natively frequency-domain, PyCBC allows calling `IMRPhenomD` via `get_td_waveform` (which will generate it in FD and mathematically transform it to TD under the hood) or via `get_fd_waveform` [cite: 3, 9, 15].
*   **TaylorT4**: A Time-Domain Post-Newtonian (PN) approximant. **Crucially, TaylorT4 models only the inspiral phase** [cite: 8, 9, 10]. It terminates abruptly at the Innermost Stable Circular Orbit (ISCO). Therefore, TaylorT4 is excellent for binary neutron stars (BNS) where the merger occurs at extremely high frequencies, but it requires special handling or avoidance for high-mass binary black holes, as the entire signal might terminate below your frequency cutoff [cite: 10, 25].

### Required Parameters
The standard function call requires specifying component masses (`mass1`, `mass2` in solar masses), a starting frequency (`f_lower`), and the desired resolution (`delta_t` for time-domain, `delta_f` for frequency-domain) [cite: 3, 9, 15].
*   **Standard `f_lower`**: The standard value is **20 Hz** (or 15 Hz). It is critical that `f_lower` aligns with or is slightly higher than the data conditioning high-pass cutoff [cite: 3, 4]. Setting `f_lower` lower than necessary drastically increases the length of the time-domain array, wasting memory and computation time [cite: 4].
*   **`delta_t` Matching**: The `delta_t` of the template **must exactly match** the `delta_t` of the conditioned data. If they differ, the matched filter will raise a `ValueError` indicating a length or resolution mismatch [cite: 4, 12].

### Code Example: Generating Templates
```python
from pycbc.waveform import get_td_waveform, get_fd_waveform

# Generating a time-domain SEOBNRv4_opt template
# Returns hp (plus polarization) and hc (cross polarization)
hp_td, hc_td = get_td_waveform(approximant="SEOBNRv4_opt",
                               mass1=30,
                               mass2=30,
                               delta_t=1.0/2048, # Must match data
                               f_lower=20.0)

# Generating a frequency-domain IMRPhenomD template
hp_fd, hc_fd = get_fd_waveform(approximant="IMRPhenomD",
                               mass1=30,
                               mass2=30,
                               delta_f=1.0/32, # Must match data delta_f
                               f_lower=20.0)
```

## 4. Matched Filtering with PyCBC

The matched filter computes the correlation between the template and the data, weighted by the inverse of the PSD. The primary function is `pycbc.filter.matched_filter()` [cite: 11, 26, 27].

### Function Signature
```python
pycbc.filter.matched_filter(template, data, psd=None, low_frequency_cutoff=None, high_frequency_cutoff=None)
```
*   `template`: The waveform (either `TimeSeries` or `FrequencySeries`) [cite: 11, 26, 27].
*   `data`: The conditioned strain data [cite: 11, 26, 27].
*   `psd`: The interpolated and truncated PSD [cite: 11, 26, 27].
*   `low_frequency_cutoff`: The frequency at which to begin the overlap integration. This **must** match the `f_lower` used during waveform generation [cite: 3, 4].

### Return Type and Extracting the SNR
The return type of `matched_filter` is a **complex SNR time series** (`pycbc.types.timeseries.TimeSeries` with complex dtype) [cite: 11, 26, 27]. The complex output contains information about the optimal phase match of the signal [cite: 11, 26]. 

To extract the physical, real-valued Signal-to-Noise Ratio, you must take the absolute magnitude of the complex time series [cite: 3, 4, 28].
```python
snr_complex = matched_filter(hp_td, conditioned, psd=psd, low_frequency_cutoff=20.0)
snr_real = snr_complex.abs()  # Equivalent to abs(snr_complex)
```

### Finding the Peak and Cropping Edge Effects
Because matched filtering relies on cross-correlation via FFTs, and because both the PSD and the template itself act as filters, the edges of the resulting SNR time series are heavily corrupted by wraparound ringing [cite: 4].
*   **PSD Corruption**: Truncating the PSD inverse to 4 seconds means 4 seconds of data at both the start and the end of the SNR time series are invalid [cite: 4].
*   **Template Corruption**: The template length introduces an additional block of invalid time at the beginning of the SNR array (equal to the duration of the template from `f_lower` to merger) [cite: 4].

Therefore, you **must** call `.crop()` on the SNR time series. A standard rule of thumb for time-domain filtering is to crop **8 seconds from the start and 4 seconds from the end** [cite: 4].

After cropping, the peak SNR is found using `numpy.argmax()`.

```python
import numpy as np

# Crop corrupted edges (8 seconds front, 4 seconds back)
snr_clean = snr_real.crop(8, 4)

# Find the peak SNR and its exact GPS time
peak_idx = np.argmax(snr_clean)
peak_time = snr_clean.sample_times[peak_idx]
peak_snr = snr_clean[peak_idx]
```

## 5. Complete Working Code Example

Below is a highly robust, reusable Python utility module incorporating all required imports, proper data conditioning, template generation, and peak extraction.

```python
import numpy as np
import pandas as pd
from pycbc.frame import read_frame
from pycbc.filter import highpass, resample_to_delta_t, matched_filter
from pycbc.psd import interpolate, inverse_spectrum_truncation
from pycbc.waveform import get_td_waveform

def compute_matched_filter_snr(gwf_path, channel, m1, m2, approximant="SEOBNRv4_opt"):
    """
    Reads a GWF file, conditions the data, and performs a matched filter 
    search for a specified CBC system.
    """
    # 1. Read the entire frame file
    strain = read_frame(gwf_path, channel)
    
    # 2. Data Conditioning
    # Highpass at 15 Hz to remove seismic wall
    strain = highpass(strain, 15.0)
    # Crop FIR filter wraparound (2 seconds both ends)
    strain = strain.crop(2, 2)
    # Downsample to 2048 Hz
    strain = resample_to_delta_t(strain, 1.0/2048)
    
    # 3. PSD Estimation
    # 4-second Welch segments
    psd = strain.psd(4)
    # Interpolate to match the specific delta_f of the continuous data array
    psd = interpolate(psd, strain.delta_f)
    # Limit time-domain filter length to 4 seconds
    max_filter_len = int(4 * strain.sample_rate)
    psd = inverse_spectrum_truncation(psd, max_filter_len, low_frequency_cutoff=15.0)
    
    # 4. Waveform Generation
    # Ensure f_lower matches the low_frequency_cutoff used in filtering
    f_low = 20.0 
    hp, hc = get_td_waveform(approximant=approximant,
                             mass1=m1,
                             mass2=m2,
                             delta_t=strain.delta_t,
                             f_lower=f_low)
    
    # 5. Template Resizing and Alignment (CRITICAL)
    # Resize the template array to perfectly match the data array length
    hp.resize(len(strain))
    # Cyclically shift the template so the merger peak aligns to the start of the array.
    # Without this, the SNR time series peak will be shifted arbitrarily.
    hp = hp.cyclic_time_shift(hp.start_time)
    
    # 6. Matched Filtering
    snr_complex = matched_filter(hp, strain, 
                                 psd=psd, 
                                 low_frequency_cutoff=f_low)
    
    # Extract absolute SNR and crop boundary corruptions (8s start, 4s end)
    snr_real = snr_complex.abs().crop(8, 4)
    
    # 7. Extract Peak Metrics
    peak_idx = np.argmax(snr_real)
    peak_snr = snr_real[peak_idx]
    peak_time = snr_real.sample_times[peak_idx]
    
    return float(peak_snr), float(peak_time)

# Example usage:
# snr, time = compute_matched_filter_snr("H-H1_GWOSC_O2_4KHZ_R1-1181155328-4096.gwf", 
#                                        "H1:GWOSC-4KHZ_R1_STRAIN", 30, 30)
# print(f"Peak SNR of {snr:.2f} at GPS {time:.3f}")
```

## 6. Common Pitfalls and Version-Specific Issues in PyCBC 2.8.5

When building robust pipelines in PyCBC, several subtle issues can trigger silent logical errors or hard crashes [cite: 4, 12].

### Differing `delta_t` or Length Mismatches
If the template and the data possess differing sampling rates (`delta_t`), PyCBC will immediately throw a `ValueError` indicating that lengths/sampling do not match [cite: 12]. 

### The Absolute Necessity of Resizing and Shifting
When generating a time-domain waveform using `get_td_waveform`, the output array length corresponds only to the duration of the physical signal from `f_lower` to ringdown. However, `matched_filter` requires the template and the data to share the exact same array length [cite: 4, 12, 15]. 
*   **Resizing**: You must call `hp.resize(len(data))` [cite: 4, 15]. This pads the template with zeros up to the data's length.
*   **Cyclic Shifting**: When the template is padded, the merger peak resides somewhere in the middle or end of the array (indicated by `hp.start_time`, which is usually a negative number representing time until merger). If filtered as-is, the resulting SNR peak will not correspond to the actual GPS time of the event in the data. You must execute `hp.cyclic_time_shift(hp.start_time)` to push the merger peak to the $t=0$ index of the array, ensuring accurate time reporting [cite: 4, 7].

### `hp` vs `hc` Polarizations
`get_td_waveform()` returns both the plus (`hp`) and cross (`hc`) polarizations [cite: 9, 10]. For single-detector matched filtering, **you only pass `hp` into `matched_filter()`** [cite: 3, 11, 15]. The matched filtering math computes a complex SNR where the real and imaginary parts inherently account for the orthogonal phase evolution, negating the need to inject `hc` manually unless you are doing coherent multi-detector projection studies [cite: 3, 9, 11].

### Low Frequency Cutoff Consistency
The `low_frequency_cutoff` parameter passed to `matched_filter()` dictates where the integration over frequency begins [cite: 11, 26, 27]. This parameter **must** match the `f_lower` passed to the waveform generator [cite: 3, 4]. If `f_lower` is higher than the matched filter cutoff, the filter integrates over regions of the template containing zero power, skewing the normalization and resulting SNR.

### Memory Issues During Mass Grid Searches
PyCBC relies on heavy C-extensions from LALSuite. Generating thousands of waveforms in a deep `for`-loop (e.g., when scanning a grid of $M_1$ and $M_2$) can cause severe memory leaks [cite: 17]. 
*   **Best Practice**: Explicitly invoke `del hp, hc, snr_complex` at the end of each loop iteration and periodically call Python's `gc.collect()`.
*   **Alternative**: When surveying massive grids, prefer `IMRPhenomD` generated in the frequency domain via `get_fd_waveform`. Frequency-domain templates are significantly lighter on memory and bypass the need for explicit time-domain resizing and shifting [cite: 3, 15].

## 7. PSD Estimation Details: Empirical vs. Analytical

Understanding how and when to generate a PSD is crucial for scientific validity [cite: 5, 6, 29].

### `from_string` vs `welch`
*   **Analytical PSDs (`from_string`, `aLIGOZeroDetHighPower`)**: These generate theoretically perfect, smooth curves based on the design sensitivity of detectors [cite: 15, 22, 29]. They are strictly meant for **simulated data**, mock data challenges, or theoretical studies [cite: 15, 29].
*   **Empirical PSDs (`welch`, `TimeSeries.psd`)**: Real interferometric data is highly non-stationary and littered with mechanical resonances (e.g., suspension violin modes at ~500 Hz) and electrical noise (60 Hz AC mains). If you are analyzing **real detector data**, you absolutely must estimate the PSD empirically directly from the surrounding data using Welch's method [cite: 5, 6].

### The Role of `interpolate` and `inverse_spectrum_truncation`
*   **`interpolate`**: Welch's method chunks the data into short overlapping segments (e.g., 4 seconds) to average out variance. Consequently, the output PSD has coarse frequency bins (`delta_f` = 0.25 Hz). To multiply this PSD against the FFT of your 32-second data segment (`delta_f` = 1/32 Hz), you must use `interpolate()` to mathematically bridge the resolutions [cite: 6, 7, 22].
*   **`inverse_spectrum_truncation`**: This is needed to control the impulse response of the PSD [cite: 6, 7, 23]. Because the true empirical PSD contains sharp noise lines, the inverse PSD ($1/S_n(f)$) used in the matched filter acts as an aggressive notch filter. In the time domain, a sharp frequency notch transforms into a very long, slowly decaying oscillation. If left unchecked, this filter would wrap around the periodic FFT boundaries and corrupt all of your data [cite: 6]. By truncating the inverse spectrum to a hard limit (e.g., 4 seconds), you force the filter's time-domain ringing to die out exactly within that window. You can then confidently use `.crop(4, 4)` on your SNR series to discard only the corrupted region, knowing the remaining data is pristine [cite: 6, 7].

## 8. Output Formatting: Aggregating a Grid Search

When deploying a matched-filter pipeline over a grid of component masses (e.g., scanning $M_1$ and $M_2$ from 10 to 40 solar masses), Pandas is the most robust tool for aggregation and export.

Below is an exemplary block of code demonstrating how to loop over parameters, correctly calculate the `total_mass`, format the results into a DataFrame, and save to CSV.

```python
import pandas as pd
import numpy as np

# Assuming `compute_matched_filter_snr` is the function defined in Section 5
gwf_file = "H-H1_GWOSC_O2_4KHZ_R1-1181155328-4096.gwf"
channel = "H1:GWOSC-4KHZ_R1_STRAIN"
approximants = ["SEOBNRv4_opt", "IMRPhenomD"]

# Define grid bounds
mass_range = np.arange(10, 42, 2) # 10 to 40 solar masses in steps of 2

results = []

for apx in approximants:
    for m1 in mass_range:
        for m2 in mass_range:
            # By convention, m1 is usually >= m2 in CBC searches
            if m1 < m2:
                continue
            
            try:
                # Perform the search
                snr, gps_time = compute_matched_filter_snr(gwf_file, channel, m1, m2, approximant=apx)
                
                # Append to records
                results.append({
                    "mass1": m1,
                    "mass2": m2,
                    "total_mass": m1 + m2,
                    "approximant": apx,
                    "peak_snr": round(snr, 4),
                    "peak_time": gps_time
                })
                
            except Exception as e:
                # Handle cases where approximants fail for specific mass combinations
                print(f"Failed for {apx} M1={m1}, M2={m2}: {e}")

# Construct a Pandas DataFrame
df_results = pd.DataFrame(results)

# Sort the data frame by the highest SNR
df_results = df_results.sort_values(by="peak_snr", ascending=False).reset_index(drop=True)

# Export to CSV
csv_filename = "pycbc_matched_filter_results.csv"
df_results.to_csv(csv_filename, index=False)

print(f"Grid search complete. Results saved to {csv_filename}.")
print("Top 5 Results:")
print(df_results.head())
```

This workflow ensures all masses are explicitly tracked, derived features like `total_mass` are calculated dynamically, and the final results are natively formatted for further statistical analysis or visualization.

**Sources:**
1. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmmu-ICP-sVCB_nVSJwLPPU93R9tWqg6eOeJfDDwqFEEHdNoDPSSG54EBZslicyCwwUPFlDBnIzUf78yBmqYlODXR4ajvUX5-ZhIKvpU5gvY316fR65yOxsTGI6IIus_9nGMKvSfSYF7KOZN_DsyAWvZf-zYMnoWE=)
2. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3peXQp_KWWm6R_sJJNIr9QvKlS4A5vIg2vwXAg0U32tUC85LYCsaYIReSPODA_JfZ_agURg5OR0WQAqW9Vp2yWtopdAvxmJGAZOtu-bC63r-iNHnviUlaUEQx0KXwXT0aCLuD0qQuJxQ=)
3. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_aeDnlXReqP136gMDi9yfGvwwtsLkQy52od_3Y27LoXGUttuZqTBZ1bnoKuqCXP4liX6LMxPI-coO9DJzBrsHPTbpcftCj46wc6wi-Mb52rW6EIC2IKXuSgh-PGLIn_cCctqbkpL8gjRtTI-5dEhhQx8fLy3dWJy5)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG95W_ifzuR7odbyEnz0gSofrET2DVo-3lbGnbFGD8x4R8zVdcN-TTjR2IMhK5MN3BDMQsQAl-IXj1iFXAXyGs4v8R5BSSWPS7ZVMypYa3zW2Pymo49EZLgfj4OvkhPTgPV4u8JNWAblUVK18BI0H1Wg1JfMsHNaPQZ2Zx6bgClNcSiPyHIwoc-uQdg9YoYM0sXbmVUyF6Vne14E9tkmcisV6u3SzKM)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFQdwMMuGwmUnnMKeKipsb5XAyUE3z9SOdDNrEXSZLTnc2SgrqZmyWy0S86xg3Z5jvF2Sffzt82ZKCGqv3Dh2XP1tUcRc69mM5jQGWq6ZZbf2e9EUHHpeLKHPqNm7ts8I1KSJFroAAf491BrhRG89U1wm3E43cB_O8_rA1aoVgl7i_vh9h0_yn5WapDuDzBlhAyUzRoXtD-lK7XmrkFkA==)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2VV_8MYRhATHv-IHt7qkIchaQoA2aWm7t78czqPsanoI981jPrhZ0J-hQf3Txt0ttSoxdAVNGXIE7XXaVX2-Lfe4bcdb3p5UxGP7gQ8qhlw8bq8funBTH6B58W4UtYKWbOVxZhBwGqo0ck75IzjkhHxaqQTHrrde-HSQNYCH3zCywV6lKltpBNKZYvyzm1GJzmFboHdVoENBdEyU=)
7. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjk96D_9XqjCHrBZ8bGXdJWtUyik5SKvhMXgLBXjZPqvoQ60S66RImsBYWHm_G8da7p0dxz-PSD5cp7o3O7AMjshbBRIJqxRvePzXGE51qeDCzcoePLqIxNSZJjXAdjuKGp95ncIWTNFEhf2SKejBSUODNZiE0DXmOxmYGtoMVv122iSD3rH7bEeSzNC4t4RgoQF7Eg2JCygkTx8G5WiKrrwahUGN8mrM=)
8. [kaggle.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHCdTG2GSIiCIpChNhe_rFrRsKO7uf2D6gdpsh3Qs-AGH80CYvU-nQLFgBrCOiGrqChHy0X5w2_N1k90RttLTA2vChHoB_pJ-myifpjPmcM7woUjXh4p07AmMPfyr6145ShD8fCRy1UZA==)
9. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEI1uxzS-ip0Tgul97WwgmMFfv9eMOGEezcKQwm9bZHIjVN9B_mccvmG7uqPmRbet59IooeRbG1uyqzHsVkiZsOtqDwkOsoaSOUjYj55tM96NL5eUPbECHHYQRZ_ohbj-oYji7pY2w=)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOXHa787BodVnFa5rv7CmG4mZ0l7sGgaovcHxTM08g-F5pL8KLy2WyfUfpcaXQkWqirQBYRg44TNtWNKgGs0lUmdvqBqZ93nenGKrxpBVQyOUA0ZBkzs2vgneubO9slHoqZFFfvxn47nCc2snso2UtGQANwbs62ElagsAjwz6OcsmuXaX6)
11. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqOk-PVBGe2JwjE8sJw1aIl0It8_Quh2uS4fMhReZM-G0TwuUIrmiz5GFnd2RUCtvN78x6U-tAImWVHiNL4rCHCg1WQ3jZ1IeKG3lCXEUl9TY0Bn8TpCQJu5woWed0ofA6cODXVpMWQJ4S9mBv14VdxIyMEPvYQ-UgFZ26JpB5Mqo=)
12. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHvlYwts8ruDJVbblSoosiNaG39rkJc167hGCwHZsEYxHFuBMneG3_2ihhdS49dJAU9EFIkErcVRc_PjXKVF2zTXtop5KxuDnW3Km_wSfqDZF8IQ0pwRRkgIZXra6I6RaXFU3NySgLj07rXLTUIRYyI40qLcxqOkNeMPYBIx5o)
13. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHL-hQpDV4qBCcuziaoYUMiD00KzZ_7W9YHMe7x9nyU8-bstkjEm53bngVJNQBJn-y93gvXmnh1ch_6hsOqKBhwDGLxQTy5suIoK1ZyFLomlQTCspkofceJaH9RtYFLo1C1SftKDsFRWE6VmaCSdhSRvM_SflX9au4O_NF6etPiH773uLd2iBd7Z0ABAYsCaF2sZv-Y8Lye-9hUMEVpYQ2CebQu31jogp51ciBssXTSgA==)
14. [uliege.be](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWziZBz0CTsPfMcS85cQs1PTPOKIAvY97niGli9dCfDFeQ2VSyBrMblDTPJZhcQ5ElWyCs3tH9U5bli9dkS4Cskr_jTIAsWgooEKuueueuroJW-M6gIxKHrRjMXLfLsUOqPJxKTPGavWQTRR8ftsLAvny9aTi0HrsDG15iWCBfhA==)
15. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlVXa5il49i0gSDXbepyOvfjL6P8ywd-r23A3LFRXmfkjRgKpS9UHxR_i79GqCrFUhhWvfLODS35e3MON4aFR6P8vqxjThSMeEC0z5h3_g2iXX14j4Ok299adKkDxA6F1xS4Qy)
16. [uni-hannover.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPHRSo7-N1WK6j7vU_67sA_TUvTier1nbOSvd6GaOOFXbaA9jLU2h2JV8rmuyy5VlKgylAbM9bSv97pM4AIvKSndS6jHm9OdhRBll3myV5IPllI7U41TW3Q17aHpB4MwKaK1kccEtgfqNKUykUr3xH8laWCiui3hHBN-VavV0pLvJvIKKnTbUzUD2EFUQHycPSTjCZ0gGaHLEGOG_77FxbvtserVyw)
17. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMP_sT5vpPgydVfSDfvV8YtnXeeVgcqTxUSs2VtLh9foQxDJy0f8Jm8PltuY2mjAH2XFfVRP8GkEe4PanzoGOBpb3J288t1KiwYUYHtWWkGZ7WNr0STkqSqrvz7AzG8Sm2REALuDeskQUiuwjxyfVMpIfTM5-SKg53qE2UCjho3UAVvBcnbpRTE0xQ6I86AdPVOHOxF9XiWwx5lPEO3mSNuYp0zDPT0Yh-VL4LLWGtUz01_zjnb9cEgkNBizBFbWsHhBQ9Yoz_RPo5mA==)
18. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGacGjIjIzpuw-477bfXaQyOY0XD4hD1qJU7IsrmN3xZeeZJEgFm5SAAu_82fGug_KPXY8S4tflh78eWFxsL4sFoY6GjMRPTrI88408jDdKydqr0EeV5Q1fly4tU124wQtjl78=)
19. [kasi.re.kr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGYHfEMFIFM55lbm75MWgR_NHQVds9wsuxcW_gTBRcRJnwv4FXBkjmC5Wor2CKS5hTCuxzTJZSUQYBEguDoV96CfZ7X8Mbb9-RefAbA_FSQU8cvWNHTVM90GIVM4ZAn15fSo2NqrGKv_QcjOm9tzPOaVp8IzS_fPDdpNw_v1w==)
20. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7evbTp7ZwSB1NS39-RJU_VgDNXrwG9i94SF9TwSPgWtxtoSvVPZXF2WnFpZYgMOYw1eCdl8PWJ8Cd9lg-SUgkI5msS-WIvhECj6t13MfvxOKyxtDgMdVOK8DKBPb2sx60gV6z7C16guehPDsOCET03-Mlhw==)
21. [nr.re.kr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJfs_wSmwflCGa1KJrVW358L2wRM6hDVFK-tGjXkdoF7prtC9GruLGhapCjwfGThpi_FE0NE-qlg36bnjlo-YMw6FZ7wsrbLzI-AYnTlNOWJUwwu9dhoVKXp4f32ocxFhJk6FIDPZULk9QGBUy0g==)
22. [uni-hannover.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUBXIuxRrN0GNayTD3esN9rG4cjda6XQTUez3ktQH7CTa6kcJ_fScF8w8TbUHerntAmNNroFVK4bhCCZP5ksXhn5BZEZZWLJhPW27S_06yy-FH4hc3tBeQKIcvd9K1QhXlbAXlZhIj9cf3YtrXq53t_kwNzndvnc35ZZjJzMuSpZVWuNyL4CeVglqozTQEInryDHZhAXdL)
23. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE-udvDBDt73o1B0RJc9Y9sZFlhS96zcIYcN5Gr_ReIuYAuB4dZDR1GpS8RTzEooRq6uo_pWTxx2qbNP--wUdX_Qn-KWND6fAIjJW8PkXjpYSNth_7iYZh9038oCKB6VfPCjd4VE8oHHC8q51Fr_eZryqqKr8nST-eY)
24. [uni-hannover.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE9UgVaNwmXo3VJj7fb54qY-7-m2m82-mySic6XsLaBWul3ABZX04xhw8OqHTW-MJ4S1Enx3FEYjeaM4_dUYzP85bZUV3fVRiVuZYVAxt95OxvsvtHq-NFva7S7X_kdJq86-B4q-wFeJ6mc-2rDG-rQFltTkpRMzwu6T8OEp0Y3Oql0XjmDn03EObLai2eh3mA4RzwXUzJG9akgfd2xfYxbqel8cggz31guLaO9bgZVtpBi)
25. [igwn.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFb_LnFMZ63ftDhbUb2BRNjh8sqCOmL6ger55ongnFtmcu7iRXXs1KLp2W9gPh03TWgaSGd3bAlXELXPrfSAYnVMTZ-E-Z2r--mh383MnJf0XBOlpmXZ1fJoCU62AALrUzxsKyanHZ7LccpDKkOcPBoUiOUu5FFK52mGGQWxp9jCC5d_TSxUUYsy4QAyC7CBkgrlwc4V_rA56l7MKmm8h_65IXS0cw=)
26. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwRy7Wp0PLIMoZ-7TG1Faw5pGlGKHxiQhK5y4YqCNfFreErxJzElnz2f0WG29NHeJbzla9uwuIqfpADF6En9LPa-50mkmXJt7uDiCXlvzPM7Bp40UKj1_8TLgZmAOBvCHG3s2Gdg3rMJEQ)
27. [uni-hannover.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHSmsBlbsdmbpHxisy3Lm0FizIuUVkJehQypbLrxek8k-CY4PB2bbuFew99B-hDbC5Mf6_i5m0T8a7jo1M7XPAKqTz07aqfMmh_tsLEc9v5MDfxnutZBgvSzX3U9vnGkLGd4i3CRIqMIf-f0cmxR9KZz52BIKLi0xgHWN4u22HTN-s2XqSuRI9pPvIsRbG9tvSZMHQS3FzRtTpGijpSiBTiNk5dHwTC2ssp8zui3-Tmngbs6qNVKZM=)
28. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEoLFzUsIpzfGNabQGJcrCbSKw0N4D2RcBb_cqT1QEmTwGy0hH4qX2-9EzNjidtIDwFcnkGK3wPteNCHGaRsedd5U2sa6RjoYQV_17Y5rs8Sp__9VHMhVGEYGPEiOulrhv6JGmEze2f_52BD0XcpWtoq4gyEOgQ4-CsnyLavb_sME1yDqUB1WBw4JX)
29. [pycbc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHC102tTy80jGpiuVJoV2fJJNxajASwY64ylA611rpaIZnPwZwPruuRWy6pqOT1NGFpngODd9KDET_4t9Jaak19Vqupp8xiEcZvGdrE53O-iRaebaRwPwedDZk71yNnnRQA5TO6yhTm)
