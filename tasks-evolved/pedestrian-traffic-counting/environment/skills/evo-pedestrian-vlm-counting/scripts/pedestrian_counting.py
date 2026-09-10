"""
Pedestrian Counting Module

Sends extracted video frames to Vision LLM APIs (OpenAI GPT-4o or Google Gemini)
with carefully engineered prompts for unique pedestrian counting, parses integer
results robustly, and writes final counts to a properly formatted Excel file.
"""

import os
import re
import json
import sys
from typing import List, Dict, Optional

import pandas as pd

# Add frame extraction skill to path
sys.path.insert(0, '/app/environment/skills/evo-video-frame-extraction/scripts')
from frame_extraction import discover_video_files, extract_and_encode_frames


# ---- Prompt Templates ----

SURVEILLANCE_PROMPT = """You are an expert security analyst tasked with analyzing a sequence of {num_frames} frames extracted from a single, fixed-angle surveillance camera over a short time period.

Your task is to count the TOTAL number of UNIQUE pedestrians that appear across this entire sequence.

Follow these strict logical steps:
1. Scan each frame chronologically.
2. Identify every human figure present. Pay close attention to distinguishing features such as clothing color, carried items (e.g., backpacks, umbrellas), trajectory of movement, and body shape.
3. Perform re-identification: If a figure in one frame shares the same distinct clothing and general trajectory as a figure in another frame, recognize them as the SAME unique individual. Do not double count them.
4. Account for occlusion: Individuals may temporarily step behind pillars or other people.
5. Filter false positives: Do not count statues, posters, reflections, or animals.

Think step-by-step about the distinct individuals you identify, tracking their movement across the frames. Finally, provide the total unique count.

You MUST end your response with a JSON object exactly matching this format: {{"unique_pedestrian_count": <integer>}}"""


def parse_count_from_response(response_text: str) -> int:
    """
    Robustly extracts an integer pedestrian count from LLM response text.
    
    Handles:
    - JSON responses with unique_pedestrian_count key
    - Plain integer responses
    - Natural language with embedded numbers
    - Fallback to regex extraction
    
    Args:
        response_text: Raw text response from the LLM.
        
    Returns:
        Integer count of pedestrians (0 if parsing fails).
    """
    if not response_text:
        return 0
    
    text = response_text.strip()
    
    # Try 1: Direct integer
    try:
        return int(text)
    except ValueError:
        pass
    
    # Try 2: JSON parsing - look for JSON object in the text
    json_patterns = re.findall(r'\{[^{}]*\}', text)
    for json_str in json_patterns:
        try:
            data = json.loads(json_str)
            if 'unique_pedestrian_count' in data:
                return int(data['unique_pedestrian_count'])
            # Try other common keys
            for key in ['count', 'pedestrian_count', 'total', 'number']:
                if key in data:
                    return int(data[key])
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    
    # Try 3: Look for patterns like "count: 5" or "total: 5"
    count_patterns = re.findall(r'(?:count|total|number)[:\s]+([0-9]+)', text, re.IGNORECASE)
    if count_patterns:
        return int(count_patterns[-1])  # Take the last match
    
    # Try 4: Find all numbers and take the last one (usually the final answer)
    all_numbers = re.findall(r'\b([0-9]+)\b', text)
    if all_numbers:
        return int(all_numbers[-1])
    
    return 0


def count_pedestrians_openai(b64_frames: List[str], api_key: str = None) -> int:
    """
    Sends base64-encoded frames to OpenAI GPT-4o for unique pedestrian counting.
    
    Args:
        b64_frames: List of base64-encoded JPEG strings.
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
        
    Returns:
        Integer count of unique pedestrians.
    """
    if not b64_frames:
        return 0
    
    from openai import OpenAI
    
    key = api_key or os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=key)
    
    prompt_text = SURVEILLANCE_PROMPT.format(num_frames=len(b64_frames))
    
    content_parts = [{"type": "text", "text": prompt_text}]
    
    for b64 in b64_frames:
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "low"
            }
        })
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=500,
            temperature=0.0
        )
        
        raw_output = response.choices[0].message.content
        print(f"  OpenAI response: {raw_output}")
        return parse_count_from_response(raw_output)
        
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return 0


