---
name: evo-egomotion-dynamic-analysis
description: For consecutive sampled frame pairs, computes sparse optical flow, estimates camera egomotion via partial affine transform, and detects dynamic objects via homography-based motion compensation and frame differencing.
---

# evo-egomotion-dynamic-analysis

Analyzes consecutive grayscale frame pairs to classify camera motion and detect dynamic objects.

## Key Functions

- `compute_egomotion_labels(prev_gray, curr_gray, th_trans=2.0, th_scale=0.015, th_rot=0.01)`
  Returns `(labels, good_prev, good_curr)` where labels is a list of motion strings.

- `detect_dynamic_objects(prev_gray, curr_gray, good_prev, good_curr)`
  Returns boolean mask (H,W) where True = dynamic pixel.

- `analyze_frame_pairs(frames)`
  Processes all consecutive pairs. Returns `(motion_labels, dynamic_masks)`.
  motion_labels: list of (sample_idx_prev, sample_idx_curr, labels_list)
  dynamic_masks: list of boolean 2D arrays

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-egomotion-dynamic-analysis/scripts')
from utils import analyze_frame_pairs

motion_labels, dynamic_masks = analyze_frame_pairs(grayscale_frames)
```

## Motion Classification Rules

- **Dolly In/Out**: scale deviation > 0.015 from 1.0
- **Roll Left/Right**: rotation > 0.01 rad
- **Pan Left/Right**: |tx| > 2.0 px AND |tx| >= |ty|. Positive tx = Pan Left.
- **Tilt Up/Down**: |ty| > 2.0 px AND |ty| > |tx|. Positive ty = Tilt Up.
- **Stay**: if no other label triggered

## Pipeline

1. Shi-Tomasi corners (goodFeaturesToTrack, maxCorners=300)
2. Lucas-Kanade optical flow (calcOpticalFlowPyrLK)
3. estimateAffinePartial2D with RANSAC for egomotion
4. findHomography with RANSAC for motion compensation
5. warpPerspective + absdiff + threshold(25) for dynamic mask
6. Morphological open(3x3) + close(7x7) cleanup
