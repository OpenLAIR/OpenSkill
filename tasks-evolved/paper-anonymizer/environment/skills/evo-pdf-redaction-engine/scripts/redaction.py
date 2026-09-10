import fitz
import re
import os

def redact_exact_strings(page, strings):
    """Add redaction annotations for exact string matches on a page."""
    for target in strings:
        if not target or len(target) < 2:
            continue
        try:
            bboxes = page.search_for(target)
            for rect in bboxes:
                page.add_redact_annot(rect, fill=(0, 0, 0))
        except Exception as e:
            print(f"Warning: search_for failed for '{target}': {e}")

def redact_regex_patterns(page, patterns):
    """Add redaction annotations for regex pattern matches."""
    try:
        full_text = page.get_text("text")
    except Exception:
        return
    for pattern in patterns:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(full_text):
                exact_string = match.group()
                if len(exact_string) < 2:
                    continue
                bboxes = page.search_for(exact_string)
                for rect in bboxes:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
        except Exception as e:
            print(f"Warning: regex failed for '{pattern}': {e}")

def redact_page_region(page, rect):
    """Redact an entire rectangular region."""
    page.add_redact_annot(rect, fill=(0, 0, 0))

def scrub_hyperlinks(page, link_patterns):
    """Remove identifying hyperlinks and redact their visual text."""
    links = page.get_links()
    for link in links:
        uri = link.get("uri", "").lower()
        if not uri:
            continue
        should_remove = False
        for pattern in link_patterns:
            if pattern.lower() in uri:
                should_remove = True
                break
        if should_remove:
            page.delete_link(link)
            page.add_redact_annot(link["from"], fill=(0, 0, 0))

def scrub_metadata(doc):
    """Purge standard and XMP metadata."""
    clean_meta = {
        "author": "",
        "title": doc.metadata.get("title", ""),
        "subject": "",
        "keywords": "",
        "creator": "",
        "producer": "",
    }
    doc.set_metadata(clean_meta)
    doc.del_xml_metadata()

def save_redacted_document(doc, output_path):
    """Save with garbage=4 and deflate=True for secure redaction."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

def anonymize_pdf(input_path, output_path, exact_strings, regex_patterns, link_patterns):
    """Full anonymization pipeline for a single PDF."""
    doc = fitz.open(input_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Step 1: Redact exact strings
        redact_exact_strings(page, exact_strings)
        
        # Step 2: Redact regex patterns
        redact_regex_patterns(page, regex_patterns)
        
        # Step 3: Scrub hyperlinks
        scrub_hyperlinks(page, link_patterns)
        
        # Step 4: Apply all redactions (batch per page, preserve images)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    
    # Step 5: Scrub metadata
    scrub_metadata(doc)
    
    # Step 6: Save securely
    save_redacted_document(doc, output_path)
    print(f"Saved redacted PDF to {output_path}")
