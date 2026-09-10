"""Utility functions for running GLM simulations and calibrating against field obs."""
import os
import subprocess
import logging
import numpy as np
import pandas as pd
import f90nml
from netCDF4 import Dataset
from datetime import datetime, timedelta
import scipy.interpolate


def read_glm_nml(nml_path='/root/glm3.nml'):
    return f90nml.read(nml_path)


def update_glm_nml(nml_path, params_to_update):
    """params_to_update is dict of {block: {param: value}}"""
    nml = f90nml.read(nml_path)
    for block, parameters in params_to_update.items():
        if block not in nml:
            nml[block] = {}
        for param, value in parameters.items():
            nml[block][param] = value
    # Use overwrite via temp file
    tmp = nml_path + '.tmp'
    nml.write(tmp, force=True)
    os.replace(tmp, nml_path)
    return True


def verify_bcs(nml_path='/root/glm3.nml', base_dir='/root/'):
    nml = f90nml.read(nml_path)
    files = []
    m = nml.get('meteorology', {}).get('meteo_fl', [])
    inf = nml.get('inflow', {}).get('inflow_fl', [])
    out = nml.get('outflow', {}).get('outflow_fl', [])
    for f in [m, inf, out]:
        if isinstance(f, str): files.append(f)
        elif isinstance(f, list): files.extend(f)
    missing = [os.path.join(base_dir, f) for f in files if not os.path.exists(os.path.join(base_dir, f))]
    return missing


