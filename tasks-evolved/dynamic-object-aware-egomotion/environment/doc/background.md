# Comprehensive Analysis and Implementation of Video Egomotion and Dynamic Object Segmentation utilizing OpenCV and NumPy

Research suggests that performing complex video analytics such as camera motion (egomotion) classification and dynamic object segmentation is entirely feasible without deep learning frameworks, provided that classical computer vision algorithms are rigorously applied. It seems likely that utilizing dense and sparse optical flow alongside robust affine estimators like RANSAC can yield highly accurate egomotion parameters. Furthermore, the evidence leans toward frame differencing following homographic motion compensation as an effective strategy for isolating dynamic objects in moving-camera scenarios. 

*   **Classical Egomotion Estimation**: It appears that decomposing global optical flow via affine partial transformations allows for reliable classification of camera movements (Pan, Tilt, Dolly, Roll, Stay).
*   **Motion Compensation**: Compensating for camera motion using perspective warping allows classical frame-differencing methodologies to perform dynamic object detection, bypassing the limitations of standard background modeling techniques.
*   **Environment Constraints**: It is entirely possible to construct compressed sparse row (CSR) matrices manually utilizing only NumPy, thereby bypassing dependencies on external libraries like SciPy, which is vital for constrained deployment environments.
*   **Algorithmic Pitfalls**: Evidence indicates that practitioners must carefully navigate OpenCV nuances, such as frame-seeking unreliability in compressed MP4 files and integer underflow hazards during array arithmetic, to ensure system stability.

## 1. Video Frame Sampling Strategies with OpenCV

The initial stage of any video analysis pipeline involves decoding and sampling frames from a video file. When operating under computational constraints, processing every frame is often unnecessary and prohibitively expensive. Instead, temporally sampling frames at a calculated interval (e.g., matching a target Frames Per Second, or FPS) is standard practice.

### 1.1 API Usage for Video Capture and Frame Rate Calculation

OpenCV relies on the `cv2.VideoCapture` class to interface with video files, often leveraging the underlying FFmpeg backend for decoding. To sample a video to a target frame rate (e.g., $FPS_{target} = 6$), the original frame rate ($FPS_{original}$) must first be retrieved. This allows for the computation of a frame step size $N$, dictating that every $N$-th frame should be extracted.

The original FPS can be obtained using `cap.get(cv2.CAP_PROP_FPS)`. The frame step is then calculated as the integer division of the original FPS by the target FPS.

### 1.2 The Unreliability of `CAP_PROP_POS_FRAMES` in MP4 Files

A common instinct when sampling frames is to compute the desired frame index and jump directly to it using `cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)`. However, extensive developer consensus and issue tracking indicate that frame seeking via `CAP_PROP_POS_FRAMES` is highly unreliable, particularly for heavily compressed temporal codecs like H.264/MP4 [cite: 1, 2]. 

Research suggests that OpenCV's `VideoCapture` seeking mechanism often interacts poorly with predictive frames (P-frames) and bidirectional frames (B-frames) in MP4 containers [cite: 2, 3]. For videos lacking frequent keyframes (I-frames) or containing variable frame rates (VFR), the `set` command may silently fail or return a frame offset by several indices [cite: 1, 3]. In some OpenCV backend implementations, duplicate frames are ignored during sequential reading but cause offsets during random seeking [cite: 1]. Because of these issues, setting `CAP_PROP_POS_FRAMES` might return a boolean `True` while failing to correctly advance the decoder to the requested temporal location [cite: 3].

### 1.3 Recommended Strategy: Sequential Reading

To ensure absolute frame accuracy, it is highly recommended to read frames sequentially in a `while` loop, discarding the unneeded frames [cite: 3]. While this introduces a linear time overhead for I/O and decoding, it guarantees temporal coherence.

**Implementation Example: Reliable Frame Sampling**
```python
import cv2
import numpy as np

def sample_video_frames(video_path, target_fps=6):
    """
    Safely extract frames from an MP4 file at a target FPS using sequential reading.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video: {video_path}")
        
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    if original_fps <= 0:
        original_fps = 30.0 # Fallback heuristic
        
    # Calculate step size
    frame_step = max(1, int(round(original_fps / target_fps)))
    
    sampled_frames = []
    frame_indices = []
    current_frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break  # End of video stream
            
        if current_frame_idx % frame_step == 0:
            sampled_frames.append(frame)
            frame_indices.append(current_frame_idx)
            
        current_frame_idx += 1
        
    cap.release()
    return sampled_frames, frame_indices, original_fps
```

## 2. Optical Flow Computation for Egomotion Estimation

Egomotion estimation—determining the 3D motion of a camera within an environment from a sequence of 2D images—heavily relies on optical flow. Optical flow represents the apparent motion of brightness patterns in the image plane.

### 2.1 Dense Optical Flow: Gunnar Farneback's Algorithm

The Gunnar Farneback algorithm computes a dense optical flow field, meaning it calculates a displacement vector for every single pixel in the image [cite: 4]. The algorithm approximates the pixel neighborhoods of two consecutive frames using quadratic polynomials [cite: 4, 5]. By analyzing how these polynomials translate from the previous frame to the current frame, the dense flow field is derived. 

