# Skill Creation Plan

**Task**: Anonymize three academic PDF papers by redacting author names, affiliations, arXiv identifiers, venue information, and other identity-revealing content, then save redacted versions.

**Rationale**: This task has two distinct concerns: (1) extracting and identifying what content needs redaction from each specific PDF (author names, affiliations, emails, arXiv IDs, venue info), and (2) performing the actual PDF redaction operations including text removal, link scrubbing, and metadata purging. Since the papers are unknown, the agent must first inspect them to discover author-specific strings, then apply comprehensive redaction. These concerns are tightly coupled enough to warrant two skills rather than more.

**Number of skills**: 2

---

## Skill 1: evo-pdf-content-extraction

**Description**: Extracts and analyzes text content from PDF pages to identify author-revealing information including names, affiliations, emails, arXiv IDs, venue/conference mentions, and other identity-leaking content. Focuses on the first few pages where author blocks typically appear.

**Responsibility**: Text extraction, layout analysis of author blocks, pattern detection for identifying redaction targets (author names, institution names, emails, arXiv identifiers, conference/venue statements). Returns structured lists of exact strings and regions to redact.

**Key functions**: `extract_page_text`, `extract_words_with_positions`, `identify_author_block_region`, `detect_arxiv_identifiers`, `detect_email_addresses`, `detect_affiliations`, `detect_venue_statements`, `get_all_redaction_targets`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-content-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-pdf-redaction-engine

**Description**: Performs physical redaction of identified content in PDF documents using PyMuPDF's redaction API. Handles exact string redaction, regex-based redaction, hyperlink removal, metadata scrubbing, and secure document saving with garbage collection.

**Responsibility**: Applying redaction annotations to identified text regions, removing sensitive hyperlinks, purging standard and XMP metadata, batch processing redactions per page with image preservation, and securely saving the output PDF.

**Key functions**: `redact_exact_strings`, `redact_regex_patterns`, `redact_page_region`, `scrub_hyperlinks`, `scrub_metadata`, `anonymize_pdf`, `save_redacted_document`

**Depends on**: evo-pdf-content-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-redaction-engine/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
