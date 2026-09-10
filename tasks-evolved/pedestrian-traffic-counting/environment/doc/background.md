# Comprehensive Analysis of Video Pedestrian Counting Systems Using Python, Vision LLMs, and Multi-Frame Analysis

### Executive Summary: Key Findings

*   **Vision Language Model Capabilities:** Evidence leans toward Vision Language Models (VLMs) such as GPT-4o and Gemini 2.0 being highly capable of interpreting multi-frame sequences, though research suggests they may occasionally struggle with accurate spatial tracking across disjointed frames without structured prompting.
*   **Library Transitions and Paradigm Shifts:** It appears highly likely that migrating to MoviePy 2.x and the newly unified `google-genai` SDK requires significant refactoring from older tutorials, as both ecosystems have introduced major breaking changes and deprecated legacy modules.
*   **Data Integrity and State Management:** Best practices suggest that actively managing video file resources (explicitly closing subprocesses) and enforcing integer-type casting on LLM outputs are critical steps for preventing memory leaks and ensuring downstream data integrity in Excel reports.

### Introduction to VLM-Based Video Analysis
The integration of generative artificial intelligence into computer vision tasks has transformed how developers approach surveillance and pedestrian counting. Instead of relying entirely on heavily fine-tuned, specialized Convolutional Neural Networks (CNNs) like YOLO or Faster R-CNN, modern architectures increasingly leverage Vision Language Models (VLMs). These models combine natural language understanding with deep visual feature extraction, allowing developers to query video content using plain text prompts.

### Navigating Evolving Python Ecosystems
Building a robust pedestrian counting utility module requires coordinating multiple specialized Python packages. Recently, several of these core libraries have undergone massive architectural shifts. MoviePy recently transitioned to a 2.x architecture, stripping away legacy Python 2 support and changing how effects and internal arrays are managed. Similarly, Google has deprecated its legacy generative AI SDK in favor of a unified `google-genai` package. Understanding these shifting dependencies is crucial for building maintainable, future-proof modules.

---

## 1. Introduction and Methodological Framework

The automated analysis of surveillance footage for pedestrian tracking and counting is a foundational task in urban planning, security, and retail analytics. Historically, this required complex pipelines involving object detection models, multi-object tracking (MOT) algorithms (such as DeepSORT), and careful threshold tuning. The advent of massive Vision Language Models (VLMs)—specifically OpenAI's GPT-4o and Google's Gemini series—has introduced a novel paradigm: reasoning-based visual analysis.

By passing a sequence of temporally spaced video frames to a VLM, a system can theoretically ask the model to infer the number of unique individuals present, leveraging the model's zero-shot reasoning capabilities to account for occlusion, overlapping trajectories, and varying camera angles. 

This report comprehensively details the construction of a Python-based utility module to perform this exact task. The architecture relies on specific, strictly versioned packages: `moviepy` (2.1.2) for frame extraction, `openai` (2.15.0) and `google-genai` (1.59.0) for VLM inference, and `pandas` (2.3.3) paired with `openpyxl` (3.1.5) for deterministic reporting. The subsequent sections provide an exhaustive academic and technical breakdown of each component, exploring theoretical underpinnings, API mechanics, optimization strategies, and critical failure modes.

## 2. File Discovery and Deterministic Processing

Before video extraction or AI inference can occur, a robust system must possess a reliable mechanism for discovering and ingesting video files. In academic and forensic contexts, data processing pipelines must be strictly deterministic; running the same script on the same directory twice must yield the exact same order of operations and output structure.

### Python File Discovery Patterns

The standard Python library provides two primary modules for file discovery: `os` and `glob`. 

Using `os.listdir()` returns a list of all files in a directory, but it is fundamentally non-deterministic. The order of the returned files depends on the underlying operating system's file system structure (e.g., NTFS, ext4, APFS) and is virtually guaranteed to vary across different machines or after file modifications. 

To ensure a deterministic output order, the discovered files must be explicitly sorted. The `glob` module is generally preferred when filtering by specific file extensions, as it supports Unix-style pathname pattern expansion.

```python
import glob
import os

def discover_video_files(directory_path: str) -> list[str]:
    """
    Discovers all MP4, AVI, and MOV files in a directory deterministically.
    """
    search_pattern = os.path.join(directory_path, "*.*")
    all_files = glob.glob(search_pattern)
    
    # Filter for standard surveillance video formats
    valid_extensions = {'.mp4', '.avi', '.mov', '.mkv'}
    video_files = [
        f for f in all_files 
        if os.path.splitext(f)[cite: 1].lower() in valid_extensions
    ]
    
    # Strict lexicographical sorting for deterministic processing
    return sorted(video_files)
```

For environments where files are named with unpadded numbers (e.g., `cam_1.mp4`, `cam_10.mp4`, `cam_2.mp4`), standard lexicographical sorting will fail to order them intuitively. In such edge cases, utilizing a natural sorting algorithm (e.g., via the `natsort` package) or implementing a custom regex-based sort key is highly recommended to maintain logical processing timelines.

## 3. Video Frame Extraction with MoviePy 2.1.2

MoviePy is a highly versatile Python library for video editing and manipulation. Operating as a high-level wrapper around the ubiquitous FFmpeg multimedia framework, MoviePy abstracts the complexities of video decoding into accessible Python objects (primarily relying on NumPy arrays).

