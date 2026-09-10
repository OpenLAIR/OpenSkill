import gc
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, '/app/environment/skills/evo-gw-matched-filter-engine/scripts')
from engine_utils import read_and_condition_data, estimate_psd, generate_template, compute_matched_filter_snr


def search_approximant(apx, data, psd, mass_values):
    """Search all m1,m2 combinations for an approximant."""
    best_snr = 0
    best_m1 = 0
    best_m2 = 0
    count = 0
    
    for m1 in mass_values:
        for m2 in mass_values:
            if m1 < m2:
                continue
            try:
                hp = generate_template(apx, float(m1), float(m2), data.delta_t, 20.0)
                snr_val, _ = compute_matched_filter_snr(data, psd, hp, 20.0)
                count += 1
                
                if snr_val > best_snr:
                    best_snr = snr_val
                    best_m1 = m1
                    best_m2 = m2
                
                del hp
                if count % 20 == 0:
                    gc.collect()
            except Exception as e:
                continue
    
    return best_snr, best_m1, best_m2


def run_grid_search(gwf_path, channel, approximants, mass_range, conditioned_data=None, psd=None):
    """
    Run matched filtering grid search using coarse-to-fine strategy.
    Phase 1: Coarse grid (step=3) to find approximate best
    Phase 2: Fine grid (step=1) around best +-3
    """
    if conditioned_data is None:
        conditioned_data = read_and_condition_data(gwf_path, channel)
    if psd is None:
        psd = estimate_psd(conditioned_data)
    
    mass_list = list(mass_range)
    mass_min = min(mass_list)
    mass_max = max(mass_list)
    
    results = []
    
    for apx in approximants:
        # Phase 1: Coarse grid
        coarse_masses = list(range(mass_min, mass_max + 1, 3))
        if mass_max not in coarse_masses:
            coarse_masses.append(mass_max)
        best_snr, best_m1, best_m2 = search_approximant(apx, conditioned_data, psd, coarse_masses)
        
        # Phase 2: Fine grid around best
        fine_m1_range = list(range(max(mass_min, best_m1-3), min(mass_max, best_m1+3)+1))
        fine_m2_range = list(range(max(mass_min, best_m2-3), min(mass_max, best_m2+3)+1))
        fine_masses = sorted(set(fine_m1_range + fine_m2_range))
        fine_snr, fine_m1, fine_m2 = search_approximant(apx, conditioned_data, psd, fine_masses)
        
        if fine_snr > best_snr:
            best_snr = fine_snr
            best_m1 = fine_m1
            best_m2 = fine_m2
        
        results.append({
            'approximant': apx,
            'snr': round(best_snr, 2),
            'total_mass': best_m1 + best_m2
        })
        gc.collect()
    
    return results


def extract_best_per_approximant(results):
    df = pd.DataFrame(results)
    best = df.loc[df.groupby('approximant')['snr'].idxmax()]
    return best.to_dict('records')


def write_detection_results_csv(results, output_path='/root/detection_results.csv'):
    df = pd.DataFrame(results)
    df = df[['approximant', 'snr', 'total_mass']]
    df.to_csv(output_path, index=False)
    return df
