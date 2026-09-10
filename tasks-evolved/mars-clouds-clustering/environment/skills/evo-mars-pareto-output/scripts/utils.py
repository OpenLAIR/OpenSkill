import pandas as pd
import numpy as np
from paretoset import paretoset


def compute_pareto_frontier(results_df):
    """Compute Pareto frontier from grid search results.
    
    Maximize F1, minimize delta.
    """
    valid = results_df.dropna(subset=['delta']).copy()
    
    if len(valid) == 0:
        return pd.DataFrame(columns=['F1', 'delta', 'min_samples', 'epsilon', 'shape_weight'])
    
    objectives = valid[['F1', 'delta']]
    mask = paretoset(objectives, sense=['max', 'min'])
    
    return valid[mask].copy()


def format_and_save_pareto_csv(pareto_df, output_path='/root/pareto_frontier.csv'):
    """Format and save Pareto frontier to CSV with exact decimal places.
    
    F1: 5 decimal places
    delta: 5 decimal places  
    shape_weight: 1 decimal place
    min_samples: integer
    epsilon: integer
    """
    out = pareto_df.copy()
    
    # Build formatted strings to preserve trailing zeros
    lines = ['F1,delta,min_samples,epsilon,shape_weight']
    for _, row in out.iterrows():
        line = f"{row['F1']:.5f},{row['delta']:.5f},{int(row['min_samples'])},{int(row['epsilon'])},{row['shape_weight']:.1f}"
        lines.append(line)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    
    print(f"Saved Pareto frontier ({len(out)} points) to {output_path}")
    return out