### The Evolution from MoviePy 1.x to 2.x

The release of MoviePy 2.0 introduced substantial, breaking changes to the library's architecture, driven by a need to modernize the codebase, eliminate technical debt, and drop support for end-of-life Python versions (2.7, 3.4, 3.5) [cite: 1, 2]. 

Key architectural shifts in MoviePy 2.x include:
1. **Object-Oriented Effects:** In 1.x, video effects were simple functional manipulations. In 2.x, effects are encapsulated within classes inheriting from an `Effect` abstract base class, improving modularity and reusability [cite: 1].
2. **Transparency and Compositing Overhaul:** Extensive refactoring occurred within the FFmpeg reader and writer specifically to address long-standing bugs regarding alpha-channel transparency and video compositing (`CompositeVideoClip`) [cite: 2, 3].
3. **Strict Boundaries:** Subclipping operations that fall outside the actual boundaries of the video clip now raise explicit exceptions rather than silently failing or returning empty frames [cite: 4].
4. **Deprecations Removed:** All methods and parameters previously marked as deprecated in 1.x were entirely removed in the 2.x releases [cite: 2].

### Frame Extraction API Mechanics

To extract frames for VLM analysis, the primary class utilized is `VideoFileClip`. When initialized, it spawns a background FFmpeg subprocess that reads the video header, calculates metadata, and opens a pipe to stream uncompressed frame data.

The relevant attributes—`.duration` (representing the video length in seconds as a float) and `.fps` (frames per second)—remain valid and essential in version 2.1.2.

To extract frames, developers generally choose between two methods:
*   `.iter_frames()`: Yields every single frame (or frames at a specified internal FPS) sequentially. This is highly efficient for continuous processing but overkill if only a few sampled frames are needed.
*   `.get_frame(t)`: Returns a specific frame at time `t` (in seconds). This method utilizes FFmpeg's seeking capabilities to jump to the closest keyframe and decode forward, returning the exact requested RGB NumPy array [cite: 5, 6].

For a pedestrian counting module where we wish to sample frames at a specific interval (e.g., every 5 seconds), `.get_frame(t)` combined with `numpy.arange` is the optimal strategy.

```python
import numpy as np
from moviepy import VideoFileClip
from typing import List

def extract_sampled_frames(video_path: str, interval_seconds: float) -> List[np.ndarray]:
    """
    Extracts frames from a video at a specified interval using MoviePy 2.1.2.
    """
    clip = None
    frames = []
    
    try:
        clip = VideoFileClip(video_path)
        video_duration = clip.duration
        
        # Generate timestamps for frame extraction
        timestamps = np.arange(0, video_duration, interval_seconds)
        
        for t in timestamps:
            # get_frame returns a HxWx3 NumPy array in RGB format
            frame_array = clip.get_frame(t)
            frames.append(frame_array)
            
    except Exception as e:
        print(f"Error processing video {video_path}: {e}")
    finally:
        # Critical: Release resources to prevent memory leaks and zombie FFmpeg processes
        if clip is not None:
            clip.close()
            
    return frames
```

### Memory Management and Resource Deallocation

A critical pitfall when processing multiple surveillance videos is memory mismanagement. Each instantiated `VideoFileClip` opens a piped subprocess to FFmpeg and loads audio/video stream buffers into RAM. Failing to explicitly close these resources will result in memory leaks, eventually causing the host machine to throw an Out-Of-Memory (OOM) exception or operating system freeze. 

In MoviePy 2.1.2, the `close()` method must be explicitly called on the clip object once processing is complete [cite: 7, 8]. Utilizing a `try...finally` block, as demonstrated above, or a context manager (`with VideoFileClip(path) as clip:`) guarantees that the FFmpeg subprocess is terminated and file handles are released, regardless of whether frame extraction succeeds or encounters an exception. Note that MoviePy has occasionally exhibited bugs where processing hangs indefinitely on corrupted video segments during `get_frame` calls, making robust error handling and potentially external timeout wrappers highly advisable [cite: 9].

### Transforming NumPy Arrays to Base64 

Vision LLM APIs typically accept images via standard internet protocols, necessitating the conversion of MoviePy's raw NumPy arrays (which are inherently uncompressed and massive) into a compressed format like JPEG or PNG, and subsequently encoded into a Base64 string.

Because MoviePy returns arrays in RGB format, we can safely utilize the Python Imaging Library (`Pillow` / `PIL`) to handle the conversion in-memory without needing to juggle color channels (as would be required with OpenCV, which defaults to BGR).

```python
import base64
import io
from PIL import Image

def numpy_to_base64_jpeg(frame_array: np.ndarray, quality: int = 85) -> str:
    """
    Converts a MoviePy RGB NumPy array to a Base64-encoded JPEG string.
    """
    # Convert NumPy array to PIL Image
    img = Image.fromarray(frame_array)
    
    # Create an in-memory bytes buffer
    buffer = io.BytesIO()
    
    # Save the image to the buffer in JPEG format to compress size
    img.save(buffer, format="JPEG", quality=quality)
    
    # Retrieve byte data and encode to Base64
    b64_bytes = base64.b64encode(buffer.getvalue())
    
    # Decode bytes to a UTF-8 string for JSON payload inclusion
    return b64_bytes.decode("utf-8")
```