def run_glm(working_dir='/root/', timeout=300):
    """Run GLM binary in working_dir. Returns (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            ['glm'], cwd=working_dir, capture_output=True, text=True,
            timeout=timeout, check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', 'TIMEOUT'
    except FileNotFoundError:
        return False, '', 'GLM not found'


def process_glm_netcdf(nc_path, start_date=None):
    """Parse GLM NetCDF, convert layer height-from-bottom into depth-from-surface.
    Returns DataFrame with columns: datetime, depth, temp.
    Uses surface = max layer height z[t,NS-1] as the dynamic surface reference,
    so depth = z_surface - z_layer.
    """
    nc = Dataset(nc_path, 'r')
    try:
        time_var = nc.variables['time'][:]
        # Determine start date from time units if not provided
        if start_date is None:
            units = nc.variables['time'].units  # e.g., 'hours since 2009-01-01 12:00:00'
            try:
                tok = units.split('since')[1].strip()
                start_date = datetime.strptime(tok[:19], '%Y-%m-%d %H:%M:%S')
            except Exception:
                start_date = datetime(2009, 1, 1, 12, 0, 0)
        z_var = nc.variables['z'][:]      # shape (T, MaxLayers, ...) likely
        temp_var = nc.variables['temp'][:]
        ns_var = nc.variables['NS'][:]

        # Normalize shapes
        def _squeeze(a):
            arr = np.array(a)
            # remove trailing singletons
            while arr.ndim > 2 and arr.shape[-1] == 1:
                arr = arr[..., 0]
            return arr
        z_arr = _squeeze(z_var)
        t_arr = _squeeze(temp_var)
        ns_arr = np.array(ns_var).astype(int).ravel()

        records = []
        for ti in range(z_arr.shape[0]):
            n = int(ns_arr[ti])
            if n <= 0: continue
            heights = np.array(z_arr[ti, :n])
            temps = np.array(t_arr[ti, :n])
            # mask invalid
            mask = np.isfinite(heights) & np.isfinite(temps)
            heights = heights[mask]; temps = temps[mask]
            if len(heights) < 1: continue
            z_surface = heights.max()
            depths = z_surface - heights
            # Sort by depth ascending
            idx = np.argsort(depths)
            depths = depths[idx]; temps = temps[idx]
            dt = start_date + timedelta(hours=float(time_var[ti]))
            for d, T in zip(depths, temps):
                records.append((dt, float(d), float(T)))
        df = pd.DataFrame(records, columns=['datetime', 'depth', 'temp'])
        return df
    finally:
        nc.close()


def load_field_observations(csv_path='/root/field_temp_oxy.csv'):
    df = pd.read_csv(csv_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df[['datetime', 'depth', 'temp']].copy()


def calculate_rmse(sim_df, obs_df, depth_tol=0.5, time_tol_hours=24):
    """For each obs (datetime, depth), find the sim row with same date and
    interpolate to that depth. Compute RMSE over all matched pairs."""
    # Aggregate sim to daily (one date per day) - GLM with nsave=24 already daily
    sim_df = sim_df.copy()
    sim_df['date'] = sim_df['datetime'].dt.normalize()
    obs_df = obs_df.copy()
    obs_df['date'] = obs_df['datetime'].dt.normalize()

    # Build interp per date
    matched_sim = []
    matched_obs = []
    for date, grp in obs_df.groupby('date'):
        sgrp = sim_df[sim_df['date'] == date]
        if sgrp.empty:
            # nearest day within tolerance
            diffs = (sim_df['date'] - date).abs()
            if diffs.min() > pd.Timedelta(hours=time_tol_hours):
                continue
            closest = sim_df['date'].iloc[diffs.argmin()]
            sgrp = sim_df[sim_df['date'] == closest]
            if sgrp.empty: continue
        sgrp = sgrp.sort_values('depth')
        sd = sgrp['depth'].values
        st = sgrp['temp'].values
        if len(sd) < 2: continue
        f = scipy.interpolate.interp1d(sd, st, bounds_error=False, fill_value=(st[0], st[-1]))
        for _, r in grp.iterrows():
            d = r['depth']
            ov = r['temp']
            if not np.isfinite(ov): continue
            if d < sd.min() - depth_tol or d > sd.max() + depth_tol:
                continue
            tval = float(f(d))
            if not np.isfinite(tval): continue
            matched_sim.append(tval)
            matched_obs.append(ov)
    if not matched_obs:
        return float('nan'), 0
    a = np.array(matched_obs); b = np.array(matched_sim)
    rmse = float(np.sqrt(np.mean((a - b) ** 2)))
    return rmse, len(a)


def calibrate_parameters(nml_path='/root/glm3.nml', obs_path='/root/field_temp_oxy.csv',
                        working_dir='/root/', nc_path='/root/output/output.nc',
                        target_rmse=1.95, max_iters=30):
    """Greedy grid search over Kw, sw_factor, wind_factor, coef_mix_hyp."""
    obs = load_field_observations(obs_path)

    # Compact grid centered near defaults
    grid = []
    for Kw in [0.4, 0.45, 0.5, 0.55, 0.6]:
        for sw in [0.95, 1.0, 1.05]:
            for wf in [0.95, 1.0, 1.05]:
                for hyp in [0.5, 0.6, 0.7]:
                    grid.append((Kw, sw, wf, hyp))

    best = None
    history = []
    iters = 0
    for (Kw, sw, wf, hyp) in grid:
        if iters >= max_iters: break
        iters += 1
        update_glm_nml(nml_path, {
            'light': {'Kw': Kw},
            'meteorology': {'sw_factor': sw, 'wind_factor': wf},
            'mixing': {'coef_mix_hyp': hyp},
        })
        ok, so, se = run_glm(working_dir=working_dir)
        if not ok:
            history.append((Kw, sw, wf, hyp, None, 'FAIL'))
            continue
        try:
            sim = process_glm_netcdf(nc_path)
        except Exception as e:
            history.append((Kw, sw, wf, hyp, None, f'parse:{e}'))
            continue
        rmse, n = calculate_rmse(sim, obs)
        history.append((Kw, sw, wf, hyp, rmse, n))
        if best is None or (np.isfinite(rmse) and rmse < best[0]):
            best = (rmse, Kw, sw, wf, hyp)
        if np.isfinite(rmse) and rmse < target_rmse:
            break
    # Apply best
    if best is not None:
        _, Kw, sw, wf, hyp = best
        update_glm_nml(nml_path, {
            'light': {'Kw': Kw},
            'meteorology': {'sw_factor': sw, 'wind_factor': wf},
            'mixing': {'coef_mix_hyp': hyp},
        })
        run_glm(working_dir=working_dir)
    return best, history
