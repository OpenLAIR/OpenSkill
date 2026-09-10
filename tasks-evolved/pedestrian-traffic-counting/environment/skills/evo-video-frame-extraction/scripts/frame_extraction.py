"""
Video Frame Extraction Module

Extracts and encodes sampled frames from video files using MoviePy 2.x.
Handles file discovery, temporal sampling, base64 JPEG encoding,
and proper resource cleanup to prevent memory leaks.
"""

import os
import glob
import io
import base64
import gc
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image
from moviepy import VideoFileClip


# Supported video file extensions
VALID_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}


def discover_video_files(directory: str) -> List[str]:
    """
    Discovers all video files in a directory and returns them in
    deterministic (lexicographically sorted) order.

    Args:
        directory: Path to the directory containing video files.

    Returns:
        Sorted list of absolute paths to video files.
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Directory does not exist: {directory}")

    all_files = []
    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path):
            _, ext = os.path.splitext(entry)
            if ext.lower() in VALID_VIDEO_EXTENSIONS:
                all_files.append(full_path)

    return sorted(all_files)


def extract_sampled_frames(
    video_path: str,
    interval_seconds: float = 3.0,
    max_frames: int = 10
) -> List[np.ndarray]:
    """
    Extracts frames from a video at a specified interval using MoviePy 2.x.

    Frames are sampled at regular intervals starting from t=0. If the total
    number of sampled frames exceeds max_frames, frames are evenly subsampled
    to stay within the limit.

    Args:
        video_path: Path to the video file.
        interval_seconds: Time between frame samples in seconds.
        max_frames: Maximum number of frames to extract.

    Returns:
        List of RGB NumPy arrays (H x W x 3, dtype uint8).
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    clip = None
    frames = []

    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration

        if duration is None or duration <= 0:
            return frames

        # Generate timestamps at the specified interval
        timestamps = np.arange(0, duration, interval_seconds)

        # If we have more timestamps than max_frames, subsample evenly
        if len(timestamps) > max_frames:
            indices = np.linspace(0, len(timestamps) - 1, max_frames, dtype=int)
            timestamps = timestamps[indices]

        for t in timestamps:
            try:
                # get_frame returns an HxWx3 RGB NumPy array
                frame_array = clip.get_frame(float(t))
                frames.append(frame_array)
            except Exception as e:
                print(f"Warning: Could not extract frame at t={t:.1f}s from {video_path}: {e}")
                continue

    except Exception as e:
        print(f"Error processing video {video_path}: {e}")
    finally:
        # Critical: Release MoviePy resources to prevent memory leaks
        if clip is not None:
            try:
                clip.close()
            except Exception:
                pass
        # Help garbage collector reclaim memory
        gc.collect()

    return frames


def numpy_to_base64_jpeg(
    frame_array: np.ndarray,
    quality: int = 80,
    max_size: Tuple[int, int] = (1024, 1024)
) -> str:
    """
    Converts a NumPy RGB array to a base64-encoded JPEG string.

    The image is optionally resized to fit within max_size while maintaining
    aspect ratio, then compressed as JPEG and base64-encoded.

    Args:
        frame_array: RGB NumPy array (H x W x 3).
        quality: JPEG compression quality (1-100).
        max_size: Maximum (width, height) for the output image.

    Returns:
        Base64-encoded JPEG string.
    """
    # Convert NumPy array to PIL Image (MoviePy gives RGB, PIL expects RGB)
    img = Image.fromarray(frame_array.astype(np.uint8))

    # Resize if larger than max_size while maintaining aspect ratio
    if max_size:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Compress to JPEG in memory
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)

    # Encode to base64 string
    b64_bytes = base64.b64encode(buffer.getvalue())
    return b64_bytes.decode("utf-8")


def extract_and_encode_frames(
    video_path: str,
    interval_seconds: float = 3.0,
    max_frames: int = 10,
    jpeg_quality: int = 80,
    max_size: Tuple[int, int] = (1024, 1024)
) -> List[str]:
    """
    Convenience function that extracts frames from a video and encodes
    them as base64 JPEG strings in one step.

    This combines extract_sampled_frames and numpy_to_base64_jpeg,
    providing a simple interface for preparing video frames for
    vision LLM API consumption.

    Args:
        video_path: Path to the video file.
        interval_seconds: Time between frame samples in seconds.
        max_frames: Maximum number of frames to extract.
        jpeg_quality: JPEG compression quality (1-100).
        max_size: Maximum (width, height) for output images.

    Returns:
        List of base64-encoded JPEG strings.
    """
    # Extract raw frames
    raw_frames = extract_sampled_frames(video_path, interval_seconds, max_frames)

    # Encode each frame to base64 JPEG
    encoded_frames = []
    for frame in raw_frames:
        try:
            b64_str = numpy_to_base64_jpeg(frame, quality=jpeg_quality, max_size=max_size)
            encoded_frames.append(b64_str)
        except Exception as e:
            print(f"Warning: Could not encode frame: {e}")
            continue

    # Free raw frame memory
    del raw_frames
    gc.collect()

    return encoded_frames


if __name__ == "__main__":
    import sys

    # Simple test: extract frames from a video file
    if len(sys.argv) < 2:
        print("Usage: python frame_extraction.py <video_path_or_directory>")
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isdir(target):
        videos = discover_video_files(target)
        print(f"Found {len(videos)} video files:")
        for v in videos:
            print(f"  {v}")
    else:
        videos = [target]

    for video_path in videos:
        print(f"\nProcessing: {video_path}")
        frames = extract_and_encode_frames(video_path, interval_seconds=3.0, max_frames=10)
        print(f"  Extracted {len(frames)} frames")
        if frames:
            print(f"  First frame base64 length: {len(frames[0])} chars")
