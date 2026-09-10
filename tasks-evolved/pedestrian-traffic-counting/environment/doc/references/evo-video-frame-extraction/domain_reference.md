# Domain Reference for evo-video-frame-extraction

**Responsibility**: Video file discovery, frame extraction at configurable intervals, NumPy-to-base64-JPEG conversion, and MoviePy resource management

**Key functions to implement**: discover_video_files, extract_sampled_frames, numpy_to_base64_jpeg, extract_and_encode_frames

---

## 2. File Discovery and Deterministic Processing


Before video extraction or AI inference can occur, a robust system must possess a reliable mechanism for discovering and ingesting video files. In academic and forensic contexts, data processing pipelines must be strictly deterministic; running the same script on the same directory twice must yield the exact same order of operations and output structure.

## 3. Video Frame Extraction with MoviePy 2.1.2


MoviePy is a highly versatile Python library for video editing and manipulation. Operating as a high-level wrapper around the ubiquitous FFmpeg multimedia framework, MoviePy abstracts the complexities of video decoding into accessible Python objects (primarily relying on NumPy arrays).