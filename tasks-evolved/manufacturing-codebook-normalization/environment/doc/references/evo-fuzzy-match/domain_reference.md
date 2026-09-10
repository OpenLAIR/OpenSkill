# Domain Reference for evo-fuzzy-match

**Responsibility**: All similarity computation and scoring: difflib SequenceMatcher, Levenshtein distance, Jaccard similarity, cosine similarity, ensemble scoring, confidence calibration, and UNKNOWN thresholding. Does NOT handle I/O or text preprocessing.

**Key functions to implement**: levenshtein_distance, levenshtein_ratio, jaccard_similarity, cosine_similarity, get_ngrams, ensemble_similarity, calibrate_confidence, match_segment

---

## 1. Fuzzy String Matching with Python Standard Library


In a restricted runtime environment where libraries like `fuzzywuzzy` or `python-Levenshtein` cannot be installed via `pip`, the Python standard library provides sufficient primitives to implement robust fuzzy string matching algorithms [cite: 1, 2]. The primary tool for this is the `difflib` module, supplemented by custom mathematical implementations of edit distance and set-based similarity metrics.

### 1.1 `difflib.SequenceMatcher`


The `difflib.SequenceMatcher` class is a highly flexible utility for comparing pairs of hashable sequences [cite: 3, 4]. The underlying algorithm predates standard minimal edit distance algorithms; it is based on Ratcliff and Obershelp's "Gestalt pattern matching" algorithm from the late 1980s [cite: 3, 5]. 

The fundamental principle of Gestalt pattern matching is to identify the longest contiguous matching subsequence that contains no "junk" elements. Once this matching block is found, the algorithm recursively applies the same logic to the pieces of the sequences lying to the left and the right of the matched block [cite: 3, 6]. This approach does not yield minimal edit sequences (like Levenshtein), but it excels at producing matches that intuitively "look right" to human readers [cite: 4, 5].

### 1.2 Custom Implementation of Levenshtein Distance


While `SequenceMatcher` is human-friendly, it calculates sequence overlap rather than absolute transformation cost. The Levenshtein distance (edit distance) is defined as the minimum number of single-character operations (insertions, deletions, substitutions) required to transform string \(A\) into string \(B\) [cite: 10, 11]. 

Implementing Levenshtein in pure Python requires dynamic programming to achieve an \(O(N \times M)\) time complexity, where \(N\) and \(M\) are the lengths of the two strings [cite: 2, 12]. 

*Dynamic Programming Matrix Implementation:*
```python
def levenshtein_distance(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    # Initialize an (m+1) x (n+1) matrix
    dp = [ * (n + 1) for _ in range(m + 1)]
    
    # Base cases: transforming to empty string requires deletion
    for i in range(m + 1):
        dp[i] = i
    for j in range(n + 1):
        dp[j] = j
        
    # Fill the DP matrix
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # Deletion
                dp[i][j - 1] + 1,      # Insertion
                dp[i - 1][j - 1] + cost # Substitution
            )
            
    return dp[m][n]

def levenshtein_ratio(s1: str, s2: str) -> float:
    # Convert absolute distance to a 0.0 - 1.0 confidence score
    dist = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (dist / max_len)
```
This metric is highly critical in QA contexts where typographical errors in acronyms (e.g., "PCB" vs "PBB") create high edit distance ratios despite short string lengths [cite: 13].

### 1.3 Jaccard Similarity and Cosine Similarity (n-grams)


For text fields where word ordering is jumbled (e.g., "Scratch Panel" vs "Panel Scratch" or "划伤 屏幕" vs "屏幕 划伤"), `SequenceMatcher` and Levenshtein penalize the reordering heavily. Set-based metrics like Jaccard and Cosine similarity over character n-grams resolve this [cite: 13].

*Jaccard Similarity* computes the intersection over the union of two sets.
\[ J(A, B) = \frac{|A \cap B|}{|A \cup B|} \]

*Cosine Similarity* measures the angle between two frequency vectors.

```python
from collections import Counter
import math

def get_ngrams(text: str, n: int = 2) -> list[str]:
    # Pad string if shorter than n
    if len(text) < n:
        return [text]
    return [text[i:i+n] for i in range(len(text)-n+1)]

def jaccard_similarity(s1: str, s2: str, n: int = 2) -> float:
    set1, set2 = set(get_ngrams(s1, n)), set(get_ngrams(s2, n))
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def cosine_similarity(s1: str, s2: str, n: int = 2) -> float:
    vec1 = Counter(get_ngrams(s1, n))
    vec2 = Counter(get_ngrams(s2, n))
    
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    
    sum1 = sum([val**2 for val in vec1.values()])
    sum2 = sum([val**2 for val in vec2.values()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    
    if not denominator:
        return 0.0
    return numerator / denominator
```

---

## 4. Codebook Matching and Confidence Calibration


Once a raw string is normalized and segmented, it must be mapped against the standard codebook. Mapping yields a confidence score, but raw string metric scores (like `difflib.ratio()`) are often deceiving and require calibration.

### 4.1 Computing a Meaningful Confidence Score


A best practice is to compute an ensemble score combining the order-preserving Gestalt similarity (`SequenceMatcher`) and the order-agnostic Cosine n-gram similarity. 

```python
def ensemble_similarity(noisy: str, canonical: str) -> float:
    # 1. difflib SequenceMatcher
    sm_ratio = difflib.SequenceMatcher(None, noisy, canonical, autojunk=False).ratio()
    
    # 2. Character Bigram Cosine Similarity
    cos_sim = cosine_similarity(noisy, canonical, n=2)
    
    # Weighting: heavily favor Gestalt if the strings are very similar, 
    # but let Cosine save the score if word order is swapped.
    return 0.6 * sm_ratio + 0.4 * cos_sim
```

### 4.2 Thresholds and "UNKNOWN" Classification

Industrial AI applications strictly demand an "UNKNOWN" classification rather than confidently predicting an incorrect defect code. When `difflib.get_close_matches()` uses a default `cutoff=0.6`, it may inadvertently return matches for short words that are conceptually completely different but share a few characters [cite: 4, 5].

For manufacturing contexts:
*   **Threshold formulation:** The threshold should scale inversely with string length. A ratio of `0.6` on a 4-character string means only ~2 characters match (highly unreliable). A ratio of `0.6` on a 50-character string indicates significant lexical overlap.
*   **Absolute Minimums:** Establish a hard floor (e.g., `0.55` for ensemble scoring) below which all matches are mapped to `UNKNOWN_CODE`.

### 4.3 Engineering Calibration

A calibrated confidence score should reflect statistical probability. If the raw ensemble score is \(0.6\), but \(0.55\) is the UNKNOWN threshold, returning a confidence of \(0.6\) to the user is confusing (it looks like a failing grade). 

**Min-Max Scaling with a Threshold Shift:**
Translate the raw score space \([\text{threshold}, 1.0]\) into a user-facing confidence space \([0.5, 1.0]\). If the prediction is UNKNOWN, the confidence is defined by the margin below the threshold.

```python
def calibrate_confidence(raw_score: float, threshold: float = 0.55) -> float:
    if raw_score >= threshold:
        # Scale [threshold, 1.0] -> [0.5, 1.0]
        return 0.5 + 0.5 * ((raw_score - threshold) / (1.0 - threshold))
    else:
        # UNKNOWN prediction gets a low confidence
        # Scale [0.0, threshold) -> [0.0, 0.49]
        return (raw_score / threshold) * 0.49
```
This calibration ensures that UNKNOWN predictions intrinsically possess lower confidence scores than non-UNKNOWN predictions, establishing a statistically coherent distribution.

---