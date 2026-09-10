# Comprehensive Analysis of Embedded OLE Object Manipulation in Open Packaging Convention (.pptx) Archives

**Key Points**
*   **Feasibility of Manipulation**: Extracting, reading, and modifying embedded Excel spreadsheets (OLE objects) within PowerPoint (`.pptx`) files using `python-pptx` and `openpyxl` is highly feasible through a combination of API interactions and Open Packaging Convention (OPC) archive manipulation.
*   **Object Representation**: Embedded Excel workbooks are stored as binary or XML-based parts within the `.pptx` ZIP archive (typically under `ppt/embeddings/`), referenced by a `GraphicFrame` shape with the type `MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT`.
*   **Formula Preservation**: The `openpyxl` library can successfully modify Excel data while preserving formulas by setting `data_only=False`. However, it clears cached formula values, requiring Excel to recalculate upon subsequent openings.
*   **Visual Synchronization**: Updating the underlying `.xlsx` binary does not automatically update the visual preview (usually an EMF image) cached on the slide. Refreshing this cached image programmatically is complex and generally requires OS-level COM automation or headless application execution, though evidence suggests headless LibreOffice approaches have specific limitations.

The manipulation of embedded documents within Microsoft Office presentations presents a unique challenge in automated reporting and data pipeline generation. Research suggests that while the `python-pptx` library provides excellent abstractions for native PowerPoint elements, its support for deep OLE (Object Linking and Embedding) manipulation remains partial, requiring developers to bridge the gap using low-level XML and ZIP archive modifications [cite: 1, 2]. This report provides an exhaustive, academic-level exposition on the programmatic handling of embedded Excel data within PowerPoint files, using Python. We will explore the Open XML architecture, OLE shape detection, data extraction, formula preservation, package rebuilding, and visual cache synchronization.

## 1. Accessing Embedded Excel Objects in python-pptx

### 1.1 The Open Packaging Convention (OPC) and OLE Architecture
A `.pptx` file is not a singular binary blob; rather, it is a specialized ZIP archive defined by the Open Packaging Convention (OPC) [cite: 3]. In OPC parlance, the archive is known as a "package," and the individual files within it are "parts" [cite: 3]. An embedded Excel workbook exists as a distinct part within this package, typically located at a path such as `ppt/embeddings/oleObject1.xlsx` or `Microsoft_Excel_Worksheet1.xlsx` [cite: 4]. 

When an Excel worksheet is embedded onto a PowerPoint slide, PowerPoint constructs a `GraphicFrame` container to hold the object [cite: 2]. This is fundamentally different from a native PowerPoint DrawingML table. A graphic-frame serves as a container for non-native shapes, such as charts, smart-art, and embedded MS Office objects [cite: 2]. 

### 1.2 Shape Types and Identification
To access these embedded objects using `python-pptx` (version 1.0.2), one must iterate through the shape tree of a slide and inspect the `shape_type` property. The correct enumeration for an embedded Excel workbook is `MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT` (often represented by the integer 7) [cite: 5, 6]. It is critical not to confuse this with `MSO_SHAPE_TYPE.TABLE` or `MSO_SHAPE_TYPE.LINKED_OLE_OBJECT` [cite: 2, 7].

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

prs = Presentation('sample.pptx')
for slide_index, slide in enumerate(prs.slides):
    for shape_index, shape in enumerate(slide.shapes):
        # Identify embedded OLE objects
        if shape.shape_type == MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT:
            print(f"Found embedded OLE object on slide {slide_index}")
        elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            print(f"Found native DrawingML table on slide {slide_index}")
```

### 1.3 The `ole_format` Property and XML Inspection
When a shape is identified as an `EMBEDDED_OLE_OBJECT`, `python-pptx` exposes an `ole_format` property, which returns an `_OleFormat` object [cite: 6, 7]. This object provides access to the underlying binary blob and the Programmatic Identifier (`prog_id`).

The `prog_id` indicates the OLE server application registered to open the object [cite: 6]. For modern Excel workbooks, this is typically `Excel.Sheet.12`, corresponding to the `PROG_ID.XLSX` enumeration [cite: 6, 8].

If direct API access is insufficient, you can inspect the underlying XML representation (`shape._element`). An OLE object inside a `GraphicFrame` is represented by a `<p:oleObj>` element containing an `r:id` attribute. This `r:id` is the relationship ID that maps the shape to the embedded part in the `.rels` file [cite: 6].

```python
if shape.shape_type == MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT:
    ole_format = shape.ole_format
    print(f"Prog ID: {ole_format.prog_id}") # e.g., 'Excel.Sheet.12'
    
    # Accessing the raw binary bytes via API
    excel_bytes = ole_format.blob 
    
    # Low-level XML inspection to find the Relationship ID (rId)
    # The graphic frame contains a graphicData element, which contains the oleObj
    ole_obj_xml = shape._element.xpath('.//p:oleObj')
    r_id = ole_obj_xml.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
    print(f"Relationship ID: {r_id}")
