import cv2
import os
import glob


def get_video_metadata(video_path):
    """
    Extract metadata from a video file.
    Returns dict with fps, frame_count, width, height, duration_seconds.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    
    metadata = {
        'fps': cap.get(cv2.CAP_PROP_FPS),
        'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    metadata['duration_seconds'] = metadata['frame_count'] / metadata['fps'] if metadata['fps'] > 0 else 0
    cap.release()
    return metadata


def extract_keyframes(video_path, output_dir, sample_interval_seconds=1.0, name_format="keyframes_{:03d}.png"):
    """
    Extract keyframes from video using uniform temporal sampling.
    
    Args:
        video_path: Path to the MP4 video file
        output_dir: Directory to save keyframe images (e.g., '/root')
        sample_interval_seconds: Extract 1 frame every N seconds (default 1.0)
        name_format: Format string for keyframe filenames with {:03d} placeholder
    
    Returns:
        List of saved keyframe file paths in timeline order
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = int(fps * sample_interval_seconds)
    
    if frame_interval < 1:
        frame_interval = 1
    
    os.makedirs(output_dir, exist_ok=True)
    
    saved_paths = []
    frame_idx = 0
    keyframe_counter = 1  # 1-based counter for naming
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % frame_interval == 0:
            filename = name_format.format(keyframe_counter)
            filepath = os.path.join(output_dir, filename)
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            saved_paths.append(filepath)
            keyframe_counter += 1
        
        frame_idx += 1
    
    cap.release()
    print(f"[INFO] Extracted {len(saved_paths)} keyframes from {total_frames} total frames (interval={frame_interval})")
    return saved_paths


def convert_frames_to_grayscale(frame_paths):
    """
    Convert a list of image files from BGR/RGB to grayscale IN-PLACE.
    Reads each image, converts to grayscale, and overwrites the original file.
    
    Args:
        frame_paths: List of file paths to convert
    
    Returns:
        List of successfully converted file paths
    """
    converted = []
    for filepath in frame_paths:
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[WARN] Could not read: {filepath}")
            continue
        cv2.imwrite(filepath, img)
        converted.append(filepath)
    
    print(f"[INFO] Converted {len(converted)} frames to grayscale in-place")
    return converted
