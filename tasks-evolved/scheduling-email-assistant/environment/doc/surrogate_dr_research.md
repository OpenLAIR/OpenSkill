To verify the scheduling agent's output, you can implement a `pytest` suite that validates the generated email content, date/time formatting, and the structure of the `results.json` output.

### 1. Independently Computable Reference Values
The following table provides the expected formatting for the meeting requests based on the provided instructions.

| Input Request | Date | Time Range | Duration | Expected Date Format | Expected Time Format |
| :--- | :--- | :--- | :--- | :--- | :--- |
| John Smith | Jan 8, 2026 | 10:00am-2:00pm | 1 hr | `Thursday, January 08, 2026` | `10:00 AM - 11:00 AM` |
| Robert Wilson | Jan 8-9, 2026 | 11:00am-3:00pm | 1.5 hr | `Wednesday, January 08, 2026`* | `11:00 AM - 12:30 PM` |
| Amanda Lee | Jan 6-7, 2026 | 9:30am-11:30am | 0.75 hr | `Tuesday, January 06, 2026`* | `09:30 AM - 10:15 AM` |

*\*Note: The agent is instructed to select the "earliest time slots," so the verification logic should assert that the date chosen is the earliest available within the requested range.*

### 2. Dataset-Level Statistical Invariants
Your `pytest` should enforce these invariants on the output:
*   **Completeness**: The `results.json` file must contain exactly 3 entries (one for each input email).
*   **Format Strictness**:
    *   **Date**: Must match regex `^[A-Z][a-z]+, [A-Z][a-z]+ \d{2}, \d{4}$`.
    *   **Time**: Must match regex `^\d{2}:\d{2} [AP]M - \d{2}:\d{2} [AP]M$`.
*   **Logical Consistency**: The `Duration` in the email body must match the duration requested in the input JSON.
*   **Chronological Order**: If multiple slots are available, the selected slot must be the earliest one (e.g., for Amanda Lee, Jan 6th must be prioritized over Jan 7th).

### 3. Cross-Validation Approaches
You can use Python's `datetime` module to independently verify the agent's calculations:

```python
import pytest
from datetime import datetime, timedelta

def test_date_formatting():
    # Independent verification of the required format
    dt = datetime(2026, 1, 8)
    formatted = dt.strftime("%A, %B %d, %Y")
    assert formatted == "Thursday, January 08, 2026"

def test_time_formatting():
    # Independent verification of the required time format
    start = datetime(2026, 1, 8, 10, 0)
    end = start + timedelta(hours=1)
    formatted = f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
    assert formatted == "10:00 AM - 11:00 AM"
```

### 4. Benchmarks and Reference Implementation
*   **RFC 2822 Compliance**: Ensure the generated email headers include `Message-ID` and `In-Reply-To` (referencing the original email's ID) to maintain thread integrity.
*   **RFC 3339 Compliance**: When querying the Google Calendar API, ensure timestamps are strictly formatted as `YYYY-MM-DDTHH:MM:SSZ`. Any deviation (e.g., missing 'Z' or incorrect separators) will result in a `400 Bad Request` error.
*   **Verification Oracle**: Since you cannot access the live calendar, your test should mock the `google-calendar-skill` response to return a predefined "busy" list, then assert that the agent's proposed time does not overlap with those busy slots.