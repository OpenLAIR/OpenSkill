# Skill Creation Plan

**Task**: Extract embedded Excel table from a PPTX file, read an updated exchange rate from an adjacent text box, update the Excel table while preserving formulas, and save the modified PPTX.

**Rationale**: This task involves a single cohesive workflow: manipulating embedded OLE Excel objects within PPTX files. While it touches multiple libraries (python-pptx and openpyxl), the operations are tightly coupled and sequential, making a single comprehensive skill the most practical decomposition to avoid artificial boundaries.

**Number of skills**: 1

---

## Skill 1: evo-pptx-embedded-excel-updater

**Description**: Provides utilities for finding and manipulating embedded Excel OLE objects within PPTX files, reading text boxes for context, modifying Excel cell values while preserving formulas, and saving the updated PPTX. Covers the full workflow of OLE object identification, blob extraction, openpyxl modification with formula preservation, blob replacement, and presentation saving.

**Responsibility**: End-to-end handling of embedded Excel OLE objects in PPTX files: identifying OLE shapes and text boxes on slides, extracting embedded xlsx blobs via python-pptx relationship IDs, reading/modifying Excel data with openpyxl while preserving formula cells, writing modified blobs back into the PPTX package, and parsing text box content for updated values.

**Key functions**: `find_embedded_ole_excel_shapes`, `extract_excel_blob_from_ole_shape`, `read_text_boxes_from_slide`, `parse_exchange_rate_from_text`, `load_excel_from_blob`, `update_excel_cell_preserve_formulas`, `save_excel_to_blob`, `replace_ole_blob_in_pptx`, `find_cell_by_currency_pair`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pptx-embedded-excel-updater/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
