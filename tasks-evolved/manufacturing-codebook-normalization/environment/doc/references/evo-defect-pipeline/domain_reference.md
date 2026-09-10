# Domain Reference for evo-defect-pipeline

**Responsibility**: File discovery and CSV reading with encoding fallbacks, codebook dictionary construction per product, record-level orchestration of segmentation and matching, segment_id generation, output JSON assembly conforming to the required schema, and numpy/pandas type-safe JSON serialization.

**Key functions to implement**: safe_read_csv, discover_codebooks, build_codebook_mapping, process_record, export_results_to_json, run_pipeline

---

## 5. Data Pipeline with Pandas


The context requires parsing input data and saving the output using `pandas==2.2.3`. Handling Chinese character encodings in `pandas` historically introduces severe friction.

### 5.1 Reading Mixed-Encoding CSV Files

When reading legacy factory data, files often mix `UTF-8`, `GBK`, and `ISO-8859-1` encodings [cite: 24, 25]. Standard `pd.read_csv()` throws a `UnicodeDecodeError` if a single byte violates the strict `utf-8` decoder [cite: 26, 27].

The `encoding_errors` parameter (introduced in Python 3 and supported by Pandas) dictates how to handle decoding failures [cite: 28, 29]. Using `encoding_errors='replace'` injects a replacement marker (``) instead of crashing the pipeline, allowing the rest of the text to be processed [cite: 28]. 

Furthermore, Chinese text often includes full-width quotes or irregular escaping that breaks the default C-engine parser, throwing `ParserError: EOF inside string` [cite: 30]. Using the `engine='python'` fallback is slower but exponentially more resilient [cite: 24].

```python
import pandas as pd

def safe_read_csv(file_path: str) -> pd.DataFrame:
    try:
        # Attempt standard UTF-8 parsing with strict error handling
        return pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback 1: Try GBK (Standard for simplified Chinese systems)
        try:
            return pd.read_csv(file_path, encoding='gbk')
        except UnicodeDecodeError:
            # Fallback 2: Read with utf-8, replace bad bytes, use python engine for quote safety
            return pd.read_csv(
                file_path, 
                encoding='utf-8', 
                encoding_errors='replace', 
                engine='python',
                on_bad_lines='skip' # Drops malformed rows instead of crashing
            )
```

### 5.2 Building Lookup Dictionaries

Iterating over a parsed codebook CSV to create a mapping:
```python
def build_codebook_mapping(codebook_df: pd.DataFrame, code_col: str, text_col: str) -> dict:
    # Ensure no NaN values corrupt the mapping
    df_clean = codebook_df.dropna(subset=[code_col, text_col])
    # Build dictionary mapping standard text to its code
    # (Values are preprocessed to ensure parity during matching)
    return {
        preprocess_text(str(row[text_col])): str(row[code_col])
        for _, row in df_clean.iterrows()
    }
```

### 5.3 JSON Serialization Issues with Numpy Data Types

A notorious pitfall in Pandas/JSON data pipelines is the `TypeError: Object of type int64 is not JSON serializable` [cite: 31, 32]. When Pandas performs aggregations or data type inferences, standard integers are cast to `numpy.int64` [cite: 31, 33]. The native `json` library explicitly refuses to serialize `numpy` types because they do not inherit from Python's base `int` or `float` classes [cite: 31, 34].

**Solution: Subclassing `json.JSONEncoder`**
To recursively sanitize the output schema before dumping, inject a custom encoder [cite: 34, 35]:

```python
import json
import numpy as np

class PandasNumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj) # Convert np.int64 to native int
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if pd.isna(obj): # Handle pd.NA, np.nan
            return None
        return super(PandasNumpyEncoder, self).default(obj)

def export_results_to_json(data: list[dict], output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dumps(
            data, 
            f, 
            cls=PandasNumpyEncoder, 
            ensure_ascii=False, # CRITICAL: True turns Chinese into \uXXXX hex codes
            indent=2
        )
```
Setting `ensure_ascii=False` is non-negotiable for multilingual outputs; without it, Chinese characters are irreversibly serialized into unreadable ASCII escape sequences in the file payload.

---

## 6. End-to-End Working Code Patterns


Below is the integrated, modular pipeline incorporating the techniques discussed above. This utility class serves as the core skill for an AI coding agent handling defect log ETLs.

