import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

def train_random_forest(X, y, n_estimators=100, random_state=42):
    """Train a Random Forest Regressor.
    
    Args:
        X: DataFrame or array of predictor features
        y: Series or array of target variable (water temperature)
        n_estimators: number of trees (default 100)
        random_state: random seed for reproducibility
    
    Returns:
        fitted RandomForestRegressor model
    """
    rf = RandomForestRegressor(n_estimators=n_estimators, random_state=42)
    rf.fit(X, y)
    return rf

def compute_feature_importances(model, feature_names):
    """Extract feature importances from a fitted Random Forest model.
    
    Args:
        model: fitted RandomForestRegressor
        feature_names: list of feature column names
    
    Returns:
        DataFrame with columns: feature, importance, contribution_pct
        - importance: raw feature_importances_ values (sum to 1.0)
        - contribution_pct: percentage contribution (sum to 100%)
    """
    importances = model.feature_importances_
    pct = importances * 100
    
    df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances,
        'contribution_pct': pct
    }).sort_values('contribution_pct', ascending=False).reset_index(drop=True)
    
    return df

def map_features_to_categories(importance_df, category_map):
    """Map features to their physical categories and aggregate contributions.
    
    Args:
        importance_df: DataFrame from compute_feature_importances()
        category_map: dict mapping feature_name -> category (e.g., {'AirTempLake': 'Heat'})
    
    Returns:
        DataFrame with columns: category, contribution_pct, sorted descending
    """
    importance_df = importance_df.copy()
    importance_df['category'] = importance_df['feature'].map(category_map)
    
    category_contributions = importance_df.groupby('category')['contribution_pct'].sum()
    category_contributions = category_contributions.sort_values(ascending=False).reset_index()
    category_contributions.columns = ['category', 'contribution_pct']
    
    return category_contributions

def get_dominant_category(category_contributions):
    """Get the most important category and its contribution.
    
    Args:
        category_contributions: DataFrame from map_features_to_categories()
    
    Returns:
        tuple: (category_name, contribution_percentage)
        contribution is in decimal form (0-1 range, e.g., 0.45 for 45%)
    """
    top = category_contributions.iloc[0]
    category_name = top['category']
    # Convert from percentage to decimal (0-1 range)
    contribution = top['contribution_pct'] / 100.0
    return category_name, contribution

def save_dominant_factor(category_name, contribution, output_path='/root/output/dominant_factor.csv'):
    """Save the dominant factor to CSV with columns: variable, contribution.
    
    Args:
        category_name: string, the dominant category (Heat/Flow/Wind/Human)
        contribution: float, contribution in decimal form (0-1 range)
        output_path: path to output CSV file
    """
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    result_df = pd.DataFrame([{
        'variable': category_name,
        'contribution': contribution
    }])
    result_df.to_csv(output_path, index=False)
    return result_df
