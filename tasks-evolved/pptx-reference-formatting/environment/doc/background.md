# Comprehensive API Guide and Methodological Analysis for Programmatic PowerPoint (PPTX) Manipulation

**Key Points:**
*   **Library Capabilities and Constraints**: The `python-pptx` library provides a robust object-oriented wrapper over the Office Open XML (OOXML) standard, facilitating the programmatic manipulation of slides, shapes, and typography. However, it lacks native API support for several advanced features, such as numbered lists and global theme overrides, necessitating direct XML manipulation [cite: 1, 2].
*   **Dependency Requirements**: `python-pptx` cannot function strictly on `lxml` alone; it maintains hard dependencies on `Pillow` (for image processing and metrics) and `XlsxWriter` (for charting) [cite: 3, 4]. In highly constrained environments (e.g., restricted Docker containers), raw ZIP and OOXML manipulation using `lxml` is the mandatory fallback.
*   **Spatial Metrics**: PowerPoint relies on English Metric Units (EMU) for all spatial positioning, allowing exact floating-point-free conversions between inches and centimeters [cite: 5, 6]. Text measurement requires external typography engines (like Pillow) as PowerPoint relies on the host OS's rendering engine for font kerning and layout [cite: 7, 8].
*   **OOXML Traversal**: Precise heuristics, structural awareness of the `a:` (DrawingML) and `p:` (PresentationML) namespaces, and Clark-notation traversal are required to distinguish semantic placeholders from orphaned structural text components.

The manipulation of Microsoft PowerPoint presentations via Python scripts represents a complex intersection of zip-archive management, XML parsing, and typographic coordinate math. The Office Open XML (OOXML) standard (ECMA-376) defines a `.pptx` file not as a single binary, but as a zipped directory of interconnected XML documents. Tools such as `python-pptx` abstract this complexity, offering Pythonic classes representing presentations, slides, and shapes. However, programmatic automation frequently hits the boundary of this abstraction layer. Issues such as accurately calculating text bounding boxes, enforcing strict numbered list typography, or operating in environments devoid of the full dependency tree demand a granular understanding of both the library's undocumented edges and the raw OOXML specification itself. This report provides an exhaustive, academic-grade guide to mastering these tasks, spanning from high-level `python-pptx` API usage to low-level byte-stream XML operations.

## 1. Reading and Iterating Slides and Shapes in `python-pptx`

The structural hierarchy of a presentation in `python-pptx` follows the sequence: `Presentation` \(\rightarrow\) `Slide` \(\rightarrow\) `Shape` \(\rightarrow\) `TextFrame` \(\rightarrow\) `Paragraph` \(\rightarrow\) `Run`. To perform comprehensive data extraction or manipulation, one must effectively traverse this hierarchy while categorizing the encountered geometric and textual elements.

### Iteration and Shape Identification
Iterating through a presentation requires sequential traversal of the `prs.slides` collection, followed by the `slide.shapes` collection. Every shape possesses a `shape_type` attribute, which returns an integer mapped to the `MSO_SHAPE_TYPE` enumeration. 

It is a critical feature of the library that **any placeholder shape** (such as the default Title or Body boxes defined by the slide master) will unconditionally return `MSO_SHAPE_TYPE.PLACEHOLDER` [cite: 9, 10]. This supersedes its geometric type; a placeholder that looks like a text box will not return `TEXT_BOX`.

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

prs = Presentation('academic_deck.pptx')

for slide_index, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        # Check if the shape can contain text
        if not shape.has_text_frame:
            continue
            
        # Distinguish placeholders from free-standing elements
        if shape.is_placeholder:
            # shape.shape_type will be MSO_SHAPE_TYPE.PLACEHOLDER (14)
            ph_format = shape.placeholder_format
            print(f"Placeholder Type: {ph_format.type}, Index: {ph_format.idx}")
        elif shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
            # Free-standing text box inserted manually by the user
            print(f"Free-standing Text Box found with text: {shape.text[:20]}...")
