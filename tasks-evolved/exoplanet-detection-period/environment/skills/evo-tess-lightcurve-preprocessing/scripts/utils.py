"""TESS lightcurve preprocessing utilities."""
import numpy as np


def load_tess_lightcurve(path):
    """Load TESS lightcurve text file.
    Returns: time, flux, quality, flux_err arrays.
    """
    data = np.loadtxt(path, comments='#')
    time = data[:, 0]
    flux = data[:, 1]
    quality = data[:, 2].astype(int)
    flux_err = data[:, 3]
    return time, flux, quality, flux_err


def filter_quality_and_nans(time, flux, quality, flux_err):
    """Keep only quality==0 cadences and drop NaN/inf values."""
    mask = (quality == 0) & np.isfinite(flux) & np.isfinite(time) & np.isfinite(flux_err)
    return time[mask], flux[mask], flux_err[mask]


def remove_outliers(time, flux, flux_err, sigma=5, iters=3):
    """Iterative sigma-clipping on the flux."""
    t, f, e = time.copy(), flux.copy(), flux_err.copy()
    for _ in range(iters):
        med = np.median(f)
        std = np.std(f)
        mask = np.abs(f - med) < sigma * std
        if mask.all():
            break
        t, f, e = t[mask], f[mask], e[mask]
    return t, f, e


def estimate_rotation_period(time, flux):
    """Estimate stellar rotation period via Lomb-Scargle."""
    from astropy.timeseries import LombScargle
    # restrict to plausible rotation period range 0.5 - 30 days
    freq = np.linspace(1/30.0, 1/0.5, 5000)
    power = LombScargle(time, flux).power(freq)
    return 1.0 / freq[np.argmax(power)]


def flatten_lightcurve(time, flux, window_length=0.5, polyorder=2):
    """Flatten lightcurve using lightkurve's Savitzky-Golay filter.
    window_length is in days; converted to odd cadence count.
    """
    import lightkurve as lk
    lc = lk.LightCurve(time=time, flux=flux)
    # estimate cadence in days
    dt = np.median(np.diff(time))
    win = int(np.round(window_length / dt))
    if win % 2 == 0:
        win += 1
    if win < polyorder + 2:
        win = polyorder + 3
    flat = lc.flatten(window_length=win, polyorder=polyorder)
    return np.asarray(flat.time.value), np.asarray(flat.flux.value)