## 4. Utilizing the OpenAI Vision API (openai 2.15.0)

OpenAI's GPT-4o and GPT-4-vision models possess state-of-the-art visual reasoning capabilities. With the `openai` Python SDK version 2.15.0, these capabilities are exposed through the standard Chat Completions endpoint, treating images as native contextual input alongside text [cite: 10].

### Client Instantiation and API Mechanics

In version 2.15.0, the `openai` library relies on a robust, instantiable `OpenAI` client, cleanly separating thread-local state from global module states.

```python
from openai import OpenAI

# The client automatically infers the key from the OPENAI_API_KEY environment variable
client = OpenAI() 
```

To send images, the API expects a highly specific nested JSON schema. Inside the `messages` array, the `content` key—which historically accepted a simple string—must now accept a list of dictionaries, where each dictionary represents a distinct "part" of the message (either text or an image) [cite: 11, 12].

### Structuring Multi-Image Payloads

For multi-frame pedestrian counting, we must supply the VLM with several frames sequentially. The OpenAI API allows multiple images to be attached to a single user message. The maximum limit for a single request is 500 images, and the total payload must not exceed 50 MB [cite: 10, 13]. 

```python
def count_pedestrians_openai(client: OpenAI, b64_frames: list[str]) -> str:
    """
    Sends multiple base64 encoded frames to GPT-4o for unique pedestrian counting.
    """
    # Initialize the content array with the instructional text prompt
    content_parts = [
        {
            "type": "text", 
            "text": (
                "You are an expert surveillance analyst. I am providing a sequential series of "
                "frames extracted from a single surveillance camera over a short time interval. "
                "Carefully track the individuals across the frames. Count the TOTAL number of "
                "UNIQUE pedestrians that appear in this sequence. If the same person appears "
                "in multiple frames, only count them once. Return ONLY the final integer count."
            )
        }
    ]
    
    # Append each frame to the content array
    for b64 in b64_frames:
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "low" # Token optimization strategy
            }
        })
        
    # Execute the API call
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": content_parts
            }
        ],
        max_tokens=10, # We only expect a short integer response
        temperature=0.0 # Deterministic output
    )
    
    return response.choices.message.content
```

### Token Economics, Context Windows, and Image Resolution

Images sent to the OpenAI API consume the shared context window budget (up to 128K tokens for GPT-4o) [cite: 10]. The cost and token consumption of an image are entirely dictated by its resolution and the `detail` parameter, which can be set to `low`, `high`, or `auto` [cite: 13].

*   **Low Detail (`detail="low"`):** The image is aggressively downsampled to 512x512 pixels. Regardless of the original aspect ratio or resolution, the cost is a flat **85 tokens** per image [cite: 13]. For a pedestrian counting task where individuals are clearly visible and occupy significant portions of the frame, `low` detail is often sufficient and vastly reduces latency and cost.
*   **High Detail (`detail="high"`):** The API algorithmically scales the image so that it fits within a 2048x2048 square, while maintaining the aspect ratio, and ensures the shortest side is 768px long. It then divides the image into a grid of 512x512 pixel tiles. Each tile costs 170 tokens, plus a base cost of 85 tokens [cite: 13]. A standard 1080p surveillance frame (1920x1080) processed in high detail can easily consume upwards of 765 to 1105 tokens [cite: 13]. If sending 10 frames, this quickly escalates to 10,000+ tokens per API call.

**Recommendation on Resizing:** If `detail="low"` is utilized, the API performs the resizing internally. However, if bandwidth or the strict 50 MB total payload limit is a concern, it is highly recommended to resize the frames manually (e.g., using PIL `img.thumbnail()`) before Base64 encoding.

## 5. Utilizing the Google Gemini API (google-genai 1.59.0)

Google's Generative AI ecosystem provides a powerful alternative for multi-modal analysis, particularly with models boasting massive context windows (up to 2 million tokens for Gemini 1.5 Pro). However, interacting with this API via Python requires navigating a recent, major paradigm shift in Google's developer tooling.

### The Paradigm Shift: Deprecation of Legacy SDKs

A critical pitfall for developers is the confusion surrounding Google's package nomenclature. Prior to late 2024, the standard package for accessing Gemini was `google-generativeai`. With the release of the Gemini 2.0 architecture, Google created a unified SDK designed to consolidate both the Gemini Developer API and the Vertex AI enterprise endpoints [cite: 14, 15]. 

The legacy `google-generativeai` package is officially deprecated; it received its final end-of-life update and ceased receiving support on November 30, 2025 [cite: 15]. 

The modern, correct package—which must be utilized for version 1.59.0—is **`google-genai`** [cite: 16, 17]. The import path is `from google import genai`.

### Client Setup and API Mechanics

Initializing the client in the new SDK is straightforward. The API key is securely drawn from the `GEMINI_API_KEY` environment variable. 

```python
from google import genai
from google.genai import types

# Automatically picks up GEMINI_API_KEY
client = genai.Client()
```

Available models include `gemini-1.5-pro`, `gemini-2.0-flash`, and `gemini-2.5-flash` [cite: 18]. The `flash` variants are highly recommended for multi-frame video analysis as they are heavily optimized for fast, cost-effective multimodal reasoning, while natively supporting massive numbers of input images.

