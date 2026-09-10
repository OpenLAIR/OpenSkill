# OpenCV 4.12 Python Template Matching for Object Counting in Video Frames: Complete API Guide and Working Code Examples

**Key Points**
*   OpenCV's `cv2.matchTemplate` algorithm is highly effective for object detection in 2D spatial planes, particularly for rigid, non-deformable assets such as video game sprites [cite: 1].
*   The Normalized Correlation Coefficient method (`cv2.TM_CCOEFF_NORMED`) is mathematically and empirically the most robust technique for template matching, with optimal confidence thresholds generally residing between 0.80 and 0.95 [cite: 1, 2].
*   Extracting multiple objects of the same class from a single frame inherently produces overlapping bounding boxes, necessitating Non-Maximum Suppression (NMS) to achieve accurate counting metrics [cite: 2, 3].
*   The `opencv-python` library processes spatial color matrices in Blue-Green-Red (BGR) channel order rather than the standard Red-Green-Blue (RGB), a critical distinction when performing array manipulations [cite: 4].
*   Video frame sampling strategies in continuously scrolling environments (such as *Super Mario* gameplay) often benefit more from uniform temporal sampling rather than pixel-differencing algorithms, due to the constant global motion of the camera [cite: 5].

**Overview**
The problem of automating object detection and counting within video frames requires a synthesis of sequential data extraction, spatial image processing, and structured data serialization. The OpenCV library (version 4.12.0.88) provides an extensive suite of low-level and high-level C++ algorithms, exposed through Python bindings, to achieve these tasks. This report details the theoretical mechanisms and practical implementations of video parsing, color space conversions, and template matching for computer vision analytics.

**Methodology**
This research formalizes a processing pipeline beginning with the decoding of H.264/MP4 streams via the FFmpeg backend, followed by heuristic keyframe extraction. Images are subsequently reduced in dimensionality (converted to grayscale) to optimize the mathematical cross-correlation utilized in template matching [cite: 6, 7]. Detected artifacts are spatially clustered via Non-Maximum Suppression (NMS), and the aggregated analytical data is exported into a tabular schema via Pandas (version 2.3.3) for downstream statistical evaluation.

**Limitations**
While standard template matching is highly performant, it is fundamentally scale- and rotation-invariant [cite: 4]. Deep learning object detectors (e.g., YOLO, SSD) are often required for objects undergoing arbitrary affine transformations, but for 2D orthographic or isometric video games, template matching remains an exceptionally efficient and precise paradigm.

---

## 1. Video Frame Extraction with OpenCV

The foundational step in any video analytics pipeline involves safely and efficiently decoding the multimedia stream and transferring encoded frames into uncompressed multidimensional arrays (tensors) in system memory. 

### 1.1 The `cv2.VideoCapture` API

In OpenCV, video ingestion is managed by the `cv2.VideoCapture` class. This object acts as a bridge between the underlying hardware/software codecs (such as FFmpeg or GStreamer) and the Python environment [cite: 8, 9].

```python
import cv2

# Initialize the VideoCapture object
video_path = "super_mario_gameplay.mp4"
cap = cv2.VideoCapture(video_path)

# Verify if the file was successfully opened
if not cap.isOpened():
    raise IOError(f"Error: Could not open video stream or file at {video_path}")
```

#### Metadata Extraction
Before reading the frame sequence, it is imperative to understand the temporal constraints of the video. The `cap.get()` method queries the backend for specific metadata properties encoded in the video container [cite: 5, 10].

*   `cap.get(cv2.CAP_PROP_FRAME_COUNT)`: Returns the total number of frames in the video file as a float.
*   `cap.get(cv2.CAP_PROP_FPS)`: Returns the frames per second (frame rate) of the video as a float.
*   `cap.get(cv2.CAP_PROP_FRAME_WIDTH)` / `cv2.CAP_PROP_FRAME_HEIGHT`: Returns the spatial dimensions.

