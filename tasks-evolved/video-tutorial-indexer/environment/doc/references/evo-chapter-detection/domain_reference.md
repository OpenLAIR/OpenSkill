# Domain Reference for evo-chapter-detection

**Responsibility**: Fuzzy string matching of chapter titles against transcript words using sliding windows, enforcing monotonic ordering and boundary constraints, and writing the final tutorial_index.json output file in the required format.

**Key functions to implement**: find_chapter_timestamp, detect_all_chapters, enforce_monotonic_timestamps, generate_tutorial_index_json

---

## 4. Text Matching and Chapter Detection Patterns


Given an expected list of chapter titles (e.g., "Introduction", "Setting up the Environment", "Data Visualization"), the goal is to pinpoint the exact floating-point timestamp where the speaker transitions into these topics. Because speakers rarely say the exact chapter title verbatim, strict string equality (`==`) will fail.

### 4.1 Fuzzy String Matching with Levenshtein Distance

The most effective Python approach utilizes the `fuzzywuzzy` (or its updated fork `thefuzz`) library, which calculates the Levenshtein distance between strings to determine a similarity ratio [cite: 25, 26]. The Levenshtein distance measures the minimum number of single-character edits (insertions, deletions, or substitutions) required to change one word into the other [cite: 27].

To map chapter titles, the `process.extractOne()` function is ideal. It compares a query string against an iterable of choices and returns a tuple containing the best match and its score out of 100 [cite: 25, 28]. Additionally, it supports a `score_cutoff` parameter to discard poor matches [cite: 28].

### 4.2 The Sliding Window Algorithm over Transcript Segments

Because a chapter title might span across the boundary of two Whisper segments, or a segment might contain an entire paragraph burying the chapter transition phrase, comparing the chapter title to individual words or small sliding windows of words yields the highest accuracy.

**Algorithmic Approach:**
1. Extract all `words` from the Whisper output (requires `word_timestamps=True`).
2. Construct a sliding window of \( N \) words (where \( N \) is roughly the word count of the target chapter title plus a small margin).
3. Compute the `fuzz.partial_ratio` or `fuzz.token_set_ratio` [cite: 25, 26] between the target chapter title and the joined words in the window.
4. Record the start timestamp of the window that yields the highest score above a predefined threshold (e.g., 80%).

```python
from thefuzz import process, fuzz
from typing import List, Dict, Optional

def find_chapter_timestamp(target_title: str, whisper_words: List[Dict], window_size: int = 5, threshold: int = 80) -> Optional[float]:
    """
    Finds the timestamp of a spoken chapter title using a sliding window and fuzzy matching.
    """
    if not whisper_words:
        return None

    best_match_time = None
    best_score = 0
    
    # Iterate through words with a sliding window
    for i in range(len(whisper_words) - window_size + 1):
        window = whisper_words[i : i + window_size]
        window_text = " ".join([w["word"].strip() for w in window])
        
        # Calculate ratio ignoring case and punctuation
        score = fuzz.token_set_ratio(target_title.lower(), window_text.lower())
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match_time = window["start"] # Get start time of the first word in the match
            
            # Short-circuit if perfect match found
            if score == 100:
                break
                
    return best_match_time
```

---

## 5. Video Frame Analysis with OpenCV


To validate the textual chapter boundaries, visual analysis can identify title cards or abrupt scene changes. OpenCV (`cv2`) provides the necessary API to seek through a video file efficiently without decoding every frame [cite: 29, 30].

### 5.2 Scene Change Detection (Frame Differencing)

If a chapter transition is marked by a slide change, frame differencing can detect it. By taking a frame immediately before the audio timestamp and a frame immediately after, we can compute the Absolute Difference.

```python
def detect_scene_change(frame1: np.ndarray, frame2: np.ndarray, threshold: float = 30.0) -> bool:
    """
    Detects if a scene change occurred between two frames.
    """
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Compute absolute difference
    diff = cv2.absdiff(gray1, gray2)
    
    # Calculate the mean pixel difference
    mean_diff = np.mean(diff)
    
    # If the mean difference exceeds the threshold, a significant change occurred
    return mean_diff > threshold
```

## 8. Complete Working Python Implementation


Below is the complete, reusable skill module integrating audio extraction, Whisper transcription, fuzzy chapter detection, and OpenCV validation.