### Multimodal Input Structuring: Bytes and PIL

Unlike the OpenAI API, which primarily relies on Base64-encoded strings wrapped in verbose JSON dictionaries, the `google-genai` SDK allows developers to pass rich Python objects directly into the `contents` list of the `generate_content` method. 

The API accepts multi-image inputs in several formats, notably natively loaded PIL `Image` objects, or raw byte streams utilizing the `types.Part.from_bytes` schema [cite: 17, 18].

**Method A: Using PIL Images Directly**
This is often the most Pythonic and seamless method when frames have already been converted to PIL objects.
```python
from PIL import Image

def count_pedestrians_gemini_pil(client: genai.Client, frames_arrays: list[np.ndarray]) -> str:
    prompt = "Review this sequence of surveillance frames and count the total unique pedestrians. Output only the integer."
    
    # The contents list can seamlessly mix strings and PIL Image objects
    contents = [prompt]
    
    for arr in frames_arrays:
        pil_img = Image.fromarray(arr)
        contents.append(pil_img)
        
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.0)
    )
    
    return response.text
```

**Method B: Using Byte Streams**
For scenarios where image bytes are already available (e.g., loaded directly from a disk or pre-compressed), `from_bytes` is highly efficient.
```python
def count_pedestrians_gemini_bytes(client: genai.Client, frames_jpeg_bytes: list[bytes]) -> str:
    prompt = types.Part.from_text("Review this sequence and count total unique pedestrians.")
    
    contents = [prompt]
    
    for img_bytes in frames_jpeg_bytes:
        image_part = types.Part.from_bytes(
            data=img_bytes,
            mime_type='image/jpeg'
        )
        contents.append(image_part)
        
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents
    )
    
    return response.text
```

### Rate Limits and Batching Strategy

While the Gemini API possesses massive context limits, allowing developers to dump entire unsampled videos into the prompt, best practices dictate batching frames. The Gemini Developer API enforces specific Rate Limits (Requests Per Minute - RPM, and Tokens Per Minute - TPM). Pushing hundreds of frames simultaneously can easily trigger a `429 Too Many Requests` error by blowing through the TPM quota [cite: 19]. A highly effective strategy is to sample a manageable batch of frames (e.g., 5 to 10 frames per request) and process them sequentially, utilizing a sleep timer or exponential backoff strategy for retry logic.

## 6. Advanced Unique Pedestrian Counting Strategy

Applying Vision LLMs to the task of video pedestrian counting is not a trivial substitution for traditional MOT (Multi-Object Tracking) systems. While VLMs excel at zero-shot object recognition, research indicates they exhibit notable weaknesses in spatial tracking, object permanence across disparate viewpoints, and basic counting when numbers scale beyond small groups [cite: 20, 21].

### The Core Challenges: Re-identification and Occlusion

To count *unique* pedestrians across a temporally disjointed sequence of frames, the VLM must perform "re-identification" (Re-ID). It must recognize that a person wearing a red jacket in Frame 1 is the exact same entity as the person in the red jacket in Frame 5, despite changes in scale, posture, camera angle, or partial occlusion by environmental geometry.

Research explicitly notes that while VLMs succeed in single-view scenarios, they frequently fail in multi-view or multi-frame scenarios where partial information must be reconciled across time [cite: 20]. They are prone to two critical failure modes:
1. **Overcounting (Double Counting):** Treating the same individual in three different frames as three separate unique individuals.
2. **Undercounting (Occlusion/Crowding):** Missing individuals entirely due to overlap, or failing to differentiate a densely packed crowd. Misidentifying non-pedestrian objects (e.g., mannequins, posters) as people can also skew results [cite: 20, 21].

### Temporal Sampling Rates

Providing an un-sampled video (e.g., 30 frames per second) to an LLM is both financially ruinous in API costs and likely to overwhelm the model's attention mechanisms. The key is to sample **key frames** that capture maximum variance without losing the logical thread of movement. 

For a short 30-second surveillance clip, sampling one frame every 3 to 5 seconds yields 6 to 10 distinct images. This strikes the optimal balance: the temporal gap is large enough to capture meaningful scene changes (people entering and exiting), yet short enough that the visual appearance of a specific pedestrian has not completely changed, allowing the model to perform Re-ID successfully. It is highly recommended to send all sampled frames from a short clip in a **single API call** rather than multiple calls; isolated API calls completely lack the temporal context required to prevent double-counting across the full sequence.

### Prompt Engineering for VLMs

Because counting large quantities inherently challenges the attention mechanisms of autoregressive language models, prompt engineering must explicitly enforce a "Divide-and-Conquer" or "Chain-of-Thought" reasoning structure [cite: 20, 21]. The prompt must aggressively contextualize the scene and dictate the logical steps for Re-ID.

