# Skill Creation Plan

**Task**: Fill the California SC-100 Small Claims Court PDF form with case-specific data (plaintiff/defendant info, claim details, venue, dates) and save the completed form.

**Rationale**: This task involves two distinct concerns: (1) extracting and mapping the PDF form field names from the blank SC-100 template, and (2) filling those fields with the correct case data and writing the output. Since both are tightly coupled to the same PDF and the task is straightforward form-filling, two skills provide clean separation between field discovery/mapping and the actual form-filling logic.

**Number of skills**: 2

---

## Skill 1: evo-pdf-field-inspector

**Description**: Inspects a PDF form to enumerate all AcroForm field names, types (text, checkbox, radio), and current values. Essential for discovering the exact internal field keys of the SC-100 form before filling.

**Responsibility**: Read and catalog all interactive form fields from a PDF, returning their names, types, flags, appearance states (for checkboxes), and default values.

**Key functions**: `enumerate_pdf_fields`, `get_checkbox_on_states`, `classify_field_type`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-field-inspector/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-pdf-form-filler

**Description**: Fills a PDF AcroForm with provided data (text fields, checkboxes, radio buttons) using pypdf/pdfrw, sets the NeedAppearances flag, and writes the output PDF. Handles checkbox state detection and proper value/appearance-state updates.

**Responsibility**: Accept a field-name-to-value mapping and a source PDF path, fill all specified fields correctly (including checkboxes with proper /V and /AS states), set /NeedAppearances flag, and write the filled PDF to an output path.

**Key functions**: `fill_pdf_form`, `set_need_appearances`, `fill_checkbox_field`, `fill_text_field`

**Depends on**: evo-pdf-field-inspector


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pdf-form-filler/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
