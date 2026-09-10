# Domain Reference for evo-pdf-field-inspector

**Responsibility**: Read and catalog all interactive form fields from a PDF, returning their names, types, flags, appearance states (for checkboxes), and default values.

**Key functions to implement**: enumerate_pdf_fields, get_checkbox_on_states, classify_field_type

---

## 1. The California SC-100 Form (Rev 2024) Architecture and Field Taxonomy


The California Judicial Council periodically updates the SC-100 form. Understanding its structure is critical for programmatic interaction.

### 1.2 Exact PDF Form Field Names

*Limitation Note: While we have comprehensive metadata regarding the structure of the SC-100 form [cite: 4], exact internal AcroForm keys (e.g., `form1.Page1.TextField1`) can vary between localized county versions or specific minor revisions of the Judicial Council PDF. The data provided below represents the canonical logical structure and commonly used string literals.*

To map your data, the SC-100 incorporates roughly 140 interactive fields [cite: 4]. The following table categorizes the standard fillable fields based on their semantic purpose:

| Section | Logical Field Representation | Expected Data Type / Formatting |
| :--- | :--- | :--- |
| **Court Info** | `Court Name`, `Court Street Address`, `Case Number` | Text string. Usually left blank for the clerk [cite: 1]. |
| **Plaintiff 1** | `Plaintiff 1 Name`, `Plaintiff 1 Phone`, `Plaintiff 1 Email` | Text string. Full legal name required [cite: 4]. |
| **Plaintiff 1 Address**| `Plaintiff Street Address`, `Plaintiff City`, `Plaintiff State`, `Plaintiff ZIP Code` | Text string. Address is typically split into distinct fields, not a combined block [cite: 4]. |
| **Plaintiff 2** | `Plaintiff 2 Name`, `Plaintiff 2 Phone`, `Plaintiff 2 Email` | Text string. Used if multiple plaintiffs [cite: 4]. |
| **Defendant 1** | `Defendant 1 Name`, `Defendant 1 Address`, `Def 1 City`, `Def 1 State`, `Def 1 Zip` | Text string. Crucial for process service [cite: 5, 6]. |
| **Claim Info** | `Claim Amount`, `Claim Description`, `Calculation Method` | Text string. Amount formatted as standard numeric (e.g., 5000.00) [cite: 1, 7]. |
| **Dates** | `Date of Incident`, `Date Started`, `Through Date` | Text string. Standard format (MM/DD/YYYY) [cite: 1]. |
| **Venue Reasons** | `Defendant lives in district`, `Property damaged here`, `Contract signed here` | Checkboxes. Represents CCP § 395(b) venue rules [cite: 1, 2]. |
| **Procedural** | `Has filed more than 12 claims`, `Has asked for payment` | Checkboxes / Radio buttons [cite: 1, 6]. |
| **Accessibility** | `MC-410 Disability Request`, `INT-300 Interpreter Request` | Buttons/Links [cite: 4]. |

### 1.3 Programmatic Enumeration of Field Names

Because hardcoding field names is fragile against form updates, the standard architectural pattern is to programmatically extract the keys from the exact PDF template you intend to fill. 

Using `pypdf`, you can enumerate all AcroForm field names and their properties. The following utility script outputs a complete mapping of the SC-100 form:

```python
from pypdf import PdfReader
from pypdf.constants import AnnotationDictionaryAttributes as ADA

def enumerate_sc100_fields(pdf_path: str):
    """
    Reads a PDF and prints out every interactive form field, 
    its internal mapping name, and its structural type.
    """
    try:
        reader = PdfReader(pdf_path)
        fields = reader.get_fields()
        
        if not fields:
            print("No AcroForm fields detected. Form may be XFA or flattened.")
            return

        print(f"{'Field Key (mapping_name)':<45} | {'Type':<15} | {'Default Value'}")
        print("-" * 80)
        
        for key, field in fields.items():
            # field_type can be /Tx (Text), /Btn (Button/Checkbox/Radio), /Ch (Choice)
            f_type = str(field.field_type) if field.field_type else "Unknown"
            
            # The value or default value currently held in the form
            f_val = str(field.value) if field.value else ""
            
            print(f"{key:<45} | {f_type:<15} | {f_val}")
            
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")

## 2. Reading PDF Form Field Names Using `pypdf` (Version 5.1.0)


The `pypdf` library (which recently absorbed and replaced the deprecated `PyPDF2` [cite: 8]) offers a high-level API for reading the AcroForm structure.

### 2.1 The `get_fields()` and `get_form_text_fields()` Methods

The `PdfReader` class provides two primary methods for field extraction:
1. `reader.get_fields()`: Returns a Python dictionary where the keys are the string field names and the values are `pypdf.generic.Field` objects [cite: 9]. This is the most comprehensive method.
2. `reader.get_form_text_fields()`: Returns a simplified dictionary containing only text fields, mapped as `{"field_name": "field_text_content"}` [cite: 10]. This is useful for simple data extraction but inadequate for complex forms with checkboxes.

### 2.2 Distinguishing Between Text, Checkboxes, and Radio Buttons

When you invoke `reader.get_fields()`, the returned `Field` object [cite: 9] contains several read-only properties derived from the PDF standard specification:
* `Field.field_type`: Returns a `NameObject` indicating the type [cite: 9].
  * `'/Tx'`: Text field.
  * `'/Btn'`: Button. This encompasses regular push buttons, checkboxes, and radio buttons.
  * `'/Ch'`: Choice field (Dropdown or List box).
  * `'/Sig'`: Digital Signature field.

To distinguish between a checkbox and a radio button (both of which are `/Btn`), one must examine the `flags` property of the `Field`. The `Field.flags` property corresponds to Table 8.70 of the PDF 1.7 reference [cite: 9]. If the `Radio` bit (bit 16) is set, the button is a radio button; otherwise, it is a checkbox or push button.

### 2.3 Code Example: Comprehensive Field Inspector

The following code demonstrates how to accurately read fields and distinguish their types using `pypdf` version 5.1.0:

```python
from pypdf import PdfReader

def inspect_pdf_fields(pdf_path: str):
    reader = PdfReader(pdf_path)
    fields = reader.get_fields()
    
    if not fields:
        return {}
        
    analysis = {}
    
    for field_name, field_obj in fields.items():
        field_type = field_obj.field_type
        
        # Determine specific widget type
        human_readable_type = "Unknown"
        if field_type == "/Tx":
            human_readable_type = "Text Field"
        elif field_type == "/Ch":
            human_readable_type = "Dropdown/List"
        elif field_type == "/Btn":
            # Check the flags to differentiate Checkbox from Radio Button
            flags = field_obj.flags
            if flags is not None and (flags & (1 << 15)): # Bit 16 (0-indexed 15) is Radio
                human_readable_type = "Radio Button"
            else:
                # To further distinguish Checkbox vs Push Button, check the appearance dict
                # However, for most AcroForms, non-Radio /Btn are Checkboxes
                human_readable_type = "Checkbox"
                
        # Retrieve current values
        current_value = field_obj.value
        default_value = field_obj.default_value
        
        analysis[field_name] = {
            "type": human_readable_type,
            "current_value": current_value,
            "default_value": default_value,
            "mapping_name": field_obj.mapping_name
        }
        
    return analysis
```

---