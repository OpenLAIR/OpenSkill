import numpy as np
import pandas as pd
import itertools
from joblib import Parallel, delayed
import importlib.util
import os

# Load clustering eval module directly to avoid name conflicts
_clustering_spec = importlib.util.spec_from_file_location(
    "clustering_utils",
    os.path.join(os.path.dirname(__file__), 
                 '../../evo-mars-clustering-eval/scripts/utils.py')
)
_clustering_mod = importlib.util.module_from_spec(_clustering_spec)
_clustering_spec.loader.exec_module(_clustering_mod)
score_image = _clustering_mod.score_image


def load_data(citsci_path, expert_path):
    """Load citizen science and expert CSV data.
    
    Returns:
        citsci_df, expert_df, unique_images, citsci_dict, expert_dict
    """
    citsci_df = pd.read_csv(citsci_path, usecols=['file_rad', 'x', 'y'])
    expert_df = pd.read_csv(expert_path, usecols=['file_rad', 'x', 'y'])
    
    unique_images = expert_df['file_rad'].unique().tolist()
    
    citsci_dict = {}
    for file_rad, group in citsci_df.groupby('file_rad'):
        citsci_dict[file_rad] = group[['x', 'y']].to_numpy()
    
    expert_dict = {}
    for file_rad, group in expert_df.groupby('file_rad'):
        expert_dict[file_rad] = group[['x', 'y']].to_numpy()
    
    return citsci_df, expert_df, unique_images, citsci_dict, expert_dict


def evaluate_hyperparameter_combo(min_samples, epsilon, shape_weight,
                                   unique_images, citsci_dict, expert_dict):
    """Evaluate one hyperparameter combination across all images."""
    f1_scores = []
    delta_scores = []
    
    for file_rad in unique_images:
        expert_pts = expert_dict.get(file_rad, np.array([]).reshape(0, 2))
        citsci_pts = citsci_dict.get(file_rad, None)
        
        f1, delta = score_image(citsci_pts, expert_pts, epsilon, min_samples, shape_weight)
        
        f1_scores.append(f1)
        if not np.isnan(delta):
            delta_scores.append(delta)
    
    avg_f1 = np.mean(f1_scores) if len(f1_scores) > 0 else 0.0
    avg_delta = np.mean(delta_scores) if len(delta_scores) > 0 else float('nan')
    
    return {
        'F1': avg_f1,
        'delta': avg_delta,
        'min_samples': min_samples,
        'epsilon': epsilon,
        'shape_weight': shape_weight
    }


def run_grid_search(unique_images, citsci_dict, expert_dict, n_jobs=-1):
    """Run parallel grid search over all hyperparameter combinations."""
    min_samples_grid = list(range(3, 10))
    epsilon_grid = list(range(4, 25, 2))
    shape_weight_grid = [round(0.9 + i * 0.1, 1) for i in range(11)]
    
    combos = list(itertools.product(min_samples_grid, epsilon_grid, shape_weight_grid))
    print(f"Grid search: {len(combos)} combinations, {len(unique_images)} images, {n_jobs} jobs")
    
    results = Parallel(n_jobs=n_jobs, prefer='processes')(
        delayed(evaluate_hyperparameter_combo)(
            ms, eps, sw, unique_images, citsci_dict, expert_dict
        )
        for ms, eps, sw in combos
    )
    
    return pd.DataFrame(results)


def filter_results(results_df, min_f1=0.5):
    """Filter results to only keep rows with F1 > min_f1."""
    return results_df[results_df['F1'] > min_f1].copy()