```

## 2. Extracting the Embedded xlsx Binary from the pptx Package

Extraction of the underlying `.xlsx` file can be achieved through two primary paradigms: utilizing the internal relationship mappings of `python-pptx` or employing Python's standard `zipfile` library to interact directly with the OPC container.

### 2.1 Approach A: Using python-pptx Internal API
The `python-pptx` library maintains an internal graph of relationships. Every `SlidePart` has a `related_parts` dictionary, keyed by the relationship ID (`rId`) [cite: 9]. Once the `rId` is extracted from the `p:oleObj` XML element as demonstrated above, you can retrieve the `EmbeddedPackagePart`.

```python
# Assuming r_id was extracted from shape._element.xpath('.//p:oleObj')
embedded_part = slide.part.related_parts[r_id]

# The _blob attribute holds the raw bytes of the Excel file
extracted_excel_bytes = embedded_part._blob
print(f"Extracted {len(extracted_excel_bytes)} bytes from part: {embedded_part.partname}")
```
The `partname` property will explicitly show the OPC path, such as `/ppt/embeddings/Microsoft_Excel_Worksheet1.xlsx` [cite: 4].

### 2.2 Approach B: Direct Extraction via `zipfile`
For pipelines requiring strict memory management or bypass of the `python-pptx` parsing overhead, direct ZIP manipulation is highly effective. The Open Packaging Convention maps slide relationships in XML files located at `ppt/slides/_rels/slideX.xml.rels`. 

By parsing the `.rels` file, we can map the `rId` to the `Target` attribute, which provides the path to the embedding.

```python
import zipfile
import xml.etree.ElementTree as ET
import os

pptx_path = 'sample.pptx'
namespaces = {
    'rels': 'http://schemas.openxmlformats.org/package/2006/relationships'
}

with zipfile.ZipFile(pptx_path, 'r') as z:
    # 1. Read the relationship file for a specific slide (e.g., slide1.xml)
    rels_content = z.read('ppt/slides/_rels/slide1.xml.rels')
    rels_tree = ET.fromstring(rels_content)
    
    # 2. Iterate through relationships to find OLE objects
    for rel in rels_tree.findall('rels:Relationship', namespaces):
        if 'oleObject' in rel.attrib['Type']:
            target_path = rel.attrib['Target'] # e.g., '../embeddings/oleObject1.xlsx'
            
            # Normalize the path relative to the 'ppt/slides' directory
            # target_path usually starts with '../'
            normalized_path = os.path.normpath(os.path.join('ppt/slides', target_path)).replace('\\', '/')
            
            # 3. Extract the binary
            excel_bytes_from_zip = z.read(normalized_path)
            print(f"Extracted from ZIP: {normalized_path}")
```

## 3. Reading the Extracted xlsx with openpyxl

With the `.xlsx` bytes extracted, we transition to data manipulation using `openpyxl` (version 3.1.5). `openpyxl` is robust but requires specific parameters to handle formulas correctly.

### 3.1 The `data_only` Parameter
To preserve formulas when reading and subsequently modifying the workbook, it is absolutely critical to initialize `openpyxl.load_workbook()` with `data_only=False` [cite: 10, 11]. If `data_only=True` is used, `openpyxl` discards the formulas and replaces them with the cached output values generated the last time Excel calculated the sheet [cite: 11, 12]. 

```python
import io
from openpyxl import load_workbook

# Load the workbook from memory buffer
wb = load_workbook(io.BytesIO(extracted_excel_bytes), data_only=False)
ws = wb.active
```

### 3.2 Iterating Cells and Distinguishing Formulas
In `openpyxl`, formula cells evaluate as strings beginning with the `=` character [cite: 12]. Mathematical distinction between dynamic formula cells \( C_f \) and static value cells \( C_v \) can be executed via a string prefix check.

```python
for row in ws.iter_rows():
    for cell in row:
        if cell.value is not None:
            # Distinguish formulas from static values
            if isinstance(cell.value, str) and cell.value.startswith('='):
                print(f"Formula found at {cell.coordinate}: {cell.value}")
                # Example: =SUM(A1:A5)
            else:
                print(f"Static value at {cell.coordinate}: {cell.value} (Type: {type(cell.value)})")