The API for this algorithm is `cv2.calcOpticalFlowFarneback()`. The input arrays must be 8-bit single-channel (grayscale) images (`np.uint8`) [cite: 4, 6]. The resulting flow field is an array of the same spatial dimensions, with two channels representing the $X$ and $Y$ displacement vectors, stored as 32-bit floating-point numbers (`np.float32` / `CV_32FC2`) [cite: 7, 8].

**Table 1: `cv2.calcOpticalFlowFarneback` Parameters and Recommended Values**

| Parameter | Type | Description | Recommended Egomotion Value |
| :--- | :--- | :--- | :--- |
| `prev` | `uint8` 2D | First input image (grayscale). | N/A |
| `next` | `uint8` 2D | Second input image (grayscale, same size). | N/A |
| `flow` | `None` / `float32` | Computed flow image. Passed as `None` to allocate a new matrix. | `None` |
| `pyr_scale` | `float` | Image scale to build the pyramid (< 1). A value of 0.5 halves the size at each layer. | `0.5` [cite: 4, 9] |
| `levels` | `int` | Number of pyramid layers (including initial image). Increases robustness to large motions. | `3` to `5` [cite: 10, 11] |
| `winsize` | `int` | Averaging window size. Larger values increase robustness to noise and detect fast motion, but blur the motion field. | `13` or `15` [cite: 10] |
| `iterations` | `int` | Number of iterations the algorithm does at each pyramid level. | `3` to `10` [cite: 10] |
| `poly_n` | `int` | Size of pixel neighborhood for polynomial expansion. Yields smoother surfaces. | `5` or `7` [cite: 5, 10] |
| `poly_sigma` | `float` | Standard deviation of the Gaussian used to smooth derivatives. | `1.1` (if `poly_n=5`), `1.5` (if `poly_n=7`) [cite: 5, 10] |
| `flags` | `int` | Operation flags (e.g., `cv2.OPTFLOW_FARNEBACK_GAUSSIAN`). | `0` or `cv2.OPTFLOW_FARNEBACK_GAUSSIAN` [cite: 9, 10] |

**Implementation Example: Dense Flow**
```python
def compute_dense_flow(prev_frame, next_frame):
    # Ensure inputs are 8-bit single-channel (grayscale)
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    next_gray = cv2.cvtColor(next_frame, cv2.COLOR_BGR2GRAY)
    
    flow = cv2.calcOpticalFlowFarneback(
        prev=prev_gray,
        next=next_gray,
        flow=None,
        pyr_scale=0.5,
        levels=5,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.1,
        flags=0
    )
    return flow # Shape: (H, W, 2), dtype: float32
```

### 2.2 Sparse Optical Flow: Lucas-Kanade Method

An alternative, computationally lighter approach is sparse optical flow, commonly implemented via the Lucas-Kanade (LK) algorithm (`cv2.calcOpticalFlowPyrLK()`). Instead of tracking all pixels, it tracks specific, highly textured keypoints [cite: 12]. 

The initial features are typically extracted using the Shi-Tomasi corner detector via `cv2.goodFeaturesToTrack()` [cite: 7, 13]. 

**Key Parameters for `goodFeaturesToTrack`:**
*   `image`: Input 8-bit single-channel image.
*   `maxCorners`: Maximum number of corners to return (e.g., 200). If there are more, the strongest are returned [cite: 12].
*   `qualityLevel`: Minimal accepted quality (e.g., 0.01). Corners with a quality measure less than this multiplied by the best corner quality are rejected [cite: 12].
*   `minDistance`: Minimum possible Euclidean distance between returned corners (e.g., 30 pixels) [cite: 12].
*   `blockSize`: Size of an average block for computing a derivative covariation matrix (e.g., 3) [cite: 12].

**Key Parameters for `calcOpticalFlowPyrLK`:**
*   `prevImg`, `nextImg`: 8-bit single-channel images [cite: 7].
*   `prevPts`: Vector of 2D points to track (`float32`) [cite: 7].
*   `nextPts`: Output vector of 2D points [cite: 7].
*   `winSize`: Size of the search window at each pyramid level (e.g., `(15, 15)`). Smaller windows miss large motion [cite: 12].
*   `maxLevel`: 0-based maximal pyramid level number [cite: 12].
*   `criteria`: Termination criteria for the iterative search, defined by a tuple `(type, maxCount, epsilon)`. E.g., `(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)` [cite: 12].

### 2.3 Mathematical Decomposition of Egomotion

To classify the cinematographic camera motion labels (Pan, Tilt, Dolly, Roll, Stay), the global flow field must be modeled mathematically. The transformation of a planar scene (or a scene far from the camera) between consecutive frames can be modeled by an affine transformation matrix [cite: 14, 15]. 

A partial 2D affine transformation (similarity transform) has 4 degrees of freedom: uniform scale ($s$), rotation ($\theta$), and translation ($t_x, t_y$) [cite: 15, 16]. This avoids the shearing components found in a full 6-DOF affine transformation, cleanly separating the operations we wish to classify [cite: 15, 17].

The operation maps a source point $(x, y)$ to a destination point $(x', y')$ [cite: 14]:
\[
\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} a & b \\ c & d \end{bmatrix} \begin{bmatrix} x \\ y \end{bmatrix} + \begin{bmatrix} t_x \\ t_y \end{bmatrix} = \begin{bmatrix} s \cos \theta & -s \sin \theta \\ s \sin \theta & s \cos \theta \end{bmatrix} \begin{bmatrix} x \\ y \end{bmatrix} + \begin{bmatrix} t_x \\ t_y \end{bmatrix}
\]
[cite: 14, 16].

