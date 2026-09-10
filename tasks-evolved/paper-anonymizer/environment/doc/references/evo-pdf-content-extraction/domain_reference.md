# Domain Reference for evo-pdf-content-extraction

**Responsibility**: Text extraction, layout analysis of author blocks, pattern detection for identifying redaction targets (author names, institution names, emails, arXiv identifiers, conference/venue statements). Returns structured lists of exact strings and regions to redact.

**Key functions to implement**: extract_page_text, extract_words_with_positions, identify_author_block_region, detect_arxiv_identifiers, detect_email_addresses, detect_affiliations, detect_venue_statements, get_all_redaction_targets

---

## 1. Text Extraction and Search Operations in PyMuPDF 1.24.0



## 5. Academic Paper Anonymization: Specific Patterns


To automate double-blind review preparation, the utility must target specific academic identifiers using targeted regex and keyword lists.

## 8. pypdf and pdfplumber as Supplementary Extraction Tools


Before applying physical redactions with PyMuPDF, one might wish to use highly specialized layout-aware libraries to perform complex analysis (e.g., distinguishing between an author block and the abstract).