#### Frame Iteration
Frames are extracted sequentially using `cap.read()`. This function returns a tuple containing two values:
1.  `ret` (bool): A boolean flag indicating whether the frame was successfully read. If `False`, the end of the video has been reached, or a decoding error occurred.
2.  `frame` (numpy.ndarray): The actual image matrix. If `ret` is `False`, this will be `None`.

### 1.2 Key Frame Extraction Strategies

To optimize storage and computational overhead, it is practically infeasible to process every single frame of a 60 FPS video. "Key frames" are representative frames that capture the essential semantic information of a scene [cite: 5]. 

There are two primary algorithms for extracting keyframes in the context of gameplay analysis:

#### Method A: Uniform Temporal Sampling
For games characterized by continuous background scrolling (like *Super Mario*), the entire screen shifts every few frames. Relying on pixel differences will erroneously flag every frame as a "scene change." Uniform sampling mitigates this by extracting a frame at a fixed mathematical interval (e.g., 1 frame per second).

```python
fps = cap.get(cv2.CAP_PROP_FPS)
frame_interval = int(fps * 1.0) # Extract 1 frame every second
```

#### Method B: Scene Change Detection via Frame Differencing
For environments with distinct structural cuts (e.g., transitioning from a level map to an inventory screen), calculating the Mean Squared Error (MSE) or Mean Absolute Difference between consecutive frames is highly effective [cite: 11].

The algorithm utilizes `cv2.absdiff()` to compute the per-element absolute difference between two arrays:
\[ D(x, y) = | I_{t}(x, y) - I_{t-1}(x, y) | \]

The sum of these differences is evaluated against a pre-defined threshold [cite: 5, 12].

```python
def is_scene_change(prev_frame, curr_frame, threshold=30.0):
    """
    Detects scene changes using grayscale absolute difference.
    """
    # Convert frames to grayscale for faster scalar difference computation
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
    
    # Compute absolute difference
    diff = cv2.absdiff(curr_gray, prev_gray)
    
    # Calculate the mean pixel difference
    mean_diff = np.mean(diff)
    
    return mean_diff > threshold
```

### 1.3 Saving Extracted Frames

Frames isolated as keyframes must be serialized to disk. The `cv2.imwrite()` function is utilized for this purpose, combined with Python's string formatting to ensure sequential naming convention (e.g., `keyframes_001.png`, `keyframes_002.png`) [cite: 10, 12].

```python
frame_index = 1
# Save using zero-padded format for clean lexical sorting
filename = f"keyframes_{frame_index:03d}.png"

# Save as PNG (lossless compression)
# Parameter cv2.IMWRITE_PNG_COMPRESSION ranges from 0 to 9 (higher is smaller size but slower)
cv2.imwrite(filename, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
```

---

## 2. RGB to Grayscale Conversion with OpenCV

### 2.1 The BGR Paradigm

It is a pervasive pitfall in OpenCV development to assume that the library handles color channels in standard Red-Green-Blue (RGB) order. For historical and hardware-related reasons (originating from early Windows bitmap formats), OpenCV natively reads and stores multi-channel color images in **Blue-Green-Red (BGR)** format [cite: 4].

Failure to account for this order when interfacing OpenCV data with other libraries (like Matplotlib or PIL) will result in structurally inverted color channels (e.g., red Mario will appear blue).

### 2.2 Grayscale Transformation

Template matching relies fundamentally on structural gradients and intensity matrices rather than chromatic hues. Processing 3-channel color arrays significantly increases the algorithmic complexity from \( O(N \times M) \) to \( O(3 \times N \times M) \) without a proportional increase in matching fidelity [cite: 6, 7]. Therefore, converting frames and templates to single-channel Grayscale is a standard best practice [cite: 7].

The exact API signature is:
```python
gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
```

The mathematical transformation applied across the tensor is calculated via a weighted sum based on human perceptive luminescence:
\[ Y = 0.299 \cdot R + 0.587 \cdot G + 0.114 \cdot B \]

### 2.3 In-Place Overwrites and `cv2.imread()` Flags

When an image must be converted to grayscale and permanently updated on the filesystem, `cv2.imread()` and `cv2.imwrite()` are utilized in tandem. 