OpenCV's `cv2.estimateAffinePartial2D(srcPoints, dstPoints, method=cv2.RANSAC)` perfectly captures this 4-DOF transformation [cite: 16, 17]. It utilizes RANSAC to ignore outlier flow vectors that may belong to independently moving objects [cite: 17], ensuring the resulting matrix represents the global background (camera) motion [cite: 18].

**Exact Decomposition of the 2x3 Matrix `M`:**
Given the returned matrix $M = \begin{bmatrix} M_{00} & M_{01} & M_{02} \\ M_{10} & M_{11} & M_{12} \end{bmatrix}$ [cite: 16]:
1.  **Translation Vector**: The $x$ and $y$ translations are directly available.
    *   $t_x = M_{02}$
    *   $t_y = M_{12}$
2.  **Rotation Angle ($\theta$)**: Utilizing the arctangent function.
    *   $\theta = \arctan2(M_{10}, M_{00})$ [cite: 16]
    *   In radians, convert to degrees via `np.degrees()`.
3.  **Scale Factor ($s$)**: The magnitude of the column vectors.
    *   $s = \sqrt{M_{00}^2 + M_{10}^2}$ [cite: 16]

### 2.4 Cinematographic Motion Thresholding Rules

Once the parameters are decomposed, specific thresholds determine the camera labels [cite: 18]. Assuming a 720p or 1080p frame, the thresholds must be scaled relative to the resolution. Let us define:
*   `th_trans`: Minimum pixel translation to register a Pan or Tilt (e.g., 2.0 pixels) [cite: 18].
*   `th_rot`: Minimum rotation in radians to register a Roll (e.g., $0.01$ rad $\approx 0.57^\circ$) [cite: 18].
*   `th_scale`: Minimum scale deviation from 1.0 to register a Dolly (e.g., 0.02, triggering on $< 0.98$ or $> 1.02$) [cite: 18].

**Logic Gate for Multi-label Classification** [cite: 18]:
*   **Pan Left/Right**: Triggered by $t_x$. If $|t_x| > \text{th\_trans}$ and $|t_x| > |t_y|$. A positive $t_x$ (image moves right) implies the camera is panning **Left**. A negative $t_x$ implies the camera is panning **Right** [cite: 18].
*   **Tilt Up/Down**: Triggered by $t_y$. If $|t_y| > \text{th\_trans}$ and $|t_y| > |t_x|$. A positive $t_y$ (image moves down) implies the camera is tilting **Up**. A negative $t_y$ implies the camera is tilting **Down** [cite: 18].
*   **Dolly In/Out**: Triggered by $s$. If $|s - 1.0| > \text{th\_scale}$. $s > 1.0$ is **Dolly In** (zoom in, objects get larger). $s < 1.0$ is **Dolly Out** [cite: 18].
*   **Roll Left/Right**: Triggered by $\theta$. If $|\theta| > \text{th\_rot}$. $\theta > 0$ is **Roll Right** (clockwise), $\theta < 0$ is **Roll Left** (counter-clockwise) [cite: 18].
*   **Stay**: If none of the above criteria are met [cite: 18].

**Implementation Example: Egomotion Extraction**
```python
def extract_egomotion_labels(src_pts, dst_pts, th_trans=2.0, th_scale=0.015, th_rot=0.01):
    labels = []
    
    # Require at least 3 points for affine transform
    if len(src_pts) < 3:
        return ["Stay"]
        
    M, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC)
    
    if M is None:
        return ["Stay"] # Fallback to identity transform [cite: 18]
        
    tx = M[cite: 4]
    ty = M[cite: 1, 4]
    theta = np.arctan2(M[cite: 1], M)
    s = np.sqrt(M**2 + M[cite: 1]**2)
    
    if abs(s - 1.0) > th_scale:
        labels.append("Dolly In" if s > 1.0 else "Dolly Out")
        
    if abs(theta) > th_rot:
        labels.append("Roll Right" if theta > 0 else "Roll Left")
        
    if abs(tx) > th_trans and abs(tx) >= abs(ty):
        labels.append("Pan Left" if tx > 0 else "Pan Right")
        
    if abs(ty) > th_trans and abs(ty) > abs(tx):
        labels.append("Tilt Up" if ty > 0 else "Tilt Down")
        
    if not labels:
        labels.append("Stay")
        
    return labels
```

## 3. Dynamic Object Detection without Deep Learning

Extracting independently moving objects is traditionally handled by background subtractors. However, standard models like `cv2.createBackgroundSubtractorMOG2()` and `cv2.createBackgroundSubtractorKNN()` assume a static camera [cite: 13, 19, 20]. When the camera moves (egomotion), these statistical mixture models erroneously update the entire field of view as foreground, rendering them severely limited for dynamic scene analysis [cite: 20]. Thus, ego-motion compensation is strictly required.

### 3.1 Separating Egomotion using Homography and Warping

To isolate dynamic objects, the previous frame must be mathematically aligned to the current frame—effectively "canceling out" the camera's movement. While `estimateAffinePartial2D` is excellent for categorization, the full planar perspective projection modeled by a Homography matrix (8 degrees of freedom) provides a superior pixel-to-pixel alignment across the depth of field [cite: 21].

