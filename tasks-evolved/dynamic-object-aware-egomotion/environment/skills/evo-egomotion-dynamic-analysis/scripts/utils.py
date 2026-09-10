import cv2
import numpy as np


def compute_egomotion_labels(prev_gray, curr_gray, th_trans=2.0, th_scale=0.015, th_rot=0.01):
    """
    Compute egomotion labels between two consecutive grayscale frames.
    Uses sparse optical flow (Lucas-Kanade) + partial affine 2D estimation.
    
    Returns:
        labels: list of strings from {Stay, Dolly In, Dolly Out, Pan Left, Pan Right,
                Tilt Up, Tilt Down, Roll Left, Roll Right}
        good_prev: matched source points (for reuse in dynamic detection)
        good_curr: matched destination points
    """
    # Detect features in previous frame
    prev_pts = cv2.goodFeaturesToTrack(
        prev_gray, maxCorners=300, qualityLevel=0.01,
        minDistance=30, blockSize=3
    )
    
    if prev_pts is None or len(prev_pts) < 4:
        return ["Stay"], None, None
    
    # Track features to current frame
    curr_pts, status, err = cv2.calcOpticalFlowPyrLK(
        prev_gray, curr_gray, prev_pts, None,
        winSize=(15, 15), maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
    )
    
    # Filter by status
    good_prev = prev_pts[status.flatten() == 1]
    good_curr = curr_pts[status.flatten() == 1]
    
    if len(good_prev) < 4:
        return ["Stay"], None, None
    
    # Estimate partial affine (4-DOF: scale, rotation, tx, ty)
    M, inliers = cv2.estimateAffinePartial2D(
        good_prev, good_curr, method=cv2.RANSAC
    )
    
    if M is None:
        return ["Stay"], good_prev, good_curr
    
    # Decompose the 2x3 matrix
    tx = M[0, 2]
    ty = M[1, 2]
    theta = np.arctan2(M[1, 0], M[0, 0])
    s = np.sqrt(M[0, 0]**2 + M[1, 0]**2)
    
    labels = []
    
    # Dolly (scale)
    if abs(s - 1.0) > th_scale:
        labels.append("Dolly In" if s > 1.0 else "Dolly Out")
    
    # Roll (rotation)
    if abs(theta) > th_rot:
        labels.append("Roll Right" if theta > 0 else "Roll Left")
    
    # Pan (horizontal translation) - only if |tx| > |ty|
    if abs(tx) > th_trans and abs(tx) >= abs(ty):
        labels.append("Pan Left" if tx > 0 else "Pan Right")
    
    # Tilt (vertical translation) - only if |ty| > |tx|
    if abs(ty) > th_trans and abs(ty) > abs(tx):
        labels.append("Tilt Up" if ty > 0 else "Tilt Down")
    
    if not labels:
        labels.append("Stay")
    
    return labels, good_prev, good_curr


def detect_dynamic_objects(prev_gray, curr_gray, good_prev, good_curr):
    """
    Detect dynamic objects by homography-based motion compensation + frame differencing.
    
    Returns:
        mask: boolean 2D array (H, W) where True = dynamic object pixel
    """
    h, w = curr_gray.shape[:2]
    
    if good_prev is None or good_curr is None or len(good_prev) < 4:
        return np.zeros((h, w), dtype=bool)
    
    # Estimate homography for motion compensation
    H, hmask = cv2.findHomography(good_prev, good_curr, cv2.RANSAC, 3.0)
    
    if H is None:
        return np.zeros((h, w), dtype=bool)
    
    # Warp previous frame to align with current frame
    aligned_prev = cv2.warpPerspective(prev_gray, H, (w, h))
    
    # Compute absolute difference (avoids uint8 underflow)
    diff = cv2.absdiff(curr_gray, aligned_prev)
    
    # Threshold to binary
    _, binary = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    
    # Morphological cleanup
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open, iterations=1)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close, iterations=2)
    
    return cleaned > 0  # Convert to boolean


def analyze_frame_pairs(frames):
    """
    Analyze all consecutive frame pairs for egomotion and dynamic objects.
    
    Args:
        frames: list of grayscale np.uint8 2D arrays
    
    Returns:
        motion_labels: list of (sample_idx_prev, sample_idx_curr, labels_list)
        dynamic_masks: list of boolean 2D arrays
    """
    motion_labels = []
    dynamic_masks = []
    
    for i in range(1, len(frames)):
        prev_gray = frames[i - 1]
        curr_gray = frames[i]
        
        # Egomotion
        labels, good_prev, good_curr = compute_egomotion_labels(prev_gray, curr_gray)
        motion_labels.append((i - 1, i, labels))
        
        # Dynamic objects
        mask = detect_dynamic_objects(prev_gray, curr_gray, good_prev, good_curr)
        dynamic_masks.append(mask)
    
    return motion_labels, dynamic_masks
