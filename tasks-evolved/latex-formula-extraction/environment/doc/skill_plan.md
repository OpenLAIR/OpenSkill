# Skill Creation Plan

**Task**: Extract all standalone (display) LaTeX formulas from a research paper PDF, clean them, fix syntax errors, and write them to a markdown file.

**Rationale**: The task naturally splits into three concerns: (1) PDF-to-Markdown conversion using marker-pdf to get raw LaTeX, (2) extraction and cleaning of display math formulas from the markdown output, and (3) syntax validation and fixing of extracted formulas. This separation keeps each skill focused and testable independently.

**Number of skills**: 3

---

## Skill 1: evo-pdf-to-markdown

**Description**: Converts an academic PDF to Markdown using marker-pdf v1.3.3, preserving LaTeX math delimiters. Handles model initialization, converter setup, and text extraction.

**Responsibility**: PDF ingestion and conversion to Markdown text with LaTeX formulas preserved in $$ delimiters

**Key functions**: `convert_pdf_to_markdown`, `setup_marker_models`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-to-markdown/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-latex-formula-extraction

**Description**: Extracts display math formulas from marker-pdf Markdown output, strips equation numbers/tags/trailing punctuation, normalizes environments, and organizes them for output.

**Responsibility**: Regex-based extraction of $$...$$ blocks, stripping of equation numbering/tags/trailing punctuation, normalization of LaTeX environments to clean display math format

**Key functions**: `extract_display_formulas`, `strip_equation_numbering`, `strip_trailing_punctuation`, `normalize_formula`

**Depends on**: evo-pdf-to-markdown


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-latex-formula-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-latex-syntax-validation

**Description**: Validates extracted LaTeX formulas for syntax correctness (balanced braces, matched \left/\right delimiters, valid command names) and produces fixed versions of problematic formulas. Focuses only on typos/syntax errors, not physics meaning.

**Responsibility**: Syntax validation of LaTeX strings, detection of unmatched braces/delimiters/broken commands, and automated heuristic fixing of syntax errors

**Key functions**: `validate_latex_formula`, `check_balanced_braces`, `fix_left_right_delimiters`, `fix_broken_commands`, `detect_and_fix_all`

**Depends on**: evo-latex-formula-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-latex-syntax-validation/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
