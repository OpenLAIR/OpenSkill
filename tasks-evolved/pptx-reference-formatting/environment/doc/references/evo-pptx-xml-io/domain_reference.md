# Domain Reference for evo-pptx-xml-io

**Responsibility**: ZIP archive management, XML parsing with proper OOXML namespaces (DrawingML 'a:', PresentationML 'p:'), slide enumeration, and safe repackaging of modified PPTX files.

**Key functions to implement**: open_pptx_archive, parse_slide_xml, get_all_slide_paths, get_presentation_xml, write_pptx_archive, get_namespaces, find_shapes_in_slide

---

## 5. Working with `lxml` to Manipulate OOXML Directly


As demonstrated above, `python-pptx` permits an escape hatch into raw XML manipulation. The underlying engine mapping the objects to the XML tree is called `xmlchemy` [cite: 20]. 

When manipulating these raw XML nodes (`_Element` instances from `lxml.etree`), we must strictly adhere to the OpenXML namespace constraints.

## 6. Important Pitfalls: The Docker/Dependency Constraint


**Critical Clarification:** `python-pptx` **cannot** work strictly with `lxml` and `defusedxml` if the `python-pptx` package itself is uninstalled. While `python-pptx` relies on `lxml` as its XML parsing engine, it is not a part of the standard library and explicitly requires `Pillow` and `XlsxWriter` as mandatory dependencies [cite: 3, 4, 24]. 

If you are operating inside a locked-down Dockerfile that only possesses `lxml`, `defusedxml`, and `six`, `import pptx` will fail with a `ModuleNotFoundError` [cite: 25]. 

Under these rigid constraints, you must construct a zero-dependency script using Python's native `zipfile` module alongside `lxml` to decompress the `.pptx`, alter the specific slide's XML file, and repackage it.