```

#### Exact Enum Values for `MSO_SHAPE_TYPE`
The `MSO_SHAPE_TYPE` enumeration provides the definitive classification for elements [cite: 11]. The most commonly encountered values include:
*   `AUTO_SHAPE` (1): Standard geometric shapes (rectangles, circles).
*   `GROUP` (6): A grouped collection of shapes.
*   `PICTURE` (13): Raster images or vectors.
*   `PLACEHOLDER` (14): A layout-derived placeholder (unconditional for placeholders) [cite: 10].
*   `TEXT_BOX` (17): A standard, free-standing text container.
*   `TABLE` (19): A graphical table object.

### Detecting "Dangling" Text and Academic Paper Titles
A frequent task in document parsing is differentiating regular content from semantic headers, particularly identifying "dangling" or "orphan" text boxes that operate as document titles but are not formally linked to the `idx=0` title placeholder. 

A programmatic heuristic engine can identify academic paper titles based on spatial positioning, textual density, and typography. Academic titles are generally 5 to 25 words long, possess elevated font sizes, and are positioned in the upper third of the canvas. If a text box meets these criteria and `shape.is_placeholder` is `False`, it is a dangling title.

```python
def is_dangling_academic_title(shape, slide_height):
    """
    Heuristic algorithm to detect orphaned paper titles.
    """
    if not shape.has_text_frame:
        return False
        
    # 1. Must be a free-standing text box, NOT a placeholder
    if shape.is_placeholder:
        return False
        
    if shape.shape_type != MSO_SHAPE_TYPE.TEXT_BOX:
        return False
        
    # 2. Spatial Heuristic: Top edge must be in the upper 33% of the slide
    if shape.top > (slide_height * 0.33):
        return False
        
    # 3. Textual Heuristic: Length of academic titles
    text = shape.text.strip()
    words = text.split()
    if not (5 <= len(words) <= 30):
        return False
        
    # 4. Typographic Heuristic: Checking run font sizes
    # We examine the first paragraph and its first run
    try:
        first_run = shape.text_frame.paragraphs.runs
        # Font size might be None if inherited, requiring raw XML checks
        if first_run.font.size and first_run.font.size.pt < 20:
            return False
    except IndexError:
        pass # Handle empty paragraphs safely
        
    return True
```

## 2. Typography and Font Formatting in `python-pptx`

In OOXML, text formatting is strictly applied at the `Run` level (`<a:r>`), which exists inside a `Paragraph` (`<a:p>`). While some paragraph-level defaults exist (`<a:defRPr>`), `python-pptx` requires the developer to iterate over runs to explicitly assign character properties.

### Exact API Implementations for Runs
To enforce precise typography, you must interact with the `font` proxy object on the `Run` instance.

*   **Font Name**: The typeface is applied directly via a string assignment.
    ```python
    run.font.name = 'Arial'
    ```
*   **Font Size**: Sizes are assigned using dimension objects. The exact import path is `from pptx.util import Pt` [cite: 5, 12].
    ```python
    from pptx.util import Pt
    run.font.size = Pt(24)
    ```
*   **Font Color (Hexadecimal / RGB)**: Colors require the `RGBColor` object. The exact import path is `from pptx.dml.color import RGBColor` [cite: 12, 13].
    ```python
    from pptx.dml.color import RGBColor
    # Setting hex #989596 requires mapping to integer RGB values
    run.font.color.rgb = RGBColor(0x98, 0x95, 0x96)
    ```
*   **Font Bold/Italic Toggle**: The bold property is a tri-state boolean (`True`, `False`, or `None`). Setting it to `False` explicitly forces the text to be non-bold, overriding any inherited styles.
    ```python
    run.font.bold = False
    ```

### The Pitfall of Inherited and Theme Fonts
A common limitation reported by developers is that `run.font.size` or `run.font.color.rgb` returns `None` [cite: 14]. This does *not* mean the text has no size or color; it indicates that the value is inherited from the Slide Master, the layout placeholder, or the document theme, and is not explicitly serialized on the run's local XML node (`<a:rPr>`). 

To completely override inherited theme fonts, you cannot rely on paragraph-level settings using the standard API. You must iterate through every run in the text frame and explicitly stamp the `<a:rPr>` node with your exact specifications.

```python
def override_run_typography(paragraph, font_name='Arial', size_pt=18, hex_color=0x000000):
    """Iterates runs to explicitly sever theme inheritance."""
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    
    # Extract RGB components from hex
    r = (hex_color >> 16) & 0xFF
    g = (hex_color >> 8) & 0xFF
    b = hex_color & 0xFF

    for run in paragraph.runs:
        run.font.name = font_name
        run.font.size = Pt(size_pt)
        run.font.color.rgb = RGBColor(r, g, b)
        run.font.bold = False # Force override inherited boldness
