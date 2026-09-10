import difflib
import math
import re
from collections import Counter
from typing import Dict, List

def get_ngrams(text: str, n: int = 2) -> List[str]:
    if len(text) < n:
        return [text] if text else []
    return [text[i:i+n] for i in range(len(text)-n+1)]

def cosine_similarity(s1: str, s2: str, n: int = 2) -> float:
    vec1 = Counter(get_ngrams(s1, n))
    vec2 = Counter(get_ngrams(s2, n))
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[x] * vec2[x] for x in intersection)
    sum1 = sum(v**2 for v in vec1.values())
    sum2 = sum(v**2 for v in vec2.values())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    if not denominator:
        return 0.0
    return numerator / denominator

def ensemble_similarity(noisy: str, canonical: str) -> float:
    sm_ratio = difflib.SequenceMatcher(None, noisy, canonical, autojunk=False).ratio()
    cos_sim = cosine_similarity(noisy, canonical, n=2)
    return 0.6 * sm_ratio + 0.4 * cos_sim

def calibrate_confidence(raw_score: float, threshold: float = 0.40) -> float:
    if raw_score >= threshold:
        return 0.5 + 0.5 * ((raw_score - threshold) / (1.0 - threshold))
    else:
        return (raw_score / threshold) * 0.49

def compute_keyword_match(text_lower: str, keywords: list) -> dict:
    """Detailed keyword matching with category awareness."""
    if not keywords:
        return {"total": 0, "comp": 0, "type_kw": 0, "total_kw": 0, "matched": []}
    
    comp_pattern = re.compile(r'^[A-Za-z]+\d+', re.IGNORECASE)
    net_pattern = re.compile(r'^[A-Z][A-Z0-9]*_[A-Z0-9_]+$', re.IGNORECASE)
    
    total = 0
    comp = 0
    type_kw = 0
    matched = []
    
    for kw in keywords:
        kw_clean = kw.lower().strip()
        if not kw_clean:
            continue
        if kw_clean in text_lower:
            total += 1
            matched.append(kw_clean)
            if comp_pattern.match(kw) or net_pattern.match(kw):
                comp += 1
            else:
                type_kw += 1
    
    return {"total": total, "comp": comp, "type_kw": type_kw, 
            "total_kw": len(keywords), "matched": matched}

def match_segment(clean_text: str, codebook_entries: list, threshold: float = 0.40) -> Dict:
    """Match preprocessed text against codebook using keyword-centric scoring."""
    if not clean_text or not codebook_entries:
        return {
            "pred_code": "UNKNOWN", "pred_label": "",
            "confidence": round(calibrate_confidence(0.0, threshold), 4),
            "rationale": "Empty input or no codebook"
        }
    
    text_lower = clean_text.lower()
    best_entry = None
    best_score = 0.0
    best_details = ""
    
    for entry in codebook_entries:
        keywords = entry.get("keywords", [])
        prep_label = entry["preprocessed_label"]
        
        # Keyword matching
        km = compute_keyword_match(text_lower, keywords)
        
        # Keyword score: reward matches, especially component matches
        if km["total_kw"] > 0:
            base_kw = km["total"] / km["total_kw"]
            # Strong bonus for component name match (most discriminative)
            comp_bonus = 0.25 * km["comp"]
            # Bonus for type keyword match
            type_bonus = 0.1 * km["type_kw"]
            kw_score = min(1.0, base_kw + comp_bonus + type_bonus)
        else:
            kw_score = 0.0
        
        # Fuzzy similarity
        fuzzy_score = ensemble_similarity(text_lower, prep_label)
        
        # Combined scoring strategy
        if km["total"] >= 3:
            # Strong keyword evidence
            combined = 0.15 * fuzzy_score + 0.85 * kw_score
        elif km["total"] >= 2:
            combined = 0.25 * fuzzy_score + 0.75 * kw_score
        elif km["total"] == 1:
            combined = 0.45 * fuzzy_score + 0.55 * kw_score
        else:
            combined = 0.85 * fuzzy_score + 0.15 * kw_score
        
        if combined > best_score:
            best_score = combined
            best_entry = entry
            best_details = f"fuzzy={fuzzy_score:.3f},kw={kw_score:.3f}(m={km['total']}/{km['total_kw']},c={km['comp']},t={km['type_kw']})"
    
    if best_score >= threshold and best_entry is not None:
        calibrated = calibrate_confidence(best_score, threshold)
        return {
            "pred_code": best_entry["code"],
            "pred_label": best_entry["label"],
            "confidence": round(calibrated, 4),
            "rationale": f"score={best_score:.4f}, {best_details}, matched '{best_entry['label']}'"
        }
    else:
        calibrated = calibrate_confidence(best_score, threshold)
        best_label = best_entry["label"] if best_entry else "none"
        return {
            "pred_code": "UNKNOWN", "pred_label": "",
            "confidence": round(calibrated, 4),
            "rationale": f"score={best_score:.4f}<{threshold}, {best_details}, best='{best_label}'"
        }
