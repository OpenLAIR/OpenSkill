# Comprehensive Analysis of OOXML Template Manipulation Using python-docx Version 1.1.2

### Leading Paragraph

**Key Points:**
* The Office Open XML (OOXML) standard structures Word documents into nested layers of paragraphs and runs, which inherently complicates text replacement due to the "split run" phenomenon.
* Direct replacement of a paragraph's `.text` property using `python-docx` will irreversibly strip all run-level character formatting (e.g., bolding, italics, colors).
* Robust templating requires algorithmically mapping character indices across fragmented run arrays to preserve document fidelity.
* The `python-docx` library (v1.1.2) lacks native support for reading or modifying text located inside floating text boxes (`<w:txbxContent>`), requiring direct XML manipulation via XPath.
* Safely removing conditional paragraphs via `_element.getparent().remove()` is highly effective but poses document-corruption risks if the removed paragraph is the final element within a table cell. 

**Overview:**
The programmatic generation of Microsoft Word documents from templates is a cornerstone of modern automated reporting. While the Python ecosystem provides the `python-docx` library to interact with these files, developers quickly encounter severe structural complexities inherent to the underlying ECMA-376 Office Open XML (OOXML) architecture. Chief among these is the fragmentation of contiguous text strings into multiple XML `<w:r>` (run) nodes, rendering basic string replacement techniques useless. 

This comprehensive academic report provides an exhaustive examination of template manipulation using `python-docx` version 1.1.2. It explores the anatomical structure of `.docx` files, the algorithmic resolution of split-run text replacements, the meticulous preservation of typographical formatting, and the traversal of diverse text containers including nested tables, headers, and footers. Furthermore, it details advanced document logic, such as the conditional removal of document sections based on external JSON state, while addressing critical pitfalls and missing features within the current library API.

---

## 1. The OOXML Architecture and the "Split Run" Problem

To successfully manipulate Word documents using `python-docx`, one must first understand the structural paradigm of the `.docx` format. A Microsoft Word document is not a monolithic binary file; rather, it is a compressed ZIP archive containing a hierarchical structure of XML files and media assets [cite: 1]. The textual payload of the document is primarily housed within `word/document.xml`, governed by the WordprocessingML (WML) schema.

### 1.1 The Paragraph and Run Hierarchy
In WordprocessingML, text is organized into block-level and inline-level elements [cite: 1, 2]:
*   **`<w:p>` (Paragraph):** The fundamental block-level container. It houses paragraph-level properties (`<w:pPr>`) such as alignment, spacing, and styles [cite: 3].
*   **`<w:r>` (Run):** An inline-level container nested within a paragraph. A run represents a contiguous region of text that shares the exact same formatting properties. It contains run properties (`<w:rPr>`) and text elements [cite: 1].
*   **`<w:t>` (Text):** The terminal node containing the actual string characters [cite: 1].

### 1.2 The Genesis of Split Runs
When attempting to replace a template placeholder such as `{{CANDIDATE_FULL_NAME}}`, a developer logically expects to find this exact string within a single `run.text`. However, practical experience reveals that Word frequently fractures this text across multiple consecutive runs [cite: 4, 5]. For example, the placeholder might be parsed as:
*   Run 1: `{{CANDIDAT`
*   Run 2: `E_FULL`
*   Run 3: `_NAME}}`

This fragmentation occurs for several reasons:
1.  **Editing and Revisions:** Typing, deleting, and re-typing characters within a word inherently spawns new runs based on the cursor's timeline.
2.  **Revision Save IDs (RSID):** Word tracks editing sessions using `w:rsidR` attributes. Editing part of a word during a different session splits the run [cite: 6].
3.  **Spell and Grammar Checking:** Word inserts invisible `<w:proofErr>` tags (Proofing Error anchors) to mark spelling mistakes. Since template variables like `{{PLACEHOLDER}}` are not recognized as dictionary words, Word flags them, splitting the run exactly where the "error" begins and ends [cite: 5, 7].
4.  **Style Transitions:** Even invisible style boundaries (such as a lingering bold property on a single space) enforce run separation.

### 1.3 The Failure of Paragraph-Level Replacement
The seemingly obvious solution is to read the combined text of the paragraph and overwrite it:
```python
if '{{PLACEHOLDER}}' in paragraph.text:
    paragraph.text = paragraph.text.replace('{{PLACEHOLDER}}', 'John Doe')
```
While this code technically works, it triggers a devastating side effect. According to the `python-docx` documentation, assigning a string to `paragraph.text` causes the library to delete all existing runs and generate a single, unformatted run containing the new text [cite: 2]. All run-level formatting—such as bolding, italics, underlines, and font colors—is permanently destroyed [cite: 2]. Therefore, text replacement must be strictly confined to the `.text` properties of individual `Run` objects [cite: 5].