**Optimized Surveillance Prompt Structure:**
> "You are an expert security analyst tasked with analyzing a sequence of 8 frames extracted from a single, fixed-angle surveillance camera over a 30-second period. 
> 
> Your task is to count the TOTAL number of UNIQUE pedestrians that appear across this entire sequence. 
> 
> Follow these strict logical steps:
> 1. Scan each frame chronologically.
> 2. Identify every human figure present. Pay close attention to distinguishing features such as clothing color, carried items (e.g., backpacks, umbrellas), trajectory of movement, and body shape.
> 3. Perform re-identification: If a figure in Frame 3 shares the same distinct clothing and general trajectory as a figure in Frame 1, recognize them as the SAME unique individual. Do not double count them.
> 4. Account for occlusion: Individuals may temporarily step behind pillars or other people.
> 5. Filter false positives: Do not count statues, posters, reflections, or animals.
> 
> Think step-by-step about the distinct individuals you identify, tracking their movement across the frames. Finally, provide the total unique count. 
> 
> You MUST end your response with a JSON object exactly matching this format: `{"unique_pedestrian_count": <integer>}`"

By forcing the model to explicitly list and track the features of individuals before outputting the final number, the accuracy of the final count increases dramatically compared to a naive "how many people are in these images" prompt.

## 7. Persisting Results with OpenPyXL 3.1.5 and Pandas 2.3.3

Once the LLM has successfully inferred the unique pedestrian count, the resulting data must be aggregated and serialized into a standard reporting format, typically Microsoft Excel. In Python, this is facilitated by the `pandas` data manipulation library, utilizing `openpyxl` as its underlying serialization engine.

### Native OpenPyXL Implementation

If external dependencies must be minimized, or strict control over the workbook structure is required, developers can bypass pandas and write directly to an Excel file using the `openpyxl` 3.1.5 API. 

A common annoyance when creating a new `Workbook` in openpyxl is the default generation of an empty sheet named "Sheet" [cite: 22]. If a new sheet named "results" is appended, the workbook looks unprofessional with the blank "Sheet" lingering in the first tab position. To ensure no extra sheets are created, developers should capture the default active sheet immediately upon instantiation and simply rename its title attribute.

```python
from openpyxl import Workbook
import os

def write_results_openpyxl(data: list[dict], output_path: str):
    """
    Writes results to Excel natively using OpenPyXL 3.1.5.
    Ensures a single sheet named 'results' exists.
    """
    wb = Workbook()
    
    # Grab the default sheet created by OpenPyXL and rename it
    ws = wb.active
    ws.title = "results"
    
    # Append the Header Row
    ws.append(["filename", "number"])
    
    # Append the Data Rows
    for entry in data:
        # Enforce strict integer casting to prevent string-based numbers in Excel
        filename = str(entry.get("filename", "unknown.mp4"))
        try:
            count = int(entry.get("number", 0))
        except ValueError:
            count = 0 # Fallback in case of LLM hallucination
            
        ws.append([filename, count])
        
    wb.save(output_path)
```

### Pandas Integration: DataFrame.to_excel()

For modern data pipelines, assembling a list of dictionaries into a `pandas` DataFrame is the standard operating procedure. Pandas version 2.3.3 provides a robust `to_excel` method that transparently invokes openpyxl. 

When utilizing pandas, the engine will automatically handle sheet creation without leaving a default "Sheet" artifact behind, provided the entire DataFrame is dumped simultaneously to a fresh file. The exact parameters required to achieve a clean output—specifically avoiding the auto-generation of an arbitrary numerical index column and setting the proper sheet name—are `index=False` and `sheet_name="results"` [cite: 23, 24].

```python
import pandas as pd

def write_results_pandas(data: list[dict], output_path: str):
    """
    Writes results to Excel using Pandas 2.3.3 and the openpyxl engine.
    """
    df = pd.DataFrame(data)
    
    # Enforce integer data type on the 'number' column before export
    df['number'] = pd.to_numeric(df['number'], errors='coerce').fillna(0).astype(int)
    
    # Export without index column, naming the sheet explicitly
    df.to_excel(
        output_path, 
        index=False, 
        sheet_name="results", 
        engine="openpyxl"
    )
```

## 8. Critical Pitfalls and System Robustness

Building a composite pipeline linking video rendering, network APIs, and data serialization introduces multiple vectors for failure. Below is an exhaustive detailing of critical pitfalls that must be mitigated.

### Data Type Coercion and Hallucinations
A frequent failure mode when integrating LLMs into automated pipelines is the failure to guarantee the output format. While instructed to return an integer, an LLM might return `"The total unique count is 5."` or `"five"`. If this string is blindly appended to Excel, downstream analytical systems will fail to parse the metric.
*   **Mitigation:** The system must utilize structured outputs. OpenAI provides JSON Mode and strict Structured Outputs (via Pydantic schemas) which algorithmically guarantee the response shape. Alternatively, utilizing a robust regex parser (`re.search(r'\d+', text)`) acts as a fallback to extract the integer, which must then be explicitly cast using Python's `int()`.

### MoviePy Breaking Changes and Deprecations
Porting code from MoviePy 1.x to 2.1.2 will invariably trigger `AttributeError` exceptions if legacy effects or functional paradigms are used [cite: 1, 2]. Furthermore, if the FFmpeg backend encounters deeply corrupted bytes in a video stream, MoviePy 2.x may hang indefinitely within the `get_frame` logic rather than raising an explicit exception [cite: 9]. 
*   **Mitigation:** Critical extraction operations should ideally be wrapped in a thread-based timeout mechanism, ensuring that a single corrupted video file does not silently deadlock the entire batch processing pipeline.