```

## 3. Text Box Sizing, Positioning, and Spatial Mathematics

All coordinates and dimensions in OOXML are stored in English Metric Units (EMU). The EMU is an integer unit designed specifically for cross-platform graphic fidelity, defined such that 1 Inch = 914,400 EMU, and 1 Centimeter = 360,000 EMU [cite: 5, 6]. This prevents floating-point precision errors during serialization.

### Conversions and Resizing
Resizing a text box involves modifying its `width` and `height` properties using the `pptx.util` classes. 

```python
from pptx.util import Inches, Pt, Emu, Cm

# Example of reading properties (returned in raw EMU as an integer subclass)
current_width_emu = shape.width
current_width_inches = shape.width.inches

# Example of writing properties
shape.width = Inches(5.5)
shape.height = Cm(4.0)
```

### Advanced Spatial Math: Centering and Docking
Positioning a shape relies strictly on its `left` (X coordinate) and `top` (Y coordinate) boundaries relative to the top-left origin of the slide canvas.

**Centering Horizontally:**
```python
slide_width = prs.slide_width
shape.left = int((slide_width - shape.width) / 2)
```

**Docking to Bottom of Slide:**
```python
slide_height = prs.slide_height
margin = Inches(0.5)
shape.top = int(slide_height - shape.height - margin)
```

### Calculating Text Width via PIL/Pillow
One of the most profound limitations of `python-pptx` is its inability to calculate text dimensions. Because it operates strictly on XML generation, it possesses no rendering engine to measure font metrics, kerning, or glyph advances. To calculate the exact width of a single line of text dynamically, an external rendering library such as `Pillow` (PIL) is mandatory [cite: 7, 8].

The traditional `ImageDraw.textsize()` method is deprecated in newer versions of Pillow. Modern text measurement requires utilizing `font.getbbox()` or `font.getmask(text).getbox()` [cite: 7, 8].

```python
from PIL import ImageFont

def calculate_text_width(text: str, font_path: str, point_size: int) -> int:
    """
    Calculates exact pixel width of text accounting for kerning.
    Returns the width. You must convert pixels to EMUs based on DPI (usually 96).
    """
    try:
        font = ImageFont.truetype(font_path, point_size)
    except IOError:
        # Fallback to default if TTF is not found on OS
        font = ImageFont.load_default()
        
    # Use getbbox for modern Pillow versions (>8.0.0)
    # Returns (left, top, right, bottom)
    bbox = font.getbbox(text)
    width_pixels = bbox[cite: 15] - bbox
    
    return width_pixels

# Conversion formula assuming 96 DPI screen scaling standard for Windows/PPT:
# 1 Pixel = 914400 / 96 = 9525 EMU
def px_to_emu(pixels: int, dpi: int = 96) -> int:
    from pptx.util import Emu
    return Emu(int(pixels * (914400 / dpi)))
```

### Word Wrap and Auto-Fit Behaviors
Controlling how text flows inside the calculated bounding box is managed via the `text_frame` object.

*   **Disabling Word Wrap**: To ensure text stays on a single horizontal line, set `word_wrap` to `False`.
    ```python
    shape.text_frame.word_wrap = False
    ```
*   **Auto-Fit Settings**: The auto-size settings define how the bounding box reacts to text overflow. The exact import path is `from pptx.enum.text import MSO_AUTO_SIZE` [cite: 15, 16, 17].
    *   `MSO_AUTO_SIZE.NONE`: Bounding box is rigid; text will spill over [cite: 15, 16].
    *   `MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT`: Box height (and width if word wrap is off) expands to accommodate the string [cite: 15].
    *   `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`: Point sizes are shrunk algorithmically until the string bounds fit within the rigid shape coordinates [cite: 15].

    ```python
    from pptx.enum.text import MSO_AUTO_SIZE
    shape.text_frame.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
    ```

## 4. Creating Slides and the Numbered List Dilemma

Appending a slide to the presentation requires indexing into the presentation's `slide_layouts` collection. Usually, `slide_layouts` is the Title layout, and `slide_layouts[cite: 9]` is the Title and Content layout.

```python
layout = prs.slide_layouts[cite: 9] # Typical "Title and Body" layout
slide = prs.slides.add_slide(layout)