```
It is worth noting that if an application relies on a formula not defined in the initial OpenXML specification, it may be prefixed with `_xlfn.` [cite: 12]. `openpyxl` will read this syntax verbatim.

## 4. Reading Text Boxes in python-pptx

While manipulating embedded tables, automated reporting tools often need to contextualize the data by reading adjacent text boxes. In `python-pptx`, text is nested hierarchically: `Shape` $\rightarrow$ `TextFrame` $\rightarrow$ `Paragraph` $\rightarrow$ `Run` [cite: 13]. 

Not all shapes contain text. `GraphicFrame` objects (like our embedded Excel files) do not. To safely extract text, query the `has_text_frame` property [cite: 14].

```python
for shape in slide.shapes:
    if shape.has_text_frame:
        # Direct access to all text
        full_text = shape.text
        print(f"Text Box Content: {full_text}")
        
        # Granular access for formatting preservation
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                print(f"Run text: {run.text}, Bold: {run.font.bold}")
```
As of `python-pptx` version 0.6.18, line breaks (soft carriage returns) are correctly encoded as vertical tabs (ASCII 11 / `\x0B`), matching PowerPoint's internal copy/paste behavior, which allows them to be programmatically distinguished from hard paragraph boundaries [cite: 14, 15].

## 5. Modifying Specific Cells in the Embedded Excel while Preserving Formulas

When a targeted modification is executed, you simply assign a new value to the desired cell. Because the workbook was loaded with `data_only=False`, any cells containing formulas (e.g., `=A1*1.2`) will remain entirely untouched [cite: 10, 16]. 

```python
# Modifying a static value cell
ws['B2'].value = 45000.50

# Verifying a formula cell is intact
print(ws['C2'].value) # Output remains: =B2*0.10
```

### 5.1 Formula Preservation Caveat
A critical edge case in `openpyxl` revolves around how it saves workbooks. Excel files cache the computed results of formulas. When `openpyxl` saves a workbook, it strips these cached values because it does not have a calculation engine to update them [cite: 16]. 

Consequently, when the `.pptx` is later opened by the user and the user double-clicks the OLE object to edit it, Excel will open and re-calculate the formulas automatically. However, before Excel forces a recalculation, the formula cells might temporarily display zero, `#VALUE!`, or a blank, depending on the client application viewing the underlying XML.

To save the modified workbook back to a binary stream:
```python
new_excel_stream = io.BytesIO()
# Saving back to the byte stream. Openpyxl handles the ZIP packaging internally.
wb.save(new_excel_stream)
modified_excel_bytes = new_excel_stream.getvalue()
```

## 6. Writing the Modified xlsx Back into the pptx File

This phase represents the most technically rigorous aspect of the operation. We must inject `modified_excel_bytes` back into the OPC container. Two methods exist, each with unique architectural implications.

### 6.1 Approach A: Internal API (Replacing Part Blob)
The `python-pptx` package reads all parts into memory. As deduced from internal source code handling image replacements, `part._blob` serves as the authoritative binary store before the package is serialized back to disk [cite: 3]. By modifying the `_blob` attribute of the `EmbeddedPackagePart`, we instruct `python-pptx` to write our new bytes when `prs.save()` is called.

```python
# Step 1: Find the OLE object relationship
for shape in slide.shapes:
    if shape.shape_type == MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT:
        ole_obj_xml = shape._element.xpath('.//p:oleObj')
        r_id = ole_obj_xml.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        
        # Step 2: Access the underlying OPC part
        target_part = slide.part.related_parts[r_id]
        
        # Step 3: Overwrite the blob with our modified openpyxl bytes
        target_part._blob = modified_excel_bytes

# Step 4: Save the presentation
prs.save('modified_output_api.pptx')
```
*Benefits:* Preserves all surrounding XML context, relationship IDs, and `[Content_Types].xml` integrity automatically.

### 6.2 Approach B: The ZipFile Rebuild Strategy
While the internal API approach is elegant, the undocumented `_blob` property can be subject to regression in future versions. The universally robust fallback is to manipulate the `.pptx` as a raw ZIP archive, creating a new archive and copying all contents except the specific OLE part, which is substituted with our new payload.

