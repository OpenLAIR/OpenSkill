import pandas as pd
import numpy as np

def build_conversion_registry():
    registry = {
        'Serum_Creatinine': {'us_range': [0.1, 25.0], 'si_to_us': 0.0113},
        'BUN': {'us_range': [2.0, 200.0], 'si_to_us': 2.8},
        'Serum_Calcium': {'us_range': [4.0, 16.0], 'si_to_us': 4.0},
        'Ionized_Calcium': {'us_range': [1.5, 8.0], 'si_to_us': 4.0},
        'Phosphorus': {'us_range': [1.0, 15.0], 'si_to_us': 3.1},
        'Hemoglobin': {'us_range': [3.0, 22.0], 'si_to_us': 0.1, 'alt_factor': 6.4458, 'alt_range': [0.5, 3.5]},
        'Hematocrit': {'us_range': [10.0, 70.0], 'si_to_us': 100.0},
        'Albumin_Serum': {'us_range': [0.5, 6.0], 'si_to_us': 0.1},
        'Total_Protein': {'us_range': [3.0, 12.0], 'si_to_us': 0.1},
        'Total_Cholesterol': {'us_range': [40.0, 700.0], 'si_to_us': 38.67},
        'LDL_Cholesterol': {'us_range': [10.0, 500.0], 'si_to_us': 38.67},
        'HDL_Cholesterol': {'us_range': [5.0, 150.0], 'si_to_us': 38.67},
        'Non_HDL_Cholesterol': {'us_range': [10.0, 600.0], 'si_to_us': 38.67},
        'Triglycerides': {'us_range': [20.0, 5000.0], 'si_to_us': 88.57},
        'Glucose': {'us_range': [30.0, 1200.0], 'si_to_us': 18.0},
        'HbA1c': {'us_range': [3.0, 20.0], 'conversion_type': 'linear', 'linear_params': {'slope': 0.0915, 'intercept': 2.15}},
        'Uric_Acid': {'us_range': [1.0, 20.0], 'si_to_us': 0.0168},
        'Total_Bilirubin': {'us_range': [0.05, 35.0], 'si_to_us': 0.0585},
        'Direct_Bilirubin': {'us_range': [0.0, 25.0], 'si_to_us': 0.0585},
        'Serum_Iron': {'us_range': [5.0, 400.0], 'si_to_us': 5.587},
        'TIBC': {'us_range': [50.0, 700.0], 'si_to_us': 5.587},
    }
    return registry


def detect_and_convert_value(val, config):
    if pd.isna(val):
        return np.nan
    us_low, us_high = config['us_range']
    conv_type = config.get('conversion_type', 'multiply')
    if us_low <= val <= us_high:
        return val
    if conv_type == 'multiply':
        factor = config['si_to_us']
        converted = val * factor
        if us_low * 0.8 <= converted <= us_high * 1.2:
            return converted
        # Check alt_factor (e.g., hemoglobin mmol/L)
        if 'alt_factor' in config and 'alt_range' in config:
            alt_lo, alt_hi = config['alt_range']
            if alt_lo <= val <= alt_hi:
                alt_converted = val * config['alt_factor']
                if us_low * 0.8 <= alt_converted <= us_high * 1.2:
                    return alt_converted
    elif conv_type == 'linear':
        params = config['linear_params']
        converted = val * params['slope'] + params['intercept']
        if us_low * 0.8 <= converted <= us_high * 1.2:
            return converted
    return val


def harmonize_all_features(df, skip_cols=None):
    if skip_cols is None:
        skip_cols = []
    registry = build_conversion_registry()
    for col in df.columns:
        if col in skip_cols or col not in registry:
            continue
        config = registry[col]
        df[col] = df[col].apply(lambda v: detect_and_convert_value(v, config))
    return df
