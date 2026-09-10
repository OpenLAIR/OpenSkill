# Skill Creation Plan

**Task**: Fill placeholders in a Word template with employee data from JSON, handle conditional relocation section, and save the result as a .docx file.

**Rationale**: This task involves two distinct concerns: (1) robust text replacement in OOXML documents handling split runs, text boxes, headers/footers, and tables, and (2) conditional block processing for IF/END_IF markers. These are tightly coupled and share the same document traversal logic, so a single comprehensive skill is most appropriate to avoid fragmentation.

**Number of skills**: 1

---

## Skill 1: evo-docx-template-filler

**Description**: A utility module for filling Word document templates (.docx) with data from JSON files. Handles split-run-aware text replacement to preserve formatting, traverses all document containers (body, tables, nested tables, headers, footers, text boxes), and processes conditional IF/END_IF blocks by keeping or removing content based on data values.

**Responsibility**: Load JSON data, iterate all document containers (paragraphs, tables, headers, footers, text boxes), replace {{PLACEHOLDER}} tokens with values using run-level manipulation to preserve formatting, process {{IF_*}}...{{END_IF_*}} conditional blocks (keep content but remove markers when condition is true, remove entire block when false), and save the output document.

**Key functions**: `load_json_data`, `iter_all_paragraphs`, `replace_text_in_paragraph`, `process_conditional_blocks`, `delete_paragraph`, `handle_textbox_paragraphs`, `apply_template_data`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-docx-template-filler/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