def count_pedestrians_gemini(b64_frames: List[str], api_key: str = None) -> int:
    """
    Sends frames to Google Gemini for unique pedestrian counting.
    
    Uses the google-genai 1.59.0 SDK with the modern import path.
    
    Args:
        b64_frames: List of base64-encoded JPEG strings.
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var).
        
    Returns:
        Integer count of unique pedestrians.
    """
    if not b64_frames:
        return 0
    
    import base64
    from google import genai
    from google.genai import types
    
    key = api_key or os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=key)
    
    prompt_text = SURVEILLANCE_PROMPT.format(num_frames=len(b64_frames))
    
    # Build contents with text prompt and image parts
    contents = [prompt_text]
    
    for b64 in b64_frames:
        # Decode base64 to bytes for Gemini
        img_bytes = base64.b64decode(b64)
        image_part = types.Part.from_bytes(
            data=img_bytes,
            mime_type='image/jpeg'
        )
        contents.append(image_part)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.0)
        )
        
        raw_output = response.text
        print(f"  Gemini response: {raw_output}")
        return parse_count_from_response(raw_output)
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # Try fallback model
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            raw_output = response.text
            print(f"  Gemini fallback response: {raw_output}")
            return parse_count_from_response(raw_output)
        except Exception as e2:
            print(f"Gemini fallback also failed: {e2}")
            return 0


def write_results_to_excel(results: List[Dict], output_path: str) -> None:
    """
    Writes results to an Excel file with proper formatting.
    
    Creates a single sheet named "results" with columns "filename" and "number".
    Enforces integer type on the number column. No index column.
    
    Args:
        results: List of dicts with 'filename' and 'number' keys.
        output_path: Path to the output Excel file.
    """
    df = pd.DataFrame(results)
    
    # Enforce column order and types
    df = df[['filename', 'number']]
    df['number'] = pd.to_numeric(df['number'], errors='coerce').fillna(0).astype(int)
    
    # Write to Excel with openpyxl engine
    df.to_excel(
        output_path,
        index=False,
        sheet_name="results",
        engine="openpyxl"
    )
    print(f"Results written to {output_path}")


def run_pedestrian_counting_pipeline(
    video_dir: str,
    output_path: str,
    api: str = "gemini",
    interval: float = 3.0,
    max_frames: int = 10
) -> List[Dict]:
    """
    End-to-end pipeline: discovers videos, extracts frames, counts pedestrians
    via VLM, and writes results to Excel.
    
    Args:
        video_dir: Directory containing video files.
        output_path: Path for the output Excel file.
        api: Which API to use - "openai" or "gemini".
        interval: Seconds between frame samples.
        max_frames: Maximum frames to extract per video.
        
    Returns:
        List of result dicts with 'filename' and 'number' keys.
    """
    # Discover videos
    video_files = discover_video_files(video_dir)
    print(f"Found {len(video_files)} video files in {video_dir}")
    
    if not video_files:
        print("No video files found!")
        return []
    
    results = []
    
    for video_path in video_files:
        filename = os.path.basename(video_path)
        print(f"\nProcessing: {filename}")
        
        # Extract and encode frames
        b64_frames = extract_and_encode_frames(
            video_path,
            interval_seconds=interval,
            max_frames=max_frames
        )
        print(f"  Extracted {len(b64_frames)} frames")
        
        if not b64_frames:
            print(f"  No frames extracted, setting count to 0")
            count = 0
        else:
            # Count pedestrians using selected API
            if api == "openai":
                count = count_pedestrians_openai(b64_frames)
            else:
                count = count_pedestrians_gemini(b64_frames)
        
        results.append({
            "filename": filename,
            "number": count
        })
        print(f"  Count: {count} unique pedestrians")
    
    # Write results to Excel
    write_results_to_excel(results, output_path)
    
    return results


if __name__ == "__main__":
    # Default execution
    video_dir = "/app/video"
    output_path = "/app/video/count.xlsx"
    
    results = run_pedestrian_counting_pipeline(
        video_dir=video_dir,
        output_path=output_path,
        api="gemini",
        interval=3.0,
        max_frames=10
    )
    
    print(f"\nFinal results:")
    for r in results:
        print(f"  {r['filename']}: {r['number']} pedestrians")