# Setting the Title
title_shape = slide.shapes.title
title_shape.text = "Empirical Analysis"

# Setting standard bullet points in the Body
body_shape = slide.placeholders[cite: 9]
tf = body_shape.text_frame
tf.text = "First standard point"
p = tf.add_paragraph()
p.text = "Second standard point"
```

### The Critical Issue: Numbered (Auto-Numbered) Bullet Points
Native API support for numbered lists does not exist in `python-pptx` as of the current releases [cite: 1, 2, 18]. Calling `.setBullet(True)` (or its Python equivalent) simply enforces standard symbol bullets. OOXML structures numbered lists via the `<a:buAutoNum>` tag located inside the paragraph properties (`<a:pPr>`).

To bypass this limitation, we must execute direct XML injection using `lxml` via the underlying oxml architecture of the paragraph object.

#### Valid `buAutoNum` Types
The `type` attribute determines the numbering style. Common drawingML valid values include [cite: 2]:
*   `arabicPeriod`: (1., 2., 3.)
*   `arabicParenR`: (1), 2), 3))
*   `alphaLcParenR`: (a), b), c))
*   `alphaUcPeriod`: (A., B., C.)
*   `romanUcPeriod`: (I., II., III.)

#### LXML Manipulation Code for Numbered Bullets
This solution drops into the `_p` private variable (which holds the `lxml.etree._Element` representing the paragraph) to inject DrawingML tags natively [cite: 18, 19].

```python
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn

def set_numbered_bullet(paragraph, numbering_type="arabicPeriod"):
    """
    Forces a python-pptx Paragraph to use numbered lists via lxml injection.
    """
    # 1. Access the raw <a:p> XML element
    p_element = paragraph._p
    
    # 2. Get or add the Paragraph Properties (<a:pPr>) element
    pPr = p_element.get_or_add_pPr()
    
    # 3. Clean existing bullet configurations to prevent conflicts
    # Remove <a:buNone>, <a:buChar>, <a:buFont>, <a:buBlip> if they exist
    for tag in ['a:buNone', 'a:buChar', 'a:buFont', 'a:buBlip', 'a:buAutoNum']:
        existing = pPr.find(qn(tag))
        if existing is not None:
            pPr.remove(existing)

    # 4. Create the new <a:buAutoNum> element
    # Use OxmlElement which acts as lxml.etree.SubElement but respects the registry
    buAutoNum = OxmlElement('a:buAutoNum')
    
    # 5. Set the numbering type
    buAutoNum.set('type', numbering_type)
    
    # Optional: ensure correct indentation attributes on pPr
    # marL is margin left, indent is negative to create the hanging effect
    pPr.set('marL', '457200')  # 0.5 inches in EMU
    pPr.set('indent', '-228600') # -0.25 inches in EMU

    # 6. Append the buAutoNum element to paragraph properties
    pPr.insert(0, buAutoNum)

# Application usage:
p2 = slide.placeholders[cite: 9].text_frame.add_paragraph()
p2.text = "First Item"
set_numbered_bullet(p2, "arabicPeriod")

p3 = slide.placeholders[cite: 9].text_frame.add_paragraph()
p3.text = "Second Item"
set_numbered_bullet(p3, "arabicPeriod")
```

## 5. Working with `lxml` to Manipulate OOXML Directly

As demonstrated above, `python-pptx` permits an escape hatch into raw XML manipulation. The underlying engine mapping the objects to the XML tree is called `xmlchemy` [cite: 20]. 

When manipulating these raw XML nodes (`_Element` instances from `lxml.etree`), we must strictly adhere to the OpenXML namespace constraints.

### The Namespace Context
The DrawingML namespace URI is: `http://schemas.openxmlformats.org/drawingml/2006/main`.
In OOXML, this is nearly universally mapped to the `a:` prefix.

The `pptx.oxml.ns.qn()` function (standing for *Qualified Name*) converts a human-readable prefix (like `a:pPr`) into the standard Clark notation required by `lxml` (e.g., `{http://schemas.openxmlformats.org/drawingml/2006/main}pPr`) [cite: 21, 22].

