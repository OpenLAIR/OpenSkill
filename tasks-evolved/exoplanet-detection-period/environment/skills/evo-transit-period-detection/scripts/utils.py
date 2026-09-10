"""Transit period detection utilities."""
import numpy as np


def detect_transit_tls(time, flux, period_min=0.5, period_max=None):
    """Run Transit Least Squares to find best period."""
    from transitleastsquares import transitleastsquares
    t = np.asarray(time, dtype=float)
    f = np.asarray(flux, dtype=float)
    mask = np.isfinite(t) & np.isfinite(f)
    t, f = t[mask], f[mask]
    if period_max is None:
        period_max = (t.max() - t.min()) / 2.0
    model = transitleastsquares(t, f)
    results = model.power(period_min=period_min, period_max=period_max,
                          show_progress_bar=False, use_threads=1)
    return float(results.period), results


def detect_transit_bls(time, flux, flux_err=None, period_min=0.5, period_max=None,
                       durations=None):
    """Run BLS periodogram and return best period."""
    from astropy.timeseries import BoxLeastSquares
    t = np.asarray(time, dtype=float)
    f = np.asarray(flux, dtype=float)
    mask = np.isfinite(t) & np.isfinite(f)
    t, f = t[mask], f[mask]
    if durations is None:
        durations = np.array([0.05, 0.1, 0.15, 0.2]) # days
    if flux_err is not None:
        flux_err = np.asarray(flux_err)[mask]
        model = BoxLeastSquares(t, f, dy=flux_err)
    else:
        model = BoxLeastSquares(t, f)
    if period_max is None:
        period_max = (t.max() - t.min()) / 2.0
    periodogram = model.autopower(durations, minimum_period=period_min,
                                  maximum_period=period_max)
    best = np.argmax(periodogram.power)
    return float(periodogram.period[best]), periodogram


def save_period(period, path='/root/period.txt'):
    """Save period to file rounded to 5 decimal places."""
    with open(path, 'w') as fp:
        fp.write(f"{float(period):.5f}\n")
