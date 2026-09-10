---
name: evo-pedestrian-vlm-counting
description: Count unique pedestrians in surveillance video frames using Vision LLM APIs (OpenAI GPT-4o or Google Gemini) and write results to Excel. Use when you need to analyze surveillance footage for pedestrian counting, perform person re-identification across video frames, or generate Excel reports of pedestrian counts per video file. Supports both OpenAI and Gemini vision APIs with robust response parsing.
---

# Pedestrian VLM Counting

Sends extracted video frames to Vision LLM APIs with carefully engineered prompts for unique pedestrian counting, parses integer results robustly, and writes final counts to a properly formatted Excel file.

## When to Use

- Counting unique pedestrians in surveillance video footage
- Analyzing foot traffic across multiple video files
- Generating Excel reports of pedestrian counts per video
- Using vision AI to perform person re-identification across frames

## Dependencies

This skill depends on `evo-video-frame-extraction` for frame extraction. Import frame extraction functions from that skill.

## Core Functions

The skill provides these functions in `scripts/pedestrian_counting.py`:

### `count_pedestrians_openai(b64_frames: list[str], api_key: str = None) -> int`
Sends base64-encoded frames to OpenAI GPT-4o for unique pedestrian counting. Uses structured prompting with chain-of-thought reasoning to improve accuracy. Returns an integer count.

### `count_pedestrians_gemini(b64_frames: list[str], api_key: str = None) -> int`
Sends frames to Google Gemini for unique pedestrian counting. Accepts base64 JPEG strings. Returns an integer count.

### `parse_count_from_response(response_text: str) -> int`
Robustly extracts an integer pedestrian count from LLM response text. Handles JSON responses, plain integers, and natural language responses. Falls back to regex extraction.

### `write_results_to_excel(results: list[dict], output_path: str) -> None`
Writes results to an Excel file with columns "filename" and "number" on a sheet named "results". Uses pandas with openpyxl engine. Enforces integer types.

### `run_pedestrian_counting_pipeline(video_dir: str, output_path: str, api: str = "openai", interval: float = 3.0, max_frames: int = 10) -> list[dict]`
End-to-end pipeline: discovers videos, extracts frames, counts pedestrians via VLM, writes Excel. The `api` parameter selects "openai" or "gemini".

## Usage Example

```python
from scripts.pedestrian_counting import run_pedestrian_counting_pipeline

# Run the full pipeline
results = run_pedestrian_counting_pipeline(
    video_dir="/path/to/videos",
    output_path="pedestrian_counts.xlsx",
    api="openai",
    interval=3.0,
    max_frames=10
)
```

## Prompt Engineering Strategy

The prompts used for pedestrian counting follow these principles:

1. **Role assignment**: The model is told it is an expert surveillance analyst
2. **Sequential context**: Frames are described as a temporal sequence from a single camera
3. **Re-identification guidance**: The model is instructed to track individuals by clothing, carried items, trajectory, and body shape
4. **Explicit de-duplication**: The model is told not to double-count the same person across frames
5. **Output format enforcement**: The model is asked to return a JSON object with the count
6. **Chain-of-thought**: The model is encouraged to reason step-by-step before giving the final count

## Excel Output Format

The output Excel file has:
- Sheet name: "results"
- Column A: "filename" (basename of the video file)
- Column B: "number" (integer count of unique pedestrians)
- No index column
- Integer data type enforced on the number column
