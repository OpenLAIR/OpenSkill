# Domain Reference for evo-pptx-reference-slide

**Responsibility**: New slide XML creation, presentation.xml and relationship file updates, title placeholder population, body text with auto-numbered bullets via a:buAutoNum elements, and deduplication of paper titles.

**Key functions to implement**: create_reference_slide_xml, add_slide_to_presentation, create_autonumbered_paragraphs, update_content_types, update_presentation_rels, deduplicate_titles

---

## 4. Creating Slides and the Numbered List Dilemma


Appending a slide to the presentation requires indexing into the presentation's `slide_layouts` collection. Usually, `slide_layouts` is the Title layout, and `slide_layouts[cite: 9]` is the Title and Content layout.

```python
layout = prs.slide_layouts[cite: 9] # Typical "Title and Body" layout
slide = prs.slides.add_slide(layout)

## 5. Working with `lxml` to Manipulate OOXML Directly


As demonstrated above, `python-pptx` permits an escape hatch into raw XML manipulation. The underlying engine mapping the objects to the XML tree is called `xmlchemy` [cite: 20]. 

When manipulating these raw XML nodes (`_Element` instances from `lxml.etree`), we must strictly adhere to the OpenXML namespace constraints.

## 6. Important Pitfalls: The Docker/Dependency Constraint


**Critical Clarification:** `python-pptx` **cannot** work strictly with `lxml` and `defusedxml` if the `python-pptx` package itself is uninstalled. While `python-pptx` relies on `lxml` as its XML parsing engine, it is not a part of the standard library and explicitly requires `Pillow` and `XlsxWriter` as mandatory dependencies [cite: 3, 4, 24]. 

If you are operating inside a locked-down Dockerfile that only possesses `lxml`, `defusedxml`, and `six`, `import pptx` will fail with a `ModuleNotFoundError` [cite: 25]. 

Under these rigid constraints, you must construct a zero-dependency script using Python's native `zipfile` module alongside `lxml` to decompress the `.pptx`, alter the specific slide's XML file, and repackage it.