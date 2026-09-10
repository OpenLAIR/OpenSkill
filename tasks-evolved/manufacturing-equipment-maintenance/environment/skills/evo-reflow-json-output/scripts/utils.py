import json
import numpy as np
import pandas as pd

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif pd.isna(obj):
            return None
        return super().default(obj)

def safe_round(val, decimals=2):
    if val is None:
        return None
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return None
    return round(float(val), decimals)

def safe_json_dump(data, filepath, indent=2):
    """Write data to JSON file with numpy/pandas type handling."""
    with open(filepath, 'w') as f:
        json.dump(data, f, cls=NumpyEncoder, indent=indent)

def build_q01_output(max_ramp_by_run, ramp_rate_limit=2.0):
    """Build Q1 output: max preheat ramp rate per run."""
    violating = []
    formatted_ramps = {}
    for run_id in sorted(max_ramp_by_run.keys()):
        info = max_ramp_by_run[run_id]
        ramp = safe_round(info['max_preheat_ramp_c_per_s'])
        formatted_ramps[run_id] = {
            'tc_id': info['tc_id'],
            'max_preheat_ramp_c_per_s': ramp
        }
        if ramp is not None and ramp > ramp_rate_limit:
            violating.append(run_id)
    
    return {
        'ramp_rate_limit_c_per_s': ramp_rate_limit,
        'violating_runs': sorted(violating),
        'max_ramp_by_run': formatted_ramps
    }

def build_q02_output(tal_results):
    """Build Q2 output: TAL per run."""
    output = []
    for r in sorted(tal_results, key=lambda x: x['run_id']):
        output.append({
            'run_id': r['run_id'],
            'tc_id': r['tc_id'],
            'tal_s': safe_round(r['tal_s']),
            'required_min_tal_s': safe_round(r['required_min_tal_s']),
            'required_max_tal_s': safe_round(r['required_max_tal_s']),
            'status': r['status']
        })
    return output

def build_q03_output(failing_runs, min_peak_by_run):
    """Build Q3 output: peak temp compliance."""
    formatted = {}
    for run_id in sorted(min_peak_by_run.keys()):
        info = min_peak_by_run[run_id]
        formatted[run_id] = {
            'tc_id': info['tc_id'],
            'peak_temp_c': safe_round(info['peak_temp_c']),
            'required_min_peak_c': safe_round(info['required_min_peak_c'])
        }
    return {
        'failing_runs': sorted(failing_runs),
        'min_peak_by_run': formatted
    }

def build_q04_output(speed_results):
    """Build Q4 output: conveyor speed compliance."""
    output = []
    for r in sorted(speed_results, key=lambda x: x['run_id']):
        output.append({
            'run_id': r['run_id'],
            'required_min_speed_cm_min': safe_round(r['required_min_speed_cm_min']),
            'actual_speed_cm_min': safe_round(r['actual_speed_cm_min']),
            'meets': r['meets']
        })
    return output

def build_q05_output(best_runs):
    """Build Q5 output: best run per board family."""
    output = []
    for r in sorted(best_runs, key=lambda x: x['board_family']):
        output.append({
            'board_family': r['board_family'],
            'best_run_id': r['best_run_id'],
            'runner_up_run_ids': sorted(r['runner_up_run_ids'])
        })
    return output