```python
import zipfile

def replace_part_in_zip(original_pptx, new_pptx, target_part_path, new_bytes):
    with zipfile.ZipFile(original_pptx, 'r') as zip_read:
        with zipfile.ZipFile(new_pptx, 'w', zipfile.ZIP_DEFLATED) as zip_write:
            for item in zip_read.infolist():
                if item.filename == target_part_path:
                    # Write our modified Excel bytes instead of the original
                    zip_write.writestr(item, new_bytes)
                else:
                    # Copy existing parts unmodified
                    zip_write.writestr(item, zip_read.read(item.filename))

# Example usage (assuming we parsed the .rels to find target_part_path)
target_path = 'ppt/embeddings/Microsoft_Excel_Worksheet1.xlsx'
replace_part_in_zip('sample.pptx', 'modified_output_zip.pptx', target_path, modified_excel_bytes)
```
*Note on `[Content_Types].xml`:* Because we are replacing an *existing* file with the exact same extension and path, no modification to `[Content_Types].xml` is required. The pre-existing mapping for `.xlsx` or the explicit override for that part name remains perfectly valid.

## 7. Updating the Cached/Displayed Table in the Slide

When PowerPoint renders an embedded Excel object, it does not invoke Excel natively during slideshow mode or standard viewing. Instead, it relies on a cached preview image, typically generated by the OLE server (Excel) when the object was last saved [cite: 6]. This preview is saved as a Windows Metafile (`.emf` or `.wmf`) in the `ppt/media/` directory [cite: 6].

Because `openpyxl` only modifies the XML of the `.xlsx` file, the `.emf` preview remains unchanged. If a user opens the resulting `.pptx`, they will see the *old* data until they double-click the object to activate Excel, at which point Excel recalculates the formulas and forces PowerPoint to update the EMF preview [cite: 6].

### 7.1 Programmatic Refresh Using Headless LibreOffice
Refreshing OLE objects without user intervention is notoriously difficult because `python-pptx` cannot interact with OLE rendering servers natively [cite: 6]. While Windows environments can use `win32com` to open PowerPoint and simulate an update, cross-platform environments often look to LibreOffice.

LibreOffice provides a headless mode (`libreoffice --headless`) for automation [cite: 17]. However, forcing an update of OLE caches and saving back to a `.pptx` format via purely command-line arguments is inherently limited. LibreOffice handles PDF conversion well, but OLE updating usually requires a macro [cite: 18]. 

To attempt a headless update of the presentation, the `--update-ole` flag can be passed via `unoconv` or LibreOffice, though its effectiveness on PPTX files varies:

```bash
# Attempt to convert or refresh via LibreOffice headless
# Note: This is an OS-level call, often used to export to PDF where the OLE *might* be refreshed.
libreoffice --headless --invisible --convert-to pdf --outdir /tmp modified_output.pptx
```
*Warning*: Research demonstrates that LibreOffice's headless conversion sometimes fails to execute the "live" OLE content updates during rendering [cite: 18, 19]. The cached preview (EMF) is often prioritized to avoid macro security risks and calculation overhead. Therefore, if pixel-perfect headless rendering of the *updated* table is required, developers often resort to extracting the Excel data, generating a new table/image via Python (e.g., `matplotlib` or `pandas` styling), and replacing the EMF image blob (`ppt/media/image1.emf`) directly using the same techniques described in Section 6 [cite: 13].

## 8. Common Pitfalls and Edge Cases

### 8.1 API Constraints on OLE Objects
`python-pptx` natively lacks direct support for editing the *contents* of OLE objects. While it allows reading the byte blob and identifying the object, the actual tabular formatting and data structures are heavily walled off. "If you want to work with an embedded Excel range you'd be on your own... mostly complicated by having to reverse-engineer the embedded MS Office object XML semantics" [cite: 2]. Modifying the archive via `zipfile` or the undocumented `_blob` is mandatory [cite: 3].

### 8.2 openpyxl Handling of Advanced Formulas
When working with `openpyxl`, shared formulas (where Excel applies a single formula definition across a range of cells) and dynamic array formulas (introduced in recent Office 365 updates) can occasionally degrade into single-cell evaluations if not handled carefully. Furthermore, as explicitly warned in `openpyxl` documentation, the library does not parse all possible elements of an Excel file. Consequently, if the embedded Excel contains embedded images or specialized shapes of its own, these may be lost when `wb.save()` is called [cite: 11, 12].

