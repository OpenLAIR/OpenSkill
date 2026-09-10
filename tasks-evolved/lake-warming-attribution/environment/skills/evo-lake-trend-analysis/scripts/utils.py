import pandas as pd
import numpy as np
import pymannkendall as mk

def run_mann_kendall_trend(temperature_series, method='original', alpha=0.05):
    """Run Mann-Kendall trend test on a temperature time series.
    
    Args:
        temperature_series: pandas Series or 1D array of temperature values.
                           NaN values are automatically dropped.
        method: 'original', 'hamed_rao', or 'yue_wang'
        alpha: significance level (default 0.05)
    
    Returns:
        dict with keys: slope, p_value, trend, h, z, Tau, s, var_s, intercept
        - slope: Sen's slope (Theil-Sen estimator) in units per time step
        - p_value: p-value of the test
        - trend: 'increasing', 'decreasing', or 'no trend'
    """
    # Clean: drop NaN values (pymannkendall cannot handle NaNs)
    if isinstance(temperature_series, pd.Series):
        clean = temperature_series.dropna()
    else:
        clean = pd.Series(temperature_series).dropna()
    
    if len(clean) < 4:
        return {'slope': np.nan, 'p_value': np.nan, 'trend': 'insufficient data'}
    
    # Select test method
    if method == 'hamed_rao':
        result = mk.hamed_rao_modification_test(clean, alpha=alpha)
    elif method == 'yue_wang':
        result = mk.yue_wang_modification_test(clean, alpha=alpha)
    else:
        result = mk.original_test(clean, alpha=alpha)
    
    return {
        'slope': result.slope,
        'p_value': result.p,
        'trend': result.trend,
        'h': result.h,
        'z': result.z,
        'Tau': result.Tau,
        's': result.s,
        'var_s': result.var_s,
        'intercept': result.intercept
    }

def save_trend_result(trend_dict, output_path='/root/output/trend_result.csv'):
    """Save trend analysis result to CSV with columns: slope, p-value.
    
    Args:
        trend_dict: dict from run_mann_kendall_trend()
        output_path: path to output CSV file
    """
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    result_df = pd.DataFrame([{
        'slope': trend_dict['slope'],
        'p-value': trend_dict['p_value']
    }])
    result_df.to_csv(output_path, index=False)
    return result_df
