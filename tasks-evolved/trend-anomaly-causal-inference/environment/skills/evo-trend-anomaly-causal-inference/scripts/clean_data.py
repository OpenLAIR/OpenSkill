import pandas as pd
import numpy as np
from sklearn.impute import KNNImputer
import warnings
import os

warnings.filterwarnings('ignore')

print("=== Step 1: Data Cleaning ===")

os.makedirs('/app/output', exist_ok=True)

# --- Clean Survey ---
print("\nCleaning survey data...")
df = pd.read_csv('/app/data/survey_dirty.csv')
print(f"  Raw: {df.shape}")

# Deduplicate on respondent ID (keep first occurrence)
df = df.drop_duplicates(subset='Survey ResponseID', keep='first')
print(f"  After dedup: {df.shape}")

# Drop rows where Survey ResponseID is missing (can't link to purchases)
df = df.dropna(subset=['Survey ResponseID'])
print(f"  After dropping null IDs: {df.shape}")

# Standardize text fields (NOT identifier columns)
text_cols = [c for c in df.columns if c != 'Survey ResponseID']
for col in text_cols:
    if df[col].dtype == object:
        # Strip whitespace; use .loc to avoid chained assignment (pandas 2.x CoW)
        df.loc[:, col] = df[col].astype(str).str.strip()
        # Replace 'nan' strings back to actual NaN
        df.loc[df[col] == 'nan', col] = np.nan

# Parse hh-size: extract numeric values
# Common dirty patterns: "1 (just me!)", "4+", plain integers, or extreme outliers
def parse_hh_size(val):
    if pd.isna(val):
        return np.nan
    val = str(val).strip()
    if val.lower() in ['nan', '']:
        return np.nan
    if '(just me' in val.lower() or val == '1':
        return 1
    if val == '4+':
        return 4
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return np.nan

if 'Q-amazon-use-hh-size' in df.columns:
    df.loc[:, 'Q-amazon-use-hh-size'] = df['Q-amazon-use-hh-size'].apply(parse_hh_size)

# Parse howmany similarly
def parse_howmany(val):
    if pd.isna(val):
        return np.nan
    val = str(val).strip()
    if val.lower() in ['nan', '']:
        return np.nan
    if '(just me' in val.lower() or val == '1':
        return 1
    if val == '4+':
        return 4
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return np.nan

if 'Q-amazon-use-howmany' in df.columns:
    df.loc[:, 'Q-amazon-use-howmany'] = df['Q-amazon-use-howmany'].apply(parse_howmany)

# Cap numeric outliers using IQR method
# This handles extreme values like hh-size of 53, 33, etc.
numeric_cols = df.select_dtypes(include=[np.number]).columns
for col in numeric_cols:
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    df.loc[:, col] = df[col].clip(lower=lower, upper=upper)

# Impute missing categorical with mode
cat_cols = df.select_dtypes(include='object').columns.tolist()
if 'Survey ResponseID' in cat_cols:
    cat_cols.remove('Survey ResponseID')
for col in cat_cols:
    if df[col].isnull().any():
        mode_val = df[col].mode()
        if len(mode_val) > 0:
            df.loc[:, col] = df[col].fillna(mode_val.iloc[0])

# Impute missing numeric with KNN
num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(num_cols) > 0 and df[num_cols].isnull().any().any():
    imputer = KNNImputer(n_neighbors=5)
    imputed = imputer.fit_transform(df[num_cols])
    df.loc[:, num_cols] = imputed
    for col in num_cols:
        df.loc[:, col] = df[col].round().astype(int)

# Final validation
null_count = df.drop(columns=['Survey ResponseID']).isnull().sum().sum()
if null_count > 0:
    print(f"  WARNING: {null_count} nulls remain in survey data, filling with mode/0")
    for col in df.columns:
        if col == 'Survey ResponseID':
            continue
        if df[col].isnull().any():
            if df[col].dtype == object:
                df.loc[:, col] = df[col].fillna('Unknown')
            else:
                df.loc[:, col] = df[col].fillna(0)

df.to_csv('/app/output/survey_cleaned.csv', index=False)
print(f"  Saved survey_cleaned.csv: {df.shape}")

# --- Clean Purchases ---
print("\nCleaning purchase data...")
pdf = pd.read_csv('/app/data/amazon-purchases-2019-2020_dirty.csv')
print(f"  Raw: {pdf.shape}")

# Drop exact duplicates
pdf = pdf.drop_duplicates()
print(f"  After dedup: {pdf.shape}")

# Drop rows missing critical fields
critical = ['Order Date', 'Purchase Price Per Unit', 'Quantity', 'Category', 'Survey ResponseID']
# Only check columns that exist
existing_critical = [c for c in critical if c in pdf.columns]
pdf = pdf.dropna(subset=existing_critical)
print(f"  After drop nulls in critical: {pdf.shape}")

# Clean monetary columns: remove $ signs, commas, convert to numeric
# Per DR: Price columns from legacy systems often have currency symbols
if 'Purchase Price Per Unit' in pdf.columns:
    pdf.loc[:, 'Purchase Price Per Unit'] = (
        pdf['Purchase Price Per Unit']
        .astype(str)
        .str.replace(r'[\$,]', '', regex=True)
    )
    pdf.loc[:, 'Purchase Price Per Unit'] = pd.to_numeric(pdf['Purchase Price Per Unit'], errors='coerce')

if 'Quantity' in pdf.columns:
    pdf.loc[:, 'Quantity'] = pd.to_numeric(pdf['Quantity'], errors='coerce')

# Parse dates with coercion (handles mixed formats)
pdf.loc[:, 'Order Date'] = pd.to_datetime(pdf['Order Date'], errors='coerce', format='mixed')
pdf = pdf.dropna(subset=['Order Date'])

# Verify date range: 2019-2020
pdf = pdf[(pdf['Order Date'] >= '2019-01-01') & (pdf['Order Date'] <= '2020-12-31')]
print(f"  After date filter: {pdf.shape}")

# Non-positive prices or quantities are invalid
pdf = pdf.dropna(subset=['Purchase Price Per Unit', 'Quantity'])
pdf = pdf[pdf['Purchase Price Per Unit'] > 0]
pdf = pdf[pdf['Quantity'] > 0]
print(f"  After positive price/qty: {pdf.shape}")

# Strip category whitespace and normalize
if 'Category' in pdf.columns:
    pdf.loc[:, 'Category'] = pdf['Category'].astype(str).str.strip()
    # Remove empty categories
    pdf = pdf[pdf['Category'].str.len() > 0]
    pdf = pdf[pdf['Category'] != 'nan']

# Save filtered purchases (original columns only, no Total_Spend)
save_cols = [c for c in ['Order Date', 'Purchase Price Per Unit', 'Quantity',
                          'Shipping Address State', 'Title', 'ASIN/ISBN (Product Code)',
                          'Category', 'Survey ResponseID'] if c in pdf.columns]
pdf[save_cols].to_csv('/app/output/amazon-purchases-2019-2020-filtered.csv', index=False)
print(f"  Saved amazon-purchases-2019-2020-filtered.csv: {pdf[save_cols].shape}")

print("\nStep 1 complete!")