# Skill Creation Plan

**Task**: Detect dangling paper titles in a PPTX file, reformat them (font, size, color, bold), resize boxes for single-line display, center at bottom of each slide, and create a reference slide with auto-numbered deduplicated titles.

**Rationale**: The environment lacks python-pptx (only lxml, defusedxml, six are installed), so all manipulation must use raw ZIP+lxml. The task naturally splits into: (1) low-level PPTX ZIP/XML read-write utilities, (2) dangling title detection and reformatting logic, and (3) reference slide creation with numbered bullets. Keeping these separate ensures clean boundaries between I/O, detection/formatting, and slide creation concerns.

**Number of skills**: 3

---

## Skill 1: evo-pptx-xml-io

**Description**: Low-level utilities for reading/writing PPTX files as ZIP archives with lxml XML parsing, without python-pptx. Provides functions to open a PPTX, parse slide XML, enumerate shapes, read/write XML attributes, and repackage modified content into a valid PPTX.

**Responsibility**: ZIP archive management, XML parsing with proper OOXML namespaces (DrawingML 'a:', PresentationML 'p:'), slide enumeration, and safe repackaging of modified PPTX files.

**Key functions**: `open_pptx_archive`, `parse_slide_xml`, `get_all_slide_paths`, `get_presentation_xml`, `write_pptx_archive`, `get_namespaces`, `find_shapes_in_slide`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pptx-xml-io/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-pptx-title-detect-format

**Description**: Detects dangling (non-placeholder) paper title text boxes in slide XML using heuristics, applies font reformatting (Arial, size 16, color #989596, non-bold) at the run level via raw XML manipulation, calculates/adjusts box width for single-line display, and repositions titles to bottom-center of each slide.

**Responsibility**: Dangling title identification via XML heuristics (non-placeholder check, text content analysis), run-level typography manipulation in raw OOXML, text width estimation for box resizing, and spatial repositioning (bottom-center) using EMU coordinates.

**Key functions**: `detect_dangling_titles`, `apply_font_formatting_to_shape`, `estimate_text_width_emu`, `resize_textbox_for_single_line`, `position_bottom_center`, `extract_title_text`

**Depends on**: evo-pptx-xml-io


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pptx-title-detect-format/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-pptx-reference-slide

**Description**: Creates a new slide at the end of the presentation with 'Reference' as the title and all unique paper titles as auto-numbered bullet points in the body, using raw OOXML XML construction with lxml.

**Responsibility**: New slide XML creation, presentation.xml and relationship file updates, title placeholder population, body text with auto-numbered bullets via a:buAutoNum elements, and deduplication of paper titles.

**Key functions**: `create_reference_slide_xml`, `add_slide_to_presentation`, `create_autonumbered_paragraphs`, `update_content_types`, `update_presentation_rels`, `deduplicate_titles`

**Depends on**: evo-pptx-xml-io, evo-pptx-title-detect-format


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pptx-reference-slide/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
