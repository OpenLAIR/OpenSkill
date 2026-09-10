---
name: evo-tess-lightcurve-preprocessing
description: Load TESS text-format light curves and prepare them for transit detection by applying quality flag filtering, NaN removal, outlier rejection, normalization, and Savitzky-Golay flattening to remove stellar variability.
---

# TESS Lightcurve Preprocessing

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-tess-lightcurve-preprocessing/scripts')
from utils import load_tess_lightcurve, filter_quality_and_nans, remove_outliers, estimate_rotation_period, flatten_lightcurve

time, flux, flux_err = load_tess_lightcurve('/root/data/tess_lc.txt')
time, flux, flux_err = filter_quality_and_nans(time, flux, flux_err, quality)
time, flux, flux_err = remove_outliers(time, flux, flux_err, sigma=5)
rot_p = estimate_rotation_period(time, flux)
time_f, flux_f = flatten_lightcurve(time, flux, window_length=0.5)
```

## Key rules
- Drop quality flag != 0
- Drop NaN/inf values in flux
- 5-sigma outlier clipping iteratively
- Use Savitzky-Golay filter with window length sized between transit duration (~hours) and stellar rotation (~days)
- Best to use lightkurve's `flatten()` method which uses Savitzky-Golay
