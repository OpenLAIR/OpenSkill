---
name: evo-dubbing-audio-processing
description: Handles audio resampling, loudness normalization per ITU-R BS.1770-4, and LUFS measurement for TTS segments to ensure broadcast-quality output.
---

# evo-dubbing-audio-processing

Resamples audio from Kokoro's 24kHz to 48kHz and applies ITU-R BS.1770-4 loudness normalization.

## Key Functions

- `resample_audio(audio, orig_sr, target_sr)` - Resample numpy array
- `measure_lufs(audio_path)` - Measure LUFS using FFmpeg loudnorm filter (pass 1)
- `normalize_loudness(audio_path, output_path, target_lufs)` - Two-pass loudness normalization
- `process_segment_audio(input_path, output_path, target_sr, target_lufs)` - Full processing pipeline

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-dubbing-audio-processing/scripts')
from utils import process_segment_audio, measure_lufs

process_segment_audio('/outputs/tts_segments/seg_0.wav', '/outputs/tts_segments/seg_0.wav', 48000, -23.0)
lufs = measure_lufs('/outputs/tts_segments/seg_0.wav')
```

## Technical Details

- ITU-R BS.1770-4 standard for loudness measurement
- Target LUFS: -23.0 for broadcast standard
- Two-pass FFmpeg loudnorm: measure first, then normalize with linear=true
- Resample from 24kHz to 48kHz using scipy.signal.resample_poly
- Output: 48kHz mono WAV PCM_16