`cv2.imread()` accepts flags dictating how the file is parsed:
*   `cv2.IMREAD_COLOR` (Default, flag value 1): Loads a color image. Any transparency of image will be neglected.
*   `cv2.IMREAD_GRAYSCALE` (flag value 0): Loads image in grayscale mode directly from disk [cite: 6].
*   `cv2.IMREAD_UNCHANGED` (flag value -1): Loads image as such including alpha channel.

To overwrite an image in place directly as grayscale:
```python
filepath = "template_coin.png"
# Read directly as grayscale, skipping the BGR decoding phase
gray_img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)

if gray_img is not None:
    # Overwrite the same file. cv2.imwrite seamlessly handles 2D single-channel arrays
    cv2.imwrite(filepath, gray_img)
else:
    print("Error: Image not found.")
```
**Does `cv2.imwrite()` handle single-channel arrays correctly?** Yes. OpenCV automatically inspects the dimensionality of the `numpy.ndarray`. If `image.ndim == 2`, it writes a single-channel image. If `image.ndim == 3` and `image.shape[cite: 6] == 3`, it writes a BGR image.

---

## 3. Template Matching for Object Counting (`cv2.matchTemplate`)

### 3.1 The `cv2.matchTemplate` API

Template matching is an operation wherein a small template image (the object) is mathematically convolved across a larger source image (the frame). At each coordinate, a similarity metric is computed.

The complete API signature is:
```python
result_matrix = cv2.matchTemplate(image, template, method)
```

#### Method Options
OpenCV provides six comparison methods, each representing a different mathematical approach to correlation [cite: 4, 13]:

| Method Flag | Description | Optimal Use Case |
| :--- | :--- | :--- |
| `cv2.TM_SQDIFF` | Squared Difference (lower is better). | Absolute pixel-perfect matching. |
| `cv2.TM_SQDIFF_NORMED`| Normalized Squared Difference. | Variance-resistant exact matching. |
| `cv2.TM_CCORR` | Cross-Correlation (higher is better). | Controlled environments. |
| `cv2.TM_CCORR_NORMED` | Normalized Cross-Correlation. | High structural similarity [cite: 13]. |
| `cv2.TM_CCOEFF` | Correlation Coefficient. | Matching with global lighting shifts. |
| `cv2.TM_CCOEFF_NORMED`| Normalized Correlation Coefficient. | **The industry standard for game sprites.** [cite: 1, 2] |

**Why `TM_CCOEFF_NORMED` is best for Super Mario**: The Correlation Coefficient method subtracts the mean of the template from the template, and the mean of the image patch from the image patch before correlating. This "zero-mean" approach makes it highly resilient to slight global lighting changes, semi-transparent overlays (like HUDs), and background variances behind sprites [cite: 1, 4].

### 3.2 Critical Thresholding and Multiple Occurrences

When using a normalized method like `TM_CCOEFF_NORMED`, the `result_matrix` contains values strictly ranging from `-1.0` (perfect mismatch) to `1.0` (perfect match) [cite: 14, 15].

To count **multiple occurrences** (e.g., detecting 10 coins on the screen), we cannot use `cv2.minMaxLoc()`, as it only returns the single highest match [cite: 2, 13]. Instead, we apply NumPy boolean filtering to find all coordinates exceeding a confidence threshold [cite: 2, 6].

**Critical Threshold Values**: For rigid 2D pixel art like *Super Mario*, a threshold of **`0.80` to `0.95`** is optimal [cite: 1, 2]. Below `0.70`, the algorithm will trigger false positives against visually noisy background tiles. Above `0.95`, compression artifacts (if the video is MP4/H.264 encoded) will cause true positives to be missed.

```python
import numpy as np

threshold = 0.85
# Find where the result matrix exceeds the threshold
# NOTE: np.where returns coordinates in (row, column) format, which corresponds to (y, x)
locations = np.where(result_matrix >= threshold)

# Combine the y and x arrays into a list of (x, y) coordinate points
# We reverse the order using [::-1] because OpenCV expects (x, y) for drawing
points = list(zip(*locations[::-1])) 
```

