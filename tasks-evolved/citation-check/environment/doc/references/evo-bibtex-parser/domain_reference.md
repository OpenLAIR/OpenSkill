# Domain Reference for evo-bibtex-parser

**Responsibility**: BibTeX file loading, field extraction, LaTeX artifact removal, and normalization of citation metadata

**Key functions to implement**: parse_bibtex_file, clean_bibtex_artifacts, extract_citation_metadata

---

## 2. Foundational Parsing: Utilizing `bibtexparser` 1.4.2


To verify citations, the raw text must first be structured into a machine-readable format. BibTeX remains the standard for bibliographic data. The Python library `bibtexparser` version 1.4.2 is uniquely suited for this task, offering stability and broad compatibility, although its API differs entirely from the completely rewritten version 2.x [cite: 8, 9].

## 6. Navigating Edge Cases, Pitfalls, and Data Anomalies


Academic metadata is notoriously messy. A verification utility will crash or produce false positives if it does not gracefully handle structural anomalies [cite: 26, 27].