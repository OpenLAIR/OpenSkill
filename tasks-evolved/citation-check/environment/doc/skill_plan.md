# Skill Creation Plan

**Task**: Parse a BibTeX file, verify each citation against academic APIs (CrossRef, Semantic Scholar, DBLP), identify fake/hallucinated citations, and output results as JSON.

**Rationale**: The task naturally splits into three concerns: (1) parsing and cleaning BibTeX data, (2) verifying citations against external APIs with robust querying, and (3) scoring matches and producing the final output. This separation keeps I/O, network logic, and decision logic independent.

**Number of skills**: 3

---

## Skill 1: evo-bibtex-parser

**Description**: Parses BibTeX files using bibtexparser 1.4.2 and cleans LaTeX/BibTeX artifacts from fields like title, author, year, DOI, and venue. Produces a normalized list of citation dictionaries ready for verification.

**Responsibility**: BibTeX file loading, field extraction, LaTeX artifact removal, and normalization of citation metadata

**Key functions**: `parse_bibtex_file`, `clean_bibtex_artifacts`, `extract_citation_metadata`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-bibtex-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-citation-verifier

**Description**: Queries external academic APIs (CrossRef, Semantic Scholar, DBLP, doi.org) to verify whether a citation exists. Implements robust HTTP sessions with retry logic, exponential backoff, and rate limiting for unauthenticated access.

**Responsibility**: Network communication with academic APIs, DOI resolution, rate limiting, retry logic, and returning raw API results for each citation

**Key functions**: `verify_doi_exists`, `query_crossref`, `query_semantic_scholar`, `query_dblp`, `get_robust_session`, `rate_limited_query`

**Depends on**: evo-bibtex-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-citation-verifier/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-citation-scorer

**Description**: Compares parsed BibTeX citation metadata against API results using fuzzy string matching and multi-factor scoring to classify citations as real or fake, then outputs the final JSON report.

**Responsibility**: String normalization, fuzzy title/author matching, composite confidence scoring, fake/real classification, and JSON output generation

**Key functions**: `normalize_string`, `calculate_title_similarity`, `compute_composite_score`, `classify_citation`, `export_fake_citations_json`

**Depends on**: evo-bibtex-parser, evo-citation-verifier


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-citation-scorer/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
