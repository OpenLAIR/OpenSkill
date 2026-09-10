# Exoplanet Transit Detection in Stellar Activity-Contaminated TESS Light Curves: A Python Implementation Guide

**Key Points:**
*   Research suggests that robust exoplanet transit detection in TESS data heavily depends on the successful removal of stellar variability (such as rotational modulation and starspots) without attenuating the underlying transit signal.
*   The standard Python stack for this task comprises `lightkurve` for data handling and detrending, `astropy` for basic periodicity algorithms, and `transitleastsquares` for advanced transit searches.
*   It seems likely that incorrect selection of the Savitzky-Golay filter window length is the most common cause of transit signal degradation during the flattening process.
*   While Box Least Squares (BLS) remains a computationally efficient standard, Transit Least Squares (TLS) offers a ~10% higher detection efficiency for small Earth-sized planets by modeling stellar limb darkening and transit ingress/egress.

**Context and Scope:**
The Transiting Exoplanet Survey Satellite (TESS) has revolutionized time-domain astronomy by providing high-precision photometry across the sky. However, TESS light curves are frequently contaminated by instrumental systematics, background variations, and intrinsic stellar activity. Building an automated, reusable software skill module requires careful orchestration of data loading, quality filtering, robust detrending, and periodic signal extraction.

**Methodological Approach:**
This report outlines the architecture of a Python-based pipeline tailored for TESS data. It leverages `lightkurve` (v2.4.2), `astropy.timeseries`, and `transitleastsquares` (v1.32). We detail the exact API signatures, algorithmic parameters, and common pitfalls, culminating in a concrete, production-ready code implementation that transforms raw text-format light curves into a precisely detected transit period.

---

## 1. Introduction to TESS Light Curve Processing

The detection of transiting exoplanets relies on identifying periodic dips in a star's photometric flux. For small planets, these signals are often hidden beneath the noise floor of the instrument and the intrinsic variability of the host star. TESS data, typically sampled at either 2-minute (short cadence) or 30-minute (long cadence) intervals [cite: 1, 2], presents unique challenges. 

A reusable skill module must process whitespace-delimited text files containing raw arrays of time, flux, flux uncertainty, and quality flags. It must seamlessly handle time formats—specifically the Barycentric TESS Julian Date (BTJD) and Modified Julian Date (MJD)—and rigorously filter out poor-quality cadences [cite: 1]. Following data ingestion, the module must apply iterative statistical clipping to remove outliers and use localized polynomial fitting (Savitzky-Golay filtering) to isolate the high-frequency planetary transits from low-frequency stellar rotation [cite: 3, 4]. Finally, periodogram analysis using Box Least Squares (BLS) or Transit Least Squares (TLS) is employed to calculate the optimal planetary orbital period [cite: 5, 6].

## 2. Data Loading and Preprocessing with `lightkurve`

In `lightkurve` 2.x, the API underwent significant architectural shifts to integrate more deeply with the broader astronomical Python ecosystem. Crucially, the `LightCurve` object was refactored as a direct subclass of `astropy.timeseries.TimeSeries` [cite: 7, 8]. This ensures that light curve objects behave like Astropy tables and guarantee the presence of `time`, `flux`, and `flux_err` columns [cite: 8]. 

### 2.1 Constructing the `LightCurve` Object
When reading a whitespace-delimited text file (e.g., via `numpy.loadtxt`), the resulting NumPy arrays must be instantiated into a `LightCurve` object. 

**Constructor Signature:**
```python
import lightkurve as lk
from astropy.time import Time

lc = lk.LightCurve(time=time_array, flux=flux_array, flux_err=flux_err_array, quality=quality_array)
```
The constructor accepts array-like inputs or `astropy.units.Quantity` objects. Deprecations from the 1.x API, such as `flux_quantity` and `LightCurve.from_timeseries`, have been removed in favor of direct instantiation and standard Astropy column access [cite: 7, 8].

### 2.2 Handling Time Formats (MJD vs. BTJD)
TESS timestamps are typically provided in Barycentric TESS Julian Date (BTJD), which is defined as $\text{BJD} - 2457000.0$ [cite: 1]. If the text file provides Modified Julian Date (MJD), the `time` attribute in `lightkurve` must be constructed carefully. `lightkurve` relies on `astropy.time.Time`. To handle MJD inputs explicitly:
```python
time_obj = Time(time_array, format='mjd', scale='tdb')
lc = lk.LightCurve(time=time_obj, flux=flux_array, flux_err=flux_err_array)
```
Using the `Time` object guarantees that subsequent period-finding algorithms correctly interpret the temporal spacing.

