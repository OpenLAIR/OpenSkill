---
name: evo-speaker-diarization-subtitles
description: End-to-end speaker diarization and subtitle generation pipeline for video/audio files. Extracts audio via ffmpeg, performs VAD (silero-vad), extracts ECAPA-TDNN speaker embeddings (speechbrain), clusters speakers (agglomerative clustering with cosine distance), transcribes with OpenAI Whisper, aligns transcripts to speakers via IoU overlap, and outputs RTTM, ASS subtitles, and a JSON report.
---

# evo-speaker-diarization-subtitles

End-to-end speaker diarization and subtitle generation pipeline for video/audio files.

## Pipeline
1. **Audio extraction**: ffmpeg → 16kHz mono 16-bit PCM WAV
2. **Voice Activity Detection**: silero-vad (with fallback to torch.hub if direct import unavailable)
3. **Speaker embedding extraction**: SpeechBrain ECAPA-TDNN (`spkrec-ecapa-voxceleb`)
4. **Speaker clustering**: Agglomerative clustering with cosine distance + silhouette-based speaker count selection
5. **Transcription**: OpenAI Whisper with word-level timestamps
6. **Alignment**: Word-level IoU overlap mapping from Whisper words to diarized speaker segments
7. **Output generation**: RTTM (pyannote.core or manual), ASS subtitles, JSON report

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-speaker-diarization-subtitles/scripts')
from utils import (
    extract_audio, get_audio_duration, run_vad,
    merge_close_segments, extract_speaker_embeddings,
    cluster_speakers, run_whisper_transcription,
    align_transcription_with_speakers,
    write_rttm, write_ass, write_report,
    format_time_ass
)
```

## Dependencies
ffmpeg, torch, torchaudio, speechbrain, openai-whisper, silero-vad,
scikit-learn, numpy, soundfile, scipy, pyannote.core

## Key Domain Notes
- ECAPA-TDNN embeddings are trained with angular margin loss → **cosine distance** is the correct metric for clustering.
- Silero VAD v6.2.0 uses `from silero_vad import load_silero_vad, get_speech_timestamps` (not torch.hub). Fallback to torch.hub is provided for older versions.
- Whisper `word_timestamps=True` enables word-level alignment critical for accurate speaker attribution.
- ASS time format uses centiseconds: `H:MM:SS.cc` — careful rollover handling is required.
- RTTM format: `SPEAKER <file_id> 1 <start> <duration> <NA> <NA> <speaker_label> <NA> <NA>`
- Speaker labels in RTTM use `spkNN` format; in ASS subtitles use `SPEAKER_NN` format.
- Segments shorter than ~0.5s yield unreliable embeddings; minimum 0.15s is enforced, 0.5s preferred.
```