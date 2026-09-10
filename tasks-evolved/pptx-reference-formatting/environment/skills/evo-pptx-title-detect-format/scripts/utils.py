"""Detect dangling paper titles and apply formatting."""
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN


def detect_dangling_titles(slide):
    """Detect non-placeholder text boxes that contain paper titles.
    Returns list of (shape, text) tuples for dangling title shapes.
    A dangling title is a TEXT_BOX (not a placeholder) with text content.
    """
    dangling = []
    for shape in slide.shapes:
        if shape.is_placeholder:
            continue
        if not shape.has_text_frame:
            continue
        if shape.shape_type != MSO_SHAPE_TYPE.TEXT_BOX:
            continue
        text = shape.text_frame.text.strip()
        if text:
            dangling.append((shape, text))
    return dangling


def extract_title_text(shape):
    """Extract the full text from a shape's text frame."""
    if not shape.has_text_frame:
        return ''
    return shape.text_frame.text.strip()


def apply_font_formatting_to_shape(shape, font_name='Arial', font_size_pt=16,
                                     font_color_hex='989596', bold=False):
    """Apply font formatting to ALL runs in a shape.
    - font_name: e.g. 'Arial'
    - font_size_pt: e.g. 16
    - font_color_hex: e.g. '989596' (without #)
    - bold: False to disable bold
    """
    r = int(font_color_hex[0:2], 16)
    g = int(font_color_hex[2:4], 16)
    b = int(font_color_hex[4:6], 16)
    
    for para in shape.text_frame.paragraphs:
        # Set paragraph alignment to center
        para.alignment = PP_ALIGN.CENTER
        for run in para.runs:
            run.font.name = font_name
            run.font.size = Pt(font_size_pt)
            run.font.color.rgb = RGBColor(r, g, b)
            run.font.bold = bold


def estimate_text_width_emu(text, font_name='Arial', font_size_pt=16):
    """Estimate text width in EMU for single-line display.
    Uses Pillow for accurate measurement.
    Falls back to character-count heuristic if font not found.
    """
    try:
        from PIL import ImageFont
        # Try to find Arial font
        font_paths = [
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
            '/usr/share/fonts/truetype/arial.ttf',
        ]
        font = None
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, font_size_pt)
                break
            except (IOError, OSError):
                continue
        if font is None:
            font = ImageFont.load_default()
        
        bbox = font.getbbox(text)
        width_pixels = bbox[2] - bbox[0]
        # Convert pixels to EMU: 1 pixel = 9525 EMU at 96 DPI
        width_emu = int(width_pixels * 9525)
        # Add padding (margins)
        width_emu += 200000  # ~0.22 inch padding
        return width_emu
    except Exception:
        # Fallback: rough estimate based on character count
        avg_char_width_emu = 120000  # ~0.13 inches per char at 16pt
        return int(len(text) * avg_char_width_emu + 200000)


def resize_textbox_for_single_line(shape, text=None):
    """Resize the text box width so the title fits in one line."""
    if text is None:
        text = extract_title_text(shape)
    # Get font info from first run if available
    font_size_pt = 16  # default
    font_name = 'Arial'
    new_width = estimate_text_width_emu(text, font_name, font_size_pt)
    shape.width = new_width
    # Set height for single line (16pt text + padding)
    # 16pt = 203200 EMU, add padding
    shape.height = Emu(369332)  # Keep original height which works for single line
    return new_width


def position_bottom_center(shape, slide_width, slide_height, bottom_margin_emu=200000):
    """Position the shape at the bottom center of the slide.
    Args:
        shape: the shape to position
        slide_width: slide width in EMU
        slide_height: slide height in EMU  
        bottom_margin_emu: margin from bottom edge in EMU
    """
    # Center horizontally
    shape.left = int((slide_width - shape.width) / 2)
    # Position at bottom with margin
    shape.top = int(slide_height - shape.height - bottom_margin_emu)