### Memory Exhaustion at Scale
A system processing a directory of 500 surveillance videos will collapse if garbage collection is not explicitly invoked. Video tensors (NumPy arrays) occupy vast amounts of contiguous memory.
*   **Mitigation:** Rely exclusively on the context manager pattern (`with VideoFileClip(...) as clip:`) [cite: 8]. Additionally, aggressive deletion of arrays (`del frame_array`) and forcing Python's garbage collector (`import gc; gc.collect()`) between video processing loops can stabilize memory footprints on constrained hardware.

### SDK Version Conflicts
The deprecation of `google-generativeai` has rendered thousands of tutorials and StackOverflow answers obsolete [cite: 15]. Attempting to use the legacy import namespace (`import google.generativeai as genai`) will result in missing attributes or outright import failures if the environment strictly relies on the modern `google-genai` 1.59.0 package. Developers must rigorously police their `requirements.txt` to align with the modern namespaces [cite: 17].

---

## 9. Comprehensive Integrated Code Solution

The following Python script provides a robust, production-ready implementation synthesizing all concepts discussed above. It leverages MoviePy 2.1.2 for extraction, OpenAI 2.15.0 for inference, and Pandas 2.3.3 for reporting.

```python
"""
Pedestrian Counting Utility Module
Dependencies: moviepy==2.1.2, openai==2.15.0, pandas==2.3.3, openpyxl==3.1.5, Pillow
"""

import os
import glob
import io
import base64
import json
import re
import numpy as np
import pandas as pd
from PIL import Image
from moviepy import VideoFileClip
from openai import OpenAI

# ---------------------------------------------------------
# Configuration and Constants
# ---------------------------------------------------------
VIDEO_DIR = "./surveillance_footage"
OUTPUT_EXCEL = "pedestrian_counts.xlsx"
FRAME_INTERVAL_SECONDS = 5.0
MAX_FRAMES_PER_VIDEO = 10
API_KEY = os.environ.get("OPENAI_API_KEY")

# ---------------------------------------------------------
# Core Functional Modules
# ---------------------------------------------------------

def get_video_files_deterministically(directory: str) -> list[str]:
    """Finds all MP4 files and sorts them deterministically."""
    pattern = os.path.join(directory, "*.mp4")
    files = glob.glob(pattern)
    return sorted(files)

def extract_and_encode_frames(video_path: str, interval: float, max_frames: int) -> list[str]:
    """
    Extracts frames using MoviePy 2.1.2, resizing and encoding them to Base64 JPEG.
    Properly closes resources to prevent memory leaks.
    """
    b64_frames = []
    clip = None
    
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        
        # Determine timestamps to sample
        timestamps = np.arange(0, duration, interval)
        if len(timestamps) > max_frames:
            # Sample evenly across the array if it exceeds our max threshold
            indices = np.linspace(0, len(timestamps) - 1, max_frames, dtype=int)
            timestamps = timestamps[indices]
            
        for t in timestamps:
            # Extract the raw RGB numpy array
            frame_np = clip.get_frame(t)
            
            # Convert to PIL Image for compression
            img = Image.fromarray(frame_np)
            
            # Optimization: Resize to a max 768px short side to reduce base payload size 
            # prior to hitting the API, ensuring faster networking.
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            b64_frames.append(b64_str)
            
    except Exception as e:
        print(f"Error extracting frames from {video_path}: {e}")
    finally:
        # Crucial Memory Management: Close the MoviePy 2.x resource
        if clip is not None:
            clip.close()
            
    return b64_frames

def analyze_frames_with_openai(client: OpenAI, b64_frames: list[str]) -> int:
    """
    Calls the OpenAI 2.15.0 API with a sequence of images to count unique pedestrians.
    """
    if not b64_frames:
        return 0
        
    prompt_text = (
        "You are an expert security analyst. I am providing a sequential series of frames "
        "extracted from a single surveillance camera. Count the TOTAL number of UNIQUE "
        "pedestrians that appear across this sequence. Carefully track individuals across "
        "frames to avoid double counting the same person. Output a valid JSON object with "
        "a single key 'unique_pedestrian_count' and the integer value."
    )
    
    content_parts = [{"type": "text", "text": prompt_text}]
    
    for b64 in b64_frames:
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "low" # Aggressive cost/token optimization
            }
        })
        
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content_parts}],
            temperature=0.0,
            response_format={ "type": "json_object" } # Enforce JSON output for robust parsing
        )
        
        raw_output = response.choices.message.content
        parsed_json = json.loads(raw_output)
        
        count = parsed_json.get("unique_pedestrian_count", 0)
        return int(count) # Strict integer enforcement
        
    except Exception as e:
        print(f"API Error: {e}")
        return 0

def export_to_excel(results: list[dict], output_path: str):
    """
    Exports results to Excel using Pandas 2.3.3, bypassing default openpyxl sheets.
    """
    df = pd.DataFrame(results)
    
    if not df.empty:
        # Enforce strict typing on the DataFrame level
        df['number'] = df['number'].astype(int)
        
        # Engine openpyxl avoids standard csv constraints and allows sheet naming
        df.to_excel(output_path, index=False, sheet_name="results", engine="openpyxl")
        print(f"Successfully exported results to {output_path}")
    else:
        print("No data to export.")

# ---------------------------------------------------------
# Main Execution Flow
# ---------------------------------------------------------
def main():
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
    client = OpenAI(api_key=API_KEY)
    video_files = get_video_files_deterministically(VIDEO_DIR)
    
    if not video_files:
        print(f"No valid video files found in {VIDEO_DIR}.")
        return
        
    results_data = []
    
    for v_path in video_files:
        filename = os.path.basename(v_path)
        print(f"Processing {filename}...")
        
        frames = extract_and_encode_frames(v_path, FRAME_INTERVAL_SECONDS, MAX_FRAMES_PER_VIDEO)
        pedestrian_count = analyze_frames_with_openai(client, frames)
        
        results_data.append({
            "filename": filename,
            "number": pedestrian_count
        })
        print(f"Found {pedestrian_count} unique pedestrians in {filename}.")
        
    export_to_excel(results_data, OUTPUT_EXCEL)

if __name__ == "__main__":
    main()
```