**Exact Imports and Syntax:**
```python
import lxml.etree
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement # Safer than raw SubElement for pptx tracking [cite: 17, 23]

# Accessing raw paragraph
raw_p = paragraph._p

# Using XPath with Clark notation (provided natively by lxml if namespaces map is passed)
# However, python-pptx elements support namespaced XPath
flds = raw_p.xpath("./a:fld") # Finding all field elements [cite: 21]
```

## 6. Important Pitfalls: The Docker/Dependency Constraint

**Critical Clarification:** `python-pptx` **cannot** work strictly with `lxml` and `defusedxml` if the `python-pptx` package itself is uninstalled. While `python-pptx` relies on `lxml` as its XML parsing engine, it is not a part of the standard library and explicitly requires `Pillow` and `XlsxWriter` as mandatory dependencies [cite: 3, 4, 24]. 

If you are operating inside a locked-down Dockerfile that only possesses `lxml`, `defusedxml`, and `six`, `import pptx` will fail with a `ModuleNotFoundError` [cite: 25]. 

Under these rigid constraints, you must construct a zero-dependency script using Python's native `zipfile` module alongside `lxml` to decompress the `.pptx`, alter the specific slide's XML file, and repackage it.

### Structure of a `.pptx` ZIP Archive
A `.pptx` file is fundamentally a ZIP archive adhering to the Open Packaging Conventions (OPC). 
*   `[Content_Types].xml`: Maps file extensions to MIME types.
*   `_rels/.rels`: Defines global relationships (where the core presentation sits).
*   `ppt/presentation.xml`: The root presentation file holding slide sequences.
*   `ppt/slides/slide1.xml`: The individual geometric and text data for slide 1.
*   `ppt/slideLayouts/slideLayout1.xml`: The master layouts providing inherited traits.
*   `ppt/slides/_rels/slide1.xml.rels`: Maps local slide resources (e.g., hyperlinks, image paths).

### Pure Python/`lxml` Approach to Read/Modify PPTX
The following is a complete, working codebase that opens a PPTX as a ZIP, uses `lxml` to parse the slides, detects a dangling academic title using XML heuristics, alters the text to add a prefix, and saves a valid new PPTX without using the `python-pptx` library.

```python
import zipfile
import io
from lxml import etree

def process_pptx_pure_lxml(input_path: str, output_path: str):
    """
    Modifies a PowerPoint file relying strictly on zipfile and lxml.
    Requires ZERO external dependencies outside of lxml.
    """
    
    # Define the DrawingML namespace for Clark notation
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    namespaces = {'a': a_ns, 'p': p_ns}

    # Open the archive into memory
    with zipfile.ZipFile(input_path, 'r') as zin:
        # Create an in-memory zip file for output
        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            
            for item in zin.infolist():
                file_content = zin.read(item.filename)
                
                # Check if we are reading a slide XML
                if item.filename.startswith('ppt/slides/slide') and item.filename.endswith('.xml'):
                    root = etree.fromstring(file_content)
                    
                    # Iterate over all shapes (<p:sp>) in the slide's shape tree (<p:spTree>)
                    for sp in root.findall('.//p:sp', namespaces):
                        
                        # HEURISTIC CHECK: Is this an academic paper title?
                        is_title = False
                        
                        # 1. Ensure it's not a placeholder (Look for absence of <p:ph>)
                        # Placeholder shapes have <p:nvSpPr><p:nvPr><p:ph .../></p:nvPr></p:nvSpPr>
                        ph_element = sp.find('.//p:ph', namespaces)
                        if ph_element is not None:
                            continue # It's a standard layout element, not an orphan
                            
                        # 2. Check Spatial Positioning (Bounding Box <a:off>)
                        off_element = sp.find('.//a:off', namespaces)
                        if off_element is not None:
                            y_emu = int(off_element.get('y', '0'))
                            # 914400 * 7.5 (standard height) = 6858000 EMU total height
                            # Check if Y is in top 33% (approx < 2286000 EMU)
                            if y_emu > 2286000:
                                continue 
                        
                        # 3. Check Text properties
                        txBody = sp.find('.//p:txBody', namespaces)
                        if txBody is not None:
                            # Extract all text segments (<a:t>)
                            texts = [t.text for t in txBody.findall('.//a:t', namespaces) if t.text]
                            full_text = " ".join(texts)
                            
                            # Heuristic: Title length between 25 and 150 characters
                            if 25 <= len(full_text) <= 150:
                                is_title = True
                                
                        if is_title:
                            # Modify the text to demonstrate manipulation
                            first_t = txBody.find('.//a:t', namespaces)
                            if first_t is not None:
                                first_t.text = "[REVISED] " + (first_t.text or "")
                                
                    # Serialize the modified XML tree back to byte string
                    modified_xml = etree.tostring(root, encoding='utf-8', xml_declaration=True)
                    zout.writestr(item, modified_xml)
                    
                else:
                    # Non-slide files (rels, content types, images) are copied directly
                    zout.writestr(item, file_content)

# Execution
# process_pptx_pure_lxml('input.pptx', 'output_modified.pptx')
```