### 2.3 Quality Filtering and Outlier Rejection
The standard TESS pipeline assigns a `quality` bitmask to each cadence. A value of `0` indicates an optimal cadence, while non-zero values represent anomalies like momentum dumps, argabrightening, or cosmic ray hits [cite: 3, 9]. 
Masking is performed using standard boolean array indexing:
```python
lc = lc[lc.quality == 0]
```

Following quality filtering, statistical outliers (often caused by unflagged cosmic rays or minor thruster firings) must be removed. The `.remove_outliers()` method utilizes sigma-clipping [cite: 10].
**Signature:**
```python
LightCurve.remove_outliers(sigma=3, sigma_lower=None, sigma_upper=None, return_mask=False, **kwargs)
```
By default, `sigma=3` iterates over the data points, rejecting values that deviate by more than 3 standard deviations from the median flux [cite: 3, 10]. It automatically masks `NaN` and `inf` values during the calculation [cite: 10].

## 3. Stellar Variability Removal Techniques

Stellar rotational modulation and starspots create multi-day, high-amplitude sinusoidal variations that can completely mask planetary transits or cause period-finding algorithms to lock onto rotational harmonics [cite: 3]. 

### 3.1 Identifying Stellar Rotation with Lomb-Scargle
Before detrending, it is highly recommended to estimate the stellar rotation period to inform the detrending window length. The `astropy.timeseries.LombScargle` class evaluates sinusoidal models against unevenly sampled data [cite: 11].
**API Usage:**
```python
from astropy.timeseries import LombScargle

frequency, power = LombScargle(lc.time.value, lc.flux.value).autopower()
rotation_period = 1 / frequency[np.argmax(power)]
```

### 3.2 Flattening via Savitzky-Golay Filtering
The `.flatten()` method in `lightkurve` is a wrapper around `scipy.signal.savgol_filter`. It removes low-frequency trends by fitting successive overlapping windows of data with a low-degree polynomial [cite: 4].

**Signature:**
```python
LightCurve.flatten(window_length=101, polyorder=2, return_trend=False, break_tolerance=5, niters=3, sigma=3, mask=None, **kwargs)
```
*   `window_length`: The number of cadences in the filtering window. **Must be a positive odd integer** [cite: 4].
*   `polyorder`: The order of the polynomial (default is 2).
*   `break_tolerance`: Splits the data if a gap is larger than 5 times the median gap, preventing interpolation over large data down-times [cite: 4].
*   `niters` and `sigma`: Controls iterative sigma clipping during the flattening process. This is critical because in-transit points (the very signals we want to keep) are negative outliers. If `niters` > 1, the algorithm iteratively removes these outliers from the polynomial fit, preventing the transit from dragging the local trend downward and artificially shrinking the transit depth [cite: 4].

**Choosing `window_length`**:
The window length represents time, but is measured in cadences. For a 2-minute cadence TESS light curve, there are 720 cadences per day. For a 30-minute cadence, there are 48 per day [cite: 1, 2]. If a typical stellar rotation period is 5 days and a transit lasts 3 hours, the window must be longer than the transit but significantly shorter than the rotation. A window of 1 to 2 days is generally appropriate [cite: 5]. For a 2-minute cadence, a window of ~721 (approx. 1 day) is a sensible default.

### 3.3 Normalization
Detrending algorithms expect flux centered around 1.0. `lightkurve` provides the `.normalize()` method, which divides the flux by the median flux, yielding a dimensionless, unity-centered light curve [cite: 12].

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

### 5.1 API and Input Requirements
**Import:** `from transitleastsquares import transitleastsquares` [cite: 5].
**Constructor:** `model = transitleastsquares(t, y, dy=None)` [cite: 14].