```python
import difflib
import re
import unicodedata
import pandas as pd
import json
import numpy as np
from pathlib import Path
from typing import List, Dict

class DefectNormalizer:
    def __init__(self, codebook_dict: Dict[str, str]):
        """
        Initializes the normalizer.
        codebook_dict maps standard descriptive text to a specific defect code.
        e.g., {"screen cracked": "D001", "划伤": "D002"}
        """
        self.codebook = {
            self._preprocess(text): code 
            for text, code in codebook_dict.items()
        }
        self.standard_texts = list(self.codebook.keys())
        self.threshold = 0.55

    def _preprocess(self, text: str) -> str:
        if not isinstance(text, str): return ""
        text = unicodedata.normalize('NFKC', text).lower()
        # Custom domain expansions
        text = re.sub(r'\bng\b', 'defect', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _get_ngrams(self, text: str, n: int = 2) -> list:
        if len(text) < n: return [text]
        return [text[i:i+n] for i in range(len(text)-n+1)]

    def _cosine_similarity(self, s1: str, s2: str) -> float:
        from collections import Counter
        import math
        v1, v2 = Counter(self._get_ngrams(s1)), Counter(self._get_ngrams(s2))
        intersection = set(v1.keys()) & set(v2.keys())
        numerator = sum([v1[x] * v2[x] for x in intersection])
        sum1 = sum([v**2 for v in v1.values()])
        sum2 = sum([v**2 for v in v2.values()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        return numerator / denominator if denominator else 0.0

    def match_segment(self, segment_text: str) -> Dict:
        """Fuzzy matches a single segmented string against the codebook."""
        clean_text = self._preprocess(segment_text)
        
        # Edge cases: pure whitespace or empty
        if not clean_text:
            return {"predicted_code": "UNKNOWN", "confidence": 0.0, "match_text": ""}

        best_match = None
        best_score = 0.0

        for standard in self.standard_texts:
            sm_ratio = difflib.SequenceMatcher(None, clean_text, standard, autojunk=False).ratio()
            cos_sim = self._cosine_similarity(clean_text, standard)
            # Ensemble Score
            score = 0.6 * sm_ratio + 0.4 * cos_sim
            
            if score > best_score:
                best_score = score
                best_match = standard

        # Calibration & Thresholding
        if best_score >= self.threshold:
            calibrated_conf = 0.5 + 0.5 * ((best_score - self.threshold) / (1.0 - self.threshold))
            return {
                "predicted_code": self.codebook[best_match],
                "confidence": round(calibrated_conf, 4),
                "match_text": best_match
            }
        else:
            calibrated_conf = (best_score / self.threshold) * 0.49
            return {
                "predicted_code": "UNKNOWN",
                "confidence": round(calibrated_conf, 4),
                "match_text": None
            }

    def process_raw_reason(self, raw_reason: str) -> List[Dict]:
        """Splits raw compound text and maps each segment."""
        if pd.isna(raw_reason):
            return []
            
        pattern = re.compile(r'[,;/\n，；、]+')
        segments = []
        start = 0
        
        # Iteratively split and track character spans
        for match in pattern.finditer(raw_reason):
            end = match.start()
            span_text = raw_reason[start:end].strip()
            if span_text:
                result = self.match_segment(span_text)
                result.update({"span_text": span_text, "start_idx": start, "end_idx": end})
                segments.append(result)
            start = match.end()
            
        # Final block
        final_text = raw_reason[start:].strip()
        if final_text:
            result = self.match_segment(final_text)
            result.update({"span_text": final_text, "start_idx": start, "end_idx": len(raw_reason)})
            segments.append(result)
            
        return segments

## 7. Common Pitfalls and Operational Friction


Implementing normalization logic in production yields a variety of edge-case failures. Foreknowledge of these pitfalls dramatically reduces technical debt.

### 7.1 `difflib.get_close_matches()` Defaults

Using `get_close_matches` with its default `cutoff=0.6` implies that the target string and the reference string must share at least 60% of their character sequence weighting [cite: 4, 5]. For short Chinese phrases (e.g., "破损" vs "严重破损"), the ratio calculated by `SequenceMatcher` easily dips below `0.6`. Relying blindly on the defaults results in false negatives (returning an empty list) [cite: 5]. Always construct an explicit loop relying directly on `.ratio()` combined with domain-specific conditional thresholding (as demonstrated in the `match_segment` ensemble method) instead of trusting the built-in cutoff wrapper.

### 7.2 Pandas Silently Dropping Rows

If `pandas.read_csv` encounters a misconfigured delimiter structure or EOF inside strings due to unbalanced full-width quotes (e.g., a Chinese `“` mismatched with an English `"`), the default `C` parsing engine can silently aggregate multiple rows into a single row, permanently corrupting the ingestion index [cite: 24, 30].
*   **Mitigation:** Always use `engine='python'` and `on_bad_lines='warn'` when parsing raw user input files so that parsing errors generate terminal warnings rather than stealthily dropping or merging records [cite: 24, 36].