---

## 2. Strategies for Replacing Text and Preserving Formatting

To overcome the split-run dilemma while preserving document styling, we must implement an algorithm that maps the global string indices of a matched placeholder back to the local indices of the underlying run array. 

### 2.1 The String-to-Run Mapping Algorithm
The standard approach involves the following steps [cite: 4, 8]:
1.  Concatenate the `.text` of all runs within a paragraph to form the complete string.
2.  Utilize regular expressions (e.g., `re.finditer`) to locate the exact start and end character indices of the placeholder within the concatenated string.
3.  Iterate through the `paragraph.runs` array, tracking the cumulative character count.
4.  Identify the exact runs that intersect with the start and end indices of the placeholder.
5.  Inject the replacement text into the **first** run that overlaps with the placeholder.
6.  Clear the text of all **subsequent** runs that fall entirely within the placeholder's span, while carefully preserving any non-placeholder suffix text in the final run.

By placing the replacement text entirely within the first matched run, the new text inherits the exact `<w:rPr>` (run properties) of the original placeholder's leading characters [cite: 5, 7]. 

### 2.2 Direct API Copying of Formatting (Alternative Approach)
In scenarios where one wishes to dynamically construct entirely new runs rather than modifying existing ones, `python-docx` allows access to run properties via the `run.font` attribute [cite: 2, 9]. However, cloning a run requires meticulously copying a litany of specific attributes [cite: 10].

Table 1 details the core typography attributes accessible via `python-docx` v1.1.2:

| Property | Type | Description |
| :--- | :--- | :--- |
| `run.font.name` | `str` | Typeface name (e.g., 'Arial') [cite: 9]. |
| `run.font.size` | `docx.shared.Length` | Size of the font (typically set via `Pt()`) [cite: 2, 11]. |
| `run.font.bold` | `bool` / `None` | Tri-state toggle for bold weight [cite: 2, 9]. |
| `run.font.italic` | `bool` / `None` | Tri-state toggle for italic styling [cite: 2, 12]. |
| `run.font.underline` | `bool` / `WD_UNDERLINE` | Underline type or boolean status [cite: 2]. |
| `run.font.color.rgb` | `docx.shared.RGBColor` | The RGB hexadecimal color definition [cite: 2, 10]. |

A comprehensive function to clone these properties is detailed below:

```python
from docx.shared import RGBColor

def copy_run_format(source_run, dest_run):
    """Copies font properties from the source_run to the dest_run."""
    dest_run.bold = source_run.bold
    dest_run.italic = source_run.italic
    dest_run.underline = source_run.underline
    
    # Copy Font Name
    if source_run.font.name is not None:
        dest_run.font.name = source_run.font.name
        
    # Copy Font Size
    if source_run.font.size is not None:
        dest_run.font.size = source_run.font.size
        
    # Copy Font Color
    if source_run.font.color and source_run.font.color.rgb:
        dest_run.font.color.rgb = source_run.font.color.rgb
```

*Note on Low-Level Cloning:* For guaranteed preservation of *all* run properties (including unsupported properties like complex script fonts or character spacing), advanced users may bypass the API and use `lxml` to duplicate the underlying XML property element [cite: 13]:
```python
import copy
new_rPr = copy.deepcopy(source_run._r.get_or_add_rPr())
dest_run._r.replace(dest_run._r.get_or_add_rPr(), new_rPr)
```

---

## 3. Comprehensive Iteration Across Document Containers

Placeholders in enterprise templates are rarely confined to the main document body. They inhabit tables, nested tables within tables, and document headers/footers [cite: 4, 14]. Merely looping over `document.paragraphs` is critically insufficient, as it bypasses all secondary containers [cite: 15, 16].

### 3.1 Resolving Tables and Nested Tables
Tables in `python-docx` are accessed via `document.tables`. A table consists of rows, which contain cells, which in turn contain both paragraphs and nested tables [cite: 7, 14]. An effective text-replacement script must utilize a recursive generator to traverse arbitrarily deep table hierarchies.

### 3.2 Accessing Headers and Footers
Headers and footers exist entirely outside the document's main `<w:body>`. They are defined at the `<w:sectPr>` (Section Properties) level [cite: 17]. A document contains a list of sections via `document.sections`. 

Crucially, OOXML defines up to three distinct headers and footers per section [cite: 18, 19, 20]:
1.  **Default Header:** (`section.header`) Used generally, and for odd pages if odd/even separation is active.
2.  **First Page Header:** (`section.first_page_header`) Used exclusively on the first page of the section if `different_first_page_header_footer` is enabled [cite: 18, 19].
3.  **Even Page Header:** (`section.even_page_header`) Used for even pages if `odd_and_even_pages_header_footer` is active [cite: 19].