**Strict Input Requirements:**
1.  **Normalization:** The input flux `y` must have a median close to 1.0. An unnormalized light curve will trigger warnings or silently fail [cite: 5].
2.  **No NaNs:** Older versions of TLS would crash if provided `NaN` or `inf` values. While v1.32 has internal cleaning, it is highly recommended to use `cleaned_array(t, y, dy)` or `lightkurve`'s `remove_nans()` before passing data to TLS [cite: 14, 15].
3.  **Time Units:** The time array `t` must strictly be in units of days [cite: 14].

### 5.2 The `.power()` Method
The `.power()` method executes the grid search over trial periods, durations, and epochs.
```python
results = model.power(
    period_min=None, 
    period_max=None, 
    n_transits_min=2, 
    oversampling_factor=3, 
    duration_grid_step=1.1, 
    use_threads=1
)
```
*   `oversampling_factor`: Controls the phase step size. A value of 2-5 is reasonable for short-baseline data like a single TESS sector [cite: 14, 15].
*   `use_threads`: Leverages multiprocessing to speed up the grid search. Setting `use_threads=multiprocessing.cpu_count()` maximizes efficiency [cite: 14, 15].
*   `n_transits_min`: Requires at least 2 transits to consider a signal valid [cite: 14].

### 5.3 Results Extraction
The `results` object returned by `.power()` is a dictionary-like structure containing comprehensive diagnostics [cite: 5, 14]:
*   `results.period`: The best-fit planetary orbital period in days.
*   `results.SDE`: Signal Detection Efficiency. An SDE > 7.0 is generally required to claim a valid transit candidate (corresponding to a <1% False Alarm Probability in white noise) [cite: 2, 16].
*   `results.T0`: Mid-transit time of the first detected transit.
*   `results.duration`: Transit duration in days.
*   `results.depth`: Maximum transit depth.
*   `results.power`: The full power spectrum array (SDE-ogram).
*   `results.periods`: The array of tested trial periods.

## 6. Common Pitfalls and Mitigation Strategies

A reusable skill module must be resilient against the common failure modes of automated transit detection:

1.  **Failing to remove stellar variability:** If a light curve is not detrended (or poorly detrended), BLS and TLS will lock onto the dominant stellar rotation signal or its harmonics, resulting in a false planetary period [cite: 3, 5].
2.  **Wrong `window_length`:** A Savitzky-Golay window smaller than the transit duration will fit the transit itself, removing the planetary signal entirely. Conversely, a window larger than the rotation period will leave stellar variability intact [cite: 3].
3.  **Not masking quality flags:** TESS momentum dumps occur regularly. If `quality != 0` cadences are left in the array, periodograms often detect the momentum dump cadence as a false periodic transit [cite: 3, 9].
4.  **NaN or inf values crashing TLS:** TESS pipelines pad data gaps with NaNs. Passing NaNs to `transitleastsquares` results in undefined behavior or silent failures in the `power` array [cite: 14, 15]. Always use `.remove_nans()`.
5.  **Confusing Rotation with Transit Period:** A simple safeguard is to check the `results.duration` and the `results.depth`. Planetary transits typically last hours and have depths < 0.05. Rotational signals are broad and deep.
6.  **Period Aliases / Harmonics:** Periodograms often show high peaks at $1/2 \times P$, $2 \times P$, or aliases related to the Earth's or satellite's orbit. TLS mitigates this better than BLS by looking for the specific U-shape of a transit [cite: 2, 5].

## 7. Python Implementation: Reusable Skill Module

The following code provides the concrete, working Python code examples requested, encapsulating the entire pipeline from loading a text file to outputting a 5-decimal period.