### 3.3 Non-Maximum Suppression (NMS)

Because the template matching algorithm evaluates *every single pixel shift*, a high-confidence object will trigger positive matches not just perfectly on the object, but also 1 pixel to the left, 1 pixel to the right, etc [cite: 16]. This "halo" effect causes a single coin to register as 15 overlapping detections [cite: 16].

To extract accurate counts, **Non-Maximum Suppression (NMS)** is mandatory [cite: 2, 7]. NMS evaluates all bounding boxes, compares their spatial overlap, and collapses boxes that overlap by a defined percentage (Intersection over Union - IoU) into a single box [cite: 3]. 

For 2D games, a spatial clustering approach based on distance is often just as effective and computationally simpler. If two detection coordinates are within a distance equal to half the template's width, they correspond to the same object [cite: 3].

### 3.4 Multi-Scale and Channel Compatibility

**Multi-Scale Matching**: If the game footage undergoes upscaling or downscaling (e.g., playing at 1080p vs 720p), the static template will not match. Template matching is strictly scale-invariant [cite: 4]. To handle this, an image pyramid must be utilized: the template (or the input frame) is repeatedly resized (e.g., in 10% increments) using `cv2.resize()`, and `matchTemplate` is executed at every scale. The scale yielding the highest correlation coefficient is retained [cite: 6].

**Grayscale to Grayscale Matching**: Both the source frame and the template **must** possess the exact same number of channels and data types (typically `uint8`) [cite: 6]. Attempting to match a 1-channel grayscale template against a 3-channel BGR image will result in a fatal `cv2.error`. Matching grayscale-to-grayscale works perfectly and is the recommended paradigm [cite: 4, 7].

---

## 4. Critical Pitfalls and Edge Cases

When developing robust computer vision pipelines, specific OpenCV idiosyncrasies must be defensively programmed against.

### 4.1 Array Sizing and Output Dimensions
A frequent source of `cv2.error` crashes occurs when the template matrix is spatially larger than the input image matrix in either the width or height dimension. 

When `cv2.matchTemplate` executes, it returns a 2D result array. If the input image dimensions are \( W \times H \), and the template dimensions are \( w \times h \), the dimensions of the output result matrix are strictly:
**Width**: \( W - w + 1 \)
**Height**: \( H - h + 1 \) [cite: 2, 13]

Because the sliding window cannot traverse past the bounds of the image, the output matrix is slightly smaller than the input image [cite: 13].

### 4.2 The `np.where` Coordinate System
As previously noted, multi-dimensional array indices in Python (NumPy) are structured as `[row, column]`. Therefore, `np.where(res >= thresh)` returns `(y_coords, x_coords)`. However, OpenCV drawing functions (`cv2.rectangle`, `cv2.putText`) mandate Cartesian geometry coordinates `(x, y)` [cite: 2]. Failing to invert these coordinates will cause bounding boxes to be transposed, frequently resulting in `IndexError` exceptions.

### 4.3 Silent Failures in `cv2.imread`
Unlike Python's standard `open()` which raises a `FileNotFoundError`, `cv2.imread()` will silently fail and return a `None` object if a file does not exist, if the path is malformed, or if the file permissions are restricted. Executing subsequent methods (like `.shape` or `cv2.cvtColor`) on a `NoneType` will crash the application. Always validate the return:
```python
template = cv2.imread("mario_coin.png")
if template is None:
    raise FileNotFoundError("Could not read template file. Verify path and integrity.")
```

### 4.4 Codec Compatibility in `opencv-python` on Ubuntu
A common infrastructure question involves the necessity of manually compiling FFmpeg to decode `.mp4` files. The standard Python wheel (`pip install opencv-python==4.12.0.88`) natively ships with an embedded FFmpeg backend built-in [cite: 8, 17]. It will successfully execute `cv2.VideoCapture('video.mp4')` out-of-the-box on Ubuntu 20.04/22.04/24.04 without requiring `sudo apt-get install libavcodec-dev` [cite: 8, 9]. Hardware acceleration (CUDA/NVENC), however, *does* require compiling OpenCV from source [cite: 18].

