# Domain Reference for evo-docx-template-filler

**Responsibility**: Load JSON data, iterate all document containers (paragraphs, tables, headers, footers, text boxes), replace {{PLACEHOLDER}} tokens with values using run-level manipulation to preserve formatting, process {{IF_*}}...{{END_IF_*}} conditional blocks (keep content but remove markers when condition is true, remove entire block when false), and save the output document.

**Key functions to implement**: load_json_data, iter_all_paragraphs, replace_text_in_paragraph, process_conditional_blocks, delete_paragraph, handle_textbox_paragraphs, apply_template_data

---

## 1. The OOXML Architecture and the "Split Run" Problem


To successfully manipulate Word documents using `python-docx`, one must first understand the structural paradigm of the `.docx` format. A Microsoft Word document is not a monolithic binary file; rather, it is a compressed ZIP archive containing a hierarchical structure of XML files and media assets [cite: 1]. The textual payload of the document is primarily housed within `word/document.xml`, governed by the WordprocessingML (WML) schema.

## 2. Strategies for Replacing Text and Preserving Formatting


To overcome the split-run dilemma while preserving document styling, we must implement an algorithm that maps the global string indices of a matched placeholder back to the local indices of the underlying run array.

## 3. Comprehensive Iteration Across Document Containers


Placeholders in enterprise templates are rarely confined to the main document body. They inhabit tables, nested tables within tables, and document headers/footers [cite: 4, 14]. Merely looping over `document.paragraphs` is critically insufficient, as it bypasses all secondary containers [cite: 15, 16].

## 4. Advanced Pattern Matching and Conditional Deletion


Templates frequently require conditional rendering. A common pattern is wrapping optional text in marker tags, such as:
`{{IF_RELOCATION}}`
`Candidate requires relocation assistance.`
`{{END_IF_RELOCATION}}`

If the data payload specifies that relocation is false, the script must systematically delete the marker paragraphs and all paragraphs located between them.

## 5. Implementation: The Complete Production-Ready Code


The following Python script provides an exhaustive, robust implementation satisfying all requirements. It encompasses split-run resolution, recursive container traversal, conditional block deletion, JSON payload mapping, and formatting preservation.

## 6. Common Pitfalls and Limitations in python-docx 1.1.2


While `python-docx` is exceptionally capable, version 1.1.2 harbors several structural limitations and undocumented behaviors that developers must navigate [cite: 22, 28].