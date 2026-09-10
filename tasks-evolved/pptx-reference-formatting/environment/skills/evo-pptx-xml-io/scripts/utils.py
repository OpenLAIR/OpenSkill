"""Low-level PPTX utilities using python-pptx."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE


def open_presentation(path):
    """Open a PPTX file and return the Presentation object."""
    return Presentation(path)


def save_presentation(prs, path):
    """Save the Presentation object to a file."""
    prs.save(path)


def get_slide_dimensions(prs):
    """Return (slide_width, slide_height) in EMU."""
    return prs.slide_width, prs.slide_height


def get_all_slides(prs):
    """Return list of all slides."""
    return list(prs.slides)


def find_shapes_in_slide(slide):
    """Return all shapes in a slide."""
    return list(slide.shapes)


def get_namespaces():
    """Return OOXML namespace dict."""
    return {
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    }
