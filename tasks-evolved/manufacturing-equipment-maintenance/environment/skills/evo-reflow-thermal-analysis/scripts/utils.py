import pandas as pd
import numpy as np

def load_thermocouple_data(filepath='/app/data/thermocouples.csv'):
    """Load and sort thermocouple data."""
    df = pd.read_csv(filepath)
    df = df.sort_values(by=['run_id', 'tc_id', 'time_s']).reset_index(drop=True)
    return df

def load_mes_log(filepath='/app/data/mes_log.csv'):
    """Load MES log data."""
    df = pd.read_csv(filepath)
    return df

def load_test_defects(filepath='/app/data/test_defects.csv'):
    """Load test defects data."""
    df = pd.read_csv(filepath)
    return df

def calculate_ramp_rates(tc_df):
    """Calculate ramp rate (dT/dt) for each run/tc pair."""
    df = tc_df.copy()
    df = df.sort_values(['run_id', 'tc_id', 'time_s'])
    df['dt'] = df.groupby(['run_id', 'tc_id'])['time_s'].diff()
    df['dT'] = df.groupby(['run_id', 'tc_id'])['temp_c'].diff()
    df['ramp_rate'] = df['dT'] / df['dt']
    return df

def get_max_preheat_ramp_by_run(tc_df, preheat_max_c=150.0):
    """Get max preheat ramp rate per run.
    
    Preheat zone: temperatures up to preheat_max_c (150C from handbook).
    Selects TC at 'largest_mass' location as representative (coldest spot).
    Returns dict: {run_id: {'tc_id': str, 'max_preheat_ramp_c_per_s': float}}
    """
    df = calculate_ramp_rates(tc_df)
    
    # Filter for largest_mass TC (representative per handbook)
    df_rep = df[df['tc_location'] == 'largest_mass'].copy()
    
    # Filter for preheat zone: temp_c <= preheat_max_c
    # Use the current temperature reading to define preheat zone
    preheat_mask = df_rep['temp_c'] <= preheat_max_c
    df_preheat = df_rep[preheat_mask & df_rep['ramp_rate'].notna()].copy()
    
    # Get max ramp rate per run
    result = {}
    for run_id in sorted(tc_df['run_id'].unique()):
        run_data = df_preheat[df_preheat['run_id'] == run_id]
        if run_data.empty:
            result[run_id] = {'tc_id': None, 'max_preheat_ramp_c_per_s': None}
        else:
            idx = run_data['ramp_rate'].idxmax()
            result[run_id] = {
                'tc_id': run_data.loc[idx, 'tc_id'],
                'max_preheat_ramp_c_per_s': round(float(run_data.loc[idx, 'ramp_rate']), 2)
            }
    return result

def calculate_tal_by_run(tc_df, mes_df):
    """Calculate Time Above Liquidus for each run.
    
    Uses the largest_mass TC (coldest spot) as representative.
    Liquidus temperature comes from MES solder_liquidus_c column.
    TAL = sum of time intervals where temperature >= liquidus.
    """
    # Get liquidus per run from MES
    liquidus_map = mes_df.set_index('run_id')['solder_liquidus_c'].to_dict()
    
    # Filter for largest_mass TC
    df = tc_df[tc_df['tc_location'] == 'largest_mass'].copy()
    df = df.sort_values(['run_id', 'tc_id', 'time_s'])
    
    results = []
    for run_id in sorted(tc_df['run_id'].unique()):
        liquidus = liquidus_map.get(run_id)
        if liquidus is None:
            results.append({
                'run_id': run_id, 'tc_id': None,
                'tal_s': None, 'required_min_tal_s': 30.0,
                'required_max_tal_s': 60.0, 'status': 'non-compliant'
            })
            continue
        
        run_data = df[df['run_id'] == run_id]
        if run_data.empty:
            results.append({
                'run_id': run_id, 'tc_id': None,
                'tal_s': None, 'required_min_tal_s': 30.0,
                'required_max_tal_s': 60.0, 'status': 'non-compliant'
            })
            continue
        
        # Use TC1 (largest_mass)
        tc_id = run_data['tc_id'].iloc[0]
        tc_data = run_data[run_data['tc_id'] == tc_id].sort_values('time_s')
        
        # Calculate TAL as sum of time intervals where temp >= liquidus
        tc_data = tc_data.copy()
        tc_data['above'] = tc_data['temp_c'] >= liquidus
        tc_data['dt'] = tc_data['time_s'].diff().fillna(0)
        tal = float(tc_data[tc_data['above']]['dt'].sum())
        
        status = 'compliant' if 30.0 <= tal <= 60.0 else 'non-compliant'
        results.append({
            'run_id': run_id, 'tc_id': tc_id,
            'tal_s': round(tal, 2), 'required_min_tal_s': 30.0,
            'required_max_tal_s': 60.0, 'status': status
        })
    
    return results

