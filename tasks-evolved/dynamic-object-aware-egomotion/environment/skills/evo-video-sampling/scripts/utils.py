import cv2
import numpy as np


def sample_video_frames(video_path, target_fps=6):
    """
    Safely extract frames from an MP4 file at a target FPS using sequential reading.
    Returns grayscale frames to avoid BGR issues downstream.
    
    Returns:
        sampled_frames: list of np.uint8 grayscale 2D arrays
        frame_indices: list of original frame indices
        original_fps: float, the video's native FPS
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video: {video_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    if original_fps <= 0:
        original_fps = 30.0  # Fallback heuristic

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
            # Convert BGR to grayscale immediately
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sampled_frames.append(gray)
            frame_indices.append(current_frame_idx)

        current_frame_idx += 1

    cap.release()
    return sampled_frames, frame_indices, original_fps