### 8.3 Relationship ID Consistency
If utilizing the zipfile approach and attempting to *rename* the embedded part (which is unnecessary but sometimes attempted), the `rId` in the slide XML and the target path in `ppt/slides/_rels/slideX.xml.rels` must be updated synchronously. Failure to maintain referential integrity results in PowerPoint rejecting the file as corrupted [cite: 4].

### 8.4 Zipfile Encoding and Binary Handling
When reading/writing from `zipfile`, always operate in binary mode (by using byte streams like `io.BytesIO()`) and ensure that the compression type matches OPC standards (`ZIP_DEFLATED`). Mismatched encodings during text/binary conversions will irrevocably corrupt the binary XML signatures of OpenXML documents.

## 9. Complete Working Code Pattern

The following code synthesizes all previously discussed mechanisms into a reusable, end-to-end Python script. It relies strictly on `python-pptx` and `openpyxl`, executing the modification via the robust internal `_blob` replacement method.

```python
import io
import os
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from openpyxl import load_workbook

def modify_embedded_excel_in_pptx(input_pptx_path, output_pptx_path, cell_coordinate, new_value):
    """
    Finds the first embedded Excel OLE object in a PowerPoint presentation,
    modifies a specific cell, preserves formulas, and saves the updated .pptx.
    """
    
    print(f"Opening presentation: {input_pptx_path}")
    prs = Presentation(input_pptx_path)
    
    excel_part_found = False
    
    # 1. Iterate over slides and shapes
    for slide_idx, slide in enumerate(prs.slides):
        for shape_idx, shape in enumerate(slide.shapes):
            
            # 2. Identify the OLE Embedded Object
            if shape.shape_type == MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT:
                prog_id = shape.ole_format.prog_id
                
                # Verify it is an Excel workbook
                if 'Excel' in prog_id:
                    print(f"Found embedded Excel object on slide {slide_idx+1}")
                    
                    # 3. Extract the relationship ID via low-level XML DOM
                    try:
                        ole_obj_xml = shape._element.xpath('.//p:oleObj')
                        r_id = ole_obj_xml.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    except IndexError:
                        print("Warning: Malformed OLE object XML. Skipping.")
                        continue
                    
                    # 4. Access the embedded part using python-pptx relationships
                    target_part = slide.part.related_parts[r_id]
                    excel_blob = target_part._blob
                    print(f"Extracted excel payload: {len(excel_blob)} bytes.")
                    
                    # 5. Read with openpyxl (preserving formulas with data_only=False)
                    excel_stream = io.BytesIO(excel_blob)
                    wb = load_workbook(excel_stream, data_only=False)
                    ws = wb.active
                    
                    original_val = ws[cell_coordinate].value
                    print(f"Original value at {cell_coordinate}: {original_val}")
                    
                    # 6. Modify the specific cell
                    ws[cell_coordinate].value = new_value
                    print(f"New value set at {cell_coordinate}: {new_value}")
                    
                    # 7. Save modified excel back to a byte stream
                    out_stream = io.BytesIO()
                    wb.save(out_stream)
                    modified_excel_blob = out_stream.getvalue()
                    
                    # 8. Write back the blob to the pptx part
                    target_part._blob = modified_excel_blob
                    excel_part_found = True
                    print("Overwritten part blob with modified Excel data.")
                    
                    # For this example, we break after updating the first found Excel file
                    break 
        if excel_part_found:
            break
            
    if not excel_part_found:
        print("No embedded Excel objects found in the presentation.")
        return

    # 9. Save the modified presentation
    prs.save(output_pptx_path)
    print(f"Successfully saved updated presentation to: {output_pptx_path}")
    print("\nNote: The visual preview (EMF) in PowerPoint may not reflect the new data "
          "until the user double-clicks the OLE object to refresh the cache.")

# Execution entry point
if __name__ == "__main__":
    # Ensure you have a 'template.pptx' containing an embedded Excel object
    INPUT_FILE = "template.pptx"
    OUTPUT_FILE = "updated_template.pptx"
    
    if os.path.exists(INPUT_FILE):
        # Update cell B2 to the integer 9999
        modify_embedded_excel_in_pptx(INPUT_FILE, OUTPUT_FILE, "B2", 9999)
    else:
        print(f"Please provide an input file named {INPUT_FILE}")
```