def extract_peak_temperatures(tc_df):
    """Extract peak temperature per run per TC."""
    peaks = tc_df.groupby(['run_id', 'tc_id', 'tc_location'])['temp_c'].max().reset_index()
    peaks.rename(columns={'temp_c': 'peak_temp'}, inplace=True)
    return peaks

def select_representative_thermocouple(peak_df):
    """Select the largest_mass TC as representative (coldest spot on board)."""
    rep = peak_df[peak_df['tc_location'] == 'largest_mass'].copy()
    # If multiple largest_mass TCs per run, pick the one with lowest peak
    idx = rep.groupby('run_id')['peak_temp'].idxmin()
    return rep.loc[idx].reset_index(drop=True)

def check_peak_temp_compliance(tc_df, mes_df, peak_margin_c=20.0):
    """Check if each run meets peak temperature requirement.
    
    Required min peak = solder_liquidus_c + peak_margin_c
    Uses largest_mass TC (coldest spot).
    If no TC data, run is failing.
    Returns: failing_runs list, min_peak_by_run dict
    """
    liquidus_map = mes_df.set_index('run_id')['solder_liquidus_c'].to_dict()
    all_runs = sorted(mes_df['run_id'].unique())
    
    peaks = extract_peak_temperatures(tc_df)
    rep = select_representative_thermocouple(peaks)
    rep_dict = rep.set_index('run_id').to_dict('index')
    
    failing_runs = []
    min_peak_by_run = {}
    
    for run_id in all_runs:
        liquidus = liquidus_map.get(run_id, 183.0)
        required_min = liquidus + peak_margin_c
        
        if run_id in rep_dict:
            info = rep_dict[run_id]
            peak = float(info['peak_temp'])
            tc_id = info['tc_id']
            if peak < required_min:
                failing_runs.append(run_id)
        else:
            # No TC data - failing
            peak = None
            tc_id = None
            failing_runs.append(run_id)
        
        min_peak_by_run[run_id] = {
            'tc_id': tc_id,
            'peak_temp_c': round(peak, 2) if peak is not None else None,
            'required_min_peak_c': round(required_min, 2)
        }
    
    return failing_runs, min_peak_by_run

def check_conveyor_speed_compliance(mes_df):
    """Check conveyor speed feasibility.
    
    LINE SPEED (MIN) = boards_per_min * board_length_cm / loading_factor
    Actual speed must be >= minimum.
    """
    results = []
    for _, row in mes_df.iterrows():
        min_speed = row['boards_per_min'] * row['board_length_cm'] / row['loading_factor']
        meets = bool(row['conveyor_speed_cm_min'] >= min_speed)
        results.append({
            'run_id': row['run_id'],
            'required_min_speed_cm_min': round(float(min_speed), 2),
            'actual_speed_cm_min': round(float(row['conveyor_speed_cm_min']), 2),
            'meets': meets
        })
    results.sort(key=lambda x: x['run_id'])
    return results

def find_best_run_per_board_family(mes_df, defects_df, tc_df):
    """Select best run per board_family based on quality and efficiency.
    
    Criteria (in priority order):
    1. Lowest total defect count (quality)
    2. Highest first-pass yield (fp_yield_pct)
    3. Highest conveyor speed (efficiency/throughput)
    """
    # Get summary defect data per run
    summary = defects_df[defects_df['inspection_stage'] == 'SUMMARY'].copy()
    
    # Total defects per run (sum of all non-summary defect counts)
    defect_counts = defects_df[defects_df['inspection_stage'] != 'SUMMARY'].groupby('run_id')['count'].sum().reset_index()
    defect_counts.rename(columns={'count': 'total_defects'}, inplace=True)
    
    # Get yield from summary
    yield_data = summary[['run_id', 'fp_yield_pct']].drop_duplicates()
    
    # Merge with MES
    merged = mes_df[['run_id', 'board_family', 'conveyor_speed_cm_min']].copy()
    merged = merged.merge(defect_counts, on='run_id', how='left')
    merged = merged.merge(yield_data, on='run_id', how='left')
    merged['total_defects'] = merged['total_defects'].fillna(0)
    merged['fp_yield_pct'] = merged['fp_yield_pct'].fillna(0)
    
    # Sort: lowest defects, highest yield, highest speed
    merged = merged.sort_values(
        by=['board_family', 'total_defects', 'fp_yield_pct', 'conveyor_speed_cm_min'],
        ascending=[True, True, False, False]
    )
    
    results = []
    for bf in sorted(merged['board_family'].unique()):
        bf_data = merged[merged['board_family'] == bf].copy()
        best_run = bf_data.iloc[0]['run_id']
        runner_ups = sorted(bf_data.iloc[1:]['run_id'].tolist())
        results.append({
            'board_family': bf,
            'best_run_id': best_run,
            'runner_up_run_ids': runner_ups
        })
    
    return results
