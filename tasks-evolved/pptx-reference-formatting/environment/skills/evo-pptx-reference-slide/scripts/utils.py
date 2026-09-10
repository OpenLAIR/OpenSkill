"""Create a reference slide with auto-numbered bullet points."""
from pptx.util import Pt, Emu, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from lxml import etree


def deduplicate_titles(titles):
    """Remove duplicate titles while preserving order."""
    seen = set()
    unique = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def create_reference_slide(prs, titles):
    """Create a new slide at the end with 'Reference' title and auto-numbered paper titles.
    
    Args:
        prs: Presentation object
        titles: list of unique paper title strings
    Returns:
        The new slide object
    """
    # Use a layout that has title and content body
    # Try layout index 1 (Title and Content), fallback to others
    layout = None
    for i, sl in enumerate(prs.slide_layouts):
        if 'title' in sl.name.lower() and 'content' in sl.name.lower():
            layout = sl
            break
    if layout is None:
        # Try index 1 which is typically Title and Content
        try:
            layout = prs.slide_layouts[1]
        except:
            layout = prs.slide_layouts[0]
    
    slide = prs.slides.add_slide(layout)
    
    # Set the title to "Reference"
    if slide.shapes.title is not None:
        slide.shapes.title.text = "Reference"
    else:
        # Find title placeholder
        for shape in slide.placeholders:
            if shape.placeholder_format.idx == 0:
                shape.text = "Reference"
                break
    
    # Find the body/content placeholder (usually idx=1)
    body_shape = None
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == 1:
            body_shape = shape
            break
    
    if body_shape is None:
        # Fallback: use any non-title placeholder
        for shape in slide.placeholders:
            if shape.placeholder_format.idx != 0:
                body_shape = shape
                break
    
    if body_shape is not None:
        tf = body_shape.text_frame
        tf.clear()
        
        # Add each title as a paragraph with auto-numbered bullet
        for i, title in enumerate(titles):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = title
            # Apply auto-numbered bullet via XML manipulation
            _set_autonumber_bullet(p)
    
    return slide


def _set_autonumber_bullet(paragraph):
    """Set auto-numbered bullet (1. 2. 3.) on a paragraph using XML manipulation."""
    a_ns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    
    # Access the raw <a:p> XML element
    p_element = paragraph._p
    
    # Get or create paragraph properties <a:pPr>
    pPr = p_element.find('{%s}pPr' % a_ns)
    if pPr is None:
        pPr = etree.SubElement(p_element, '{%s}pPr' % a_ns)
        # Insert pPr as first child
        p_element.insert(0, pPr)
    
    # Remove any existing bullet settings
    for tag in ['buNone', 'buChar', 'buFont', 'buBlip', 'buAutoNum']:
        existing = pPr.find('{%s}%s' % (a_ns, tag))
        if existing is not None:
            pPr.remove(existing)
    
    # Create <a:buAutoNum type="arabicPeriod"/>
    buAutoNum = etree.SubElement(pPr, '{%s}buAutoNum' % a_ns)
    buAutoNum.set('type', 'arabicPeriod')
