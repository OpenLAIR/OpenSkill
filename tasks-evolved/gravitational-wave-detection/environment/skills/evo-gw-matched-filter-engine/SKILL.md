---
name: evo-gw-matched-filter-engine
description: Core utility for reading GWF frame files, conditioning gravitational wave detector data (highpass filtering, resampling, cropping, PSD estimation), generating waveform templates, and performing matched filtering to extract peak SNR values using PyCBC.
---

# evo-gw-matched-filter-engine

Core GW data processing and matched filtering engine for PyCBC-based gravitational wave detection.

## Functions

### read_and_condition_data(gwf_path, channel)
Reads a GWF frame file and conditions the data:
1. Read entire frame (no time bounds needed)
2. Highpass filter at 15 Hz
3. Crop 2s from both ends (FIR wraparound removal)
4. Resample to 2048 Hz

### estimate_psd(conditioned_data)
Estimates PSD using Welch's method (4s segments), interpolates to data resolution, applies inverse spectrum truncation (4s max filter, 15 Hz cutoff).

### generate_template(approximant, mass1, mass2, delta_t, f_lower=20.0)
Generates a waveform template using get_td_waveform. Returns hp (plus polarization).
Supported approximants: SEOBNRv4_opt, IMRPhenomD, TaylorT4.

### compute_matched_filter_snr(conditioned_data, psd, hp, f_lower=20.0)
Performs matched filtering:
1. Resizes template to data length
2. Cyclic shifts template (hp.start_time)
3. Runs matched_filter with PSD weighting
4. Takes abs() of complex SNR
5. Crops edges (8s start, 4s end)
6. Returns (peak_snr, peak_time)

### find_peak_snr(gwf_path, channel, mass1, mass2, approximant, conditioned_data=None, psd=None)
High-level function combining all steps. Accepts pre-conditioned data/PSD to avoid recomputation.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-gw-matched-filter-engine/scripts')
from utils import read_and_condition_data, estimate_psd, generate_template, compute_matched_filter_snr, find_peak_snr

# Option 1: All-in-one
snr, time = find_peak_snr('data.gwf', 'H1:TEST-STRAIN', 30, 30, 'SEOBNRv4_opt')

# Option 2: Reuse conditioned data across many templates
data = read_and_condition_data('data.gwf', 'H1:TEST-STRAIN')
psd = estimate_psd(data)
hp = generate_template('SEOBNRv4_opt', 30, 30, data.delta_t)
snr, time = compute_matched_filter_snr(data, psd, hp)
```

## Key Parameters
- Highpass cutoff: 15 Hz
- Resample rate: 2048 Hz
- Data crop: 2s both ends
- PSD Welch segment: 4s
- Inverse spectrum truncation: 4s max filter, 15 Hz cutoff
- Template f_lower: 20 Hz
- SNR crop: 8s start, 4s end
- Only hp polarization used for single-detector filtering
