# Domain Reference for evo-dubbing-tts-synthesis

**Responsibility**: Parse SRT files (segments, source text, reference target text), read target language, synthesize TTS audio for each segment using Kokoro with speed adjustment to fit the time window, and save individual WAV segment files.

**Key functions to implement**: parse_srt_file, read_target_language, synthesize_segment, fit_audio_to_window, generate_tts_segments

---

## 1. SRT File Parsing with pysrt


The SubRip Subtitle (SRT) format is the ubiquitous standard for defining subtitle timing and text. In Python, the `pysrt` library (v1.1.2) provides a robust, object-oriented API for interacting with these files [cite: 1, 2]. Accurately parsing this data establishes the foundational time windows constraint for the entire dubbing pipeline.

## 2. Speech Synthesis with Kokoro TTS (v0.9.4)


Kokoro-82M is a highly efficient, open-weight non-autoregressive text-to-speech model based on the StyleTTS 2 architecture [cite: 8, 9]. At only 82 million parameters, it is optimal for local deployment in a dubbing pipeline [cite: 10, 11].

## 3. Alternative Speech Synthesis with `edge-tts` (v6.1.12)


When high-fidelity on-device processing via Kokoro is insufficient, or varying voice sets are required, the `edge-tts` library serves as a robust alternative. It intercepts the underlying API requests used by the Microsoft Edge "Read Aloud" function, circumventing the need for Azure API keys [cite: 19].

## 7. Speed and Rate Adjustment Strategies


Fitting generated TTS into a fixed temporal window without causing a "chipmunk" effect (pitch distortion) requires advanced Time-Scale Modification (TSM).