# Domain Reference for evo-gw-matched-filter-engine

**Responsibility**: Handles all PyCBC-specific operations: frame file reading, data conditioning pipeline (highpass, resample, crop, PSD estimation with Welch's method, interpolation, inverse spectrum truncation), waveform template generation (get_td_waveform for SEOBNRv4_opt, IMRPhenomD, TaylorT4), template resizing/cyclic shifting, matched filtering execution, SNR extraction with edge cropping.

**Key functions to implement**: read_and_condition_data, estimate_psd, generate_template, compute_matched_filter_snr, find_peak_snr

---

## 1. Reading GWF Frame Files with PyCBC


The standard data format for gravitational-wave observatories is the Gravitational-Wave Frame (GWF) file. These files containerize time-stamped strain data alongside auxiliary channels and data-quality flags [cite: 18, 19]. PyCBC provides a streamlined API to read these files directly into memory as `TimeSeries` objects.

## 2. Data Conditioning for Matched Filtering in PyCBC


Raw strain data from ground-based interferometers is dominated by extreme low-frequency noise (such as seismic activity and suspension thermal noise) and sharp spectral lines. Attempting to matched-filter unconditioned data will severely compromise the numerical stability of the Fast Fourier Transforms (FFTs) and pollute the SNR output. Therefore, a strict data conditioning pipeline is required [cite: 3, 5, 20].

## 3. Generating Waveform Templates with PyCBC


To perform matched filtering, we must generate theoretical waveform templates corresponding to expected astrophysical signals [cite: 3, 13]. PyCBC provides standard interfaces: `pycbc.waveform.get_td_waveform()` for time-domain generation and `get_fd_waveform()` for frequency-domain generation [cite: 3, 9, 10, 15].

## 4. Matched Filtering with PyCBC


The matched filter computes the correlation between the template and the data, weighted by the inverse of the PSD. The primary function is `pycbc.filter.matched_filter()` [cite: 11, 26, 27].

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

## 6. Common Pitfalls and Version-Specific Issues in PyCBC 2.8.5


When building robust pipelines in PyCBC, several subtle issues can trigger silent logical errors or hard crashes [cite: 4, 12].

## 7. PSD Estimation Details: Empirical vs. Analytical


Understanding how and when to generate a PSD is crucial for scientific validity [cite: 5, 6, 29].