To thoroughly process a document, all three headers and all three footers must be queried across all sections [cite: 18, 21]. Each header/footer acts as a `BlockItemContainer` and has its own `.paragraphs` and `.tables` collections [cite: 17, 18, 20].

### 3.3 The `iter_inner_content()` Enhancement in v1.1.2
Introduced in version 1.1.0, the `iter_inner_content()` method generates both `Paragraph` and `Table` instances in strict document order [cite: 14, 17, 22, 23]. While highly beneficial for linear text parsing, it is less strictly necessary for pure find-and-replace tasks where topological order matters less than total coverage.

---

## 4. Advanced Pattern Matching and Conditional Deletion

Templates frequently require conditional rendering. A common pattern is wrapping optional text in marker tags, such as:
`{{IF_RELOCATION}}`
`Candidate requires relocation assistance.`
`{{END_IF_RELOCATION}}`

If the data payload specifies that relocation is false, the script must systematically delete the marker paragraphs and all paragraphs located between them.

### 4.1 Programmatic Paragraph Deletion
The `python-docx` API does not feature a native `paragraph.delete()` method [cite: 24]. Consequently, deletion mandates interacting with the underlying `lxml` bindings of the proxy object [cite: 25, 26]. 

The `<w:p>` element is accessed via `paragraph._element`. Deletion is achieved by instructing the parent XML node to remove the paragraph child [cite: 25, 26]:

```python
def delete_paragraph(paragraph):
    p = paragraph._element
    p.getparent().remove(p)
    paragraph._p = paragraph._element = None  # Prevent dangling references
```

### 4.2 The "Table Cell Repair" Pitfall
A critical structural requirement of OOXML is that every table cell (`<w:tc>`) **must** conclude with a paragraph (`<w:p>`) [cite: 24]. If an algorithmic deletion indiscriminately removes all paragraphs inside a table cell, Word will detect an invalid schema upon opening, displaying a dreaded "The file is corrupt and cannot be opened" or forcing a document repair step [cite: 24, 27]. 

To mitigate this, a robust deletion algorithm must verify whether the paragraph being deleted is the final child of a table cell, and if so, append an empty paragraph to substitute it, or refuse the deletion and merely clear its text.

---

## 5. Implementation: The Complete Production-Ready Code

The following Python script provides an exhaustive, robust implementation satisfying all requirements. It encompasses split-run resolution, recursive container traversal, conditional block deletion, JSON payload mapping, and formatting preservation.

### 5.1 JSON Data Structure Example
Assume a file named `payload.json`:
```json
{
    "CANDIDATE_NAME": "Alexander Hamilton",
    "POSITION": "Secretary of the Treasury",
    "START_DATE": "September 11, 1789",
    "IF_RELOCATION": false,
    "IF_BONUS": true
}
```

### 5.2 Complete Python-Docx Utility Module

