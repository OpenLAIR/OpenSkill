# Domain Reference for evo-tess-lightcurve-preprocessing

**Responsibility**: Data ingestion, cleaning, and stellar-activity detrending to produce a flattened, normalized light curve ready for periodogram analysis.

**Key functions to implement**: load_tess_lightcurve, filter_quality_and_nans, remove_outliers, estimate_rotation_period, flatten_lightcurve

---

## 1. Introduction to TESS Light Curve Processing


The detection of transiting exoplanets relies on identifying periodic dips in a star's photometric flux. For small planets, these signals are often hidden beneath the noise floor of the instrument and the intrinsic variability of the host star. TESS data, typically sampled at either 2-minute (short cadence) or 30-minute (long cadence) intervals [cite: 1, 2], presents unique challenges. 

A reusable skill module must process whitespace-delimited text files containing raw arrays of time, flux, flux uncertainty, and quality flags. It must seamlessly handle time formats—specifically the Barycentric TESS Julian Date (BTJD) and Modified Julian Date (MJD)—and rigorously filter out poor-quality cadences [cite: 1]. Following data ingestion, the module must apply iterative statistical clipping to remove outliers and use localized polynomial fitting (Savitzky-Golay filtering) to isolate the high-frequency planetary transits from low-frequency stellar rotation [cite: 3, 4]. Finally, periodogram analysis using Box Least Squares (BLS) or Transit Least Squares (TLS) is employed to calculate the optimal planetary orbital period [cite: 5, 6].

## 2. Data Loading and Preprocessing with `lightkurve`


In `lightkurve` 2.x, the API underwent significant architectural shifts to integrate more deeply with the broader astronomical Python ecosystem. Crucially, the `LightCurve` object was refactored as a direct subclass of `astropy.timeseries.TimeSeries` [cite: 7, 8]. This ensures that light curve objects behave like Astropy tables and guarantee the presence of `time`, `flux`, and `flux_err` columns [cite: 8].

## 3. Stellar Variability Removal Techniques


Stellar rotational modulation and starspots create multi-day, high-amplitude sinusoidal variations that can completely mask planetary transits or cause period-finding algorithms to lock onto rotational harmonics [cite: 3].

## 6. Common Pitfalls and Mitigation Strategies


A reusable skill module must be resilient against the common failure modes of automated transit detection:

1.  **Failing to remove stellar variability:** If a light curve is not detrended (or poorly detrended), BLS and TLS will lock onto the dominant stellar rotation signal or its harmonics, resulting in a false planetary period [cite: 3, 5].
2.  **Wrong `window_length`:** A Savitzky-Golay window smaller than the transit duration will fit the transit itself, removing the planetary signal entirely. Conversely, a window larger than the rotation period will leave stellar variability intact [cite: 3].
3.  **Not masking quality flags:** TESS momentum dumps occur regularly. If `quality != 0` cadences are left in the array, periodograms often detect the momentum dump cadence as a false periodic transit [cite: 3, 9].
4.  **NaN or inf values crashing TLS:** TESS pipelines pad data gaps with NaNs. Passing NaNs to `transitleastsquares` results in undefined behavior or silent failures in the `power` array [cite: 14, 15]. Always use `.remove_nans()`.
5.  **Confusing Rotation with Transit Period:** A simple safeguard is to check the `results.duration` and the `results.depth`. Planetary transits typically last hours and have depths < 0.05. Rotational signals are broad and deep.
6.  **Period Aliases / Harmonics:** Periodograms often show high peaks at $1/2 \times P$, $2 \times P$, or aliases related to the Earth's or satellite's orbit. TLS mitigates this better than BLS by looking for the specific U-shape of a transit [cite: 2, 5].