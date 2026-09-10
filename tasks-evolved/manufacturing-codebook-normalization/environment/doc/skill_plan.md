# Skill Creation Plan

**Task**: Normalize noisy, multilingual defect reason texts from manufacturing test center logs by fuzzy-matching them against standard product codebooks, producing structured JSON output with confidence scores.

**Rationale**: The task has three distinct concerns: (1) preprocessing and normalizing noisy multilingual text, (2) fuzzy matching normalized text segments against codebook entries with confidence calibration, and (3) orchestrating the data pipeline (reading CSVs, segmenting compound reasons, assembling the output JSON). Separating text normalization from matching logic keeps each skill focused and testable, while the pipeline skill handles I/O and orchestration.

**Number of skills**: 3

---

## Skill 1: evo-text-normalize

**Description**: Preprocesses and normalizes noisy multilingual (Chinese-English mixed) industrial text. Handles full-width to half-width conversion, Unicode normalization, lowercasing, whitespace cleanup, punctuation normalization, abbreviation expansion, and splitting mixed Chinese/English tokens.

**Responsibility**: All text preprocessing: NFKC normalization, full-width/half-width conversion, Chinese punctuation mapping, whitespace normalization, case folding, abbreviation expansion, and mixed-language token splitting. Does NOT perform matching or scoring.

**Key functions**: `normalize_width`, `preprocess_text`, `expand_abbreviations`, `split_mixed_text`, `split_compound_reasons`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-text-normalize/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-fuzzy-match

**Description**: Provides fuzzy string matching algorithms and confidence calibration for mapping normalized text segments against codebook entries. Implements SequenceMatcher ratio, Levenshtein distance, Jaccard similarity, cosine similarity over character n-grams, ensemble scoring, and threshold-based UNKNOWN classification with calibrated confidence.

**Responsibility**: All similarity computation and scoring: difflib SequenceMatcher, Levenshtein distance, Jaccard similarity, cosine similarity, ensemble scoring, confidence calibration, and UNKNOWN thresholding. Does NOT handle I/O or text preprocessing.

**Key functions**: `levenshtein_distance`, `levenshtein_ratio`, `jaccard_similarity`, `cosine_similarity`, `get_ngrams`, `ensemble_similarity`, `calibrate_confidence`, `match_segment`

**Depends on**: evo-text-normalize


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-fuzzy-match/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-defect-pipeline

**Description**: End-to-end data pipeline that reads test center log CSVs and product codebook files, orchestrates text normalization and fuzzy matching, and produces the structured solution.json output with proper JSON serialization handling for numpy/pandas types.

**Responsibility**: File discovery and CSV reading with encoding fallbacks, codebook dictionary construction per product, record-level orchestration of segmentation and matching, segment_id generation, output JSON assembly conforming to the required schema, and numpy/pandas type-safe JSON serialization.

**Key functions**: `safe_read_csv`, `discover_codebooks`, `build_codebook_mapping`, `process_record`, `export_results_to_json`, `run_pipeline`

**Depends on**: evo-text-normalize, evo-fuzzy-match


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-defect-pipeline/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
