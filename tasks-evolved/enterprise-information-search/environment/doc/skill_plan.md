# Skill Creation Plan

**Task**: Parse enterprise documents (DOCX, XLSX, PPTX, PDF, etc.) from /root/DATA, answer retrieval questions from /root/question.txt about employee IDs, team members, and URLs related to specific products, and write structured JSON answers to /root/answer.json.

**Rationale**: The task involves three distinct concerns: (1) parsing diverse enterprise file formats to extract text, (2) parsing malformed question input and searching extracted text to answer specific queries, and (3) assembling and writing the final JSON output with token tracking. Given the 600s timeout and moderate complexity, two skills provide clean separation: one for document parsing/extraction and one for the question-answering pipeline that ties everything together.

**Number of skills**: 2

---

## Skill 1: evo-enterprise-doc-parser

**Description**: Provides utility functions to discover files recursively in a directory and extract text content from diverse enterprise document formats including DOCX, XLSX, PPTX, PDF, and plain text files. Handles dependency installation, merged cells in Excel, presenter notes in PowerPoint, headers/footers in Word documents, and encoding detection.

**Responsibility**: File discovery, binary/text classification, format-specific text extraction (PDF, DOCX, XLSX, PPTX, TXT/CSV/JSON), encoding handling, and runtime dependency installation for Ubuntu 24.04 environments.

**Key functions**: `ensure_dependencies`, `discover_files`, `extract_text_from_pdf`, `extract_text_from_docx`, `extract_text_from_xlsx`, `extract_text_from_pptx`, `safe_read_text`, `process_file`, `extract_all_documents`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-enterprise-doc-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-enterprise-qa-pipeline

**Description**: Orchestrates the end-to-end question-answering pipeline: parses the malformed question.txt file, searches extracted document text for answers (employee IDs, URLs, team member names), tracks token consumption, and writes the final answer.json output in the required format.

**Responsibility**: Parsing malformed/unquoted JSON questions, mapping questions to search strategies (regex for employee IDs and URLs, keyword/context-based search for names), aggregating answers across multiple documents, token counting, and writing structured JSON output.

**Key functions**: `parse_question_file`, `extract_employee_ids`, `extract_urls`, `search_context_for_answer`, `count_tokens_for_text`, `run_qa_pipeline`, `write_answer_json`

**Depends on**: evo-enterprise-doc-parser


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-enterprise-qa-pipeline/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