### Heuristics for Title Detection at the Raw XML Level
Identifying academic paper titles strictly through XML elements, without the `python-pptx` abstraction, relies on traversing the `<p:sp>` (Shape) node:
1.  **Non-Placeholder Check**: The shape properties node `<p:nvPr>` must **not** contain a `<p:ph>` tag. If `<p:ph>` exists, it relies on template inheritance rather than being an orphaned copy-paste object.
2.  **Y-Axis Extents**: Check the `<a:off y="X">` element. If `X` is minimal (e.g., `< 2000000` EMU), the text box is pinned to the header boundary.
3.  **Typographic Density**: Check `<a:rPr sz="X">`. If `sz="2400"` or greater, the text is at least 24pt (XML font sizes are 100x the point value). A high font size tied to moderate string length (`<a:t>`) strongly correlates with a document title.
4.  **Bullet Abstinence**: Academic titles lack bullets. Ensure that `<a:buNone>` is present in the `<a:pPr>` properties, indicating the text is not part of a standardized content list.

By utilizing these heuristics inside an `lxml` pipeline, you completely circumvent the Docker dependency lock-out, granting full read-write architecture manipulation over PowerPoint documents.

**Sources:**
1. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFm2bjJgysNJjVzQFq9UXXckLyNDoCK_c4ILit8oP9mkxq2IkqnAYmZE5JeVRgwsvyPtu5wAHTzTkska3PBdpZsuLgYCNHhG2NcynBRE8Oc2O3trUeXuSFS5uEyCqZNWMgJyvU-e3pCNlEN3e9deDVUb2G3IJrDDQch60GnyVCzyKNkPeDdknheG0mLasVr9MevxW20r-YFkjX9L_5OLv22qPSj)
2. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUej6dTh_Ng9PJCw6mXJmaGfTNWrSXmP_EGulgsANU449kAdAFY2Zz4ZB1Cl7DfxsSzpQ43B70_dwPOmK-v_lv-LAWtL4eEgrJC6pQXoBzvTrScf9bksrk9ii5q6_ZgpCBjNPncm3uJDkdQR0VYKzSHkJa8xXQLI16Df1k868IjQnx6uGwe-lSdD-hwe9PlPTm)
3. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHMtEYnLaa6g6XWaDGJktJGqGLn6X_5IH2yM2ng3WGeAg5yEexRusYQGVYBXY1U9h9qaJ61TuSL1t8AjJYshQeoWA2dZq7nLx__ADqR-A0uKukEQhdLQcI6PUmFfK5JU6CPoekee8FNrjVGHr7oLNC_cJn3lg==)
4. [pypistats.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGL-poVtpoEgwzF3A2aWGYdNEq5uJggAf_Rpw262lUCBjIjD-CogBt4dtAioHFaqDNrItNEZxcWsotoDvrfyFmQhmADJYYT3WiToWoBDNDtlmtuR9wFXkyygF4Xln8-3lA=)
5. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSeeM23z3k8pFd5hsjIxHTzeDjkj8fp3NQrBDTKj6rX1rqh8g2f-DcETJiXRe2vriEuhtKDvAYcICu4l2ghLHIydiaBoCVcbS8Mu0JsHy0PIjJL0XlPoe5J_4aDwElMaY3XPcXcLz5cCNYYJZOjFg4LFXbpwC_Uw==)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTUFwZscKjtRXSJZczNc0iVwvJXn5djqTBDZI-djSDVxHPSiVjs46fpfMHCpaZtipbgYOWKem7W54xNBLrwVS2XloQY1QIVS-JW1XcI_8tWpjQr96tsCB25WWL1S-Ka5y1_3XLZq0MqZzQONr1l6rBuwEEZ7UOVGpxreQBM6FuiA==)
7. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQM2qlYTzegOKOecUkAMC0CB3oDnInY7M0yihrWQgJ4PaivCt3zVX4LpzpPHuDJwvVCb_v4Y4WcKVqBxAc2bS0SxaFRehpRR9hIemgkoy5LFu9Zp8kI0zwoeWAb1HuP-Fk-SzmElX3dwI373Z5UgawCBo8HC1QaylrYuXFfnNggtIgp8_d)
8. [gitconnected.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4K_KanulmvlFY5frKJhfLU6bRl_E3pMXH-ORHVLKm3Jz_wSRMLgIeq7unZ3P0L-X5Rl5X1vWp3iEwqFe0uN6aNfCHLRpeH5E1p6rsIU6vyuPI3JaVTA_igDHS5XTqN1-9dMZK1Oi2sNOMndY8jYaN80-Y5liNLU_83e3l4X3xRrSrjVwY8t4_0FmD-DMd3lQXYykBtQ==)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlYDicqvo5DkeESumdArF7QXjKzSXuGTDJmVPEQR_Lhrzs47eSRtjG9AhRhwFgzg8mo4pZ9US496Rt9BhtZ-IUzlkxW0qdGKJozUbw_ycHUasuYyAuVN8OmQV1FxXGXOChdtLsgrBfeEFpq9VF4qfkM5qWxqonhTvMnJ71JlU2)
10. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOpQjbHgT5DpR3ii_Lhkuu6RO2Fe7hVQmaj9vh4baNoCBZILq6jmQrmv2bM1gpSidVVKP-u6SbkDlMYt47VKpk016Pof7DXfMVv14-FqcS2yPwJgmyd6cViqgX2-_QJzqX)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGiaE8IHjKjOV4EPUEtI5Og4kr4vt4V-SKmLGE-a2MlgeJ416EuVjELQzHSFLoaKkCxkcQvhUn8Gaqkxu63CZydKLjj8EXQTNGJ6o2e-hB1R9ehWcXBWGIGIlyAK_wEYHtAHAv0jy9pDIjAqkQOwhjz6dVyqa2J6NvsFJg3HQ==)
12. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_sc8valN84UQwi5LzkodP37PypeS9SK3XV4iGZ6XSHeuE_Y-7Qyv__rBImW37gMZEsWuYYtIqfh1RNFrKxfD4VCKTzL4KmP9glkZGAoxKa6TAl8HwNC6CKvQcWRil-DfccMtC3g8Vo4NGt9SjAJMpB8W_bkX9gGuIHv6_cQZDOL0h6ZLh)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHWRtnm4kxrThOoWeVpkoa7i1DTLZwkM0C2Rd6kzCIcbxkeNMU_vPd5Em_yNvahBYQhBmABD9QHTqZFKMgiWXnriHh5NTbXBDb8shLmnoVCzTz7GKS5TH3fTQW8ej-QyVUJZG3KxpmRDYzJ3xFo0Nc4qjGs1DDMwZHxyYMfq5ZZ0dmKgg==)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjV8MD1npdK2adE4VY7_Aps5rDbavuN812rN04NKKFjt7k7qPSZpn4mT0OKnxh9h7LkN0RlY7hud6h4KHoqM20srT1DVHc2eWtWjlZtCoNPG8XK2pH4bPg9qj0rel5c2zB5VO9bOHy8DFP_GJ1lDSpT3enZ3nTajAbKgs9ryI=)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGweRq6RIG9vOmmQeDCVi1uXNUfn1tkXH0qD84WE78oZpZ8qVCjVtbH5VQdeUXcIMxTVAj0DMKPCnJqmCjXs4hYjVB4rmJ5jNoBCokI4uOhXbR71Wx8hkg3A__ANVdINz6DlB8YR103fcis3XCJ3HJZcxTACHcQvWLNHPMP)
16. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFC8aRE1Sx11Y3DdYGnHOU9srLCVs4qgYkNpiiIbtLH352PgoxCMGPf6_ammGL62sm0lhbywwh_efFG7fdeyBJVbih4nHpr0nEgQZtbM7u0Zy2VII46jYCiWLrJ4VdTayOLZU_XcmDnF14=)
17. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKhaOxQbk84VPJDG0uc_jtQZrC-ajpO9i4hwFPHEI251WFIrCemV62g61yhJuH_z1xrGCXfCdhs74M7xHgmRNiHhsZEohE7Y3iQzAFXPoZzL_7GBC0Npsj9zI89u1KQsbgA--FLBuxcvxeQ0eW52fH7KhaWGpEw4c3xZKuoz0bMdtn_Q==)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXMLGzWaqPSF2DdB1tX4XSzIZZzFLyBMH6Dp8Vo5RE_qp3ZZE21ByEMPLH1oCdjhR7KW--tPnP4tQBlueRpIsi_FANLHJniqMq57zJImw9Ufi2WlxJwrz55yfxIswU6LwQixu5SO8JCPVFoVmQUFHIhCRdfN1VOVQ9HpLRHZK6DZ7TAF0=)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtr6oE1YaKsu5qNio_0LBFHTsZP2LenGXFTE3uBQi8YZM8VQcMWAWrtevQxXDLo2ffd3dqlLnuu49KUbofAkNny3docJzl1OBqyxS6Ub1--82I-hQJVd9cRMi4ZWHZ9Grm5FXi6wiKu-wo4YtqURjsPKbOS8I6fXJeYXfXqlW0)
20. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFiKLbnuN1HDSGshZ8aNVLe1OlWtHi7W9dvD5Y1y4iFoBJPmE3TYfdHvkWFcmP_GeOg40WtnFxdkWCGnlukwibGjh0Rlgaie1MO5ibQUXMXyZo9e9ko1vGlf17U2MjKEgpsVk6nBsd2_1vRwir37HEdFPgiuQ==)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_W4JeOCwXeO30DQhmjV8rxO6F0V88X9nH-MNrBGEa-WAMzf6lXGlLqKXPoFTJ4Ap47IZfit7GurIFqriWjXch1KegSE-hjJEUE5rczLrNmm0QBqiyJ9nxRwd_r8FxNNsEp_ss6LYi11HX5m2sR-mWy6ZSa6-F4UMplX_2VyF4ktomftFCN0kfBkuX6DtpNP1J2bLxd-xhlpHZnfwRP4bpMuWCn--Ho9BGKzRM5J_m1KU5og==)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAQt10NEzEHq8pgjQeh4BeFJxxgQ9LkG_8pX1sz0BOaqtwrRX-rxkaxshF2OWBPHQBuNRq-BWhoKaIEavBEeQlgf7au0m5L9HQN8oJtQy7phf4BYigVkfNM6lC4YF77Pq_6au49mRmiNu5bs_AvgKKbeQBwjAdMY80jDjhk4eduoIB2IWxyofVV7BclnBEXJnFlPhjTp32kjko)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE28Z-HvMhKYttVHcNlbPREqAtvppiA0fXVf5JFbuoHMB9kyXLOQiQpCXO0ljWOzrSEaoytM4_Ho9utPAp0f-x94yd4uksUx1wXoSmbZ57c6u9IIROOSU0oVFs2jLN2Wkj7JxBZRYbvLySgtEpJlg==)
24. [piwheels.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNUk68WjQC1la-fvtpbMy0-igpsqAw6r74gyA11XH47_jjHvaezHF3nrK5xfWszkCwX-sFVXfI2umZvawHW3amVOW8By5s4p6d6uid32YD2Y8Rv0KerWoIrAVxM46LRTAxpjw=)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnXuCSjfa7y4w2ZHV7mHwdc4ono_wzwZ4IjTJVQG3Rz_80SDvJr9xjRoJhJz-BOWm-XS8CwTYqoBZp23QFu_jJZD31yY5ltidGSyqbP8Z9sZNgsgEy9H0EdlcLvucq6R4qKDAGxkfjF0VyXzl7-Y0BMvbqPA7fhLygvJwhj5rlF40GSaAxJnblip4_-3TQRN1SkV2pVThxmSpNY26J1qo9lg==)
