import json
import re
from docx import Document
from docx.text.paragraph import Paragraph


def load_json_data(filepath):
    """Load mapping data from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def iter_all_paragraphs(doc):
    """
    Comprehensive generator yielding every paragraph from all document
    containers: body, tables (nested), headers, footers, and text boxes.
    """
    # 1. Body paragraphs
    for paragraph in doc.paragraphs:
        yield paragraph

    # 2. Recursive table paragraphs
    def yield_from_table(table):
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph
                for nested_table in cell.tables:
                    yield from yield_from_table(nested_table)

    for table in doc.tables:
        yield from yield_from_table(table)

    # 3. Headers and footers across all sections
    for section in doc.sections:
        for header in [section.header, section.first_page_header, section.even_page_header]:
            if not header.is_linked_to_previous:
                for paragraph in header.paragraphs:
                    yield paragraph
                for table in header.tables:
                    yield from yield_from_table(table)

        for footer in [section.footer, section.first_page_footer, section.even_page_footer]:
            if not footer.is_linked_to_previous:
                for paragraph in footer.paragraphs:
                    yield paragraph
                for table in footer.tables:
                    yield from yield_from_table(table)

    # 4. Text boxes (not natively supported by python-docx)
    try:
        nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                 'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'}
        txbx_elements = doc.element.body.findall('.//wps:txbx//w:p', nsmap)
        for p_element in txbx_elements:
            yield Paragraph(p_element, doc.element.body)
    except Exception:
        pass


def replace_text_in_paragraph(paragraph, search_text, replace_text):
    """
    Replace search_text with replace_text in a paragraph, handling split runs
    to preserve formatting.
    """
    if not paragraph.runs:
        # No runs - check if text matches directly
        if search_text in (paragraph.text or ''):
            paragraph.text = paragraph.text.replace(search_text, replace_text)
        return

    full_text = "".join(run.text for run in paragraph.runs)
    if search_text not in full_text:
        return

    # Find all occurrences and process them
    while search_text in "".join(run.text for run in paragraph.runs):
        full_text = "".join(run.text for run in paragraph.runs)
        match = re.search(re.escape(search_text), full_text)
        if not match:
            break

        start_idx = match.start()
        end_idx = match.end()

        current_idx = 0
        first_run_found = False

        for run in paragraph.runs:
            run_len = len(run.text)
            run_start = current_idx
            run_end = current_idx + run_len

            if run_end > start_idx and run_start < end_idx:
                if not first_run_found:
                    # First overlapping run: inject replacement
                    prefix = run.text[:max(0, start_idx - run_start)]
                    if run_end > end_idx:
                        suffix = run.text[end_idx - run_start:]
                    else:
                        suffix = ""
                    run.text = prefix + replace_text + suffix
                    first_run_found = True
                else:
                    # Subsequent runs in the placeholder span
                    if run_end > end_idx:
                        run.text = run.text[end_idx - run_start:]
                    else:
                        run.text = ""

            current_idx += run_len


def delete_paragraph(paragraph):
    """
    Delete a paragraph safely. If it's the last paragraph in a table cell,
    clear its text instead to avoid OOXML corruption.
    """
    p = paragraph._element
    parent = p.getparent()
    if parent is None:
        return

    # Check if parent is a table cell (tc)
    if parent.tag.endswith('}tc') or parent.tag == 'tc':
        ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        p_elements = parent.findall(f'{ns}p')
        if len(p_elements) <= 1:
            # Last paragraph in cell - just clear text
            for run in paragraph.runs:
                run.text = ""
            return

    parent.remove(p)


def process_conditional_blocks(doc, data):
    """
    Process {{IF_KEY}}...{{END_IF_KEY}} conditional blocks.
    
    The conditional markers can be:
    1. On separate paragraphs (delete marker paragraphs, optionally delete content paragraphs)
    2. Within the same paragraph as content (remove marker text from runs)
    
    For RELOCATION_PACKAGE: if 'Yes', keep content, remove markers.
    The key mapping: IF_RELOCATION -> check data['RELOCATION_PACKAGE']
    """
    paragraphs = list(iter_all_paragraphs(doc))
    
    for paragraph in paragraphs:
        text = paragraph.text
        
        # Check for inline conditional pattern: {{IF_X}}content{{END_IF_X}} in same paragraph
        inline_pattern = re.compile(r'\{\{IF_([A-Za-z0-9_]+)\}\}(.*?)\{\{END_IF_\1\}\}', re.DOTALL)
        inline_match = inline_pattern.search(text)
        
        if inline_match:
            key = inline_match.group(1)
            # Determine if condition is met
            condition_met = _evaluate_condition(key, data)
            
            if condition_met:
                # Keep content, remove markers from runs
                _remove_markers_from_runs(paragraph, key)
            else:
                # Remove entire paragraph or clear content
                delete_paragraph(paragraph)
            continue
    
    # Handle multi-paragraph conditional blocks
    paragraphs = list(iter_all_paragraphs(doc))
    in_block = False
    current_key = None
    condition_met = False
    block_start_para = None
    block_content_paras = []
    paragraphs_to_delete = []
    
    for paragraph in paragraphs:
        text = paragraph.text.strip()
        
        start_match = re.match(r'^\{\{IF_([A-Za-z0-9_]+)\}\}$', text)
        if start_match and not in_block:
            in_block = True
            current_key = start_match.group(1)
            condition_met = _evaluate_condition(current_key, data)
            block_start_para = paragraph
            block_content_paras = []
            continue
        
        end_match = re.match(r'^\{\{END_IF_([A-Za-z0-9_]+)\}\}$', text)
        if end_match and in_block and end_match.group(1) == current_key:
            in_block = False
            # Always delete marker paragraphs
            paragraphs_to_delete.append(block_start_para)
            paragraphs_to_delete.append(paragraph)
            if not condition_met:
                paragraphs_to_delete.extend(block_content_paras)
            continue
        
        if in_block:
            block_content_paras.append(paragraph)
    
    for p in reversed(paragraphs_to_delete):
        delete_paragraph(p)


def _evaluate_condition(key, data):
    """
    Evaluate a conditional key against the data.
    For IF_RELOCATION, check RELOCATION_PACKAGE field.
    General pattern: check IF_KEY, or KEY_PACKAGE, or KEY directly.
    """
    # Direct check: IF_KEY in data (e.g., data has "IF_RELOCATION": true)
    if f"IF_{key}" in data:
        val = data[f"IF_{key}"]
        if isinstance(val, bool):
            return val
        return str(val).lower() in ('yes', 'true', '1')
    
    # Check KEY_PACKAGE (e.g., RELOCATION -> RELOCATION_PACKAGE)
    if f"{key}_PACKAGE" in data:
        val = data[f"{key}_PACKAGE"]
        if isinstance(val, bool):
            return val
        return str(val).lower() in ('yes', 'true', '1')
    
    # Check KEY directly
    if key in data:
        val = data[key]
        if isinstance(val, bool):
            return val
        return str(val).lower() in ('yes', 'true', '1')
    
    return False


def _remove_markers_from_runs(paragraph, key):
    """
    Remove {{IF_KEY}} and {{END_IF_KEY}} marker text from paragraph runs,
    preserving the content between them and all formatting.
    """
    start_marker = f"{{{{IF_{key}}}}}"
    end_marker = f"{{{{END_IF_{key}}}}}"
    
    for run in paragraph.runs:
        if start_marker in run.text:
            run.text = run.text.replace(start_marker, "")
        if end_marker in run.text:
            run.text = run.text.replace(end_marker, "")


def apply_template_data(template_path, json_path, output_path):
    """
    Main orchestration: load data, process conditionals, replace placeholders, save.
    """
    doc = Document(template_path)
    data = load_json_data(json_path)
    
    # 1. Process conditional blocks first
    process_conditional_blocks(doc, data)
    
    # 2. Replace all placeholders in all containers
    for paragraph in iter_all_paragraphs(doc):
        for key, value in data.items():
            if not key.startswith("IF_"):
                placeholder = "{{" + key + "}}"
                replace_text_in_paragraph(paragraph, placeholder, str(value))
    
    # 3. Save output
    doc.save(output_path)
    print(f"Document saved to {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4:
        apply_template_data(sys.argv[1], sys.argv[2], sys.argv[3])