```python
import numpy as np
import pandas as pd
import lightkurve as lk
from astropy.time import Time
from astropy.timeseries import BoxLeastSquares, LombScargle
from transitleastsquares import transitleastsquares
import multiprocessing
import warnings

def load_tess_lightcurve(filepath: str, time_format: str = 'mjd') -> lk.LightCurve:
    """
    (1) Load a whitespace-delimited text TESS lightcurve.
    Expected columns: Time, Flux, Quality, Flux_err.
    """
    # Using numpy to load the text file
    data = np.loadtxt(filepath)
    
    time_array = data[:, 0]
    flux_array = data[:, 1]
    quality_array = data[:, 2]
    flux_err_array = data[:, 3]
    
    # Construct astropy Time object
    t_obj = Time(time_array, format=time_format, scale='tdb')
    
    # Construct the lightkurve 2.x object
    lc = lk.LightCurve(time=t_obj, flux=flux_array, flux_err=flux_err_array, quality=quality_array)
    return lc

def preprocess_and_detrend(lc: lk.LightCurve, cadence_minutes: float = 2.0) -> lk.LightCurve:
    """
    (2 & 3) Quality filtering, outlier rejection, and variability detrending.
    """
    # Filter by TESS quality flag (keep only optimal data)
    lc = lc[lc.quality == 0]
    
    # Remove NaNs (critical to prevent TLS/BLS crashes)
    lc = lc.remove_nans()
    
    # Remove statistical outliers (thruster firings, cosmic rays)
    lc = lc.remove_outliers(sigma=3.0)
    
    # Normalize the flux to a median of 1.0 (Required for TLS)
    lc = lc.normalize()
    
    # Determine Savitzky-Golay window length based on cadence
    # We aim for ~1.5 days to remove rotation but preserve hours-long transits.
    pts_per_day = (24 * 60) / cadence_minutes
    window_length = int(pts_per_day * 1.5)
    
    # window_length must be a positive odd integer
    if window_length % 2 == 0:
        window_length += 1
        
    # Flatten using iterative clipping (niters=3) to prevent transits from pulling the fit down
    lc_flat = lc.flatten(window_length=window_length, polyorder=2, niters=3, break_tolerance=5)
    
    return lc_flat

def detect_stellar_rotation(lc: lk.LightCurve) -> float:
    """
    Helper to identify the stellar rotation period using Lomb-Scargle.
    Should be run on the unflattened (but normalized) light curve.
    """
    frequency, power = LombScargle(lc.time.value, lc.flux.value).autopower(minimum_frequency=1/20.0, maximum_frequency=1/0.5)
    best_period = 1 / frequency[np.argmax(power)]
    return best_period

def detect_transit_tls(lc: lk.LightCurve) -> dict:
    """
    (4) Period detection using Transit Least Squares (TLS).
    Returns the results dictionary.
    """
    # TLS requires time in days, flux ~ 1.0, and no NaNs
    t = lc.time.value
    y = lc.flux.value
    dy = lc.flux_err.value
    
    # Initialize TLS model
    model = transitleastsquares(t, y, dy)
    
    # Determine threads
    threads = multiprocessing.cpu_count()
    
    # Run TLS power search
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = model.power(
            oversampling_factor=3,
            n_transits_min=2,
            use_threads=threads,
            show_progress_bar=False
        )
        
    return results

def detect_transit_bls(lc: lk.LightCurve) -> float:
    """
    (4) Alternative: Box Least Squares via astropy.
    Returns the best period as a float.
    """
    model = BoxLeastSquares(lc.time.value, lc.flux.value, dy=lc.flux_err.value)
    # Search durations between 1 and 5 hours (in days)
    durations = np.linspace(0.04, 0.2, 20)
    results = model.autopower(durations)
    
    best_period = results.period[np.argmax(results.power)]
    return best_period

def save_period(period_value: float, output_path: str):
    """
    (6) Format and write the output period rounded to 5 decimals.
    """
    with open(output_path, "w") as f:
        f.write(f"{period_value:.5f}\n")

# --- Example Execution Pipeline ---
if __name__ == "__main__":
    # Define file paths (placeholders)
    input_file = "tess_lc_sector_01.txt"
    output_file = "detected_period.txt"
    
    try:
        # 1. Load Data
        lc_raw = load_tess_lightcurve(input_file, time_format='mjd')
        
        # Optional: Check rotation period on the raw (but normalized) data
        lc_norm = lc_raw[lc_raw.quality == 0].remove_nans().remove_outliers().normalize()
        rot_period = detect_stellar_rotation(lc_norm)
        print(f"Detected stellar rotation: {rot_period:.2f} days")
        
        # 2. Preprocess and Detrend (Flatten)
        # Assuming 2-minute short-cadence data
        lc_clean = preprocess_and_detrend(lc_raw, cadence_minutes=2.0)
        
        # 3. Detect Transit via TLS
        tls_results = detect_transit_tls(lc_clean)
        best_period = tls_results.period
        sde = tls_results.SDE
        
        print(f"TLS Best Period: {best_period:.5f} days (SDE: {sde:.2f})")
        
        # Ensure SDE is statistically significant (typically > 7.0)
        if sde > 7.0:
            # 4. Save Output
            save_period(best_period, output_file)
            print(f"Period successfully saved to {output_file}")
        else:
            print("No statistically significant transit detected.")
            
    except Exception as e:
        print(f"Pipeline failed: {str(e)}")
```

