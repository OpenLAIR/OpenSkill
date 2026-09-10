"""PDF Field Inspector utilities for enumerating AcroForm fields."""
from pypdf import PdfReader


def enumerate_pdf_fields(pdf_path: str) -> dict:
    """Enumerate all interactive form fields from a PDF.
    
    Returns dict mapping field_name -> {type, value, flags, mapping_name}
    """
    reader = PdfReader(pdf_path)
    fields = reader.get_fields()
    if not fields:
        return {}
    
    result = {}
    for key, field in fields.items():
        f_type = str(field.field_type) if field.field_type else "Unknown"
        result[key] = {
            "type": classify_field_type(field),
            "raw_type": f_type,
            "value": str(field.value) if field.value else None,
            "flags": field.flags,
            "mapping_name": field.mapping_name
        }
    return result


def classify_field_type(field_obj) -> str:
    """Classify a pypdf Field object into human-readable type.
    
    Returns one of: 'Text Field', 'Checkbox', 'Radio Button', 'Dropdown/List', 'Unknown'
    """
    field_type = field_obj.field_type
    if field_type == "/Tx":
        return "Text Field"
    elif field_type == "/Ch":
        return "Dropdown/List"
    elif field_type == "/Btn":
        flags = field_obj.flags
        if flags is not None and (flags & (1 << 15)):  # Bit 16 = Radio
            return "Radio Button"
        return "Checkbox"
    return "Unknown"


def get_checkbox_on_states(pdf_path: str) -> dict:
    """Extract the 'on' appearance state for every checkbox in the PDF.
    
    Returns dict mapping field_name -> on_state_string (e.g., '/1', '/Yes')
    Inspects /AP/N dictionary of each widget annotation to find non-Off state.
    """
    reader = PdfReader(pdf_path)
    checkbox_states = {}
    
    for page in reader.pages:
        annots = page.get('/Annots', [])
        if not annots:
            continue
        for annot in annots:
            annot_obj = annot.get_object()
            field_type = annot_obj.get('/FT')
            if field_type != '/Btn':
                continue
            
            # Build full field name by traversing parent chain
            name_parts = []
            obj = annot_obj
            while obj:
                t = obj.get('/T')
                if t:
                    name_parts.insert(0, str(t))
                parent = obj.get('/Parent')
                if parent:
                    obj = parent.get_object()
                else:
                    break
            
            full_name = '.'.join(name_parts)
            
            # Get AP/N keys
            ap = annot_obj.get('/AP')
            if ap:
                ap_obj = ap.get_object()
                n = ap_obj.get('/N')
                if n:
                    n_obj = n.get_object()
                    states = list(n_obj.keys())
                    on_states = [s for s in states if s != '/Off']
                    if on_states:
                        checkbox_states[full_name] = on_states[0]
    
    return checkbox_states
