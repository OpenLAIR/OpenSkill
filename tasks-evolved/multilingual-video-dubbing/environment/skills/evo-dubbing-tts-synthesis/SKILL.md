---
name: evo-dubbing-tts-synthesis
description: Synthesizes target-language speech from text using Kokoro TTS, with speed/duration control to fit precise time windows. Handles SRT parsing, text extraction, and produces WAV segments.
---

# evo-dubbing-tts-synthesis

Synthesizes target-language TTS audio fitted to SRT time windows using Kokoro.

## Key Functions

- `parse_srt_file(path)` - Parse SRT file, return list of dicts with index, text, start_sec, end_sec, duration_sec
- `read_target_language(path)` - Read target language code from file
- `synthesize_segment(text, lang_code, voice, speed)` - Generate audio array using Kokoro
- `fit_audio_to_window(text, lang_code, voice, target_duration)` - Synthesize and adjust speed to fit window
- `generate_tts_segments(segments_srt, source_srt, target_srt, lang_code, output_dir)` - Full pipeline

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-dubbing-tts-synthesis/scripts')
from utils import parse_srt_file, read_target_language, generate_tts_segments

segments = parse_srt_file('/root/segments.srt')
lang = read_target_language('/root/target_language.txt')
results = generate_tts_segments(
    '/root/segments.srt', '/root/source_text.srt',
    '/root/reference_target_text.srt', lang, '/outputs/tts_segments'
)
```

## Technical Details

- Kokoro native sample rate: 24000 Hz
- Japanese lang_code for Kokoro: 'j'
- Default Japanese voice: 'jf_alpha'
- Speed parameter range: 0.5 to 2.0 for quality
- SRT time conversion: sub.start.ordinal / 1000.0 for seconds
- Use encoding='utf-8-sig' for BOM handling