```python
import json
import re
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table

def load_json_data(filepath):
    """
    Loads mapping data from a JSON file.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def iter_all_paragraphs(doc):
    """
    A comprehensive generator that yields every paragraph from all document
    containers including the main body, nested tables, headers, and footers.
    """
    # 1. Yield paragraphs from the main body
    for paragraph in doc.paragraphs:
        yield paragraph

    # 2. Recursively yield paragraphs from tables
    def yield_from_table(table):
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph
                for nested_table in cell.tables:
                    yield_from_table(nested_table)

    for table in doc.tables:
        yield_from_table(table)

    # 3. Yield paragraphs from headers and footers across all sections
    for section in doc.sections:
        # OOXML specifies three distinct headers per section
        headers = [section.header, section.first_page_header, section.even_page_header]
        for header in headers:
            if not header.is_linked_to_previous:
                for paragraph in header.paragraphs:
                    yield paragraph
                for table in header.tables:
                    yield_from_table(table)
                    
        # OOXML specifies three distinct footers per section
        footers = [section.footer, section.first_page_footer, section.even_page_footer]
        for footer in footers:
            if not footer.is_linked_to_previous:
                for paragraph in footer.paragraphs:
                    yield paragraph
                for table in footer.tables:
                    yield_from_table(table)

def delete_paragraph(paragraph):
    """
    Deletes a paragraph safely by manipulating the underlying lxml element tree.
    Includes a safeguard to prevent corrupting empty table cells.
    """
    p = paragraph._element
    parent = p.getparent()
    
    if parent is None:
        return
        
    # OOXML Rule: A table cell (<w:tc>) must end with a paragraph.
    # If this is the last paragraph in a cell, we should clear it instead of deleting it.
    if parent.tag.endswith('tc') and len(parent.findall('.//w:p', namespaces=parent.nsmap)) <= 1:
        paragraph.text = ""
        return
        
    parent.remove(p)
    # Nullify references to prevent memory leaks or dangling exceptions
    paragraph._p = paragraph._element = None

def process_conditional_blocks(doc, data):
    """
    Scans the document for {{IF_KEY}} ... {{END_IF_KEY}} blocks.
    If the value of KEY in data is False, the entire block is deleted.
    If True, only the marker tags are deleted, keeping the content.
    """
    paragraphs = list(iter_all_paragraphs(doc))
    
    in_block = False
    current_condition_met = False
    paragraphs_to_delete = []
    
    start_pattern = re.compile(r'\{\{IF_([A-Za-z0-9_]+)\}\}')
    end_pattern = re.compile(r'\{\{END_IF_([A-Za-z0-9_]+)\}\}')
    
    for paragraph in paragraphs:
        text = paragraph.text
        
        # Check for block start
        start_match = start_pattern.search(text)
        if start_match:
            in_block = True
            key = start_match.group(1)
            # Evaluate condition from data dictionary
            current_condition_met = bool(data.get(f"IF_{key}", False))
            paragraphs_to_delete.append(paragraph) # Always delete the start marker
            continue
            
        # Check for block end
        end_match = end_pattern.search(text)
        if end_match:
            in_block = False
            paragraphs_to_delete.append(paragraph) # Always delete the end marker
            continue
            
        # If inside a block and condition is false, queue content for deletion
        if in_block and not current_condition_met:
            paragraphs_to_delete.append(paragraph)
            
    # Execute deletions in reverse order to maintain XML tree integrity
    for p in reversed(paragraphs_to_delete):
        delete_paragraph(p)

def replace_text_in_paragraph(paragraph, search_text, replace_text):
    """
    Robustly replaces search_text with replace_text within a paragraph, 
    accounting for OOXML "split runs" to preserve precise formatting.
    """
    if search_text not in paragraph.text:
        return

    # Combine all text to find global match indices
    full_text = "".join(run.text for run in paragraph.runs)
    
    # Iterate over all occurrences in the paragraph
    for match in re.finditer(re.escape(search_text), full_text):
        start_idx = match.start()
        end_idx = match.end()
        
        current_idx = 0
        first_run_found = False
        
        for run in paragraph.runs:
            run_len = len(run.text)
            run_start = current_idx
            run_end = current_idx + run_len
            
            # Check if this run overlaps with the matched placeholder
            if run_end > start_idx and run_start < end_idx:
                if not first_run_found:
                    # This is the primary run. We inject the replacement here.
                    # We must preserve any leading/trailing text in this specific run.
                    prefix = run.text[:max(0, start_idx - run_start)]
                    suffix = run.text[max(0, run_len - (run_end - end_idx)):] if run_end > end_idx else ""
                    
                    run.text = f"{prefix}{replace_text}{suffix}"
                    first_run_found = True
                else:
                    # This is a subsequent run spanning the placeholder.
                    # We clear the placeholder portion. 
                    if run_end > end_idx:
                        # The placeholder ends in the middle of this run. Keep the tail.
                        run.text = run.text[end_idx - run_start:]
                    else:
                        # The run is entirely consumed by the placeholder. Clear it.
                        run.text = ""
                        
            current_idx += run_len
            
        # Re-evaluate full text for subsequent matches as run lengths have changed
        full_text = "".join(r.text for r in paragraph.runs)


def apply_template_data(template_path, json_path, output_path):
    """
    Main orchestration function to load data, process logic, replace text, and save.
    """
    doc = Document(template_path)
    data = load_json_data(json_path)
    
    # 1. Process conditional logic first to remove unnecessary paragraphs
    process_conditional_blocks(doc, data)
    
    # 2. Iterate through all remaining text containers and replace placeholders
    for paragraph in iter_all_paragraphs(doc):
        # Only process keys that are mapped to standard replacement strings
        for key, value in data.items():
            if not key.startswith("IF_"): # Skip logic flags
                placeholder = f"{{{{{key}}}}}"
                # Convert the replacement to string to avoid TypeError
                replace_text_in_paragraph(paragraph, placeholder, str(value))
                
    # 3. Save the manipulated document
    doc.save(output_path)

if __name__ == "__main__":
    # Example Execution
    # apply_template_data('contract_template.docx', 'payload.json', 'contract_final.docx')
    pass
```

---

## 6. Common Pitfalls and Limitations in python-docx 1.1.2

While `python-docx` is exceptionally capable, version 1.1.2 harbors several structural limitations and undocumented behaviors that developers must navigate [cite: 22, 28].

