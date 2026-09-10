---
name: evo-transit-period-detection
description: Run BLS and/or Transit Least Squares (TLS) periodograms on a cleaned, flattened light curve to identify the exoplanet orbital period, and write the result to a properly formatted output file.
---

# Transit Period Detection

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-transit-period-detection/scripts')
from utils import detect_transit_tls, detect_transit_bls, save_period

period, results = detect_transit_tls(time, flux)
save_period(period, '/root/period.txt')
```

## Notes
- TLS is preferred over BLS for small planets due to limb-darkening modeling.
- Search period range can be constrained to avoid stellar rotation aliases (>0.5 d typical).
- Output format: single float, 5 decimal places via `f"{value:.5f}"`.
