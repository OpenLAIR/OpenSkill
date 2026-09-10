# Domain Reference for evo-pptx-embedded-excel-updater

**Responsibility**: End-to-end handling of embedded Excel OLE objects in PPTX files: identifying OLE shapes and text boxes on slides, extracting embedded xlsx blobs via python-pptx relationship IDs, reading/modifying Excel data with openpyxl while preserving formula cells, writing modified blobs back into the PPTX package, and parsing text box content for updated values.

**Key functions to implement**: find_embedded_ole_excel_shapes, extract_excel_blob_from_ole_shape, read_text_boxes_from_slide, parse_exchange_rate_from_text, load_excel_from_blob, update_excel_cell_preserve_formulas, save_excel_to_blob, replace_ole_blob_in_pptx, find_cell_by_currency_pair

---

## 1. Accessing Embedded Excel Objects in python-pptx



## 2. Extracting the Embedded xlsx Binary from the pptx Package


Extraction of the underlying `.xlsx` file can be achieved through two primary paradigms: utilizing the internal relationship mappings of `python-pptx` or employing Python's standard `zipfile` library to interact directly with the OPC container.

## 3. Reading the Extracted xlsx with openpyxl


With the `.xlsx` bytes extracted, we transition to data manipulation using `openpyxl` (version 3.1.5). `openpyxl` is robust but requires specific parameters to handle formulas correctly.

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

## 6. Writing the Modified xlsx Back into the pptx File


This phase represents the most technically rigorous aspect of the operation. We must inject `modified_excel_bytes` back into the OPC container. Two methods exist, each with unique architectural implications.

## 8. Common Pitfalls and Edge Cases



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