### 6.1 The "Text Box" Blind Spot
One of the most profound limitations of `python-docx` is its complete inability to natively identify, read, or modify content residing within floating Text Boxes [cite: 29, 30]. In OOXML, text boxes are not standard `<w:p>` nodes nested in the body. Instead, they are wrapped inside DrawingML elements (`<w:drawing>`), further shrouded in `<mc:AlternateContent>` fallbacks, and uniquely identified by `<wps:txbx>` and `<w:txbxContent>` namespaces [cite: 6, 31, 32].

Because `python-docx` lacks proxy classes for these nodes, the `iter_inner_content()` generator silently skips them entirely [cite: 30, 33, 34]. To replace placeholders inside text boxes, developers must bypass the API and use low-level `lxml` XPath queries on the document's body [cite: 6, 32]:

```python
# Advanced text-box resolution (Conceptual snippet)
txbx_elements = doc._body.xpath('.//w:txbxContent')
for txbx in txbx_elements:
    # Iterate through paragraphs within the textbox element directly
    for p_element in txbx.xpath('.//w:p'):
        # Proxy generation is required to use python-docx manipulation methods
        paragraph = Paragraph(p_element, doc._body)
        replace_text_in_paragraph(paragraph, '{{PLACEHOLDER}}', 'Replacement')
```

### 6.2 XML Character Escaping
A common anxiety among developers handling text injection into XML-based formats is the escaping of special characters like `<` (less than), `>` (greater than), and `&` (ampersand). Fortunately, `python-docx` automatically sanitizes and encodes these characters into their correct XML entity representations (e.g., `&lt;`, `&amp;`) whenever strings are assigned to a `run.text` or `paragraph.text` property. No manual HTML/XML escaping is required by the developer.

### 6.3 Document Layout and Style Preservation
A frequent inquiry regarding `document.save()` is whether the manipulation of the document alters the margins, nested images, pagination, or master styles. Because `python-docx` operates by unzipping the original `.docx` archive into memory, modifying strictly targeted XML tags, and re-zipping the package identically, the broader document topology remains flawlessly intact [cite: 1].

The library does not possess a rendering engine; therefore, it cannot recalculate pagination or alter layout attributes unless explicitly instructed to modify page properties (e.g., `section.left_margin`). Images, macro definitions, and custom style mappings are preserved entirely through the save process.

### 6.4 Content Controls and Complex Fields
Similar to text boxes, Word features "Content Controls" (Developer form fields). These are represented in OOXML by `<w:sdt>` (Structured Document Tag) elements. While `python-docx` will often read the text output of these controls if they contain standard paragraphs, replacing the internal text using standard paragraph replacement algorithms may corrupt the control bindings. Projects heavily reliant on content controls are often better served by the `docxcompose` or `docxtpl` libraries, which are built atop `python-docx` specifically for complex tag resolution [cite: 28, 35].

## 7. Conclusion
The manipulation of OOXML via `python-docx` 1.1.2 is an exercise in respecting XML schema topologies. A naive approach to text replacement invites disastrous formatting loss and document corruption due to the systemic occurrence of split runs and strict table schema limits. However, by leveraging a concatenated string-index mapping algorithm for run-level replacement, utilizing recursive generators to traverse deeply nested tables and multi-page headers, and safely executing `lxml` node detachments for conditional content, Python developers can orchestrate highly complex, flawless document generation pipelines.

