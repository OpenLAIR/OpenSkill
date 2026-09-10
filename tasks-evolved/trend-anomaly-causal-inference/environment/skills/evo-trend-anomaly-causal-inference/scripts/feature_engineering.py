import pandas as pd
import numpy as np
import warnings
import os

warnings.filterwarnings('ignore')

print("=== Step 3: Feature Engineering ===")

os.makedirs('/app/output', exist_ok=True)

df = pd.read_csv('/app/output/survey_cleaned.csv')
print(f"Input: {df.shape}")
original_ids = df['Survey ResponseID'].copy()
original_count = len(df)

# Separate ID column
result = pd.DataFrame({'Survey ResponseID': df['Survey ResponseID']})

# Process each column
for col in df.columns:
    if col == 'Survey ResponseID':
        continue

    vals = df[col]
    nunique = vals.nunique()

    # Skip columns with only 1 unique value (no information)
    if nunique <= 1:
        print(f"  Skipping constant column: {col}")
        continue

    # Check if numeric already
    if pd.api.types.is_numeric_dtype(vals):
        result[col] = vals
        continue

    # Binary columns (2 unique values)
    if nunique == 2:
        val_list = vals.unique().tolist()
        # Remove NaN from consideration if present
        val_list = [v for v in val_list if pd.notna(v)]

        if len(val_list) == 2:
            # Check for Yes/No pattern
            if 'Yes' in val_list and 'No' in val_list:
                result[col] = (vals == 'Yes').astype(int)
            elif 'Male' in val_list and 'Female' in val_list:
                result[col] = (vals == 'Male').astype(int)
            else:
                # Generic binary: alphabetically second = 1
                sorted_vals = sorted(val_list)
                mapping = {sorted_vals[0]: 0, sorted_vals[1]: 1}
                result[col] = vals.map(mapping).fillna(0).astype(int)
        elif len(val_list) == 1:
            # Only one non-null value + NaN
            result[col] = (vals == val_list[0]).astype(int)

    # Categorical with >2 levels: one-hot encode
    elif nunique > 2:
        # Per DR: Use drop='first' equivalent by removing one dummy to avoid
        # multicollinearity in OLS regressions (dummy variable trap)
        dummies = pd.get_dummies(vals, prefix=col, dtype=int)
        result = pd.concat([result, dummies], axis=1)

# Remove constant features (only one unique value after encoding)
cols_to_check = [c for c in result.columns if c != 'Survey ResponseID']
constant_cols = []
for col in cols_to_check:
    if result[col].nunique() <= 1:
        constant_cols.append(col)
if constant_cols:
    result = result.drop(columns=constant_cols)
    print(f"  Dropped {len(constant_cols)} constant features")

# Remove redundant columns for binary variables that were one-hot encoded
# When a binary variable (Yes/No) gets one-hot encoded, remove the negative indicator
cols = [c for c in result.columns if c != 'Survey ResponseID']
cols_to_drop = []
for col in cols:
    if col.endswith('_No') or col.endswith('_Female'):
        # Check if corresponding positive exists
        base = col.rsplit('_', 1)[0]
        positive = base + '_Yes' if col.endswith('_No') else base + '_Male'
        if positive in cols:
            cols_to_drop.append(col)

if cols_to_drop:
    result = result.drop(columns=cols_to_drop)
    print(f"  Dropped redundant binary columns: {cols_to_drop}")

# Replace infinities and fill any remaining NaN
num_cols = result.select_dtypes(include=[np.number]).columns
for col in num_cols:
    result.loc[:, col] = result[col].replace([np.inf, -np.inf], np.nan)
    if result[col].isnull().any():
        median_val = result[col].median()
        result.loc[:, col] = result[col].fillna(median_val if pd.notna(median_val) else 0)

# Verify row preservation
assert len(result) == original_count, f"Row count changed: {original_count} -> {len(result)}"
assert (result['Survey ResponseID'] == original_ids).all(), "IDs changed!"

result.to_csv('/app/output/survey_feature_engineered.csv', index=False)
print(f"Output: {result.shape}")
print(f"Feature columns: {len(result.columns) - 1}")
print(f"Sample columns: {list(result.columns[:15])}...")
print("\nStep 3 complete!")