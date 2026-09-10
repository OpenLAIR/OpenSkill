To verify the correctness of the filled California SC-100 form, you can implement a surrogate test using `pypdf` to inspect the PDF's internal AcroForm dictionary. Since you cannot rely on the skill's execution, the following verification anchors and invariants provide a robust basis for your `pytest` assertions.

### 1. Independently Computable Reference Values
The following values are derived directly from the provided case description and must be present in the corresponding PDF fields.

| Field Category | Expected Value (Data) |
| :--- | :--- |
| **Plaintiff Name** | "Joyce He" |
| **Plaintiff Address** | "655 S Fair Oaks Ave, Sunnyvale, CA 94086" |
| **Plaintiff Phone** | "4125886066" |
| **Defendant Name** | "Zhi Chen" |
| **Defendant Address** | "299 W Washington Ave, Sunnyvale, CA 94086" |
| **Claim Amount** | "1500" |
| **Venue Justification** | Must have the checkbox for "Where the defendant lives" selected. |

### 2. Dataset-Level Statistical Invariants
Your test suite should enforce these structural and logical constraints on the output PDF:
*   **Completeness Constraint:** The output PDF must contain non-empty values for all mandatory fields identified in the case description (Plaintiff/Defendant contact info, Claim Amount).
*   **Venue Invariant:** The venue section of the SC-100 requires selecting a checkbox. The test must verify that the specific field corresponding to "defendant lives or does business" has an `/AS` (Appearance State) value indicating it is "On" (typically `/Yes` or a specific state name found in the PDF's `/AP` dictionary).
*   **Date Format Invariant:** Any date fields (e.g., filing date) must strictly follow the `YYYY-MM-DD` format as specified in the instructions.

### 3. Cross-Validation Approach
You can independently verify the field mapping and values using a simple `pypdf` script within your test suite. This acts as a "ground-truth" checker that does not depend on the skill's logic.

```python
import pytest
from pypdf import PdfReader

def test_sc100_field_values():
    reader = PdfReader("/root/sc100-filled.pdf")
    fields = reader.get_fields()
    
    # Example assertion for a text field
    # Replace 'PlaintiffNameField' with the actual key discovered in the PDF
    assert fields['PlaintiffNameField']['/V'] == "Joyce He"
    
    # Example assertion for a checkbox
    # Checkboxes often use '/AS' to indicate state
    assert fields['VenueCheckboxField']['/AS'] == '/Yes'
```

### 4. Benchmarks and Reference Implementation
*   **Judicial Council of California (Official Forms):** The canonical source for the SC-100 structure is the [California Courts Forms website](https://www.courts.ca.gov/forms.htm).
*   **Field Taxonomy:** The SC-100 is known to contain approximately 140 fields. A reliable way to identify the correct keys is to use `reader.get_fields()` on the blank PDF provided in the environment to generate a mapping dictionary before running the filling process.
*   **Reference Logic:** The requirement to sue where the defendant lives is based on **California Code of Civil Procedure § 395(a)**, which is the authoritative basis for venue selection in small claims cases. Your test can assert that the venue selection logic aligns with this legal requirement.