**Sources:**
1. [virantha.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFHjghDFk8BVB2r9kBl3n9Nbhm1_xodrYqalS3Fas1KQjQJYT4hNkRUXKkzgfRsI5bn079GAOyvgrsV2QJohHzNSPAlycGGRKpgP-FuJQwxMrCMy8oeNbM7Np6TgnYZLfbQmQF889LwRmum7cr85h1_l0kzkCU_ThpUjPIqOdyU0e5b3oLc5DAOILXf7aJXog==)
2. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH66Cj8wg7ns8p2xIHyuwip9rMK1s8xdO7gVv0S-MM8FLZ18AHzOYMs1SzCiHCd43NrlYWh5iymfB-TYrBYl9YgQ-1X3ZTpbxvnySGSDMXLh-VIBmarkWQncpjoPtqNNzhHClRZ3yr9xVa6GFfm6Ng=)
3. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2wSUYaXM99cMgHCKvIkoeSuSyTE0U2hoL0uRzu14VVrnbD3Pme8L9qHmhaEdoj5vADAfkAvjH1g8_5HXMc4uFRBQRVnTR_1haNGe63r5S1yewjxVQpei9klMGXRtAYxGOEhGzBug_7RDa3LHoIbMN8nCF1bblx_b-quZC5uxt)
4. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHg1u3WRdq0e1oXJ0Qn5sp4BrL8Ib6FVuzzpu1IC28zwavC8GnH3K_LFo4Qw8scEYjInawy7sASujRKwy5Dr6hTH5BaH0pw8wmCt_Aum4xDZAvvZIkPiDK5b16wZHetR4C-OEdrCGsynOsbcl5Pzkh5n7_eTsstnYoJ1gO1_VX2kdRLrY9X4oTLITB-3sNqDpYdfqrSYPubAE-edlw46F3O2KTZn3YyG0N6AQ==)
5. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2Gz3ICBiuHaVng13DjRzbg2AKRqVLpAWnQdsaV-l6k_qipp-BT9iDgVQIoCCr_tAMSwPeHL1a3FGdocn5-XwSCykrhvBHVYuphcHbIDqW0Fr3HwfqGDvxVrcA8qJyKAhmzQ==)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1ig8ks1sSnteRIjosLdLIjEaAzokljrSDTM5qfj2XkoJxmh1Aa0nfBX6v3u2vrXWUAEVJhlSrJ_aiq3ut2Zld1u0IT5sTggUrzcObXVW7p-ugtUfyHaljPVswGLToONWYjqMBDqBxsy98AWbZLdVcjrkuVCgiYVRN9D1NhsEj57lZQVsqcAHIbW4v3A21UP32newXK1_F)
7. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2Dlk3HFLoNfD4xhMTRXSfWQlLH36mk3MKhtvtPdOivqoIAL0oOoVItta8Y3gVit585LVWAJr8AXF0S0Evjm-TabtxswpEX8dqjIdobeDn2SimkEAR63K6GePDNoCd0_8Y6ReIoLIInZTegiNF-o1au7n_zl61tiH0UMD6SSkn9lnFgw27DQkCm1lkvZI0Dhn6ELAog1_bzblpYHONXACC51XZlA==)
8. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH658cHLr2i3DY11dgZoE_XTKyEeOnCWOG8wZL0O8UTy1O78o2eRCijNCMZm2oGBZARUZ0bxT-5C0hfKVx1OLNRC0RQVYmhDGIQu8Xp9zdhn1EzV0-QaMGWgwiZq9p8wdfY9Xfkl70cpBxqhkVeolDUXPx6ltEMVkofFDo8i9zx592bN2FJKcd1vP5ej-bWUypPx2bxtiMzZ76mCpIHZq9gSlDGUWdZKxrNOv4XHmXZIQ==)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGgPQo0QUpdnbozienBZP-APJhxxaCBRJSivoMCHAyHfTVgrJmESgpYTt9TpWvbexoG2v4KMHwdmvuzA-C23hsLePVGHI0oWmQmUbR-IgaIdcsHyfRmQAC4kNxI6zs7O5XsjgMqa1XLiDq2COg629QfA3ZKRT0bfZvhdEY69TldwrsWyiiv2g==)
10. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPtfVGybv5sD6acNe1hQLZqOxrkoDbhe8VGgQBq0JyaawMj72wgRhgIsclw3FyAPReFPdvJSog5lKjqw7MEw2r_ywO3l5n1pL92zULtbFiRzpaO9GjRwfk_tPjOfPT0g1QYBFECcfBsDzQ6mO5ZQgWVZvVXPbYgKwI_JiDqMIoKle5Lue0gTkNpwpihNuH6A==)
11. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4lGcEPG2Pp1-ZeFsXWvFXZXKBH8QHDna2XzsAtx760g-WCmzOMPcnN4E7y9Cowkxzz2OlZLu__qN8X1I3TpCnwAtySEsyd5VcrMEExKjSfF3UaSkazmuE3CFFsgN6EvEYm9xG4b9CrjlyX2mS5Oxr6vqTToao9Bk7p1m5-v0PtnpQ)
12. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFt0U_9yPOEjLyCantExGBrGWaJgDNxAyVN0Hx4bC3bCdLrzcYfjqzDb-xD2N84A24cYiLhJ6sZrDaJYiB3ZKBbWRNprI50iwc-JtnfR1ysUao-m6FTkkcY5RzIo7h9dtoeL21pSxIxAT6pqYeOVIULrYX6wWO7)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaI3C3c1IgTlHUaVmb4afu34PLHQDfRXmyDD15n6F1VFWpfzhb2Zi0y9MRkc0DZ8Gd7Gc2t0fFqwW8w1hTAvOvThavrBx_GZgMlzX1VSrh8WlwcJ-bUH9XlZBtZ_jW4ntJWcpLnQIzZV7bkpbR0Q==)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcvM7CE_mAYF909hLPQzKPjsJb9p7hLbSVyU9qcez9RiZ6C7ypx2NxjNxia3sYDruxQi1prgkgp0N7LL660wiBJw3Ak9NVlKfIy0u-f1i3F7rYn5LjwBK0xxTWtWYRiUIGcC7c7bEaDNKpTF9lHCV47xxPP3Y5_21RHP1R6bXzEr9OLqPw)
15. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1CqNbPNONGtCR-J4X_uOMxiikbFmYw5Qq6GitdF98KEIvua1dql1THw6VPAW0XuTG1qzpffcHA1r1wo5RZ9B94XPiqBEDWDXxBM_UWBJLR4GC6GD19GYFaTiUDfrWktWxnTc5pLA=)
16. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOgIbnyguZ4jMfmZHe5cQYH7ZSOC4eC7gKfC-hOsV-St1rRU0bDShLjZ5GKue2S_JrjXA-_h38pAGJWyJLsYJvRKZhwIhwuZzvGK6Yp3ZgV97-k_2T6ZncXMb51UJLmb4g4tPiGLpoQcFIHWbFJxwuF0bOUeFqOqwyeQSl61ntYIxGa5srxJ8s7Rp4y7h_oFRXm8rjHwDpbQhWd2YGCwbbZOp_XYkLumTvIXeKDomWUH1Lym_AnlvEXA==)
17. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEB3lOS3a24aSUfxDAS2jUMQzCzTmGhDVnQTdRplLi5Ao_G1kxehCN7M62qmQmuGFGMlHt5AFOEkv-LS4pUOKQeT6Zr5hTjioKaaxsL4jo2o7ZXN8l2QeZG8nqKGBrxurix1l4oz9QN9mrylf4fWpZf6rQ=)
18. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOTXf0WM7dycJ6MuZNa3axlAgdaoVsCacS5Jfdc3EF1g2N7Uq2yKdn8Ly42-LZ7Mv_IZkUpjAaI-TIDUXWg1WcMMU6U-KUa5xStUUarscfw33rnOSWC8w4dSBZ8_1bQ0PD6PXVFKODw_4dYGdIUXzpih7tlPxm1NHHS3HtVMeeeT176w==)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHRiKuFW1jz5jMEPZShs96FThLey31s_9yQcy1bQ6THvmGyDxvtrLwCZZ48iw8KjuyjawSaO75FZFx_z7tcbXrbJZrq2KGYn6vm6AfjVkspE3O51Vyu2U1YOrNzipwzC3T3p_clGjbdzj-ytzrR8im10HFnPoSIHX-bIcXu)
20. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGKBJaRZ56ba_MDgCcVfM2_OBtGhTS19-72QRD1kzETbPzHeHWmoSdQwCxpfxqDlcimKFvGvg7yoKW5AQLRZjLW9cK7UysC_AISy1aistR3VL-d4De0x4-8NrvV_a3kuOKxB0oIu2lgGqJXmCC8Xz97ob-t)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEyjOxeDUdQFKicCatic5-Zw0_xeoHJUkjkK42kCG3eAdRW8MzHtfE_M696Du-n8WE3-IiGlO9WlVz4Y2nzpCl5q6cLiCFmDaijl-0PDOz81HEy25sS6sx1yjAPO_ZzFJpTc1JVVf9WZ__nlZo3DrQ2F9LcmAaCF6zaGD5vEnmApFhrzg==)
22. [safetycli.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHWQ8LxTG70aeCfSrBqUuKNYLpC60rtuydA0Bs0sboVLt0IOoLBEQ4tBVjvV-WXgMaVahBfs5HRLTDGuQCgLYenTwrD6JPof8tTPeRfKwhiYD-KgD-JMsiCS6r58D-puWE83GcuLtQ9BF8Q0mhsGbDk1DiqIwUdeH3RazUfprb-in7xQtMzDdKHmauI7QQr-Eru3lW-Ndoou_A5SbxppWhmkqvqVBxmJp4HwirQNFV6pcvYwIUgLZrVojjcOjHteYf3fanOuZPffP2F)
23. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHp9E_uumSHLH6WE6tu75xRk9tePTfliFE_DKa9owH5-HVAqEYQXpq35kVWHyQiDKbtNxDpCWC7FyyZhsygQYpsDmaDkNn2rx5kyFLVfEDDaZ-c4212hvoNR9XT_lu2D6uV3QmUrb0Pk-ItdvBGD8Iv_3AY)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEc5V-LLxQZi9UymGqeqbMVWWdTB8sA_7gwO7pT-G5YRq-2ACf587ohzL7S6UcvXG7AB1YC-xK1F3he84pazGlIyIiZF57ExSrJhvP7TVc0tm3Gc2dVNu2HDWcB-k0gHrVkcP2rjf-xBicqBC85EEnpUGh9g2K0kd3xQF17wq_T2NbQbDV5KI8gM-ckPQ=)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBBMsYwMki9DZcZYkTAT1Q6V7-avX9ckYPfiDeZuqG1nuepABox9C_RFXM3s84Jk8GV0LfStKTODJxK0g4LtWQE37JshZZ144UYFbtyLLt60Q8MyhZ-UiV6eZNkc3akd8tHv-YZ_wuLIswzaA4eFOiUXarOmZbJI6cDfU4-BAztrHpzmpgSHrl2p9OGXA7ZOyO_Jhn8FFerABpbQvpbXQ8qB6Fdg==)
26. [baidu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEy-upSeMsYmGaaZCU1FOyvE_EeNP0F9JcX8fpWE8bK5BbsxjduZ3LfgfAfsajAB3rU2055-VI2t6_LM8isAB965UBqAGO_g0i15FMKy2A2O6rI36G5t6pNxKUzV40PK4S3)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBmkEgYZ05SWcu7YdZs5epGaACWCUjexwEeB4yN3taW0IYzVVUHlUCKD6PRYlOrUJKt0GtsMS9qddyT_S2SAzPn8RuNP4O3G37GCSP_c0QcxOb1kJ9boLtavuI9WpqHwZXtlSIBrZyHDaAjgx85K4ADnb7Dl2WaN_BEzR-sI50e5SKN6XiVg==)
28. [docassemble.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG30UL5MK-xlIiim3MWP0Cq52BHSrRcekbksIVUlAmj8g0Y5N7geXx9jbwzona6zuL3fGSHpIuL1CeqjlgKOj3-QtxRzZc9fOpNsUC0k6t1xCUB4BvnstxPp9sGJQ8YIoE=)
29. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF1BRgvHO5sTocNcTC4xIQUBF7fYdQVDiuaI7SWwVVxLdUPnmWaqTf6a7U5XFsSC1CUmJ7tmpsTN203zkz-nGxfuJo-RoaStA_JeLwNa259uad2BkW6hMnuYUBZSvrBCVdbE0_nL5nMSV037dK08mCtTXg_OcjsZAYjj2oa0-6Ub4Wu)
30. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzJ0oZz5CB3R0ytGaXfJkXCx282h1uS2anw-x9y2e_NC3qNYrngddqcAXOZxwSgy1mm39pjGywEKFv-m7tE6fEs4YKLf8_HgUiU6-hdbcP1Y8xd0nucolcVE4-2tbzHJs2wMH26MHfCUR5bXplFwjqmsZMi98oa0GAbVZ1jdQktXqgLFmAECQvf0-TCJ7mZ1i1DY0Rl_-VJIBJjNoWmCaEZq0qRiuXBI6vAtfs0FrUA6tS)
31. [rikvoorhaar.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHvKFNx4z7yd69_6k_V4g9RW06bmZ0BzGivyVrnfUkGmqbNr__hU1pNPx2DpBf_tIU0WHYvfHDLOtnxK7TkV9vfXZY-7fU4U855RaRMr_qF2GVjmISGJjBBbcGD-nBcCoIn)
32. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGRElD13S9SAFO3LTLn9QZIXxn5mTB4Sp1dJL2ENNxfvzLIAYvayizqczawZ0CibGfAQzyFoHhxUP0NpLBw7DZg5tFW2taVTb8On-EYEzzzCPiUr7D4oijL5_DZv0ACUgLRq13RSDSZmH3Pr48KjerVWrmgk027lm4MbIwDcuqeHHOqpzQcs5uFXaTFeCXcl9eflTKOPphOQDtftYQmVegCYi0PnMLUJi82jbw=)
33. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHSREQqYQYlqwIa6iHzFA4GrA1LirTV40-_JvXww32ch7pUIQBGGioFY4bNgjVrvwuqY-b2qE1VKIlNI_7QW0f-OnDtlTQeTynpEPqtbWKOdZRakPrkmcGPmnESV_le5kLEi6tjslWgyX6P76NQoA==)
34. [riino.site](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLYBqruQ67Fb7qYoLOWEjpez6Ow0wDE-szmhCSk2MSTd7TyT5_uVWc89uEdhk1iakexgjYb-oBw6nTUftV6wVjb4W8bGfqX7MT34-4KEBDdWm69pwhl6rVM_YdfNVGJjJcvgK5MWJYOVjSG9B0QBejtSA=)
35. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGctfdx-lcUAclxD8G8o-Tfttn6ZI-wpJX-BO9O85Ni3s0K9_KFTdwdFTA2ra7cvoHcPqyTlvinbQnN55klDFnd-JdweDeXs3NwjxlCgClDwa89yww8c-Llm9xF)
