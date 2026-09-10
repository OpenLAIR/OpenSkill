"""
Audio extraction and Whisper transcription module.

Key domain insights applied:
- FFmpeg extraction to 16kHz mono PCM WAV matches Whisper's expected input format exactly,
  avoiding internal resampling overhead and potential quality loss.
- word_timestamps=True uses cross-attention DTW for much better time alignment than
  segment-level timestamps, which can drift over long audio.
- condition_on_previous_text=False prevents hallucination loops in long recordings
  where silence or music can cause the model to repeat phantom text.
- language="en" bypasses auto-detection, saving compute and preventing language shifts.
- temperature=0.0 gives deterministic decoding, ideal for clear tutorial narration.
- no_speech_threshold=0.6 helps ignore silent/music regions.
"""

import subprocess
import os
import json


def extract_audio(video_path, output_wav_path="/tmp/tutorial_audio.wav"):
    """
    Extract 16kHz mono PCM WAV audio from video using FFmpeg.
    
    This format exactly matches Whisper's internal expectations:
    - 16000 Hz sample rate
    - Single channel (mono)
    - 16-bit PCM encoding
    
    Pre-extracting avoids Whisper having to parse the full MP4 container
    dynamically, which is memory-intensive for 23+ minute files.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    command = [
        "ffmpeg",
        "-y",                    # Overwrite without prompting
        "-i", video_path,        # Input file
        "-vn",                   # Strip video stream
        "-acodec", "pcm_s16le",  # 16-bit little-endian PCM
        "-ac", "1",              # Mono channel
        "-ar", "16000",          # 16 kHz sample rate
        output_wav_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300  # 5 minute timeout for safety
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg audio extraction timed out after 300 seconds")

    if not os.path.exists(output_wav_path):
        raise RuntimeError(f"FFmpeg completed but output file not found: {output_wav_path}")

    file_size = os.path.getsize(output_wav_path)
    if file_size < 1000:
        raise RuntimeError(f"Extracted audio file suspiciously small ({file_size} bytes)")

    print(f"Audio extracted: {output_wav_path} ({file_size / 1024 / 1024:.1f} MB)")
    return output_wav_path


def transcribe_video(audio_path, model_size="base", save_path=None):
    """
    Transcribe audio using Whisper with word-level timestamps.
    
    Parameters optimized based on domain research:
    - word_timestamps=True: Uses DTW on cross-attention weights for precise word timing
    - condition_on_previous_text=False: Prevents hallucination loops in long audio
    - language="en": Skips auto-detection for English tutorials
    - temperature=0.0: Deterministic decoding for clear speech
    - no_speech_threshold=0.6: Filters silent regions
    - fp16=False on CPU: Avoids FP16 warnings/errors on CPU-only systems
    
    Returns the full Whisper result dict with segments and word-level timestamps.
    """
    import whisper
    import torch

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Loading Whisper '{model_size}' model...")
    model = whisper.load_model(model_size)

    # Detect if we're on CPU - fp16 is not supported on CPU
    use_fp16 = torch.cuda.is_available()

    print(f"Transcribing with word_timestamps=True (fp16={use_fp16})...")
    result = model.transcribe(
        audio_path,
        language="en",
        word_timestamps=True,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        temperature=0.0,
        fp16=use_fp16
    )

    # Extract stats for logging
    num_segments = len(result.get("segments", []))
    total_words = sum(
        len(seg.get("words", []))
        for seg in result.get("segments", [])
    )
    print(f"Transcription complete: {num_segments} segments, {total_words} words")

    # Optionally save transcript for debugging/reuse
    if save_path:
        save_transcript(result, save_path)

    return result


def save_transcript(result, path):
    """Save Whisper transcript result to JSON for debugging and reuse."""
    # Extract serializable data
    serializable = {
        "text": result.get("text", ""),
        "language": result.get("language", ""),
        "segments": []
    }
    for seg in result.get("segments", []):
        seg_data = {
            "id": seg.get("id"),
            "start": seg.get("start"),
            "end": seg.get("end"),
            "text": seg.get("text"),
            "no_speech_prob": seg.get("no_speech_prob"),
            "words": seg.get("words", [])
        }
        serializable["segments"].append(seg_data)

    with open(path, 'w') as f:
        json.dump(serializable, f, indent=2)
    print(f"Transcript saved to {path}")


def get_all_words(transcript_result):
    """
    Flatten all word-level entries from Whisper segments into a single list.
    
    Each word dict has: {"word": str, "start": float, "end": float, "probability": float}
    
    Returns empty list if word_timestamps were not enabled during transcription.
    """
    all_words = []
    for segment in transcript_result.get("segments", []):
        words = segment.get("words", [])
        if words:
            all_words.extend(words)
        elif "text" in segment and "start" in segment:
            # Fallback: if no word-level timestamps, create pseudo-words from segment text
            # This is less accurate but prevents total failure
            text = segment["text"].strip()
            if text:
                all_words.append({
                    "word": text,
                    "start": segment["start"],
                    "end": segment["end"],
                    "probability": 0.5  # Low confidence marker
                })
    return all_words