"""PDF Form Filler utilities for filling AcroForm fields in PDFs."""
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, DictionaryObject


def set_need_appearances(writer: PdfWriter):
    """Set the /NeedAppearances flag on the AcroForm root dictionary.
    
    This forces PDF viewers to regenerate visual appearances of all fields
    based on their logical values when opening the document.
    Handles IndirectObject by resolving it first.
    """
    try:
        acro_form = writer._root_object.get("/AcroForm")
        if acro_form:
            # Resolve IndirectObject if necessary
            if hasattr(acro_form, 'get_object'):
                acro_form = acro_form.get_object()
            acro_form[NameObject("/NeedAppearances")] = BooleanObject(True)
            # Also update the root reference
            writer._root_object[NameObject("/AcroForm")] = acro_form
    except Exception as e:
        print(f"Warning: Could not set NeedAppearances: {e}")


def fill_text_field(writer: PdfWriter, field_name: str, value: str):
    """Fill a text field across all pages of the writer."""
    data = {field_name: value}
    for page in writer.pages:
        writer.update_page_form_field_values(page, data, auto_regenerate=False)


def fill_checkbox_field(writer: PdfWriter, field_name: str, on_state: str = "/1"):
    """Fill a checkbox field by setting both /V and /AS to the on_state."""
    data = {field_name: on_state}
    for page in writer.pages:
        writer.update_page_form_field_values(page, data, auto_regenerate=False)


def fill_pdf_form(input_pdf: str, output_pdf: str, text_fields: dict,
                  checkbox_fields: dict = None):
    """Fill a PDF form with text and checkbox values.
    
    Args:
        input_pdf: Path to the blank PDF form
        output_pdf: Path to write the filled PDF
        text_fields: Dict mapping field names to string values
        checkbox_fields: Dict mapping field names to their on-state strings
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    # Clone the document structure
    writer.append(reader)
    
    # Build combined data dict
    all_fields = dict(text_fields)
    if checkbox_fields:
        all_fields.update(checkbox_fields)
    
    # Update fields on all pages
    for page in writer.pages:
        writer.update_page_form_field_values(
            page, all_fields, auto_regenerate=False
        )
    
    # Set NeedAppearances flag
    set_need_appearances(writer)
    
    # Write output
    with open(output_pdf, "wb") as f:
        writer.write(f)
    
    print(f"Filled PDF written to {output_pdf}")
    return output_pdf