## 8. Output Formats

As demonstrated in the `save_period` function above, exporting precision astrophysics data demands strict string formatting to prevent floating-point anomalies. Utilizing Python's modern f-string syntax `f"{value:.5f}"` ensures the output text file contains a single float strictly rounded to the 5 decimal places appropriate for exoplanet orbital constraints (which generally correspond to second-level precision). 

## 9. Conclusion

The pipeline presented herein leverages the mathematical rigor of `astropy.timeseries` and the tailored astronomical design of `lightkurve` 2.4.2 to prepare TESS light curves for planetary transit detection. By masking non-optimal quality cadences, statistically clipping cosmic ray events, and mathematically flattening the rotational modulations via iterative Savitzky-Golay filters, the signal-to-noise ratio of the underlying planet is maximized. Finally, executing Transit Least Squares utilizing computational multithreading ensures that even shallow, Earth-sized planetary transits can be reliably detected and their periods formally constrained. Adhering to the configurations and mitigation strategies outlined in this report will ensure the reusable skill module avoids the common photometric pitfalls inherent in time-domain space telescopy.

**Sources:**
1. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHtIAzjmvg0DVTsS-TUfaUz908Qw7jSJ4z5feA5irrg_0Q7V1nSwnaAFL0JXKz4TPmstELPN1bwriP9quTl_K1xQ2zOn9ht46PX7EJ-z6EthC7suvsK2Sikt7Y6bx9C6lqxtueeeVtgTAHKav1dPHwAL6Ul-YmZw2_GlL2-YTVP29aOePSo-0BZ0wDt5ttyozIiq0g8LwXroRdvrVPTgCS7d1GeP_6quFo=)
2. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGXTGTA3RMD4_0IxdoCZN1Ni5Y1fw2odfuoNhNoH1n_0gdHuWzTkgvF6MAyOUOIl-xWzZV90z96BQU2hwHPWA4SPW1N_Mz6r5uwdgP6JCVjTlSmczju)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmbmVI5ZcGCnYK0jnV5oGgbi4TtCv_7TEpqvc7B3ik1TQUJcozZrjLVak7tinqpIzZ3OPf-cK4cByPKV0a2q8VSj9s3UCcuXfJMUxGz1e6ta_OM6wZ0SvHw6qWTv5BQSYvg9HPBoqWXrGBjS7V62Z7OjDgsGH-MS95WgT18tHzxOWU9J8OhjhKK9IInroU0-fTSjYBV1uxmkFQFbCEeXrwXdwMeQAY7CbiW_AOeIZcs7FQr_shJ2RN4vZoAislhkEQvg==)
4. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQENUmcA_6n2a5IwJIWjN2HGOXNgzF3AHDZef05p4-SN0dMapdbHZ7yfvsp3CbNed6IXile3J8jUexiEwQDxdKWjOEoxdlN7bDxyNl1pLQbo_siiDMC5cZCdIiy2EuR1eMNrOULIGxZaX9uuGHZshT9J76Idumbhx3QS1rbQRZzsx0NiRB1cUsKGe3DIzbw=)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxLMvgkBFKnL9z7T4WL6VE2VCc_opnWrvHXo6DFueY1XIuGBccNcHyGtB-IwbPNO6VKn4fUWbBOEahv7ODK7d8R0yKtgmRlsUt10Ba6eIZH8HY1b90ptlkjLd_LLOXPQNRgj8Fm58=)
6. [astropy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHoH55_NLeQorSLy7diY4_KuRRNcySzkBpwTbjjjgJuPMuWauHXLQbnWGSrptQV1ttXx0O0d8Xs5Ey8sHG7tEW8zbfzyRBexm4bn2bwMcuQbgsVhkozs6Ye5t1H-r2A3xS9TwlkjJHOt0k6fg==)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFr2ynDy0O_TOGmHVg0RZbCHUZ6y2LRQx1alCGj1KheEFTJy9RvH1TKtjvDEHHMmMqC4KzAdEQS8arfk_njrS9BCgpUDgHHhxj8F4q8JebU_0uPqaLQcLyDWKmu48JX4wmWmfFVbvG73OnQaz9-MJ2g02Z-)
8. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmOYqe_zbWnF7t_R5VXpwd6IlzOvhFVIe_EyDUGbJTtZzEOwVplIDf6KY2aWN241echy-FA3dZ-lG4obTyYZkswWWom9WbjaB-fmOUYSiwJsDjRBP7xMAPA15PXRPZlRtF-6jCda_jzmup9XKU3c-HfNapxMezDa4fx1jYa2sWmmQ7kvRk)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEcDDj3PjM7ab5K_mVOvdiwHzwhdcT-KDtRXMfHAmwT5IL3fK4gv1CIl5LN-3OagGgGUvR06_GhvdnRYLRAdkRQJybIiDJCkfyZSmi89TMB48rztMW1WjWJ5mLUBSY_njLE8ReXvpQT0ql2ADlJ-7G0lXnUXNGlIiLDuG-2lrsRiQGBvccfP8bAb12dKj8qQfiESQIMd_6p0LzP735zvQ==)
10. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwP3rEflnsfq2yYYHoAChxMLqzSB_-laNmaWpH1lHlxsmyJMjTazppyGvqugp1Dj46ayXmHK45Wo3XAbQF2djO6KYvD2eKS0p5mPT0iQjvM1vvGxbUtShL0lpZaWNLWQ09liJMW-lXXqThp61PZ3IJlIEhGh2udjZVEUc6tbZSHlK-qyzQKkzbxolA6Mh5FR92E-mTw8yGSJFurEiaynttcNuyabcGXxAbAmN7DZBC)
11. [astropy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH3WP0Qs6DrREkNeuTM6AqylBG26an5OgW3gaa2o5LYP1_VQNUOG3-bc_S5_vuHMPdpXXpBUT9__ATJG8bjt7J0fcyfm8-8sPPeaToK3asi8CVinycGL4lRLvTx-E_IQOhGM0A2bP-kOdom438zJ5GQo0fi)
12. [iku.edu.tr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEf_IWmyF82Jnc_Iyjpj9W0C8SDrUWzFrwSDuo4CGvqWkRzOsQ-7c0vRaOG2rewr9rUTlYMH99zAYJhMcCoPFYj4b38WzALRXHGrTS88_JOUPwkW45aZrQEaJ3NYIzWP_ewoOg-SIi-3dvDVAtv08ekMXpxktI2v1rQnURRlEri8CEJNbRdhyxxgZVO)
13. [astropy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLH8doHAxATwI1UFoKEtQFfx0zqSR9pWjCh6UYHA4bFAviVHPVKhf5pYVjTKu55-uruVZgYOuEwonCIvLeFN7G_iGeOMYDdyW_SbaIVOot7mLmE7AXoeFqvLL2MmsR9ZBvFNmS9Byrox1C0wNB_-lsX7omPztncCalbGaLiAuEb-uQqw==)
14. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEG6z-Wjng6HO4cT_UXkYRQ8bSvcQXjb3MvmBEY04XELOIb_U5-XQe0jQyrVEcBM2RFESMDZStHKvfa8b6qCufzeNjhIz_VYYB4OaqieZc0wHEkvgxJ177r8sVkquqKpQycAvddrKaKGJ50L_b60yVeegiKU1WoR43AZVLwQmdy2s=)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEBWNWNujKY970bttEG2p_0r895JGIs-z1rMVbTEsLaR1SnFsd1Sn7TC5D8lLXI_BHWZVgPwoSwDXKg_lEjfuGUcvFA0C-aniKpJDkfcSDOXQXhWhtlWNilidmN-1e-ZN2pi3wnR3jcGk-SI3aA2tG78hZNBJWCDn_oqw==)
16. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHw6IlKrA6YFChF9JA3oNiPHbR21JALELlDaheaC8ssaTdSlepy7-cEl6ygMy8ifidqBfX5rJMgLIv1PTXf71SuBSSpd74WyFmLK6HkXfywn959VjsaWhXhSfUWbKq7EIGA90pm12Y1_kT4mmeFXBZuoJs=)