### Conclusion
By meticulously adhering to the architectural requirements of MoviePy 2.x and the modernized networking constraints of modern VLM SDKs, developers can build highly resilient, robust automation pipelines. The strategic sampling of frames combined with aggressive, structured prompt engineering bridges the gap between massive context processing and precise, unique temporal logic, ensuring that Excel-bound analytical data remains consistently reliable and deeply informative.

**Sources:**
1. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGNKiAAuvQc-2FSImiw4FMxbcFaSmeazYGMt5rDCJb1BhkMeaR0GiLh5KdffvvkXqAEvvDrfNMqs8E-F9mv7Zh_pbYAptFBIznGVcR0zOrhx2nqCVmefBqJq5DwgbXmAnGwvKOkZV7Kr9HVWfgiZ3FhiAGmmYfr2Ayi)
2. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGYi6I8g5SzIfyvHvEtux2e25bAeBNWT39pFnV2guAJYX2f72qRYuPlWUmOjuzDiOu7L4t-QM_v3ZptSCJiYNYf36x_7T3vr0YN5WgsgsIfrGQiz2HsJBUvvUIrRMUwpw==)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEfRPLDgh40EHQHFr4a1NOG8t1xioKD2ZZJYYKdPUeNgc38TjkBKPaUgPNOq4Zeb4D4MI-7GXo2jrFFuY3cl6dCeC4plyvLaLa1MPdu7WW11VSc1cRfJsUu7LWFsqS2JB28USFYtT7oFllf530V11c=)
4. [gitee.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEerI0qlMYkyPU1V61fj8HnmgRi5-1I62j5aNTrBJ7b8Wc8BYoOcFXw_xlO6iEu58FEykfgA4QdA6po1l7OsPDxAdl85bt4S1_aCymoaVtqXsrRhK7b2WyBxqXBZZ3pUC0gH3UQj1lMi7r_2X1RJ0Cm)
5. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFrPtsKpt8edQJPjs48jiziLcmSp3crMHUR-s-yZ-BzuNWW7ZbtLnyTWfbgddtsMRUQkJyO3kGV4IRIMfG4Nrdurf9Mc9_k0_a8w6_nI-PivqZeTRzBoK9zSPHSETz-Rq_yDBkQ4EKf6CW_40vnqeACDzykaFKON_gvKnSvzBhSW06kCK5de_I=)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAFh9oFpmdrTasSNw-7f1jq2r6bMZHcDptqSRvDipGfcr8UVlVNfLQ5Uv4Q5nQVyf7VBtw6JNb6YOITEYpOV-jMv5Q1EBusdS7gv3KeIjohF5l6_12yYq8EHfpRtpdEEpJUZHEYounLMGB3XzL6rRc8Awm9Ftz7RLP_0ZSDxo_b-7JA4geHJ3ByPH1DrmXiLmOvDNZf9-xy2u9AC87)
7. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHE0a1S_OQEdCPhwLnkNGf0W-g3Oqf6CTmSSX0HzhsYDEmm4iK4jP8FUVRJuKaeEHPSR-TE1X9oQthWTQYW2aoTHhpyNWi7OitLkdUCIcLOf3SnIO9mi68=)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFU_qyd71qOkdoun3Nw0w1h28fijLxyBqijczfQMwmKygNEX9-EOopfm9nSHOoBOWsLQPApkWJvkCsWhtzJNDoTCTiUJeyQJhciiIxCypf1A5wPVxuQMhs-N4QzxzdydxuRCf5MAnQbEE3cI39P8K-bCHw=)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7NnBPTUeTwQlEgF-D80RSBCJi3mbQjstp6Gzc4EjoPpnwX-W-LsbWv0M3sgu24xLLn5KqI5DIJTfv42Du0DTtrYtXOBMf6vaefM09FTqYA_Qa5J4_CmuKAprpnV-xzGZdFw==)
10. [getstream.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHAcTfrYUPQd2rSD_cuK0CpOlJ_Ns_20MRwZc9K8u5ECIlu6QUetyCKs-O2sjvPBgzKE0LZjHppvLKy601En1_TYqmkDYv3ccmpRlXhOsOeaiJjyYWvmjAqxD4H0elLhCUXIqJt)
11. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZy8m1j5rsQSzhuiqYoJdMumcnMObg0oBP7OPz4pJzpDQzIywdj8z6ziV5kOIwlFZ8r58DIgcTbs5Zj0I8oDftTVBQXybpvpKekwTWM4DHIRH43zxpY-ZAJVz1NYLicATemKu-0iogZmcAsSOjw3sQQkL859rxmIv4UnO8fjagE52st36saoK_M7roHTYUI7QCpL9nQ3BoPoT7b7Vc)
12. [vllm.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF0Yc_U7922qpgjWUB28PHSfqZF-VU2_l3kbgPuR4V-uU0MoCf7J4B9jdJRmmkefHbfPosO0VKCad7_CFzwqcrLUvgzFVr-xDBGUbfPhlkfqtah6vAOP4ZsPZ9qg7lzk5-z7yaboHCZ1dsywZcc5-bVNq6QYYUVfFU8TEQ_7C70y0wthoykDnT4UoGK)
13. [mintlify.app](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERNCtWJZSKFuQewQEtFeOeScu2jfoL4xZEAWAlYLr-sEccObdhwB5zgwAfAkdu50k8pY0xWVlkN_obkcXnidnTKD7hn-IfYxfmIUwmX_-6Bvyoe4IOr1YQ5rC5tAjM-0n4fziJ0qml4RAB)
14. [langchain.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7QvIOSRdE0AS2RtY9Hu2OeUpDiRvKSshZwQKeyOkn8iN31YFdShbDZvVN5vzMV3NVqoP9SLFfnNV18YmYoHi-HGXgJrDKtpjh35WcaqXWxBaC2OUxIpfloVcwOXsKVUszbo_lON-4T1QmEAyczhwuoAnV)
15. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFu55eB5uSIpHeb-vEbxSFLTMtZr00yRj-8ToYdq1EeTO-aQx0Y2SBh-SpRP2WMmAhTZlE0OwmMPi2FqWJd69kjcv8F_05688B7msCpjIwzf70tCpR4RxOoQnzcjqpew0Ls6Fk=)
16. [google.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYC_d8JnBDYeOJ6Ur60zzNYLHjv3mnjnN9diBjRbHtHCzLXaaGzXj1-13h5lO76UWfC2_PylbRYykfYZDjatku8-RQrzmOLDRYMoNtrUUpxIgcH_n4LjW4iuDMv0RV8Uo4rwse0Rc=)
17. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHrjJdVtvXu_DBua1yuIhWaXSAkz9GaT1NYpxE4NHw8pAlctkm2FLDntecbth449srFLPPrCVAh35SqreuMuNfBE1_ofywVkDiYDiFDvMHI_1wo4OyGhHCtUgBK5w==)
18. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjDgWnWx05rgbjrMWfwLbXDUObYmaXRyAFRPHRkHnMxoK-uLzAEKyhftFO1vXMlmjIXWr6oMSiafJnbaz_ncBfrsw_I6dHSH97KgmkD4WCnaU-VzMp8WDx9AXuuZGyWqx_Bj_uFsjx30yfDqqcRNmihZYtifNXXTmMeyw9PkhuNUdg)
19. [microsoft.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG8dVO5749zb9eQ4GB0Gq9PpxEazCR18724RYsGA60FVzVDKEdk2rL4wVO2vevaPjr-RI5uMsLlPo9HDL9tqanfCthNGeVJIPAwrIrBhUH63o1oLIJbNuriT8rEEBMkEW-sO0JUun8Fl9Ns-MN_EwuaT5hQzObCuJ9bgw==)
20. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmH9yUv4XiPyCg33wmtPJIpPAKaTbpuggSaazLr1Un7CXekIU-_5OFjzzwlun3vdNT0YNowXoZTAlXsMI0uFsXK2pCMzkLzR3ltkRsfxSw7MeJkmXMoJLH0Q==)
21. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVQ1bWklYBzwe67Zwo4uVpwTsBiJoHcjK8TMJaMLtxB10OJ_QCCyDaWLkpJTOV_pQ02eB1gg_HAsflyUOxIgvdcmvVVbq6_jiy5UnNoabTfBIn5SlYF0-dig==)
22. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQwWWmXazm57W4J7nJ1EJc-ow4SsMuN3xRv73HU64RqyB2GE1Z3JTlJecwQT7vt6tssn6gpsCqkqvbrdDRQoZZ9aSzbKN06jjGI1EMDLYdzXISy-hGXJv81KUJ3YMeE7w-oVjaVqhaIooC)
23. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEA8uXRntybyWtArf9FUhZs5ar23bcHVZxeNfZ-dTYO7JtoKw3cMQL7E1aeuUkcJ83-P1DaYBSdY9GhhJa00cMVlhZhc9af7Og3J4MM9XsnGbIo-RYNuRTRHnj2WVJaZHOyJWrqJc2gu_ITyhq0tsPwjKC_GRMJ7Z5-CYmEMpuhtuMhgbRgP-oAZ8KEcXL0MZq)
24. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZ6Covh1aGDhEvaKY0Mj7zhY3w1hfaw15tPzTVkQg_OlIBrlBBk3HGH0IUfFNjdcRcWxAjFV60OztSnongDlEeCpmkRmdcKIJDkXpRTieih9ZOzsO5yM-wapWxpq0EvK4_X-pJ9TAe9eTGyiau6JkC8SI0UPKmiWpenNddfcFJlKM=)
