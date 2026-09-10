import subprocess
import json
import os
import re
import sys
import tempfile

# ============================================================
# evo-video-filler-word-remover — Utility Library
# ============================================================
# Detects filler words in interview videos using faster-whisper ASR,
# outputs timestamped annotations, and stitches filler clips into
# a compilation video.
#
# Domain notes (from deep research):
# - faster-whisper with CTranslate2 is optimal for CPU-only envs
#   (avoids multi-GB PyTorch dependency, uses SIMD/int8 optimizations)
# - Whisper tokens contain leading spaces and erratic capitalization;
#   rigorous normalization is required before filler matching
# - Whisper has a strong bias toward omitting "um"/"uh" (trained on
#   cleaned subtitles); condition_on_previous_text=False helps preserve them
# - VAD filter (Silero) prevents hallucination on silent segments
# - Sub-second video cutting requires re-encoding (stream copy only
#   cuts at keyframes, which are typically 2-10s apart)
# - MPEG-TS containers allow seamless concatenation via concat demuxer
# ============================================================

# --------------- Filler word configuration ---------------

# Single-word fillers to detect
SINGLE_WORD_FILLERS = {
    "um", "uh", "hum", "hmm", "mhm",
    "like", "yeah", "so", "well", "okay", "basically"
}

# Multi-word filler phrases (as tuples for n-gram matching)
MULTI_WORD_FILLER_TUPLES = {
    ("you", "know"),
    ("i", "mean"),
    ("kind", "of"),
    ("i", "guess"),
}

# Also keep string versions for annotation output
MULTI_WORD_FILLERS_STR = {"you know", "i mean", "kind of", "i guess"}

# Hesitation equivalence class — Whisper may transcribe these variably
# e.g., "um" vs "umm" vs "hm" vs "hmm"
HESITATION_VARIANTS = {
    "umm": "um", "uhh": "uh", "hm": "hmm",
    "mmm": "mhm", "mm": "mhm", "mmhmm": "mhm",
    "ugh": "uh", "uhhh": "uh", "ummm": "um",
    "humm": "hum",
}

# Duration estimates for filler words (seconds) — used for segment extraction
# These represent typical acoustic durations of each filler type
DURATION_MAP = {
    # Short hesitations
    "uh": 0.3, "so": 0.3,
    # Medium hesitations
    "um": 0.4, "like": 0.4, "yeah": 0.4, "well": 0.4, "okay": 0.4,
    # Longer vocalizations
    "hmm": 0.5, "hum": 0.5, "mhm": 0.5, "basically": 0.55,
    # Multi-word phrases
    "you know": 0.55, "i mean": 0.55, "kind of": 0.55, "i guess": 0.55,
}

# Padding around filler timestamps to capture full acoustic envelope
# Whisper's temporal resolution is ~20ms; word boundaries are estimates
# from DTW cross-attention, so padding prevents clipping transients
BUFFER_BEFORE = 0.15   # 150ms before filler start
BUFFER_AFTER = 0.10    # 100ms after filler end


# --------------- Audio extraction ---------------