### Conclusion
By leveraging the combined architectural strengths of OpenXML, `python-pptx`, and `openpyxl`, developers can execute highly sophisticated data injection routines directly into embedded `OLE` elements [cite: 6, 11]. While `python-pptx` intentionally limits its high-level API to avoid the liabilities of reverse-engineering OLE semantics [cite: 2], accessing the `_blob` attribute or executing deep `zipfile` reconstruction provides an immensely capable workaround. Recognizing the limitations surrounding dynamic cache regeneration is essential for properly architecting reporting automation workflows.

**Sources:**
1. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESbDWm1HETgDszF3sRZxQRaYmBXQOQwBjz4Q6LnuQHxsN-RorSVRa3XJKBcFXq6JQxj3Yg2djeETWO7waKVtP_6ivIj_IcO34Wd2LLR8hHIcKWZ_9so2r52XNvAqcmhYVUAmgxx4C3GLzA_Tdd9nRzcYC2u7yAjCTouIuMlxxVm9r--SNbUjvsPjQkMLoVH9ulVcbRzTIN3cDT)
2. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF25ccPOC2X9DTL-oDxucsYqnIxWxFhGrL35Y2A6pIKGV55UXWbSF--jdNg-Oq4PUiwmmoCBtgmi4VHVWULhxMEAubkjIntM--dxpy_Oa4fESFjO1rwtDEYzmkHd9QB10sSRzRVHL1KADOUEiZs_C4v9rfgM3GP5-s2zJB6qkGBhDD-S_0Wa4gUZpfDNyeWHRHJ1DJZs8VsYCg9vEHU-sKQHaxAAdHq6WbiSn2CfRoYIQ==)
3. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFBXUWh-5hJ1YpyHC7e8pf0kThIE_LgUOj3hWCMFCmcS5Nhi6vQuG8Z5dZ2e7NzmY_49Me-ze_3RHRtYBFEe6Hm-amor_iTyMXE2TmVRQsyQ4LJrPF36BVpmwJq0N2241PBUgPKWLHDo9bHMuNZh-XKkbFmidFN_mYfasi8eX5jf1Zvuh_oyZBfQVp7fadKGwArOYpH4aoX)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEeho9h4xCfS4DnEQrQLzgtVCoKPfdgiJTGO93P5Tr_9H84p2l9LhIRpouLV5OAHz-4BE2UvYqb9cjOTxGLx8gHMv33SQwe7RLP-IrBuzafRkFcZhutxJDecOnOdnnca9st5rejcnU=)
5. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGzO8s9DlgvBq48d3KoetqCBuzhRI3-KB0Jmku4bgwihtgvegPI864M9bfROc_fS7uR5yfGEsxMLIssSKJDOo79MF3ozAJVdimKtyV26CcgsigQSVWUFATIQWUdj13gqQOi_2s7uSZYQCxZH5ApTKwAKZQ=)
6. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8qk7Y5Yguy7LVVoSnwzvgHz9qDCvEalax4RIFWKAq4lc-jB1cwNhn6Hms91c8Yp3lBPIlvYUyO3B-VZ_5Ts_9xCXLg_bujX6g6L4_pDePdoaCo7-0aYEU7hYQSfwdKhDvBqb6NGJ3ooeF0vlpR0gyDEzvMKLOI1lDI4PFsfeWn6QChw==)
7. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFR50sS6c5uXZG8qOgG1tlmGhl9RkID7xw1KyeG-DW-nMCNuG0PeQx1w431dHxrHk3E98MGczQaVFLtnB9H13wFkfUJu3leZ_YWJW05CEGNAv3rwBvqlJ7mnEoXQvX0MZdQLFzK8nV8S-JHhHNLdBXUrDW7sKo0--I=)
8. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEklcD55JUmmAArkA-RaWyoRqWRMgfb8Szy3mb3T0xR58m_Mm1kfTZmgFPLKpnr42U8NgA4RMKvCA1Xd7MLOhL5XJgQteAeTY1_rTZkfWw6QuEpUs2eFTGNSn_KJCUwBgCr6dv1NErmSBKKH4S3YbOJU7fBi9jxx4-8noTZrRBOyPNEzAth1GRAYasIYzSwFESUStCh8BhH8uMoHg==)
9. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEuZK1O9Hz2AUs8Luz0uRfr2lfCFDltnWrs6o-g_3AfNGJZAqwVxosWgEpb4yX13VEwCsp-UVm8PNP7OMcAXQmgneqKdLAoie6mQzrvMTv4B3GCcV45gX1JwlZL7d_v7vqd9dVrKjaD0lUXtJSrsJqifpsD1geEIpnypoh1yKkzCFyIWS8qZ88MovzB8JChuOHTqpzm6WQ5)
10. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHS5mHhBrvZZqaOC74Jwb1vKrd_fbx1LjH_Y-F9F1AS9MnagqGGCLufHW822vSaGYtJUk_TMWGiQH_mW2wZPR1B7miYwwsxQ4MXrL_AN4iBcfS0ZGtwqCMU1gkxaHiG9VbL2v2KcmSgJEvB3o99XoraJGY3aYHSz24hxqBnTbuFuaufWwZMMeQGBpipTct1B9AqQOzS5qPcDX7UJWE5c9aJuETbPSt3U_CJi1UFnFtpSXQ=)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFntrp5kY-YvSr6iAumeWWp1kEIfVCDcQvssIfHTmOLGyxHJzkP5FtqwLeM4utvpLH0TLSWYRtEBzj-iQDOJVrDnRBh9Isi9Q8tw67JjSxd9sZvUEPWFXSEVGpogqvgUY1x0fvqxG0LZrwb)
12. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNhSL6EhfOSXj8Z2gG3qEkkgvpAz3QOcnBF7N28sH90VwiU3oC_6eT2JAzfzfWfXODBI20WQ5IxSaNAv1cIswT6xXE2GaepP45HP5wXfwXNN_qAwKR_lQfCpTW8qUOFgGnf7XUOobn)
13. [softkraft.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEfTytYbfelhgukk8F4yXU9-CoXGa3cDXHZ_zt3vs7Or84alq8d-0-vHgwQtZzO5eTfG0Eu-1LHUp28w_W7epGku3YUr-30dhjmBI4yfgVhBdqNAyOOXkoVl_Hke61VuXK91RKt3_SA8sHVxk=)
14. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEai9l7MJnsHW8J2ZTjKHLTDTSYnV-S0CpRLvJoKKz1z1gWigqMBA2Z7QfjpW5e80Ytvz8OlPdFqm4yzfzbc22OTrVn9g-0MrqaxfHMD1znXyDrJJhv9c1IEa0ihzPM)
15. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7ucmQtZ8ov3puKsKofVxhlt5vrZqWGC6CfhozlxpYcO-wvCxtCPqm9lh6cR1g0KQkCnvnoFhX3Gv-9AHBkK-Dv6RjrfXgsXmIMzm21go5PDbkvV6ypsgiYQl42Iv1NCR7cQ==)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEaMMLfdu4AUaS12GnygHpoVOKb9oHtGeRrluoCx0qRlvveYJtJZzGO5IPWSQfQs1lHnYy11o3zwQ3wmGgC-2vxUHPN9EH02zfqq3eZlsXUU96HcEUMfWysIdOpVBaFBSipqljg0-JjoA0xP6_tKI82YhVLZDMX_87EAGAJvQlNDwZVPPHwSiymoenF0QCjCPmf-w==)
17. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHUAxF6PC7e34Gq_fhrWbQRnMlEH1-q_X-qp0-ZzJ3Kb1RaapLgJrNjRmP6mcPOAVumQo-xsP3CQkk9zuet29axOI1TjOqDdRr4oE4QdYz5jo-Glw23tqY0QXwONOgMy7cxw==)
18. [askubuntu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAjgeatCfCi1JASSCAwdH2vGOKnN5d9p1B8IlS-CU8u2ad35gDqc5zHXoht8d9CWcB0JzMFFIkDqchP88e5G6IdeP4xoDvLKsGFONkLchkviKhNesFzv8stXgQ4dxj_2okFqZVl4958ZhQQT6zP6vocfonRdUClGKJxOOaZfE9aRJs4jQAKjVz_jf2rJYekMSnT40krnK8)
19. [aspose.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEwrHYQPHnmGc4nvcEQmcz4YZ4GGLw6eK0J3sOtF1MvwvppeK1eo6vEhAN_xwHWEQMHMVVeQGcuegwrMV76Z1z5QNVZKManjSIIw_FJ8AH23FrPpoB4p1E0zhj93MZ3EE6rAy9TndrcJRV9Vg==)
