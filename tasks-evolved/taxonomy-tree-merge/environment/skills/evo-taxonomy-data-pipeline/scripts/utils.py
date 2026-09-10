import pandas as pd
import numpy as np
import re


def load_source_csvs(amz_path: str, fb_path: str, ggl_path: str) -> pd.DataFrame:
    """Load three source CSVs, add 'source' column, return combined DataFrame."""
    parts = []
    for path, src in [(amz_path, 'amazon'), (fb_path, 'facebook'), (ggl_path, 'google')]:
        df = pd.read_csv(path, dtype=str, on_bad_lines='skip')
        # Filter to category_path column only
        if 'category_path' not in df.columns:
            # Try to find
            for c in df.columns:
                if 'path' in c.lower():
                    df = df.rename(columns={c: 'category_path'})
                    break
        df = df[['category_path']].copy()
        df['source'] = src
        df = df.dropna(subset=['category_path'])
        df = df[df['category_path'].str.strip() != '']
        parts.append(df)
    combined = pd.concat(parts, ignore_index=True)
    return combined


def _clean_segment(seg: str) -> str:
    s = seg.strip()
    # Replace ampersand with 'and'
    s = s.replace('&', 'and')
    # Keep alphanumeric, spaces, hyphens, apostrophes; replace others with space
    s = re.sub(r"[^A-Za-z0-9' \-/]", ' ', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Title case
    s = s.title()
    return s


def normalize_category_paths(df: pd.DataFrame) -> pd.DataFrame:
    """Keep category_path original; create normalized_path with cleaned segments."""
    def norm_path(p):
        segs = [s.strip() for s in p.split('>')]
        segs = [_clean_segment(s) for s in segs if s.strip()]
        return ' > '.join(segs)
    df = df.copy()
    df['normalized_path'] = df['category_path'].astype(str).map(norm_path)
    return df


def split_hierarchy_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Split normalized_path into orig_level_1..N columns. Add depth column (1-5 capped)."""
    df = df.copy()
    levels = df['normalized_path'].str.split(pat=' > ', n=-1, expand=True)
    levels = levels.fillna('')
    ncols = levels.shape[1]
    levels.columns = [f'orig_level_{i+1}' for i in range(ncols)]
    df = pd.concat([df.reset_index(drop=True), levels.reset_index(drop=True)], axis=1)
    # Depth = number of non-empty segments, capped at 5
    seg_counts = df['normalized_path'].map(lambda p: len([s for s in p.split(' > ') if s.strip()]))
    df['depth'] = seg_counts.clip(lower=1, upper=5).astype(int)
    return df


def compute_source_entropy(df_cluster: pd.DataFrame) -> float:
    proportions = df_cluster['source'].value_counts(normalize=True).values
    return float(-np.sum(proportions * np.log2(proportions + 1e-9)))


def write_unified_outputs(df: pd.DataFrame, full_path: str, hierarchy_path: str):
    """Write the two required outputs."""
    cols_full = ['source', 'category_path', 'depth',
                 'unified_level_1', 'unified_level_2', 'unified_level_3', 'unified_level_4', 'unified_level_5']
    df_full = df[cols_full].copy()
    df_full.to_csv(full_path, index=False)

    hier_cols = ['unified_level_1','unified_level_2','unified_level_3','unified_level_4','unified_level_5']
    df_h = df[hier_cols].drop_duplicates().reset_index(drop=True)
    df_h.to_csv(hierarchy_path, index=False)
