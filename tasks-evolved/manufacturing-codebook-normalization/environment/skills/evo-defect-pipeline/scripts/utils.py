import pandas as pd
import json
import os
import re
import importlib.util
from pathlib import Path
from typing import Dict, List

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

text_mod = _load_module("text_utils", "/app/environment/skills/evo-text-normalize/scripts/utils.py")
fuzzy_mod = _load_module("fuzzy_utils", "/app/environment/skills/evo-fuzzy-match/scripts/utils.py")


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        if isinstance(obj, float) and (obj != obj):
            return None
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
        return super().default(obj)


def safe_read_csv(file_path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            return pd.read_csv(file_path, encoding='gbk')
        except UnicodeDecodeError:
            return pd.read_csv(
                file_path, encoding='utf-8',
                encoding_errors='replace', engine='python',
                on_bad_lines='skip'
            )


def discover_codebooks(directory: str) -> Dict[str, str]:
    result = {}
    for p in Path(directory).rglob("codebook_*.csv"):
        name = p.stem
        product_id = name.replace('codebook_', '')
        result[product_id] = str(p)
    return result


def build_codebook_entries(codebook_df: pd.DataFrame) -> List[Dict]:
    """Build list of codebook entries with preprocessed labels and keywords."""
    entries = []
    df_clean = codebook_df.dropna(subset=['code', 'standard_label'])
    
    for _, row in df_clean.iterrows():
        code = str(row['code'])
        label = str(row['standard_label'])
        preprocessed = text_mod.preprocess_text(label)
        
        # Parse keywords from keywords_examples column
        keywords = []
        if 'keywords_examples' in row.index and pd.notna(row['keywords_examples']):
            kw_str = str(row['keywords_examples'])
            keywords = [k.strip().lower() for k in kw_str.split(',') if k.strip()]
        
        if preprocessed:
            entries.append({
                "code": code,
                "label": label,
                "preprocessed_label": preprocessed,
                "keywords": keywords
            })
    
    return entries


def process_record(row: pd.Series, codebook_entries: list,
                   threshold: float = 0.55) -> Dict:
    """Process a single record: segment raw_reason_text and match each segment."""
    record_id = str(row['record_id'])
    product_id = str(row['product_id'])
    station = str(row.get('station', ''))
    engineer_id = str(row.get('engineer_id', ''))
    raw_text = row.get('raw_reason_text', '')
    
    # Handle NaN - keep as original string
    if pd.isna(raw_text):
        raw_text = ''
    else:
        raw_text = str(raw_text)
    
    # Split compound reasons
    segments = text_mod.split_compound_reasons(raw_text)
    
    # If no segments found but there is text, treat whole text as one segment
    if not segments and raw_text.strip():
        segments = [{"span_text": raw_text.strip()}]
    
    # If still no segments (empty text), create one with the raw text
    if not segments:
        segments = [{"span_text": raw_text if raw_text else ""}]
    
    normalized = []
    for i, seg in enumerate(segments):
        span_text = seg["span_text"]
        
        # Skip truly empty spans but ensure at least one segment
        if not span_text.strip() and len(segments) > 1:
            continue
            
        clean = text_mod.preprocess_text(span_text)
        
        match_result = fuzzy_mod.match_segment(clean, codebook_entries, threshold)
        
        segment_id = f"{record_id}-S{len(normalized)+1}"
        normalized.append({
            "segment_id": segment_id,
            "span_text": span_text,
            "pred_code": match_result["pred_code"],
            "pred_label": match_result["pred_label"],
            "confidence": match_result["confidence"],
            "rationale": match_result["rationale"]
        })
    
    # Ensure at least one segment
    if not normalized:
        normalized.append({
            "segment_id": f"{record_id}-S1",
            "span_text": raw_text,
            "pred_code": "UNKNOWN",
            "pred_label": "",
            "confidence": 0.1,
            "rationale": "No matchable text found"
        })
    
    return {
        "record_id": record_id,
        "product_id": product_id,
        "station": station,
        "engineer_id": engineer_id,
        "raw_reason_text": raw_text,
        "normalized": normalized
    }


def export_results_to_json(records: List[Dict], output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    output = {"records": records}
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, cls=NumpyEncoder, ensure_ascii=False, indent=2)


def run_pipeline(data_dir: str = '/app/data', output_path: str = '/app/output/solution.json',
                 threshold: float = 0.55):
    # 1. Discover codebooks
    codebook_files = discover_codebooks(data_dir)
    print(f"Found codebooks: {list(codebook_files.keys())}")
    
    # 2. Build codebook entries per product
    product_codebooks = {}
    for product_id, filepath in codebook_files.items():
        df = safe_read_csv(filepath)
        entries = build_codebook_entries(df)
        product_codebooks[product_id] = entries
        print(f"  {product_id}: {len(entries)} entries")
    
    # 3. Read test center logs
    logs_path = os.path.join(data_dir, 'test_center_logs.csv')
    logs_df = safe_read_csv(logs_path)
    print(f"Loaded {len(logs_df)} log records")
    
    # 4. Process each record
    records = []
    for idx, row in logs_df.iterrows():
        product_id = str(row['product_id'])
        entries = product_codebooks.get(product_id, [])
        record = process_record(row, entries, threshold)
        records.append(record)
        
        if (idx + 1) % 3000 == 0:
            print(f"  Processed {idx+1}/{len(logs_df)} records...")
    
    # 5. Export
    export_results_to_json(records, output_path)
    print(f"Wrote {len(records)} records to {output_path}")
    
    return records
