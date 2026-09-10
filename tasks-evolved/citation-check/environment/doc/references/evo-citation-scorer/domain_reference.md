# Domain Reference for evo-citation-scorer

**Responsibility**: String normalization, fuzzy title/author matching, composite confidence scoring, fake/real classification, and JSON output generation

**Key functions to implement**: normalize_string, calculate_title_similarity, compute_composite_score, classify_citation, export_fake_citations_json

---

## 1. Introduction to the Phenomenon of Hallucinated Citations


The integration of Large Language Models (LLMs) into academic writing has introduced a novel and insidious challenge: the generation of hallucinated citations. LLMs operate as advanced prediction engines, calculating the probability of word sequences based on massive training corpora rather than retrieving verified facts from an internal database [cite: 1, 2]. When prompted to provide sources, an LLM prioritizes linguistic fluency and structural plausibility over factual accuracy [cite: 2, 3].

## 4. Matching and Scoring Heuristics


Retrieving results from an API is insufficient; the module must programmatically decide if the retrieved paper is the *same* paper parsed from the BibTeX. Because titles may contain slightly different punctuation, missing subtitles, or differing capitalizations (e.g., Web of Science vs. Scopus norms [cite: 26]), strict string equality (`==`) will result in false negatives [cite: 26, 27].

## 7. Structuring the Output Pipeline


The final step is aggregating the verification results into an auditable, machine-readable JSON file. This file should be formatted for easy integration into subsequent data pipelines or dashboards, ensuring strict encoding and organized sorting.