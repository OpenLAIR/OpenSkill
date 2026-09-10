# Domain Reference for evo-transit-period-detection

**Responsibility**: Periodogram-based transit period detection and formatted output of the best-fit period.

**Key functions to implement**: detect_transit_tls, detect_transit_bls, save_period

---

## 4. Transit Detection with Box Least Squares (BLS)


The Box Least Squares (BLS) periodogram is a robust, computationally efficient statistical tool for detecting rectangular signals (transits) in photometric time series [cite: 6, 13].

**Constructor and Methods:**
```python
from astropy.timeseries import BoxLeastSquares

model = BoxLeastSquares(t, y, dy=None)
results = model.autopower(duration)
```
The constructor takes time `t`, flux `y`, and optional uncertainties `dy` [cite: 13]. The `.autopower()` method heuristically determines the optimum period grid based on the time baseline and input durations [cite: 6, 13]. 

To extract the best parameters:
```python
best_period = results.period[np.argmax(results.power)]
```
While highly optimized, BLS assumes a strict top-hat shape. For grazing transits or small planets where limb darkening heavily modifies the transit shape, BLS is less sensitive [cite: 2, 5].

## 5. Advanced Period Detection with Transit Least Squares (TLS)


`transitleastsquares` (TLS) was explicitly designed to improve upon BLS. By modeling realistic stellar limb darkening and planetary ingress/egress, TLS achieves up to 10% higher detection efficiency for Earth-sized planets [cite: 2, 5].

## 6. Common Pitfalls and Mitigation Strategies


A reusable skill module must be resilient against the common failure modes of automated transit detection:

1.  **Failing to remove stellar variability:** If a light curve is not detrended (or poorly detrended), BLS and TLS will lock onto the dominant stellar rotation signal or its harmonics, resulting in a false planetary period [cite: 3, 5].
2.  **Wrong `window_length`:** A Savitzky-Golay window smaller than the transit duration will fit the transit itself, removing the planetary signal entirely. Conversely, a window larger than the rotation period will leave stellar variability intact [cite: 3].
3.  **Not masking quality flags:** TESS momentum dumps occur regularly. If `quality != 0` cadences are left in the array, periodograms often detect the momentum dump cadence as a false periodic transit [cite: 3, 9].
4.  **NaN or inf values crashing TLS:** TESS pipelines pad data gaps with NaNs. Passing NaNs to `transitleastsquares` results in undefined behavior or silent failures in the `power` array [cite: 14, 15]. Always use `.remove_nans()`.
5.  **Confusing Rotation with Transit Period:** A simple safeguard is to check the `results.duration` and the `results.depth`. Planetary transits typically last hours and have depths < 0.05. Rotational signals are broad and deep.
6.  **Period Aliases / Harmonics:** Periodograms often show high peaks at $1/2 \times P$, $2 \times P$, or aliases related to the Earth's or satellite's orbit. TLS mitigates this better than BLS by looking for the specific U-shape of a transit [cite: 2, 5].

## 8. Output Formats


As demonstrated in the `save_period` function above, exporting precision astrophysics data demands strict string formatting to prevent floating-point anomalies. Utilizing Python's modern f-string syntax `f"{value:.5f}"` ensures the output text file contains a single float strictly rounded to the 5 decimal places appropriate for exoplanet orbital constraints (which generally correspond to second-level precision).