### 7.3 File Path Discovery with `glob`

While `glob.glob("*.csv")` is a staple for file discovery, it behaves inconsistently across operating systems regarding path separators and fails to parse deeply nested directories cleanly.
*   **Mitigation:** Use `pathlib.Path` from the Python 3 standard library.
    ```python
    from pathlib import Path
    
    def discover_codebooks(directory: str) -> list[str]:
        # rglob recursively finds all CSVs
        return [str(p) for p in Path(directory).rglob("*.csv")]
    ```
    `pathlib` ensures deterministic slash normalization, which is vital if the AI agent is deployed inside cross-platform Docker containers.

### 7.4 Identical Entries and Multi-Code Collisions

A frequent error in industrial codebooks is mapping the exact same label to two different defect codes (e.g., "Scratch" mapping to both `D01` and `M05`). When a Python dictionary `{label: code}` is constructed during pipeline initialization, the latter duplicate silently overwrites the former.
*   **Mitigation:** During codebook dictionary generation, implement a check enforcing a 1-to-1 or Many-to-1 bijection. If 1-to-Many is detected, either raise a `ValueError` halting the pipeline to prompt manual codebook cleansing, or map the label to a composite code (e.g., `D01/M05`) to indicate ambiguity.

**Sources:**
1. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3jVIrvTYBNIosuBJBl5H8DaY080XNRW4BBBHN5iRqTNtVuXtL1N0_siywFmR8TkLom1uZrSEXLvSP9FrXak9tDhwdanp5Ipv1ZJEdVtp9Kf_Fx8U__NCu3-8TWdLMIbNmLoV9NzjK9w80LUlUVh1-NpbXni7i5SmydjQ4gaPNZwVr)
2. [digitalocean.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjYETLcWY3Vl07WIRUITfbHvPm9ik5hPjfinCcbopI-4jaUNoq8Mz61pEL8MWlHnbK4g5NcWiEeF-5BFzdnRzIoinYvU_2td6wEo3qaSR877ikJZ0GaX78DAfoal5c-6hogvMNEc6UgroAx8MwPgYAkcgdQzsG81CzGp_yaaUOJGXr)
3. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjdb-YlW1qOnL8qwf5_4FOPU44Bw0XiTX_qphZuYQEenJy9etEq4M4ru-1M_ADYl8o15bnkGJ5glU1Q0nv9wV_tA82d8kvUEWgPZE_-MDmCbf7CFGSJMQ5u8UWbmY7xOcAHAh3_hUa-N811-13aX_BGuaMu1PLQQqMMTl7XFYa3UdwO_6WKO1z_5o-DqU=)
4. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9zUjnKcbEbOYF3uw6pu0BDQx5X88yobz-dl6zvZEeq9VvmXeIL6dwprx0bi--wBpzgp2m8oxUFaUdCMFug89dtzOrj27cioBGqv_CIy__K-7jhep6YDDukvSxhcPKNS0zERLT)
5. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG07UbUl0npL0K4MIqALCs-ET2ZIS0TcRVQEpF3yh4p_7VsSXVFo0wwiS6zG2CS2tvegdfAB-v3QbXPaP0OaV-H-i2S9r__PI3RQHNG8YxFKkfF8w1YD1hbkUTjmj1oazCardo0k3ckO5odptdX88QdgE2WWvb28OdS0DxyBRQ3LGgTrEgQGIX4Uw0cYSjJ2hOK7Tzsze6sXZIQJYX6yxuyPebJUvza5LCSs8x1ZUpclcTO)
6. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHl7m6rCRp26sn3IgDth_ktoj5BIpe-WO0YLQ2YgWILVFobDnjoazt_3H_iVWAEiZGL7UUoJiPS-_Kp00nKFLpg887mc_FbuwVh_V5qVNtW3QzL78-XAcIsIT1ISfpXMyuWIyv_kQNyDr7q)
7. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJRMGYhrdzLn53k_cUDfA32zGjhnZyk5ipLd6Dyu8S3H_au25TDapOE0_R_lFP4ktvlLLGVMF4wOsjmgRwMzrvyikYSiKjZLeVA75RYm78OWqRrkpLrSIVMtDdfL3i6ttugosND_dtiVEDvXjVeOoZiw2ig4do5HzhEZEsJtUQpVudXzY6_L_gIf0lGQ==)
8. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG3cpZ4Q5wWOrukrB6gp7VBKh-7WGRKcfO1zJoXPqNCJtr3eM1LzDil2VsC5GN8_PpeUYKJ6bWq75TN4l7xVWLsSmFmNcWC4BgitCYBtjVlaWajzVJFwbaa8nnN9XDD8evVnzZ-D5dxzXQPr3tR_3OQZOdB7Q_1ILk8-Odrejnl5fVJJqmP1L8MBQEzeHjxMA==)
9. [wangonya.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZoUiRg4DNxVLl1XNrKzgksg4S5pQn1GhmZXVLS-25ihUrIYXmCj9AU6kUplJaUBGoWshMjFXVYJF5uNKgAEia-WD06iesZcQAOXSi9IfTJg6UDvZ1S1YD)
10. [statology.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEGCPj-w7haHwI04Lu8H6jFPkT6lK6o8G3UBBka1E1e-Qtm_qheenHOXVysRtdtyH42exTcGMdXj9b1_cuhoFOZcHTZRTk-1x4f3bBEYYNGKy8-sX_SKP5Sx-34iBeoZQNegCZc2jdkeepuRV-ee-U=)
11. [scaler.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGP-4Pnl5NmgekGZeLy1RnF1HEppSmk_-T7gwLWhmsYr4hrrBjQGRVuIFT0JBpymPEa2zmwuyr70TOdi2s8xNpauxHikZ9goih15vnqypaLeLe6KZKAe31_Hw2Zg5IRqZI2QZ8-boD8GG_qyXeVSSiA)
12. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGA3jY_lmebos_wAKk3jXVMCYs8Gjgv5yvt5Topkq91HlzzzNa0AayqhUz1a7WHzFuLZMAut94R6L5Ro9_t-ohUm_TiVmFpMzKR-zQ8RLthJi0I0PUpJGTVyRJNgOqlGC-d2Yvc-3I=)
13. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6Qt2KvLbawSDHcnJWyABlRVOfmTHGRYPYzU6-FmtB8RqlQWeYcVWMfj8npxhE6zKhYeuMAG9iq-cdi5ZlVT58tJIspe-9hn2yNuEJiGRtbLoYvk4zwhDex-jOVy9TY0C1EMAJ1akVI5_dU9Jcrj00aBOOMjIsRueQVZkc0popcJ1DvkUx)
14. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGu8Q_MvycMVzBZRvEbPYTdId_ixlahu2EKr3_NFTW-pKFrIf7WwXTAARDnf3nvWEs-xY1WJmlgpVlh6KNzgZo1NTej0Gic8ths3U5eoP8uBVL8sRKjNDE0C7BS-zI2LCWBrI51pLGSaXUOm-xv4reFfaJYJ6jfswjrRFJf6Z-NxZgpS86IPWM=)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpeVho-odENn7I1ez4FVZQJ85VK47LP-1Z3Udz70-iHrHnZtF-LKR5IhkDe2Ma6rt54x5phCLyYK-n_J_mrkgQ8YjQAskuNSOnqod5wtKhvn21nT9CWqmYMUjg0r26Zwi5kqWqGJDfYe8eqay3Nhaw7bLQce4pNQi-FggCMpywJtYm8vJh0jcrzOR3hq4gwRQrx0tDni9YNoKZWBCcCCRuxgGcP6re5SCznmQ=)
16. [labex.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFfcT5mHNuBMMOvXbmeEwHlXyZf2i_fUgIcGd4ftnVeEgPzJcaQ1lSssogeTOGKvqoTo-oSxTbMlKHaQiru2KvtMSmzZwUp_knWWd5aeaPz0QnI-g5_rL99_GEh17WRJjEx8zsQ74GGj__waSDrvQdRbwBLHeARJaepAtryU9DWPbC9qA==)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEb9T42MA2bs2Geg4nPtEZEowxm-2aXJMVTECNYzN0P8m_HUVEWAiN9aTpHBLxvoIeHWDehLPn-cH7N8kosCXQ5DzQHScR8wI5SFW_Phe0nJ7uXGpIiU5dTL_bSCHJ13cqi0QyrnmZIQ8i9WX__6KkElp971mAbsrsvpUQvPnBrWlCp1K2AyjgL6GKge7daHBkhMAm6W0Llb3wujSdIB5eAKnmkl7s9VDJx3OG_torjaCWi2g==)
18. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaajTFT1URJFGveOdxe3w6moEaZ1aDsedNHxUQiewAprPePlaaX1N8keJzJugXZvFuWv8vDL60UbRRdhp4mJr3_jo3-3xzVM0FTSzBosIMixjW3ijq0Las8-iAiDKg8-wAUi_Rh-H5CRFVruBy9Mf3auIWD-lWprUbheTzvX9hPB6LGSMK)
19. [codequest.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmOU9mo4SkcbZuIzfT1cLRw5I5WvauYXFZj3_1fFMEQedkFyHoDGahBWd8rRHjkibYYCRNaBZ2364b92hiGNc57QslXLL4LhZH2FlgmD4vsyDurPGI4LhoHc78uULPXBhqqB289v9ba0H7l39B1o6hnmcfV_OytWxf)
20. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7Cxp3LcPqiQ6WsvZYEv8F5UjJX8JTSFPJIz9LEglvB-PmPuU2Fk_wRBAGWS4alIW21HQ7f8O_UuNcB1H7zqnGUMEtXr8w3m6Da_aV84O6KEuxozBbQcuFkH2iKPOANJg9xEzs89Gssb2wq9WC404OGNWzuVyxe4REBgDsu3fWvW607HaKKqLGzPHfFtPuouabQs7dFUJkBS0TgMzmOY_I)
21. [kingslermachinery.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGleg-p6wB0BWvh3yp4GkoAhW76pfLfNdtWPyK34RZB2tVrW6VMN0bGF4u4DBV5zQD-iA_Ip_V5xRAfaRXdG7osxZWnnmCm28q9IIiETVNVaMGTnhXPJkjUIvnhtONhpY9aH1QPjVnkyvCuNjwFew==)
22. [inspectionxpert.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFvDt5syloRMU99Jh4RwbWkU6WwId675fev5hK8mPRn6pfaPXn0-9t5qlR3Hc86XEQxLc2l78ndxmV_wk2gnAYi3DTHIipOXx3PoE1NNb9mauh83ikZL7uNSnGEkOHSX5Ln39HvTMkDLcvxHdkuD9IjtyljvnLiClOorKxnyc0vhSFoIJlIY-RR0zADSSSB2d3rzS5nvxK2c8pQDwCuhZwnGaeMq_ql)
23. [rockhillasia.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGcYwql1kLNgFM7d5Ah7YljssWIPNMjcoFSpEEtGxCfM9iRK1j3YQvzO6GB--eoxCehYShk2unF6fy7JAp6nrDFlW-jBHg8k_Vwh6vpinUqM_87JUMatxgm1hSM0R5h7zVH3jNfG6Rsw62qWUrO0PcPD1ZghOsLBbC-UxZjJysSxhIAaThLIShKbtPI3_ZK)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEIYMDUgezWDWo4RbbAYCSQ_sPCNGRuc6KsY0hYqVPh6QjUhkMp_PL6l3gH5quASEst0-kWziFlbzU1UO3aljWkl5BPgrCdEHa7iwNTggoYyKzSg_o4aq4PanKiwMBrVxR6Ji6FS_m_AypETDqJIq5A9fxJzdQTOkYRv6UGtQJCVNsgp1_KRZfNNn_L-SptrKldLDg=)
25. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzKLZWOuI5m5zehMxQ6ZDcnLMnwOPtS4vzu99j5oxsfb-liZ8WkmL82YLKnkXMTf_4eau5qKncTymaErOtKIw2wcjswUjDzomHoOJKycUg3KQhJceM7GppGIbBq3PwXt6hpakiVaM7g-G-SJ9NaErufxPFrRkbO0XpoLgbn7GYNEo=)
26. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjNxC3ZCyxi9oLBBuNGqYBeZlGyv5fs6iDuFZQCPmWjgOMCs9r_InCby7s_Op5Jnmc1oKiGkWST5uBIu64p85Aylr2L61FKrrF_9yZCbvQLE_BIzuZMI0H8LxiJMTxkXW_vdJbsJoA)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVYh68LM-MPussRHbVqX4dTJmwG3ypKTPRbceaTKogI8M8IdLF15cqY34AdpLF4ItytyNoRleb8bHbOdy4oG2p2hOcpgrWGSYj_Lgtgquu4OMKO8BjmkPi7_gOFhGfBvDGBgAnlqC2S--kS-6HHovXBriTyf38JtbnZDklS43jsArn1pz5FZ4D0Z8dCq-97GRugb3AbA==)
28. [nkmk.me](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgNgWBE_Cpiq_h7CsKCNqGqJqfTU7RTCdz8AWiH0wqRbUUcrH4NBvalBo15SY8RmDBfTI9tlDJco2IVutB0DAZslJ7YUqw0bsZxK7Ns6rAaHqqqyqKH6w3NBi6ZtyysaZkV0noy0N1iB8=)
29. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7zYix5oyJCrQSgjJDIc1NdDeaOY-d6_pHr4G6yFSfm4GU8mWi-Pd3h-yvOaTHhhIwEVjleG-UHxRO6eriYqGsEaDRQZ7Urn4kGQOIeUbt2oXypR-SJk-RTsJZpm-HrH2NQ7ISuyGCuF-rbts8khFn7O6d2j1OV0XE)
30. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFXZrK5qDC30sDJpuY9iaY_FRgfEU-ID99bZlBJ_Z8sSVTjJrSNsANStbg_E-2Uipze0BA0qA3aGmOq6SHswGPonRIuVNWYMGK0G_bwC56BPejKLMtOMw1Upg3woD2pksrOZj3qvbnPTZGncw9xONQtmW6k-Qt1SpZGQ1yKdqMqMvFJ_G4GNsIOJQw4NVyjPHFu8Uf0SmlOQ_PU2xJJwT7hqSgw8tyDhNxInbvBNVCT6lo=)
31. [codemia.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGcCbxN-CoLTDkpApFJj0Jp4Xnxd45du5auPtrX1KJL17DK6uAp9i87p9sfsHOeR_-7dyH5Q4yyxSD1B_V8cCzdvV-MHxyyACgBw-NHP4wuEeBZkdElqI5uIB85cjHfXNB_k7Y1osNFnJQcLNdbNTyJvH8n-WtJ5tsNQthQh2gnKae9yVNoWU0Z8FkzB8mepHsGBmdPrWlv31BkjT0=)
32. [itsourcecode.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwCIWC_o_Y22MJeR9R4JlEDIPFHeedWXN0f0m9u_c9rrw6_3VZ0qVwRpDdWKU-PLPdi-6RyUZPskVz8_LJ5VaRopGSjMWtIwCFKo_TM28u7vpuR08TUkdue7XKKzYuv1Ig884GCga3uaotmQda4I8QyTXGD8YLB3f3HOeEIxfss04rIf1XbcSm7ZCSPrCDi6Lj)
33. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZQOG5ZE9j7kRE2qYg17Vie0hW776o33BXhcg0d8avHFyDmcO40mBSCcZg_7CrqknFR1WNcjHom12hugsTdjhZysmBWRs8-VvHqMfZeZdf3z3ssApngUOU1b32zQC8zmQs0fS75UVzJtUV_nM4TUrTUJGFHnXCYT83-a8dIF8vzNeyluJ9VgJf1AmwesIvA2W5V5lQooH1Y1hlIabRPQxrwSDWDYm0ZY5guMGA_j-C2A==)
34. [hanarosg.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYdpBNtZoo1ZwnTiLxTzWSOJATeis3EBApKG8qUS3NFUli7ihg1nt_4sGl_KWEYohRxREAgH6M_ZXGxz8Q6roqBQmtYEU5wlcnmdk1O1BDclxxP5x1RYNM1zzMzUmUarhsNQwo-7BUztyxCN2D-TI=)
35. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-eycghoT1B3AY4LkDaDDEpjPEqCEMbjjeut7KEaNsGHnILvKqDGMXl_P2Tvefc0-efGbhvtPA16w9eWRmninmJMEf3xEwJByD5wiD0pjLhMgel180-M65X5fpwH-wtUVeHQt1SDJI404J_sqK209TvSrATy75znUEvD3AKUGE7Tn-6kDp3YTuJKSPEClw2Y3xYpppNu6Wau66PMWHgvC80Q==)
36. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAg4mxf2xYU6WcWbucjqM2UckLY2f_TrvhGtGLBrtfNKA0KhJcG9jPvoJQfmh9IPGLR47nnQQGYrMpdhj2lUnJ-GXiO_4PNRpA0AegTDKp5yx5fAsB0LLcMvakdzxNfAbCJsUzNE4vj6gfTdMvz7CSvvJ-eVXZzw==)