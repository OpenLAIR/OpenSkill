# Domain Reference for evo-video-sampling

**Responsibility**: Video decoding, FPS calculation, sequential frame sampling, BGR-to-grayscale conversion. No analysis logic.

**Key functions to implement**: sample_video_frames

---

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

### 6.1 BGR vs RGB Color Space Constraints

OpenCV decodes video via `VideoCapture` into the BGR color space by default. When performing optical flow calculations with `calcOpticalFlowFarneback` or `calcOpticalFlowPyrLK`, the algorithm calculates gradients and assumes a single-channel spatial intensity gradient [cite: 7, 8, 31]. Passing a 3-channel BGR/RGB image to these functions will invoke cryptic C++ assertion failures indicating dimension mismatches. Explicit invocation of `cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)` is mandatory [cite: 4, 6, 7].