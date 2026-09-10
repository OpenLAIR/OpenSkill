---
name: evo-fuzzy-match
description: Fuzzy string matching and confidence calibration for mapping normalized text segments against codebook entries. Implements SequenceMatcher, Levenshtein, Jaccard, cosine similarity, ensemble scoring, and UNKNOWN thresholding.
---

# evo-fuzzy-match

Fuzzy matching algorithms with calibrated confidence for manufacturing codebook matching.

## Key Functions

- `levenshtein_distance(s1, s2)` - Edit distance
- `levenshtein_ratio(s1, s2)` - Normalized 0-1 similarity
- `get_ngrams(text, n=2)` - Character n-grams
- `jaccard_similarity(s1, s2, n=2)` - Jaccard over n-gram sets
- `cosine_similarity(s1, s2, n=2)` - Cosine over n-gram vectors
- `ensemble_similarity(noisy, canonical)` - 0.6*SequenceMatcher + 0.4*cosine
- `calibrate_confidence(raw_score, threshold=0.55)` - Map to [0.5,1.0] or [0,0.49]
- `match_segment(clean_text, codebook, standard_texts, threshold=0.55)` - Match against codebook

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-fuzzy-match/scripts')
from utils import match_segment, ensemble_similarity, calibrate_confidence
```
