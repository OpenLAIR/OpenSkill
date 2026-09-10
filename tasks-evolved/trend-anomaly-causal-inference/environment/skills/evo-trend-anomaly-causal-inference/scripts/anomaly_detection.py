import pandas as pd
import numpy as np
import warnings
import logging
import os

# Suppress Prophet/cmdstanpy verbose logging (per DR: cmdstanpy backend is noisy)
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').disabled = True
warnings.filterwarnings('ignore')

from prophet import Prophet

print("=== Step 2: Anomaly Detection ===")

os.makedirs('/app/output', exist_ok=True)

# Load cleaned purchases
pdf = pd.read_csv('/app/output/amazon-purchases-2019-2020-filtered.csv')
pdf['Order Date'] = pd.to_datetime(pdf['Order Date'])
pdf['Total_Spend'] = pdf['Purchase Price Per Unit'] * pdf['Quantity']

target_start = pd.Timestamp('2020-03-01')
target_end = pd.Timestamp('2020-03-31')

# Filter categories with enough historical transactions (before target)
hist = pdf[pdf['Order Date'] < target_start]
cat_counts = hist.groupby('Category').size()
min_transactions = 30
valid_cats = cat_counts[cat_counts >= min_transactions].index.tolist()
print(f"Processing {len(valid_cats)} categories with >= {min_transactions} historical transactions")

# Also require at least some activity in March 2020 or the period around it
# to avoid scoring completely dead categories
march_data = pdf[(pdf['Order Date'] >= target_start) & (pdf['Order Date'] <= target_end)]

results = []
for i, cat in enumerate(valid_cats):
    try:
        cat_data = pdf[pdf['Category'] == cat].copy()
        daily = cat_data.groupby('Order Date')['Total_Spend'].sum().reset_index()
        daily.columns = ['ds', 'y']

        # Full date range from earliest data to end of March 2020
        min_date = daily['ds'].min()
        full_range = pd.date_range(min_date, target_end, freq='D')
        daily_full = daily.set_index('ds').reindex(full_range, fill_value=0).reset_index()
        daily_full.columns = ['ds', 'y']

        # Train/test split: train on everything before March 2020
        train = daily_full[daily_full['ds'] < target_start].copy()
        actual_target = daily_full[
            (daily_full['ds'] >= target_start) & (daily_full['ds'] <= target_end)
        ].copy()

        if len(train) < 30 or len(actual_target) == 0:
            continue

        # Per DR: Categories with zero sales cause Prophet fitting issues
        # Check that training data has non-zero variance
        if train['y'].std() == 0 and train['y'].mean() == 0:
            continue

        # Cap extreme values for modeling stability (prevent outlier-driven fits)
        cap_val = train['y'].quantile(0.99)
        if cap_val <= 0:
            cap_val = train['y'].max()
        if cap_val <= 0:
            continue
        train_capped = train.copy()
        train_capped.loc[:, 'y'] = train_capped['y'].clip(upper=cap_val * 3)

        # Fit Prophet with conservative changepoint prior
        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05
        )
        m.fit(train_capped)

        # Predict into March 2020
        days_ahead = (target_end - train['ds'].max()).days
        if days_ahead <= 0:
            continue
        future = m.make_future_dataframe(periods=days_ahead)
        forecast = m.predict(future)

        forecast_target = forecast[
            (forecast['ds'] >= target_start) & (forecast['ds'] <= target_end)
        ]
        merged = actual_target.merge(
            forecast_target[['ds', 'yhat', 'yhat_lower', 'yhat_upper']],
            on='ds', how='inner'
        )

        if len(merged) == 0:
            continue

        actual_sum = merged['y'].sum()
        predicted_sum = merged['yhat'].sum()

        # Compute deviation: (actual - predicted) / predicted
        # Per DR: Use tanh to bound to [-100, 100]
        if predicted_sum > 0:
            raw_deviation = (actual_sum - predicted_sum) / predicted_sum
        elif actual_sum > 0:
            raw_deviation = 2.0  # Strong positive signal
        else:
            raw_deviation = 0.0

        anomaly_index = 100 * np.tanh(raw_deviation)

        results.append({
            'Category': cat,
            'Anomaly_Index': round(anomaly_index, 2)
        })

        if (i + 1) % 25 == 0:
            print(f"  Processed {i+1}/{len(valid_cats)} categories")

    except Exception as e:
        # Silently skip categories that fail (e.g., singular matrices, convergence issues)
        continue

result_df = pd.DataFrame(results)

if len(result_df) == 0:
    print("WARNING: No categories could be scored. Creating empty output.")
    result_df = pd.DataFrame(columns=['Category', 'Anomaly_Index'])
else:
    result_df = result_df.sort_values('Anomaly_Index', ascending=False).reset_index(drop=True)

result_df.to_csv('/app/output/category_anomaly_index.csv', index=False)

print(f"\nCompleted: {len(result_df)} categories scored")
if len(result_df) > 0:
    print(f"Stats: mean={result_df['Anomaly_Index'].mean():.2f}, std={result_df['Anomaly_Index'].std():.2f}")
    print(f"Range: [{result_df['Anomaly_Index'].min():.2f}, {result_df['Anomaly_Index'].max():.2f}]")
    print(f"\nTop 10 surges:")
    print(result_df.head(10).to_string(index=False))
    print(f"\nTop 10 slumps:")
    print(result_df.tail(10).to_string(index=False))

print("\nStep 2 complete!")