---

## 5. Pandas CSV Output

Once video frames have been parsed and objects spatially deduplicated and counted, serializing the time-series data is accomplished through the Pandas library.

Pandas DataFrames provide exceptional mechanisms for formatting structured output [cite: 19, 20].

```python
import pandas as pd

# Assume we have collected data into a list of dictionaries
# data = [{"frame_id": 1, "coins": 5, "enemies": 2, "turtles": 0}, ...]

df = pd.DataFrame(data, columns=["frame_id", "coins", "enemies", "turtles"])

# Ensure data types are integers, as object counts are discrete values
df["frame_id"] = df["frame_id"].astype(int)
df["coins"] = df["coins"].astype(int)
df["enemies"] = df["enemies"].astype(int)
df["turtles"] = df["turtles"].astype(int)

# Export to CSV
# The 'index=False' argument prevents Pandas from writing the row numbers (0, 1, 2...) as the first column
df.to_csv('/root/counting_results.csv', index=False)
```

---

## 6. Complete Python Utility Module

The following code is a comprehensive, production-ready Object-Oriented utility module combining all the aforementioned paradigms. It conforms strictly to `opencv-python==4.12.0.88` and `pandas==2.3.3` standards.

```python
import cv2
import numpy as np
import pandas as pd
import os
import math

class GameAnalyzer:
    """
    A utility class for extracting keyframes from gameplay video and 
    counting specific sprites using Template Matching and Non-Maximum Suppression.
    """
    
    def __init__(self, video_path, output_dir="output"):
        self.video_path = video_path
        self.output_dir = output_dir
        self.templates = {}  # Dictionary to hold pre-loaded templates
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_template(self, label, template_path):
        """
        Reads an image in grayscale, validating its existence, 
        and caches it for repetitive processing.
        """
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Template path invalid: {template_path}")
            
        # Read as grayscale directly (cv2.IMREAD_GRAYSCALE == 0)
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        
        if template is None:
            raise ValueError(f"Failed to decode template image: {template_path}")
            
        self.templates[label] = template
        print(f"[INFO] Loaded template '{label}' with shape {template.shape}")

    def non_max_suppression_fast(self, boxes, overlapThresh):
        """
        Standard implementation of Malisiewicz et al. Non-Maximum Suppression.
        Filters overlapping bounding boxes generated by cv2.matchTemplate.
        """
        if len(boxes) == 0:
            return []

        # If bounding boxes are integers, convert them to floats.
        if boxes.dtype.kind == "i":
            boxes = boxes.astype("float")

        pick = []
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]

        # Calculate bounding box area and sort by bottom-right y-coordinate
        area = (x2 - x1 + 1) * (y2 - y1 + 1)
        idxs = np.argsort(y2)

        while len(idxs) > 0:
            last = len(idxs) - 1
            i = idxs[last]
            pick.append(i)

            # Find largest (x, y) coordinates for start and smallest for end of bounding box
            xx1 = np.maximum(x1[i], x1[idxs[:last]])
            yy1 = np.maximum(y1[i], y1[idxs[:last]])
            xx2 = np.minimum(x2[i], x2[idxs[:last]])
            yy2 = np.minimum(y2[i], y2[idxs[:last]])

            # Calculate width and height of the intersection box
            w = np.maximum(0, xx2 - xx1 + 1)
            h = np.maximum(0, yy2 - yy1 + 1)

            # Calculate intersection over union (IoU)
            overlap = (w * h) / area[idxs[:last]]

            # Delete indices from the list that have an overlap > threshold
            idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlapThresh))))

        return boxes[pick].astype("int")

    def count_objects_in_frame(self, frame_gray, threshold=0.85):
        """
        Iterates over all loaded templates, correlates them against the grayscale frame,
        applies NMS, and returns the discrete counts of each object class.
        """
        counts = {}
        
        for label, template in self.templates.items():
            template_h, template_w = template.shape[:2]
            
            # Ensure template is strictly smaller than or equal to frame dimensions
            if template_w > frame_gray.shape[cite: 1] or template_h > frame_gray.shape:
                counts[label] = 0
                continue
                
            # Perform normalized correlation coefficient matching
            res = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
            
            # Extract coordinates where correlation exceeds confidence threshold
            y_coords, x_coords = np.where(res >= threshold)
            
            rects = []
            for (x, y) in zip(x_coords, y_coords):
                # Construct bounding box: [start_x, start_y, end_x, end_y]
                rects.append([x, y, x + template_w, y + template_h])
            
            # Apply NMS to eliminate multiple overlapping detections
            # 0.3 threshold means boxes overlapping by 30% or more are merged
            nms_boxes = self.non_max_suppression_fast(np.array(rects), 0.3)
            
            # The length of the deduplicated array represents the true object count
            counts[label] = len(nms_boxes)
            
        return counts

    def process_video(self, sample_interval_seconds=1.0, match_threshold=0.85):
        """
        Parses video, extracts keyframes temporally, matches objects, 
        and returns a structured Pandas DataFrame.
        """
        cap = cv2.VideoCapture(self.video_path)
        
        if not cap.isOpened():
            raise IOError(f"Cannot initialize VideoCapture on {self.video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(round(fps * sample_interval_seconds))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"[INFO] Video loaded. Total Frames: {total_frames}, FPS: {fps}")
        
        results = []
        frame_id = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break # Video stream ended
                
            # Sample based on defined interval (Uniform Temporal Sampling)
            if frame_id % frame_interval == 0:
                # Convert active frame to grayscale for template matching
                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Execute detection
                frame_counts = self.count_objects_in_frame(frame_gray, threshold=match_threshold)
                
                # Add metadata to row payload
                row_data = {"frame_id": frame_id}
                row_data.update(frame_counts)
                results.append(row_data)
                
                # Save keyframe image to disk
                filename = os.path.join(self.output_dir, f"keyframes_{frame_id:05d}.png")
                # Write back as original BGR for visual clarity, or frame_gray if preferred
                cv2.imwrite(filename, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                
            frame_id += 1
            
        cap.release()
        
        # Structure data via Pandas
        # If no templates were loaded, ensure base structure exists
        columns = ["frame_id"] + list(self.templates.keys())
        df = pd.DataFrame(results, columns=columns)
        
        # Cast to standard integers
        for col in columns:
            df[col] = df[col].fillna(0).astype(int)
            
        return df

# ==========================================
# Execution Example
# ==========================================
if __name__ == "__main__":
    try:
        analyzer = GameAnalyzer("mario_world_1_1.mp4", output_dir="/root/keyframes")
        
        # Assume templates have been cropped directly from the game
        analyzer.load_template("coins", "assets/template_coin.png")
        analyzer.load_template("enemies", "assets/template_goomba.png")
        analyzer.load_template("turtles", "assets/template_koopa.png")
        
        # Process 1 keyframe per second of video
        # Threshold 0.85 optimal for CV2 TM_CCOEFF_NORMED
        df_results = analyzer.process_video(sample_interval_seconds=1.0, match_threshold=0.85)
        
        # Export findings, omitting the arbitrary dataframe index
        csv_out_path = '/root/counting_results.csv'
        df_results.to_csv(csv_out_path, index=False)
        print(f"[SUCCESS] Analytics saved to {csv_out_path}")
        
    except Exception as e:
        print(f"[ERROR] Process failed: {str(e)}")
```