def extract_audio(video_path, audio_path="/tmp/audio_filler.wav"):
    """Extract audio from video as 16kHz mono 16-bit PCM WAV.

    Whisper models are hardcoded to process 16kHz mono audio.
    Using -vn skips video decoding for faster extraction.

    Args:
        video_path: Path to input video file
        audio_path: Path for output WAV file

    Returns:
        Path to extracted audio file

    Raises:
        FileNotFoundError: If video file doesn't exist
        RuntimeError: If ffmpeg extraction fails
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                   # discard video stream (faster)
        "-acodec", "pcm_s16le",  # 16-bit little-endian PCM
        "-ar", "16000",          # 16kHz sample rate (Whisper requirement)
        "-ac", "1",              # mono channel
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[:500]}")

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        raise RuntimeError("Audio extraction produced empty or missing file")

    return audio_path


# --------------- Transcription ---------------

def transcribe_audio(audio_path, model_size="small"):
    """Transcribe audio using faster-whisper with word-level timestamps.

    Uses optimized settings for filler word detection on CPU:
    - int8 quantization for speed/memory efficiency
    - VAD filter to prevent hallucination on silence
    - condition_on_previous_text=False to preserve disfluencies
    - temperature=0.0 for deterministic greedy decoding

    Args:
        audio_path: Path to 16kHz mono WAV file
        model_size: Whisper model size (default: "small")
                    "small" or "small.en" recommended for CPU filler detection

    Returns:
        List of word dicts: [{"word": str, "start": float, "end": float}, ...]
    """
    from faster_whisper import WhisperModel

    # int8 quantization: ~50% memory reduction, significant CPU speedup,
    # negligible accuracy loss (~0.3%) per CTranslate2 benchmarks
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,              # REQUIRED for filler detection
        language="en",
        condition_on_previous_text=False,   # Prevents skipping disfluencies;
                                            # Whisper tends to "correct" speech
                                            # to clean grammar without this
        vad_filter=True,                    # Silero VAD: eliminates >90% of
                                            # hallucination on silent segments
        vad_parameters=dict(
            min_silence_duration_ms=300,    # Minimum silence to split on
        ),
        temperature=0.0,                   # Greedy decoding for consistency
        no_speech_threshold=0.6,           # Filter low-confidence non-speech
        log_prob_threshold=-1.0,           # Discard very low confidence tokens
    )

    words = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                words.append({
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "probability": w.probability,
                })

    print(f"  Transcribed {len(words)} words (language: {info.language}, "
          f"probability: {info.language_probability:.2f})")

    return words


# --------------- Text normalization ---------------

def normalize_word(word_str):
    """Normalize a word for filler matching.

    Whisper tokens often contain:
    - Leading spaces (e.g., " um", " like")
    - Arbitrary capitalization (e.g., "Um", "Like", "I")
    - Trailing punctuation (e.g., "uh,", "like...")

    This function strips all of these for reliable matching.

    Args:
        word_str: Raw word string from Whisper

    Returns:
        Normalized lowercase word without punctuation
    """
    w = word_str.strip().lower()
    # Remove all punctuation (keep only word chars and spaces)
    w = re.sub(r'[^\w\s]', '', w)
    w = w.strip()

    # Map hesitation variants to canonical forms
    # e.g., "umm" -> "um", "hm" -> "hmm"
    if w in HESITATION_VARIANTS:
        w = HESITATION_VARIANTS[w]

    return w


# --------------- Filler detection ---------------

def detect_fillers(words):
    """Detect filler words and phrases from transcribed word list.

    Uses a dual-pass approach:
    1. Multi-word phrases first (greedy longest match via n-gram scan)
       to prevent "you" and "know" from being matched individually
    2. Single-word fillers for remaining unmatched words

    Args:
        words: List of dicts with 'word', 'start', 'end' keys

    Returns:
        List of dicts with 'word' and 'timestamp' keys, sorted by timestamp
    """
    if not words:
        return []

    fillers = []
    used_indices = set()  # Track indices consumed by multi-word matches

    # Normalize all words once for efficient matching
    normalized = [normalize_word(w["word"]) for w in words]

    # Compute max phrase length for sliding window
    max_phrase_len = max(len(phrase) for phrase in MULTI_WORD_FILLER_TUPLES)

    # Pass 1: Multi-word filler phrases (n-gram sliding window)
    # Check from longest phrases down to 2-word phrases (greedy longest match)
    # This prevents partial matches from consuming words needed for longer phrases
    i = 0
    while i < len(words):
        match_found = False
        for window_size in range(min(max_phrase_len, len(words) - i), 1, -1):
            window_tuple = tuple(normalized[i:i + window_size])
            if window_tuple in MULTI_WORD_FILLER_TUPLES:
                phrase_str = " ".join(window_tuple)
                fillers.append({
                    "word": phrase_str,
                    "timestamp": round(words[i]["start"], 2)
                })
                for j in range(i, i + window_size):
                    used_indices.add(j)
                i += window_size
                match_found = True
                break
        if not match_found:
            i += 1

    # Pass 2: Single-word fillers (skip words already used in multi-word matches)
    for i, w in enumerate(words):
        if i in used_indices:
            continue
        norm = normalized[i]
        if norm in SINGLE_WORD_FILLERS:
            fillers.append({
                "word": norm,
                "timestamp": round(w["start"], 2)
            })

    # Sort by timestamp
    fillers.sort(key=lambda x: x["timestamp"])

    # Deduplicate: remove entries with identical (word, timestamp)
    # This can happen if Whisper produces duplicate tokens at the same position
    seen = set()
    deduped = []
    for f in fillers:
        key = (f["word"], f["timestamp"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    return deduped


# --------------- Segment computation ---------------

def get_filler_duration(word):
    """Get estimated acoustic duration for a filler word.

    Falls back to 0.4s for unknown filler types.
    """
    return DURATION_MAP.get(word, 0.4)


def compute_segments(fillers):
    """Compute video extraction segments from filler annotations.

    Applies temporal padding around each filler word to capture the full
    acoustic envelope (Whisper's word boundaries are DTW estimates with
    ~20ms resolution and can be slightly imprecise).

    Merges overlapping or closely-spaced segments (gap < 100ms) to avoid
    producing micro-clips that cause concatenation artifacts.

    Args:
        fillers: List of dicts with 'word' and 'timestamp' keys

    Returns:
        List of (start, end) tuples in seconds
    """
    if not fillers:
        return []

    # Compute raw segments with padding
    raw_segments = []
    for f in fillers:
        start = max(0, f["timestamp"] - BUFFER_BEFORE)
        end = f["timestamp"] + get_filler_duration(f["word"]) + BUFFER_AFTER
        raw_segments.append((start, end))

    # Sort by start time
    raw_segments.sort(key=lambda x: x[0])

    # Merge overlapping or closely-spaced segments (gap < 100ms)
    # This prevents micro-cuts that produce encoding artifacts
    merged = [raw_segments[0]]
    for start, end in raw_segments[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 0.1:  # overlap or gap < 100ms
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


# --------------- Video clip extraction and stitching ---------------

def extract_and_stitch(video_path, segments, output_path):
    """Extract video segments and concatenate into output video.

    Uses re-encoding (libx264/aac) for frame-accurate sub-second cuts.
    Stream copy (-c copy) cannot achieve sub-second precision because
    modern video codecs use keyframes spaced 2-10 seconds apart.

    Intermediate clips use MPEG-TS (.ts) container format which supports
    seamless concatenation via the concat demuxer without re-encoding
    the final output.

    Args:
        video_path: Path to source video
        segments: List of (start, end) tuples in seconds
        output_path: Path for output compilation video

    Returns:
        Path to output video, or None if no segments extracted
    """
    if not segments:
        print("No segments to extract")
        return None

    tmp_dir = tempfile.mkdtemp(prefix="filler_segments_")

    try:
        seg_files = []
        for i, (start, end) in enumerate(segments):
            seg_path = os.path.join(tmp_dir, f"seg_{i:04d}.ts")
            duration = end - start

            # Use input seeking (-ss before -i) for speed, combined with
            # re-encoding for frame accuracy. The re-encode creates a new
            # keyframe at the exact start position.
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),       # Fast seek (input position)
                "-i", video_path,
                "-t", str(duration),     # Exact duration
                "-c:v", "libx264",       # Re-encode video for precise cuts
                "-preset", "superfast",  # Fast encoding (acceptable quality)
                "-crf", "23",            # Standard visual quality
                "-c:a", "aac",           # Re-encode audio
                "-b:a", "128k",
                "-avoid_negative_ts", "make_zero",  # Normalize PTS to start at 0
                seg_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                seg_files.append(seg_path)
            else:
                print(f"Warning: Failed to extract segment {i} "
                      f"({start:.2f}-{end:.2f}s)")
                if result.stderr:
                    # Print last portion of stderr for debugging
                    print(f"  stderr: {result.stderr[-300:]}")

        if not seg_files:
            print("No segments were successfully extracted")
            return None

        # Create concat demuxer list file
        # Format: each line is "file '<absolute_path>'"
        concat_path = os.path.join(tmp_dir, "concat.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            for seg_path in seg_files:
                # Use absolute paths; -safe 0 is required for this
                f.write(f"file '{os.path.abspath(seg_path)}'\n")

        # Concatenate using concat demuxer with stream copy
        # (no re-encoding needed since all clips share the same codec params)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",           # Allow absolute paths in list file
            "-i", concat_path,
            "-c", "copy",           # Stream copy (clips already re-encoded)
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # Fallback: try with re-encoding if stream copy concat fails
            # This can happen with codec parameter mismatches between clips
            print("Warning: concat with stream copy failed, retrying with re-encode...")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_path,
                "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr[:500]}")

        print(f"Output video created: {output_path}")
        print(f"  Segments extracted: {len(seg_files)}")

        return output_path

    finally:
        # Clean up temporary segment files
        try:
            for f_name in os.listdir(tmp_dir):
                os.remove(os.path.join(tmp_dir, f_name))
            os.rmdir(tmp_dir)
        except OSError:
            pass  # Best-effort cleanup


# --------------- Main pipeline ---------------

def run_pipeline(video_path, output_json, output_video):
    """Run the complete filler word detection and extraction pipeline.

    Steps:
    1. Extract audio from video (16kHz mono WAV)
    2. Transcribe with faster-whisper (word-level timestamps)
    3. Detect filler words via dual-pass matching
    4. Save annotations as JSON
    5. Compute extraction segments with padding and merging
    6. Extract and stitch filler clips into compilation video

    Args:
        video_path: Path to input video (e.g., /root/input.mp4)
        output_json: Path to save annotations JSON (e.g., /root/annotations.json)
        output_video: Path to save output video (e.g., /root/output.mp4)

    Returns:
        List of filler annotation dicts
    """
    print("=" * 60)
    print("Filler Word Detection Pipeline")
    print("=" * 60)

    # Step 1: Extract audio
    print("\nStep 1: Extracting audio from video...")
    audio_path = extract_audio(video_path)
    print(f"  Audio extracted to {audio_path}")

    # Step 2: Transcribe
    print("\nStep 2: Transcribing with faster-whisper...")
    # Try small model first; fall back to base if it fails (e.g., OOM)
    try:
        words = transcribe_audio(audio_path, model_size="small")
    except Exception as e:
        print(f"  Warning: 'small' model failed ({e}), falling back to 'base'...")
        words = transcribe_audio(audio_path, model_size="base")

    if not words:
        print("  WARNING: No words transcribed. The audio may be silent or corrupted.")
        # Save empty annotations and create minimal output
        with open(output_json, "w") as f:
            json.dump([], f, indent=2)
        print(f"  Empty annotations saved to {output_json}")
        return []

    # Step 3: Detect fillers
    print("\nStep 3: Detecting filler words...")
    fillers = detect_fillers(words)
    print(f"  Found {len(fillers)} filler words/phrases")

    # Print detected fillers for debugging
    for f in fillers:
        print(f"    [{f['timestamp']:.2f}s] \"{f['word']}\"")

    # Step 4: Save annotations
    with open(output_json, "w") as f:
        json.dump(fillers, f, indent=2)
    print(f"\n  Annotations saved to {output_json}")

    # Step 5 & 6: Extract and stitch
    if fillers:
        print("\nStep 4: Computing extraction segments...")
        segments = compute_segments(fillers)
        print(f"  {len(segments)} segments to extract (after merging overlaps)")

        print("\nStep 5: Extracting and stitching filler clips...")
        extract_and_stitch(video_path, segments, output_video)
    else:
        print("\n  No filler words found — no output video generated.")

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)

    return fillers