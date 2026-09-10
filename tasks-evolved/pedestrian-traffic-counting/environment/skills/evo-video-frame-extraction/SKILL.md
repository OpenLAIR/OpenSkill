---
name: evo-video-frame-extraction
description: Extract and encode sampled frames from video files for vision AI analysis. Use when you need to process surveillance or other video files by extracting frames at regular intervals, converting them to base64-encoded JPEG images suitable for sending to vision LLM APIs. Handles video file discovery, temporal sampling, MoviePy 2.x resource management, and memory-safe batch processing.
---

# Video Frame Extraction

Extracts sampled frames from video files using MoviePy 2.x and encodes them as base64 JPEG strings for downstream vision API consumption.

## When to Use

- Processing surveillance footage for AI analysis
- Extracting representative frames from video files at configurable intervals
- Preparing video frames for vision LLM APIs (OpenAI, Gemini, etc.)
- Batch processing multiple video files in a directory

## Core Functions

The skill provides these functions in `scripts/frame_extraction.py`:

### `discover_video_files(directory: str) -> list[str]`
Finds all video files (mp4, avi, mov, mkv) in a directory and returns them in deterministic sorted order.

### `extract_sampled_frames(video_path: str, interval_seconds: float = 3.0, max_frames: int = 10) -> list[np.ndarray]`
Extracts frames from a video at the specified interval. Returns a list of RGB NumPy arrays. Properly closes MoviePy resources to prevent memory leaks.

### `numpy_to_base64_jpeg(frame_array: np.ndarray, quality: int = 80, max_size: tuple = (1024, 1024)) -> str`
Converts a NumPy RGB array to a base64-encoded JPEG string. Resizes large frames to fit within max_size to reduce payload size.

### `extract_and_encode_frames(video_path: str, interval_seconds: float = 3.0, max_frames: int = 10, jpeg_quality: int = 80) -> list[str]`
Convenience function that combines extraction and encoding. Returns a list of base64 JPEG strings ready for API consumption.

## Usage Example

```python
from scripts.frame_extraction import discover_video_files, extract_and_encode_frames

# Find all videos in a directory
videos = discover_video_files("/path/to/videos")

# Extract and encode frames from each video
for video_path in videos:
    b64_frames = extract_and_encode_frames(video_path, interval_seconds=3.0, max_frames=10)
    # Send b64_frames to a vision API...
```

## Important Notes

- This skill uses MoviePy 2.x (not 1.x). The import is `from moviepy import VideoFileClip` (not `from moviepy.editor`).
- Always ensure video resources are closed after use to prevent memory leaks and zombie FFmpeg processes.
- Frames are extracted in RGB format and converted to JPEG. No BGR conversion is needed.
- The `detail="low"` setting on OpenAI's API resizes to 512x512 internally, so pre-resizing to 1024x1024 is a good balance between quality and payload size.