**Sources:**
1. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsPh7IaniU2WRvZUYk_3SE07nzk30YV51hJeo6B1anncOX2uxWE8I6HOHnbWoT4IrOKjdq6OZOj9_nPAOO-Fq79oQQE9eEd_zigQu95fc7SwEZYJyvD0aeYyIEktuRLvkw4oUl02kmAcYq4GeGfn0rlbTQDt7N4SfUeBBXOeFPr0ZBq1DB73YuoJyzRkPAtHTT-j3-bpIn4DRRHlrI2l_9Td3KM4ELo5wc)
2. [pyimagesearch.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGsnTvm786X5A40OmB2kR7FR0zaMoM_B_7Mxbn-nNRGNzvCZkhxYmM7aiwyio3OzYn4vyl7jUu2PLNYum6AMcHeC4mU4Gfsk4Nycm0FeXM2dd9BMf1I7tfAbAp4v-hkagr0VDKi8szxUy1MC4jUpAY1aNSEhPNbnBmItAFhDQIJ)
3. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEppRjyCP6S4d_C9mr1wDs1NvXZg_TX8JPgB283IXGlh4MwZY4KsAp2R65spW2qmytqb5Sdnb__wfEmYifF0Dhu-STUrY8hlJNK5mXb4xLixOAlzXwAndvlkav5dSP4aU0GbwUuGigQfIquxvmepn1p0P7k2g8YvNGB)
4. [circuitdigest.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQExCybyVBNufgiFbXaJphvlB5EwZDEojLVTSA2cvj3TQxT0SD6TlClsFNTvGTQqej-1_cluWJNT0cHf0Llc9ozissnNa9itDDtyvD0NGxgMCCwYkGmVa98Cws6GXRvJI1Bo9-Nk-WRy-1NrzQKIVG7dHHN6KEFmFyw03SNWMA==)
5. [csdn.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaecFz1pNCG-HgEWAA0YWHG3iMs1vvE6awX0qpba9bAX_eiqzfV3crlRhhDM6Agl-JvCK7wr3kd0dZtxQD7h10L1KxC8d3Mu3nf2_tKbzqMShxIkPc9zl_w12apWff_zsAfD1nGUc0SGT-z0kmWQ==)
6. [tautvidas.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGLVy7GsGVdD7yj5px77cjCsZdcK3JCCeAcDwhuRJGi8_lWEc0LTs02RSWjvcQWJDelbMIQgxQKXksBc5H3xmVIfoqH1sI8uvxQ7ac_9Z93SDzsY0P00B6IAJItBjnnv-3QQUVTAw9Cf87P4IXUQ2aU9hnxdYJnIZgooEus1qjDS8FNvklo2BQLq5AjNu4AlSK8UQp9)
7. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEO9WYOW1xT6NyvgxzeCCFWgiuPtEsojvt2zgr_M3c6Ku_GiuWUY_SYoX-vWbPi3vvmdkmNpRqz90bTcrrbWJ569a6Qso-jynWkPbLNfpsT_dL4YyEvcgSCVWgoRUJO_ssyZAHOUw-iqGcIAZCtLKtSzoB9LpXMj0fo5shFxEgJBT2TYClk_ZTS1g==)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQcEV6ESBxVGN_GQVZvx0cC-tXxr_rQ9Gd2yiE-QA_6hEOzudnK1M6Ir1PFqQ6cq23ZOkeBHFsYYZH4B_o7OXxgWd9EOrhddcjtwwok_22dHMbdNPswNbOGmLfQfrfJM--PINlWaiWIayCVxOKfCyLYGI=)
9. [bojankomazec.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_eWOvjSNYVL8RquTURG_nQZWIbP4xSny6M7Q_HJH5UJ6YYCIvERpcadVHA5dujC8MwpBvynd09yxiUwYaW89BvJ9Cg5A6-uFfcvjAohl-ujcQd1K_B2Evo4D0o7jLi4eI3sdCKF5cQRPEVRa3Toh58eH4vAfl3hqB1fWOmV7fe1G0yVkD)
10. [cloudinary.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZK_xFW_QEKgJcm6rr0-PT5lGLMcexMOKvpXV7bKlAYPu9g40pxwOD8CH5v3SIEUzOuwZUaat7qR2nQUuYhNOuu_4hYFfAui3wxCxr2Ajq1t_rJhEjTYPe_iiHzFCGVT2GYk03xaLN_vDG98OizZchbXZr3Q4IaRPTe4bN7k7YwtH8eDwcQc91KTmxDw==)
11. [grokipedia.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUql_pF0QmvGG1f_jk8P2PItclFA6M7ac73JR-MMBItDNHzzweDrdcIeorbLdU4S2ai6SeMZsJuRBxHz4PDXbu9oAygpyTlANmiIWwO-WKiTKygJdv1rs4tpgI70rKoQDIHYGVbHVDcK1H6Vji-lI74g96o21qXw==)
12. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHE6nPlgYUA2VSkQ8ZV0cdTkMkfChwPrQ9rk_c0QOe0My6On04-al2A8vF5jWdJESMjIGQ2B6fQNjIKxhCVOOmN42lywPKquLtIHEeV6ZAADGAn8hVKiZO_xhst8gzPFgPmpEdF9xPXzIdm5u_wTF2l3TbK9QIzY4o2IZ09t3vaupI=)
13. [roboflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbSlDxnQ5ZnetdqEFJSHqnh096EhgvrCsMa7uT5Y5XDY6i1WWnLK4jaPwVocs8V899do1aan4wGWGZ2KCYSTfUoJB1UpoSJYX5uh5SDPS0evUYPNDY6VXrezLsvtZiKBjuQA==)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYu7J9pdwWjNGx-wD0Eia_jlGi4vyxyVRXTAbhsrXh5Ez1u3esG1RWI7uttZgh7f9CJzjPivwZQUwuwtUyLJyWxnDrA36xDrfpF-QFq4EcyWaA834Rt14SN39oLSSHHT-3_K-jHCbz0CjTCQCPM2xoadao6U6EiyavYdcOQrnhedXPKeNm9oVz6mPj7BzxKFlUr91Y_0aPU3xd2wf6MPh9jSl3WeXlv5POCLno2yP6HqKttg==)
15. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxzICg-88-vbx27xdS_icgAcW7AeKF3InRTFL88Jh_m0h3BaKzDXHBQ-XlpXyzK3aizQEl6B1udIjC1zrBewr3SIOGuMUH3wc6JrYdXksd9lhXeK00QUoeMMcMFOOA40yG2OVUKP3ne4HUf0OFdXD0CguEJQ1IPH8Z)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFYvq7jRnHZ3iqtl9IsYTwKTbrD92MpyjAKcOHqJ4vPyOWBDtUIYpLT8dXAJ3Ei2p7QyRshuYRR62qNqZ1gganlCQmFM3pIrBux1W3mcREiy0dAH1PiEq_Wx63g48z1NE9Xebr2IJ6YB5OT3YUAE0ejEHm83vQWWUmmEwIrwG-U01zjBNsV0T6Zru1jcRXU1E518vwgZhXxFWo9s-j4)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEDIlycddWT9DylEvq6MjdcjBqrdTdKy7QZvXvTd5sysAnCt4ky_QPJNB2xHnpZl2YEotVDUrSkFykgHgcrcnTZ0KiqQTVfETS10qsVo931jvU43ecWjBlR5rQ8NkAIqbNYWGkTAfrKLnNik4_whXuj0sXnjPY7zzfiz6SBud7DAymF9rzkOKhiR40z8xlvCKe6FPYnhWk=)
18. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFo36Y13aAf8UPERBCfjwkKfZObEVbqNyS3XodvaUFv9ywTx3c8pg9ictQkxIALNBdPQPYVtoy73iw_EoX1YtECPMTGbBsu5ywlprDOACxyPfBKQ0qx1WiRLiv3cSzb0Wvtp9PFnQaCPzGVqRZYtL4GJN6vHQQ=)
19. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFn_EpZFikQQz74rdRjr6FiM7nYjqyt5l90noYlUmy_XuBmPik7yOZfEGo2dBkZqqUCeNbr9EHsVBLbD_WV1vrR2Zbj3-f-EarSK9Yjt5XrBQ8TC539qYSUD6wHVg==)
20. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHctTzGRcHKgRmoawtgcE-rJXoiAm9zrcMamIzvZ6dAyDOUYw4rJp1I97Nsk3GnaCGvCMzQZRKOaKwW-luXg7lwWNb1Yi2Z_57rDwPTFyg-55iuw3IBypIM0fd1riuy7tUQ2qzNLt36KLDHsU28btMRA1mg718vppzIiBJcpq6k2oc=)
