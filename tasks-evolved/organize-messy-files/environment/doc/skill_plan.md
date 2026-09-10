# Skill Creation Plan

**Task**: Extract text from 100+ PDF/DOCX/PPTX files and classify them into 5 subject folders (LLM, trapped_ion_and_qc, black_hole, DNA, music_history) based on content.

**Rationale**: The task has two distinct concerns: (1) extracting text from multiple document formats (PDF, DOCX, PPTX) using available libraries and stdlib fallbacks, and (2) classifying documents into 5 predefined categories using keyword matching on extracted text, then moving files. Separating these keeps extraction logic reusable and classification/routing logic independent.

**Number of skills**: 2

---

## Skill 1: evo-document-text-extraction

**Description**: Extracts text from PDF, DOCX, and PPTX files using PyPDF2, pdfplumber, pdftotext CLI, and stdlib zipfile+XML fallbacks. Provides a unified interface that auto-detects file type by extension and returns extracted text. For PDFs, reads only first 2-3 pages for speed. For DOCX/PPTX, uses zipfile+ElementTree since python-docx and python-pptx are not installed.

**Responsibility**: All text extraction from any supported document format. No classification or file movement logic.

**Key functions**: `extract_text`, `extract_text_pdf`, `extract_text_docx`, `extract_text_pptx`, `extract_text_pdftotext_cli`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-document-text-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-document-classify-and-sort

**Description**: Classifies extracted document text into one of 5 categories (LLM, trapped_ion_and_qc, black_hole, DNA, music_history) using weighted keyword matching, then moves files into the corresponding folders. Uses comprehensive keyword dictionaries tuned to the specific 5 subjects. Handles folder creation, file routing with shutil.move, and ensures every file is placed in exactly one folder.

**Responsibility**: Document classification based on text content, folder creation, and file movement. No text extraction logic.

**Key functions**: `classify_document`, `create_category_folders`, `sort_files_into_folders`, `get_category_keywords`

**Depends on**: evo-document-text-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-document-classify-and-sort/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