`cv2.findHomography(srcPoints, dstPoints, method=cv2.RANSAC, ransacReprojThreshold=3.0)` computes the 3x3 transformation matrix $H$ that maps the coordinate system of $I_{t-1}$ to $I_t$. RANSAC ensures that the point correspondences belonging to dynamically moving objects (which violate the global background motion) are classified as outliers and excluded from the matrix computation. The `ransacReprojThreshold` determines the maximum allowed reprojection error in pixels to consider a point an inlier (typically $3.0$).

The return format is a tuple `(H, mask)`, where `H` is the `float64` 3x3 matrix, and `mask` is an `np.uint8` array of length $N$ (where $N$ is the number of points) with `1` for inliers and `0` for outliers. 

Once $H$ is acquired, `cv2.warpPerspective` applies the transformation to the previous frame [cite: 21]:
```python
aligned_prev_frame = cv2.warpPerspective(prev_frame, H, (width, height))
```

### 3.2 Difference Imaging and Binary Mask Generation

With $I_{t-1}$ perfectly warped to align with $I_t$, subtracting the two frames isolates the dynamically moving pixels. Note that integer underflow is a critical hazard here: if an `np.uint8` array is subtracted from another, negative values wrap around (e.g., $5 - 10 = 251$) [cite: 22, 23]. 

Therefore, one must strictly use `cv2.absdiff(frame1, frame2)`, which correctly calculates the per-element absolute difference bounded by 8-bit limits [cite: 24, 25].

```python
diff = cv2.absdiff(curr_gray, aligned_prev_gray)
_, binary_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
```

### 3.3 Morphological Mask Clean-up

The raw difference mask will be populated with salt-and-pepper noise and fragmented contours. Mathematical morphology operations are required to consolidate the shapes.

1.  **Erosion / Opening**: `cv2.erode` or `cv2.morphologyEx(..., cv2.MORPH_OPEN, kernel)` removes isolated noisy pixels. A smaller kernel (e.g., $3\times3$) with 1 iteration is sufficient.
2.  **Dilation / Closing**: `cv2.dilate` or `cv2.morphologyEx(..., cv2.MORPH_CLOSE, kernel)` fills holes inside dynamic objects and bridges gaps. A larger kernel (e.g., $7\times7$ or $9\times9$) with 2-3 iterations solidifies the mask.

```python
kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

mask_clean = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel_close, iterations=2)
```

## 4. Manual Construction of SciPy Sparse CSR Matrices

When packaging constraints forbid the use of external dependencies like `scipy`, utilizing its highly efficient Compressed Sparse Row (CSR) matrix format requires a manual implementation using base NumPy arrays [cite: 26, 27]. CSR is an optimized memory representation for matrices where the vast majority of elements are zero (e.g., binary segmentation masks) [cite: 27, 28].

### 4.1 Theory of the CSR Format

A CSR matrix of shape $(H, W)$ is fully defined by three 1-dimensional arrays [cite: 26, 27]:
1.  **`data`**: Contains all non-zero values of the dense array, read row-by-row (top to bottom, left to right). For a boolean mask, this is an array of `True` values [cite: 29, 30].
2.  **`indices`**: Contains the column indices corresponding to each element in the `data` array [cite: 26, 27, 29]. Length matches `data`.
3.  **`indptr`**: The "Index Pointer" array. It defines the starting index within the `data` and `indices` arrays for each row [cite: 27, 29]. Its length is strictly $H + 1$ (number of rows plus one) [cite: 26, 27, 29]. The values of the $i$-th row are stored in `data[indptr[i]:indptr[i+1]]` [cite: 26, 27, 28]. The very first element is always 0, and the last element equals the total number of non-zero elements (length of `data`) [cite: 27, 29].

### 4.2 Algorithm for Manual NumPy Conversion

To convert a 2D dense boolean NumPy array `dense_mask` into these three arrays efficiently without looping over Python iterables:

```python
import numpy as np

def dense_to_csr_manual(dense_mask):
    """
    Convert a 2D boolean NumPy array to CSR components manually.
    """
    # 1. Identify non-zero elements
    # np.where returns a tuple: (row_indices, col_indices)
    rows, cols = np.where(dense_mask)
    
    # 2. Data array: all non-zero values (all True for a binary mask)
    data = np.ones(len(rows), dtype=bool)
    
    # 3. Indices array: just the column indices of the non-zero elements
    indices = cols.astype(np.int32)
    
    # 4. Indptr array: count of non-zeros per row
    # np.bincount counts occurrences of each row index.
    # We must provide minlength to account for completely empty trailing rows.
    row_counts = np.bincount(rows, minlength=dense_mask.shape)
    
    # indptr is the cumulative sum of row counts, prepended with a 0
    indptr = np.zeros(dense_mask.shape + 1, dtype=np.int32)
    indptr[1:] = np.cumsum(row_counts)
    
    return data, indices, indptr
```

### 4.3 Serialization to NPZ Format

Once the mask for a given frame `i` is transformed into the CSR components, it should be serialized to disk using `np.savez_compressed()`. This saves multiple arrays into a single zipped binary file. 

```python
def save_csr_masks(mask_list, output_file, shape):
    """
    Saves a list of boolean masks to an NPZ file utilizing CSR structure.
    """
    save_dict = {'shape': np.array(shape, dtype=np.int32)}
    
    for i, mask in enumerate(mask_list):
        data, indices, indptr = dense_to_csr_manual(mask)
        save_dict[f'f_{i}_data'] = data
        save_dict[f'f_{i}_indices'] = indices
        save_dict[f'f_{i}_indptr'] = indptr
        
    np.savez_compressed(output_file, **save_dict)
```

