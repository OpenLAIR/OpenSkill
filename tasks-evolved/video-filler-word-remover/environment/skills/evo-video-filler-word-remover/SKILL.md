---
name: evo-video-filler-word-remover
description: Detects filler words in video/audio interviews using ASR (faster-whisper) with word-level timestamps, saves annotations as JSON, and extracts filler clips into a compilation video.
---

# evo-video-filler-word-remover

## Purpose
Detects filler words and phrases in interview videos using speech recognition (faster-whisper), outputs timestamped annotations as JSON, and stitches all filler word clips into a single compilation video.

## Key Concepts
- Uses **faster-whisper** (CTranslate2-based Whisper) for CPU-optimized transcription
- **`small` model with `int8` quantization**: optimal tradeoff between accuracy and CPU speed (~1GB RAM, 1.5-3x real-time)
- **Word-level timestamps** via DTW cross-attention alignment (~20ms resolution)
- **VAD filter** (Silero) enabled to prevent hallucination on silence
- **`condition_on_previous_text=False`** to prevent the model from skipping disfluencies in favor of grammatically clean output
- **Dual-pass detection**: multi-word phrases first (greedy longest match), then single-word fillers
- **Text normalization**: lowercase, strip punctuation, handle Whisper's leading-space tokenization artifacts
- **Hesitation equivalence**: um, uh, hum, hmm, mhm, umm variants all recognized
- **Frame-accurate cutting** with re-encoding (libx264/aac) — stream copy cannot achieve sub-second precision due to keyframe spacing
- **MPEG-TS intermediate containers** for seamless concat demuxer stitching
- **Timestamp padding** (150ms before, 100ms after) to capture full acoustic envelope of filler utterances
- **Overlapping segment merging** (gap < 100ms threshold) to avoid micro-cuts

## Filler Words Detected
### Single-word
um, uh, hum, hmm, mhm, like, yeah, so, well, okay, basically

### Multi-word (n-gram scan)
you know, i mean, kind of, i guess

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-video-filler-word-remover/scripts')
from utils import run_pipeline

# Full pipeline
fillers = run_pipeline('/root/input.mp4', '/root/annotations.json', '/root/output.mp4')

# Or step by step:
from utils import (extract_audio, transcribe_audio, detect_fillers,
                    compute_segments, extract_and_stitch)

audio_path = extract_audio('/root/input.mp4')
words = transcribe_audio(audio_path, model_size='small')
fillers = detect_fillers(words)
segments = compute_segments(fillers)
extract_and_stitch('/root/input.mp4', segments, '/root/output.mp4')
```

## Pipeline Steps
1. **Extract audio** from video as 16kHz mono 16-bit PCM WAV (Whisper's native input format)
2. **Transcribe** with faster-whisper using word-level timestamps, VAD filter, and disfluency-preserving settings
3. **Detect fillers** via dual-pass (multi-word n-gram scan first, then single-word) with text normalization
4. **Save annotations** as JSON array with `word` and `timestamp` fields
5. **Compute extraction segments** with padding, duration estimates, and overlap merging
6. **Extract segments** with re-encoding to .ts intermediate files for frame accuracy
7. **Concatenate** .ts segments into final output.mp4 via concat demuxer

## Transcription Parameters (Domain-Optimized)
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `model_size` | `small` / `small.en` | Best accuracy/speed tradeoff for CPU; captures disfluencies unlike tiny/base |
| `compute_type` | `int8` | ~50% memory reduction, significant speedup, negligible accuracy loss (~0.3%) |
| `word_timestamps` | `True` | Required for per-word temporal alignment |
| `vad_filter` | `True` | Silero VAD eliminates >90% of hallucination on silence |
| `condition_on_previous_text` | `False` | Prevents model from "correcting" filler words to clean grammar |
| `temperature` | `0.0` | Greedy decoding for deterministic, consistent results |
| `no_speech_threshold` | `0.6` | Filters low-confidence noise misidentified as speech |

## Duration Estimates
- Short (uh, so): ~0.3s
- Medium (um, like, yeah, well, okay): ~0.4s
- Long (hmm, hum, mhm, basically): ~0.5-0.55s
- Multi-word (you know, i mean, kind of, i guess): ~0.55s
- Buffer before start: 150ms
- Buffer after end: 100ms