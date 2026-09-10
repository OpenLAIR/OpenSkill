# Domain Reference for evo-video-egomotion-analysis

**Responsibility**: Frame extraction at target FPS using sequential reading, sparse optical flow (goodFeaturesToTrack + calcOpticalFlowPyrLK), estimateAffinePartial2D for global motion, affine matrix decomposition into pan/tilt/dolly/roll labels with thresholds, warpAffine-based motion compensation, absdiff-based foreground detection, morphological cleanup, and connected component filtering

**Key functions to implement**: extract_sampled_frames, compute_egomotion, classify_camera_motion, detect_dynamic_objects, run_full_pipeline

---

## 1. Video Frame Extraction and Preprocessing


The foundation of any video analysis pipeline is reliable frame extraction. A common requirement is downsampling a video's native framerate to a computationally feasible target Frames Per Second (FPS).

## 2. Camera Egomotion and Motion Classification


Egomotion refers to the 3D motion of a camera within an environment, projected onto a 2D image plane. To classify camera motion without Deep Learning, we must compute the dense or sparse optical flow between consecutive frames and resolve these local vectors into a global rigid or affine transformation.

## 3. Dynamic Object Detection/Segmentation without Deep Learning


Independent object detection requires isolating pixels that deviate from the calculated global motion model.

## 6. Monolithic Integration: The Python Utility Class


Below is the exhaustive, production-ready utility class synthesizing all aforementioned principles into a single, cohesive module without deep learning dependencies.

```python
import cv2
import numpy as np
import json
import os

class VideoEgomotionAndSegmentation:
    """
    Pure OpenCV/NumPy utility for Camera Egomotion Analysis and Dynamic Object Segmentation.
    """
    def __init__(self, video_path, target_fps=6):
        self.video_path = video_path
        self.target_fps = target_fps
        self.frames = []
        self.gray_frames = []
        self.native_fps = 0
        self.dimensions = (0, 0)
        self.motion_labels = {}
        self.sparse_masks = {}

    def extract_frames(self):
        """Extracts frames at a specific FPS sample rate using sequential reading."""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError("Failed to open video source.")

        self.native_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.dimensions = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )

        step = self.native_fps / self.target_fps
        target_indices = set(int(np.round(i * step)) for i in range(int(total_frames / step)))

        current_idx = 0
        while True:
            ret = cap.grab()
            if not ret:
                break
            if current_idx in target_indices:
                ret, frame = cap.retrieve()
                if ret:
                    self.frames.append(frame)
                    # Convert to grayscale for optical flow
                    self.gray_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            current_idx += 1
        cap.release()

    def process_pipeline(self):
        """Calculates egomotion and isolates dynamic objects between consecutive frames."""
        num_frames = len(self.gray_frames)
        
        # GoodFeaturesToTrack parameters
        feature_params = dict(maxCorners=300, qualityLevel=0.1, minDistance=30, blockSize=7)
        # Lucas Kanade optical flow parameters
        lk_params = dict(winSize=(21, 21), maxLevel=3, 
                         criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

        for i in range(num_frames - 1):
            prev_gray = self.gray_frames[i]
            curr_gray = self.gray_frames[i+1]
            
            # 1. Feature Matching for Egomotion
            prev_pts = cv2.goodFeaturesToTrack(prev_gray, mask=None, **feature_params)
            if prev_pts is None:
                self.motion_labels[f"{i}->{i+1}"] = ["Stay"]
                continue

            curr_pts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None, **lk_params)
            
            # Filter good points
            good_prev = prev_pts[status == 1]
            good_curr = curr_pts[status == 1]
            
            if len(good_prev) < 4: # Minimum required for Affine 2D
                self.motion_labels[f"{i}->{i+1}"] = ["Stay"]
                continue

            # 2. Egomotion Estimation (4-DOF Similarity Transform)
            M, inliers = cv2.estimateAffinePartial2D(good_prev, good_curr, method=cv2.RANSAC)
            
            labels = []
            if M is not None:
                # 3. Decompose Matrix into Pan, Tilt, Dolly, Roll
                dx = M[cite: 2]
                dy = M[cite: 1, 2]
                s = np.sqrt(M**2 + M[cite: 1]**2)
                theta = np.arctan2(M[cite: 1], M) * (180 / np.pi)

                if dx > 1.5: labels.append("Pan Left")
                elif dx < -1.5: labels.append("Pan Right")
                
                if dy > 1.5: labels.append("Tilt Up")
                elif dy < -1.5: labels.append("Tilt Down")
                
                if s > 1.015: labels.append("Dolly In")
                elif s < 0.985: labels.append("Dolly Out")
                
                if theta > 0.5: labels.append("Roll Clockwise")
                elif theta < -0.5: labels.append("Roll Counter-Clockwise")
                
                if not labels: labels.append("Stay")
            else:
                M = np.array([[cite: 1], [cite: 1]], dtype=np.float32)
                labels.append("Stay")
                
            self.motion_labels[f"{i}->{i+1}"] = labels

            # 4. Dynamic Object Segmentation (Background Subtraction)
            # Warp the previous frame to match the current frame's perspective
            warped_prev = cv2.warpAffine(prev_gray, M, self.dimensions, 
                                         flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            
            # Compute Absolute Difference to prevent uint8 overflow
            diff = cv2.absdiff(warped_prev, curr_gray)
            
            # Thresholding
            _, binary_mask = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            
            # Mask out the shifted borders caused by BORDER_CONSTANT warping
            border_mask = cv2.warpAffine(np.ones_like(prev_gray)*255, M, self.dimensions, borderValue=0)
            binary_mask = cv2.bitwise_and(binary_mask, border_mask)

            # Morphological Cleanup
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel, iterations=1)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

            # Connected Components Filter (Remove blobs area < 150)
            num_labels, comp_labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask, 8, cv2.CV_32S)
            clean_mask = np.zeros_like(binary_mask, dtype=bool)
            
            for label_id in range(1, num_labels): # Skip 0 (background)
                area = stats[label_id, cv2.CC_STAT_AREA]
                if area > 150:
                    clean_mask[comp_labels == label_id] = True

            # 5. Convert to CSR and store
            data, indices, indptr, shape = self._dense_to_csr(clean_mask)
            self.sparse_masks[f"f_{i}_data"] = data
            self.sparse_masks[f"f_{i}_indices"] = indices
            self.sparse_masks[f"f_{i}_indptr"] = indptr
            self.sparse_masks[f"f_{i}_shape"] = np.array(shape, dtype=np.int32)

    def _dense_to_csr(self, mask):
        """Pure NumPy conversion of dense 2D boolean mask to CSR format."""
        rows, cols = np.nonzero(mask)
        data = np.ones(len(rows), dtype=bool)
        indices = cols.astype(np.int32)
        counts = np.bincount(rows, minlength=mask.shape)
        indptr = np.zeros(mask.shape + 1, dtype=np.int32)
        np.cumsum(counts, out=indptr[1:])
        return data, indices, indptr, mask.shape

    def export_results(self, json_path="motion.json", npz_path="masks.npz"):
        """Saves JSON labels and NPZ compressed masks."""
        with open(json_path, 'w') as f:
            json.dump(self.motion_labels, f, indent=4)
        np.savez(npz_path, **self.sparse_masks)