## 5. Structuring Motion Outputs in JSON

The egomotion analysis operates between pairs of consecutive sampled frames. Therefore, the outputs are inherently interval-based. Writing these sequence intervals to JSON requires standard string manipulation to format the keys as `"start->end"` intervals. In a zero-based index logic, the movement extracted between the very first sample and the second sample will be keyed `"0->1"`.

```python
import json

def export_motion_to_json(motion_results, output_path):
    """
    motion_results: List of tuples (frame_idx_prev, frame_idx_curr, labels_list)
    """
    json_dict = {}
    
    for (prev_idx, curr_idx, labels) in motion_results:
        key = f"{prev_idx}->{curr_idx}"
        json_dict[key] = labels
        
    with open(output_path, 'w') as f:
        json.dump(json_dict, f, indent=4)
```

To reduce payload size, temporal smoothing or interval compression can be applied. If frame $0 \rightarrow 1$ is `["Pan Left"]` and frame $1 \rightarrow 2$ is `["Pan Left"]`, they can be compressed to `"0->2": ["Pan Left"]` [cite: 18]. 

## 6. Common Pitfalls and Edge Cases

### 6.1 BGR vs RGB Color Space Constraints
OpenCV decodes video via `VideoCapture` into the BGR color space by default. When performing optical flow calculations with `calcOpticalFlowFarneback` or `calcOpticalFlowPyrLK`, the algorithm calculates gradients and assumes a single-channel spatial intensity gradient [cite: 7, 8, 31]. Passing a 3-channel BGR/RGB image to these functions will invoke cryptic C++ assertion failures indicating dimension mismatches. Explicit invocation of `cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)` is mandatory [cite: 4, 6, 7].

