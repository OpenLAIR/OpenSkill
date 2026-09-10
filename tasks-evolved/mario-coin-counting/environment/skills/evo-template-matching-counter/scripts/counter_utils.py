import cv2
import numpy as np
import pandas as pd
import os


def load_template(template_path):
    """
    Load a template image in grayscale.
    
    Args:
        template_path: Path to the template image file
    
    Returns:
        Grayscale numpy array of the template
    """
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise ValueError(f"Failed to decode template: {template_path}")
    
    return template


def non_max_suppression(boxes, overlap_thresh=0.3):
    """
    Apply Non-Maximum Suppression to filter overlapping bounding boxes.
    Uses Malisiewicz et al. algorithm.
    
    Args:
        boxes: numpy array of shape (N, 4) with [x1, y1, x2, y2] format
        overlap_thresh: IoU threshold for suppression (default 0.3)
    
    Returns:
        Filtered numpy array of bounding boxes
    """
    if len(boxes) == 0:
        return np.array([])
    
    if boxes.dtype.kind == "i":
        boxes = boxes.astype("float")
    
    pick = []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)
    
    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)
        
        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])
        
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        
        overlap = (w * h) / area[idxs[:last]]
        
        idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlap_thresh)[0])))
    
    return boxes[pick].astype("int")


def count_objects_in_frame(frame_gray, template_gray, threshold=0.8, nms_overlap=0.3):
    """
    Count occurrences of a template object in a grayscale frame using
    cv2.matchTemplate with TM_CCOEFF_NORMED and Non-Maximum Suppression.
    
    Args:
        frame_gray: Grayscale frame image (2D numpy array)
        template_gray: Grayscale template image (2D numpy array)
        threshold: Confidence threshold for matches (0.8-0.95 for pixel art)
        nms_overlap: IoU overlap threshold for NMS (default 0.3)
    
    Returns:
        Integer count of detected objects
    """
    if frame_gray is None or template_gray is None:
        return 0
    
    template_h, template_w = template_gray.shape[:2]
    frame_h, frame_w = frame_gray.shape[:2]
    
    # Template must be smaller than frame
    if template_w > frame_w or template_h > frame_h:
        return 0
    
    # Perform template matching with normalized correlation coefficient
    result = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    
    # Find all locations exceeding threshold
    # np.where returns (y_coords, x_coords) - row, column order
    y_coords, x_coords = np.where(result >= threshold)
    
    if len(x_coords) == 0:
        return 0
    
    # Build bounding boxes [x1, y1, x2, y2]
    boxes = np.array([
        [x, y, x + template_w, y + template_h]
        for x, y in zip(x_coords, y_coords)
    ])
    
    # Apply NMS to deduplicate
    filtered_boxes = non_max_suppression(boxes, nms_overlap)
    
    return len(filtered_boxes)


def count_all_objects_in_frame(frame_path, templates_dict, threshold=0.8, nms_overlap=0.3):
    """
    Count all object types in a single frame.
    
    Args:
        frame_path: Path to grayscale frame image
        templates_dict: Dict mapping label -> grayscale template array
            e.g. {"coins": coin_template, "enemies": enemy_template, "turtles": turtle_template}
        threshold: Match confidence threshold
        nms_overlap: NMS overlap threshold
    
    Returns:
        Dict mapping label -> count
    """
    frame_gray = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
    if frame_gray is None:
        print(f"[WARN] Could not read frame: {frame_path}")
        return {label: 0 for label in templates_dict}
    
    counts = {}
    for label, template in templates_dict.items():
        counts[label] = count_objects_in_frame(frame_gray, template, threshold, nms_overlap)
    
    return counts


def generate_results_csv(frame_paths, templates_dict, output_csv, threshold=0.8, nms_overlap=0.3):
    """
    Process all keyframes, count objects, and write results to CSV.
    
    CSV columns: frame_id, coins, enemies, turtles
    frame_id is the full path like /root/keyframes_001.png
    
    Args:
        frame_paths: List of keyframe file paths in timeline order
        templates_dict: Dict mapping label -> grayscale template array
        output_csv: Path to output CSV file
        threshold: Match confidence threshold
        nms_overlap: NMS overlap threshold
    
    Returns:
        pandas DataFrame with results
    """
    results = []
    
    for frame_path in frame_paths:
        counts = count_all_objects_in_frame(frame_path, templates_dict, threshold, nms_overlap)
        row = {"frame_id": frame_path}
        row.update(counts)
        results.append(row)
    
    # Create DataFrame with specific column order
    df = pd.DataFrame(results, columns=["frame_id", "coins", "enemies", "turtles"])
    
    # Ensure integer types for count columns
    for col in ["coins", "enemies", "turtles"]:
        df[col] = df[col].fillna(0).astype(int)
    
    # Write CSV without index
    df.to_csv(output_csv, index=False)
    print(f"[INFO] Results saved to {output_csv} ({len(df)} rows)")
    
    return df
