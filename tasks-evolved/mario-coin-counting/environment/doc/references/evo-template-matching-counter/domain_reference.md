# Domain Reference for evo-template-matching-counter

**Responsibility**: Loading grayscale template images, performing template matching against each keyframe, applying NMS to deduplicate detections, counting objects per frame per category, and writing the final CSV with columns frame_id/coins/enemies/turtles.

**Key functions to implement**: load_template, count_objects_in_frame, non_max_suppression, generate_results_csv

---

## 3. Template Matching for Object Counting (`cv2.matchTemplate`)



### 3.1 The `cv2.matchTemplate` API


Template matching is an operation wherein a small template image (the object) is mathematically convolved across a larger source image (the frame). At each coordinate, a similarity metric is computed.

The complete API signature is:
```python
result_matrix = cv2.matchTemplate(image, template, method)
```

### 3.2 Critical Thresholding and Multiple Occurrences


When using a normalized method like `TM_CCOEFF_NORMED`, the `result_matrix` contains values strictly ranging from `-1.0` (perfect mismatch) to `1.0` (perfect match) [cite: 14, 15].

To count **multiple occurrences** (e.g., detecting 10 coins on the screen), we cannot use `cv2.minMaxLoc()`, as it only returns the single highest match [cite: 2, 13]. Instead, we apply NumPy boolean filtering to find all coordinates exceeding a confidence threshold [cite: 2, 6].

**Critical Threshold Values**: For rigid 2D pixel art like *Super Mario*, a threshold of **`0.80` to `0.95`** is optimal [cite: 1, 2]. Below `0.70`, the algorithm will trigger false positives against visually noisy background tiles. Above `0.95`, compression artifacts (if the video is MP4/H.264 encoded) will cause true positives to be missed.

```python
import numpy as np

threshold = 0.85

### 3.3 Non-Maximum Suppression (NMS)


Because the template matching algorithm evaluates *every single pixel shift*, a high-confidence object will trigger positive matches not just perfectly on the object, but also 1 pixel to the left, 1 pixel to the right, etc [cite: 16]. This "halo" effect causes a single coin to register as 15 overlapping detections [cite: 16].

To extract accurate counts, **Non-Maximum Suppression (NMS)** is mandatory [cite: 2, 7]. NMS evaluates all bounding boxes, compares their spatial overlap, and collapses boxes that overlap by a defined percentage (Intersection over Union - IoU) into a single box [cite: 3]. 

For 2D games, a spatial clustering approach based on distance is often just as effective and computationally simpler. If two detection coordinates are within a distance equal to half the template's width, they correspond to the same object [cite: 3].

### 3.4 Multi-Scale and Channel Compatibility


**Multi-Scale Matching**: If the game footage undergoes upscaling or downscaling (e.g., playing at 1080p vs 720p), the static template will not match. Template matching is strictly scale-invariant [cite: 4]. To handle this, an image pyramid must be utilized: the template (or the input frame) is repeatedly resized (e.g., in 10% increments) using `cv2.resize()`, and `matchTemplate` is executed at every scale. The scale yielding the highest correlation coefficient is retained [cite: 6].

**Grayscale to Grayscale Matching**: Both the source frame and the template **must** possess the exact same number of channels and data types (typically `uint8`) [cite: 6]. Attempting to match a 1-channel grayscale template against a 3-channel BGR image will result in a fatal `cv2.error`. Matching grayscale-to-grayscale works perfectly and is the recommended paradigm [cite: 4, 7].

---

### 4.1 Array Sizing and Output Dimensions

A frequent source of `cv2.error` crashes occurs when the template matrix is spatially larger than the input image matrix in either the width or height dimension. 

When `cv2.matchTemplate` executes, it returns a 2D result array. If the input image dimensions are \( W \times H \), and the template dimensions are \( w \times h \), the dimensions of the output result matrix are strictly:
**Width**: \( W - w + 1 \)
**Height**: \( H - h + 1 \) [cite: 2, 13]

Because the sliding window cannot traverse past the bounds of the image, the output matrix is slightly smaller than the input image [cite: 13].

### 4.2 The `np.where` Coordinate System

As previously noted, multi-dimensional array indices in Python (NumPy) are structured as `[row, column]`. Therefore, `np.where(res >= thresh)` returns `(y_coords, x_coords)`. However, OpenCV drawing functions (`cv2.rectangle`, `cv2.putText`) mandate Cartesian geometry coordinates `(x, y)` [cite: 2]. Failing to invert these coordinates will cause bounding boxes to be transposed, frequently resulting in `IndexError` exceptions.

## 5. Pandas CSV Output


Once video frames have been parsed and objects spatially deduplicated and counted, serializing the time-series data is accomplished through the Pandas library.

Pandas DataFrames provide exceptional mechanisms for formatting structured output [cite: 19, 20].

```python
import pandas as pd