### 6.2 Data Types and Optical Flow Expectations
When passing initial estimates to the `flow` parameter of `calcOpticalFlowFarneback`, one must ensure it is exactly `np.float32` [cite: 4, 8]. Attempting to use `float64` (NumPy's default for floating point matrices) will result in a fatal breakdown inside the C++ bindings [cite: 7, 9]. Similarly, the input `prev` and `next` images must be strictly 8-bit unsigned integers (`np.uint8`) [cite: 4, 6, 7].

### 6.3 Integer Underflow in Array Math
As demonstrated in the dynamic object detection section, Python arrays utilizing `np.uint8` lack signed representations [cite: 22]. `numpy` subtraction does not automatically upcast to signed integer types [cite: 22]. Ergo, `img1 - img2` wraps negatively valued differences back toward $255$ [cite: 22, 23, 24]. Direct element-wise subtraction should only be performed after explicitly casting the matrices to `np.int16` or `np.float32` [cite: 23, 24], though `cv2.absdiff` remains the vastly superior, hardware-accelerated alternative [cite: 24, 25].

### 6.4 Affine Degeneracy
When attempting to calculate `estimateAffinePartial2D` or `findHomography`, a minimum number of valid corresponding points must be present (3 for affine, 4 for homography) [cite: 21]. In environments with low texture (e.g., flat white walls or extreme darkness), the optical flow algorithms will fail to generate sufficient non-zero motion vectors [cite: 18]. Unhandled, this crashes the geometry estimators. Defensive programming—such as enforcing `if len(srcPoints) < 4: return identity_matrix`—is critical to preventing unpredictable script termination [cite: 18, 21].

## 7. Complete Integrated Code Example

The following code synthesizes the entire methodology described above into an autonomous module utilizing only the prescribed dependencies.

```python
import cv2
import numpy as np
import json

class VideoMotionAnalyzer:
    def __init__(self, video_path, target_fps=6):
        self.video_path = video_path
        self.target_fps = target_fps
        self.frames = []
        self.frame_indices = []
        
    def extract_frames(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise IOError("Cannot open video stream.")
            
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        step = max(1, int(round(original_fps / self.target_fps)))
        
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            if idx % step == 0:
                self.frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                self.frame_indices.append(idx)
            idx += 1
        cap.release()
        
    def analyze_egomotion_and_objects(self):
        motion_results = []
        dynamic_masks = []
        
        # Kernel initializations
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        
        # Need at least two frames
        if len(self.frames) < 2:
            return motion_results, dynamic_masks
            
        for i in range(1, len(self.frames)):
            prev_gray = self.frames[i-1]
            curr_gray = self.frames[i]
            prev_idx = self.frame_indices[i-1]
            curr_idx = self.frame_indices[i]
            
            # --- 1. Optical Flow (Sparse PyrLK for Efficiency in Egomotion) ---
            prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=300, qualityLevel=0.01, minDistance=30, blockSize=3)
            if prev_pts is None or len(prev_pts) < 4:
                motion_results.append((prev_idx, curr_idx, ["Stay"]))
                dynamic_masks.append(np.zeros_like(prev_gray, dtype=bool))
                continue
                
            curr_pts, status, err = cv2.calcOpticalFlowPyrLK(
                prev_gray, curr_gray, prev_pts, None, 
                winSize=(15, 15), maxLevel=2, 
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
            )
            
            good_prev = prev_pts[status == 1]
            good_curr = curr_pts[status == 1]
            
            if len(good_prev) < 4:
                motion_results.append((prev_idx, curr_idx, ["Stay"]))
                dynamic_masks.append(np.zeros_like(prev_gray, dtype=bool))
                continue
                
            # --- 2. Egomotion Analysis (4-DOF Partial Affine) ---
            M_affine, inliers = cv2.estimateAffinePartial2D(good_prev, good_curr, method=cv2.RANSAC)
            labels = []
            if M_affine is not None:
                tx, ty = M_affine[cite: 4], M_affine[cite: 1, 4]
                theta = np.arctan2(M_affine[cite: 1], M_affine)
                s = np.sqrt(M_affine**2 + M_affine[cite: 1]**2)
                
                # Thresholds
                if abs(s - 1.0) > 0.015: labels.append("Dolly In" if s > 1.0 else "Dolly Out")
                if abs(theta) > 0.01: labels.append("Roll Right" if theta > 0 else "Roll Left")
                if abs(tx) > 2.0 and abs(tx) >= abs(ty): labels.append("Pan Left" if tx > 0 else "Pan Right")
                if abs(ty) > 2.0 and abs(ty) > abs(tx): labels.append("Tilt Up" if ty > 0 else "Tilt Down")
            if not labels: labels.append("Stay")
            motion_results.append((prev_idx, curr_idx, labels))
            
            # --- 3. Dynamic Object Detection (8-DOF Homography Warp) ---
            H, mask = cv2.findHomography(good_prev, good_curr, cv2.RANSAC, 3.0)
            if H is not None:
                aligned_prev = cv2.warpPerspective(prev_gray, H, (curr_gray.shape[cite: 1], curr_gray.shape))
                diff = cv2.absdiff(curr_gray, aligned_prev)
                _, binary = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                
                # Morphology
                cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open, iterations=1)
                cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close, iterations=2)
                dynamic_masks.append(cleaned > 0) # Convert to boolean
            else:
                dynamic_masks.append(np.zeros_like(prev_gray, dtype=bool))
                
        return motion_results, dynamic_masks
```

**Sources:**
1. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7z1na1A1afDdqVc5xZTXtcM7ypj223_5IXzNhF2_ZuzbZDew6YCUXjg7l_bKdPMknb1hW_k53gCq280ynlM4GUo1qbeudOvfHHnVX5R6p_jnBtHrRXFnPqiMnExwdMlc55BXff689QNj7P4LohM1Esv0=)
2. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKe-r_2rQiimQXjiMfwtsf_zPgTAshWvcOyQ4n6Bb-pPaQKSbqypOVBas-Xnl1j9DV5_QMzqoRd3F72SPDi9qREddYntOFK2BhtftvMppdS8v4NJfk5wRvuXodyU796Up1Ig-sBIAqLd16PaG7XQ_NCIGgyo3Q-ZYiN65phlgGSSeYETaAUnl3SkfMwLgcVHQixNGfeJfb)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTifSLyP_en8753gBG5okLDDxunOYwWbO_rPKgZfq_T3yQpDtEhfYgo9jPqaekQ7DqHubMhIQxrPqNN1L5my0gbZ1ZadKTb5cHHZScmcSyZHbyhlB7FHgYyJTBhQff8eJZcrI=)
4. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhnh3k-yyA8RgYCkhWvMIyY-hRbnsbQ6zMZSEoJli3_uWU3vHvW0s3bInfNRuCGLRcfd8xNPE6oSfNAt7I-OePEQ9BqtdTw2tALt8fhWi7wDGLWNNDGsz0nycJx7JMsVRkc0wyeqJVF6LHL8J-VZwyLMYMoU-9DGEeVSCK2fIBJlbHYx4=)
5. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaR5kwv65lf3R9zQtkOJAdKisbnf3OIEdUvyn8UnPgkirbIQ3iDriVy2BxcYZ46uCpjuHHCL8Z_VpMfRmZNQFfD2jSKjG6LeORPmPh6FklHNTOnN-GBpdoa5KFxBRcwXB6obcCQiY5VMZKlksEJQAnKjgAC4VcCZiM7XUV5oCQOR_fe0VNf9s8ONnV6Yk=)
6. [velog.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNtadrWLjas7milNL5FXOjbfvob9O__z5RLycgfFIqrCDCtLQw8ukN5qxIiNk4P44fchDG07s0mbyIvU6QZswf0LEBNKNmvUJNAkqVT0yjCgy1x8rHx4QG95y35g==)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlIygtdlh5sLp4Rt1qVGmvbNKYmxVWFdOmv6kcXINGD7Up344YHVh2HkgXmrKFIK6Xcs5HFBTrgoezsnrvw8AbU3WcwSyj1toygoOxeycrQjimCn6yn7MDs3gfKKSgDFXWliqq4oUNHzrs9z2bwWgVGdjJBxMshFNbTU1KGvRubkEF3NtXi_feG5xz6NuUfRDu6ktAcf7Ik1oXt1PRSFSbIGmo6iJG0_zUZpEfyQ==)
8. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHE8ndQyX3IndXgfNe9H5rT0GMHNSDCFSpLh1QfKtfPNvGd9IRbxTo8ULFDbDvlS5ldA7HeO_nJqmfECpSufpCI9tc-bAQuYSzdxI3qcDR5ZBRnh0bVqr9IC1VvRyWxro_3ww==)
9. [datahacker.rs](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFpcBnd97jpGGZbcALh45M_EnRMiHfyEZDe6kpOdLZ0YzLJqMackp3Dt5qvSoVzJAkHAZRqSmjywfEub7tNsbD3ww_h6PlCwebP_zvWpJLm_Ka7UtADZebX-lcdOvXDNsd1AFDa16Tev79Icr65JxfQ4XvXZnLKQM3MJRM=)
10. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEm0oADeY4Xgii7lTIkXfKagC2dH_jP6JmTQY3RPpyicZ6nX6A5yeFFptAZmsqkWHViXgmqMrnYOLIwLzLzh-C6YDu6DCxesLKU8qhbAHp0neACbbOjc2TWpwnJgFQ_TximZJ9cxQ1O0I2T-K9yt0gbcbWJ4DgnM87Dlr19Ik3RarSPjNRiMA==)
11. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTm7kOuEZ5zR8kOiT69NSL1rYG0BoRBGSWN4U3n0WPmpd-EIlM86Ijc_ma2jZRjtetydOgZkXyUbHTm4JtzFyQ3qWwIdejQ1fDytiWxf6XGQJa7ycA1wlgz7IU4VspkKUEVGlihPgIom4iUEBD4qa-8S7IDJPOuv-4DVGriKWU4Nq5ULKcEMxfo1edd6a62Q==)
12. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH39SQ0oupAUIaRKJ5ZCfPf0tVo3p6hBJdDjrAEp35EVRWR1ROsaXp6FLJyA-RcoppotK2A2tX-LjJ2O4tENcBFMQJ2RYmhoiVSplJfS7S5JoDNc8SavZMjnmCdHgc29h55gtd8iph2mpsqmHCbWM7cUNfbVKVuxh84pAckYS_XaXRFZTF6)
13. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFul2mLnmsL8Zu3SNptlsklJeRLY6bpA4VVIyx-bAba1oxogA9g9L5UQeYmLykl4h12wlFsRE15ecRS3dzqgi-E8k4MmpbyRlbXZ4QqGrh6d6GoJJWxz0wNbOdwRipNtpjL)
14. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGEwphwnxqAfcr3Gq2Qi0yx9VQop21araiBItrMACuPkrkbL8kHCqm2u5xks1r3OgKX0ichlAD9-Uysbdzv3lMc6HWPfu23cmuD4YdCEAjHEuOlDaI5EKQrOLMqsnZk3cbHkrIQi3HJQLEoX_fvH72Yl8cUhQR1LL8Vj95tlJa-MRUwCzdEqwplP8Jj)
15. [nghiaho.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHvs1sAMnxRZ4Fv7roA6TJP2YcfYVoL7JUpbmZNQD0zNJFwxq2tk35sjZz_J8IJIbg3gWqE_Kk0p4rLAKJsMMMCbTjPaKet9iUnAAcQf3ngv0A=)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQErjrum8uyixgb2Icugsnx-OfCYa4eJqAo9WKvq4r7O0_mX8XLjxws3rEGwNiIA3bLRWXNpRSEgnW_dfTZl9BvyZCH6-5jJ0HHVHp5NFkLWgMQwfJnIBiG-eMU7taQ4EORlILAlaORD6jKWW2E7pMV-PvfbB7wwwS1ppAiN6HIGK4dqN073hy3D8rEP_YYD0vrufG-S_D77pw==)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdQZVinE21CPZT_roh0vyI4-LsWDoHtlBMpsZta4w72PLDeXKJ9RP5EiR_vW_roZVgM58-zcRUK380w6ZNJefZmcmSzbvYqINFIt-xIz84UB3qHoS3xOyLHa_EwD8vCrBGRojI6_lgbZRmJkQeRCM48mdqKHMNAXwIMeT6zLOdMDQq1qwW4yvLi_kzXFTQKoFxItkPpixeOFrqbuXdYo6B0sRR3LZdf5SI7Qsw)
18. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0juIN-GA-Loj-E1meRyNnzuATKQuEwnRo0EY1tqYVVUImmvh6MhfArrP8-cKfnbpe8I2LbZtrswugAMe11L2bNDUyjlgF2ADbpjqVUsnJ7ZIrTDUIW6LI-D9Bpe4S0dP8XwG3I9Sc-InBzhpO7dXIjEyLnsO3DAHKhAT2YEldlHdzp99wBp-f_CuHUMhZcc4trS5xVMJKaSzhsKHv5LpmiedBT4jxaW7xRQyu2xHwfTegjrrOraV6jJMFsmv5xyttdg==)
19. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHy1AC8D8OSeZP7W7bHDoKoz17zQqjojmBb7Vj-edQY45qCJL9Es--o7cYPlLplM9wzC2L8DEHpLxptE6cxkFELQ7AgJHXu6Kgo-21asow1Uz3mq-hxWJU5o8DTqRvpNsL2ILK5qXSAleoPENZ_jNL1aZhVweV8FFWnS_zohixvLQ==)
20. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnA67ByxGoYHfu6yeA70cxas1lzJtzqmqfZEzA7594ox61Bvf4ggkJ6iZ71-te9PT8AEB2RqRE_xxkowY1rVgir26ml5Gy7A6vv7m6brburEaLq2MmXOjIAQhlvP3Nl0BwEWS-nLL-tJCtg8rzDiEF87XXf7JIoVurAR1fN7rIfq5fdHesyL_jLZvvwz9AEs8T_m78_GbLI987GXOrSXVmwttnP5TB4zan-h0L1-Mc4Q==)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtB_Ss_lsla3j5iIMnaXbos3pEGRbCbj2uMXK0Xt_WduBBukq16Ihj2Rx3rcmhxcmQopbDuMWjvYhSmm4iyxpjdiG8orOkmkXnVQRuzWZDyMIQAfR17RdDDxpcwkp1vaOwnriaAmbMjA5dj6cX-pnkax5I5MvIfj8s_bfVXZjAWbQjDO8uCVU=)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFHIFTOiLcLGOC2h3JsdN6H26oGEKFDdy74XJDs1ZrpQJvCJklxAHdJ-9ivR0J2hXyrpsNd_QOaJ7wR_31vHK-bG_lA8od666K4xMj7rRIspWs40zssMIx6jqer0lJJBpKt34v66LMeQXYvzOcdusYvQOjshjanZE1-oNbEGYl-5W2140YbiUVap-oLHO2wR89YOFqk7mgupXIP6A==)
23. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGtk1BXXr0HfVtqvwHgHXV8knv8tHY0p6mo_m_KHGJq0E72HmONWV6GIpVlnA-nSjNj9DxN6itWxiFKpYdISQZzgQolSaydg_Wx37Q6AzT_nic8ej2BQatLwrVTufn4zdMnULQKq9PGgT7WZTQ_ryCG8oJk2D0Z2C7orazq7JIFcu63EqnOWJ63Uu1MGO-rLuBlb60=)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGy-YQFY5JV6vrHMPHLmfSUg5uIzC_rGNxrYgtkFh2YWbkpkqCaUtBxLG58mAG1LJ1DiB_dciM-MDhOzOFbKgIsEADLOpDVnz6WH88JWIXaj-em-TH8wOJbWmVgMG95q-ilHGenDSLTZT9iXAGva8hqnJkI4B_ZZIEUjA29coZCoNnE-W29R3Nve5LDeIfU2A==)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEvYBNeSfe_e9-K_h6SSO42Dt4bZp_mXXqR5k7XkoNpp2p4anQvUs37BRX1BviT0aqfqsRMV9vudUi4uLOrRV1rtpOghiVKtKGUiQ4670atlSulT-rmb3fkVApV-XbdHHQMsLUSK6pEOxthT4qIChPUNnPMXEpFRSNBguC0IqqBCMVd0cwAxlPMgnfhhbOIdCHzYavKBVr2HJaxHN-J3upXb2YmX_Ozsd6aw5-9pM8u)
26. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjYIDNqD8CcyzdTUst2d4XhGeSQnclWp9ccTzeYcyxFTwTgHnxRvpQpqSR8vCPGvjF7-BzVdZjm2ggBgfySulCLENDTP0AbUv8ss08aCS-MPQ081LTTNCrGWYBV3u0GvnNlwvDa2FG-w_UXI28AQHUUhRPf_SNthHXEno9JneJgWxNGMUxH34=)
27. [scipy-lectures.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgw1ZiGVrNom4UmfQ2_jg9yPfuCepUKl13qe2EL4dcW4uy1You2gEypjZd4d6sfqjI8h1DiiONz-8hglCCJgDywLsS2Nt84tbDv_XzmiwfnG67tguuy6Cx43Sx0-KZLzuQcwlZzzaBSsQpNB_Pzi47awh88BwA)
28. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG2OyE1kpCLH7JUzTzB3cAo32Cqry5R4uCuS8suh8Dxx7KHm8_zyQcJnVruSUWHugFdoNr0PSk079Zp-OUaSMQAPSmLWp5vRiuGrP8OsEnO8U8ZoRl1Ekei0uNNy3z7jUweore7Q89idgZG-ZXqm0WrDwVeSHczWj9WmjSY-Lze9La_Xq-4WNlC2qB5hzO1)
29. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuSWTPWI33G_JjSbdQ52eLlmu2fv-tymm9-63m2PBasGez6jzBLOsVojPqHenIjZyfoPYvRsxgg6vHaEQcCXVDgbHjSHg6orJOGtoX--r1-4pH8PczJeEMnZtuEBYwygk4P7cUz8QvEvohoVdCuZjoaX8zIw_bAJ8R4cwmYRyGVABZrWU2)
30. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_QjpW1jhAiydPSqFq1UJrqvbt8Hb1B5yh8XACbt37qyqelyZdBr1u54Rn-KbFk2D5gb6z1kJHAuKZLrTbKcBJd4Ffnxnp7Tsb8JmLCQgMdXji4D2upz9k33zz80QtexBJM5SrqooBm6BWVMXXp6NZPaHdWDpnXv_Wk3Inobn21YEIQ7BlqTlTBkUU_zkh3-NSpCVHD0LdXkn3)
31. [bilibili996.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjtWnVo5Bz3K-Ekba-sHLaMfdE4QaB77PN8eCzuYcARE5e5Ont6L4xlz0RHO2jbklRgaTsZLd6yJ08Y7bgTgLcm_zc_TmoqQYIY7b4HdlhccVSLUNhcszdQy-xGMUQLjeyDIgk6IeVJKzpJv9yhoBl_zfXwhL1ISd7Ke8pyxeHFuV3Wp0Jjot2u4Xxb8KKAbEljZA=)
