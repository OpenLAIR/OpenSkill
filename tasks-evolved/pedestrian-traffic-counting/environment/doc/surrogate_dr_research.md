To verify the pedestrian counting skill without access to ground-truth labels, you must rely on **structural invariants** (properties that must hold true regardless of the specific video content) and **cross-validation** (using alternative, simpler, or different-modality methods to check for consistency).

### 1. Dataset-Level Statistical Invariants
These invariants can be implemented as `pytest` assertions to ensure the output file adheres to the required format and logical constraints.

*   **Format Integrity:**
    *   **File Existence:** Assert that `/app/video/count.xlsx` exists after the script runs.
    *   **Schema Consistency:** Using `pandas`, assert that the DataFrame has exactly two columns: `['filename', 'number']`.
    *   **Completeness:** Assert that the number of rows in the Excel file matches the number of `.mp4` files in `/app/video`.
    *   **Data Type:** Assert that the `number` column contains only non-negative integers (`>= 0`).
*   **Logical Bounds:**
    *   **Non-Negativity:** A count of pedestrians cannot be negative. `assert df['number'].min() >= 0`.
    *   **Sanity Upper Bound:** While scene-dependent, you can define a "maximum reasonable density" for your specific surveillance context (e.g., if the street is small, a count > 100 is likely a hallucination). `assert df['number'].max() < MAX_EXPECTED_CAPACITY`.

### 2. Cross-Validation Approaches
Since you cannot rely on a single VLM output, use these methods to verify the result:

*   **Frame-Sampling Consistency (Temporal Stability):**
    *   If the model is accurate, the pedestrian count should not fluctuate wildly between consecutive time segments.
    *   **Method:** Run the counting logic on two different subsets of frames (e.g., frames 0–50 vs. frames 50–100). If the count for a specific pedestrian is "1" in the first half and "0" in the second, the model should ideally track them. If the total count for the video is significantly different from a count performed on a different subset of frames, it indicates a potential tracking failure.
*   **Alternative "Lightweight" Verification:**
    *   Use a simple, non-AI heuristic to provide a "lower bound" or "sanity check." For example, use `cv2` (OpenCV) to perform basic background subtraction (e.g., `cv2.createBackgroundSubtractorMOG2()`).
    *   **Assertion:** If the VLM reports 0 pedestrians but the background subtractor detects significant motion (high pixel-change area), flag the result for manual review.

### 3. Reference Implementation Patterns
You can use standard computer vision benchmarks as a reference for how to structure your verification.

*   **The "Detect-Track-Count" Paradigm:** Most academic benchmarks (e.g., **MOT17**, **CrowdTrack**) rely on the "detect-track-count" pipeline. Your surrogate test should verify that the skill's output is consistent with this logic.
*   **Verification via "Virtual Line" (LOI):** If the surveillance camera is fixed, a common technique is to define a "Line of Interest" (LOI).
    *   **Reference:** Research papers (e.g., *Vision-based Counting of Pedestrians and Cyclists*) often use this to reduce counting errors.
    *   **Test Implementation:** You can hard-code a simple coordinate check in your test: if the VLM output is significantly different from a simple motion-based count of objects crossing a central horizontal line in the frame, the test should fail.

### Summary of Pytest Assertions
```python
import pandas as pd
import pytest
import os

def test_excel_output_integrity():
    df = pd.read_excel('/app/video/count.xlsx')
    
    # 1. Schema checks
    assert list(df.columns) == ['filename', 'number']
    
    # 2. Completeness check
    video_files = [f for f in os.listdir('/app/video') if f.endswith('.mp4')]
    assert len(df) == len(video_files)
    
    # 3. Value constraints
    assert (df['number'] >= 0).all()
    assert (df['number'] % 1 == 0).all() # Must be integers
    
    # 4. Statistical sanity (e.g., no extreme outliers)
    assert df['number'].max() < 500 
```