```python
"""
Video Chapter Detection and Analysis Module
Requires:
pip install openai-whisper==20250625 thefuzz[speedup] opencv-python
System dependency: ffmpeg
"""

import os
import json
import subprocess
import cv2
import numpy as np
import whisper
from thefuzz import fuzz
from typing import List, Dict, Optional, Any

class VideoChapterAnalyzer:
    def __init__(self, model_size: str = "base"):
        """
        Initializes the Analyzer, loading the specified Whisper model.
        """
        print(f"Loading Whisper '{model_size}' model...")
        # Validates model size using the API
        if model_size not in whisper.available_models():
            raise ValueError(f"Invalid model. Choose from {whisper.available_models()}")
            
        self.model = whisper.load_model(model_size)
        
    def extract_audio(self, video_path: str, output_wav: str) -> bool:
        """
        Extracts 16kHz Mono WAV audio using FFmpeg subprocess.
        """
        print(f"Extracting audio from {video_path}...")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
            output_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"FFmpeg extraction failed: {res.stderr}")
            return False
        return True

    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribes audio with word-level timestamps and strict hallucination controls.
        """
        print("Starting Whisper transcription (this may take a while)...")
        # Ensure language='en', no condition on previous text for accuracy
        result = self.model.transcribe(
            audio=audio_path,
            language="en",
            word_timestamps=True,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0.0
        )
        return result

    def find_chapters_in_transcript(self, expected_chapters: List[str], transcript_result: Dict) -> List[Dict]:
        """
        Uses sliding window and fuzzy string matching to map chapter titles to timestamps.
        """
        print("Analyzing transcript for chapter boundaries...")
        
        # Flatten all words from the segmented dictionary
        all_words = []
        for segment in transcript_result.get("segments", []):
            if "words" in segment:
                all_words.extend(segment["words"])
                
        if not all_words:
            print("No word timestamps found. Ensure word_timestamps=True.")
            return []

        chapter_timestamps = []
        
        for chapter in expected_chapters:
            window_size = len(chapter.split()) + 2 # Allow margin for filler words
            best_score = 0
            best_time = 0.0
            
            for i in range(len(all_words) - window_size + 1):
                window = all_words[i : i + window_size]
                text_window = " ".join([w["word"].strip() for w in window])
                
                # Token set ratio handles substrings well
                score = fuzz.token_set_ratio(chapter.lower(), text_window.lower())
                
                if score > best_score and score >= 80: # 80 is our confidence threshold
                    best_score = score
                    best_time = window["start"]
                    
            if best_score >= 80:
                chapter_timestamps.append({
                    "chapter_title": chapter,
                    "timestamp_sec": float(best_time),
                    "confidence": best_score
                })
            else:
                print(f"Warning: Could not find confident match for '{chapter}'")
                
        # Sort chronologically
        chapter_timestamps.sort(key=lambda x: x["timestamp_sec"])
        return chapter_timestamps

    def validate_scene_visually(self, video_path: str, timestamp_sec: float) -> bool:
        """
        Validates a transition visually by calculating absolute pixel difference
        1 second before and 1 second after the timestamp.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False
            
        try:
            # Grab frame 1 second before
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0, (timestamp_sec - 1.0) * 1000))
            ret1, frame1 = cap.read()
            
            # Grab frame 1 second after
            cap.set(cv2.CAP_PROP_POS_MSEC, (timestamp_sec + 1.0) * 1000)
            ret2, frame2 = cap.read()
            
            if not ret1 or not ret2:
                return False
                
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray1, gray2)
            
            # If mean pixel shift > 20, we assume a scene change (e.g. title card)
            return np.mean(diff) > 20.0
        finally:
            cap.release()

    def process_video(self, video_path: str, expected_chapters: List[str], output_json: str):
        """
        End-to-End processing pipeline.
        """
        audio_path = "temp_audio.wav"
        
        # 1. Extract
        if not self.extract_audio(video_path, audio_path):
            return
            
        # 2. Transcribe
        transcript = self.transcribe_audio(audio_path)
        
        # 3. Find Chapters
        chapters = self.find_chapters_in_transcript(expected_chapters, transcript)
        
        # 4. Validate Visually
        print("Performing visual validation...")
        for ch in chapters:
            is_scene_change = self.validate_scene_visually(video_path, ch["timestamp_sec"])
            ch["visual_transition_detected"] = is_scene_change
            
        # 5. Output
        with open(output_json, "w") as f:
            json.dump(chapters, f, indent=4)
            
        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        print(f"Processing complete! Results saved to {output_json}")