# Domain Reference for evo-dubbing-audio-processing

**Responsibility**: Resample audio from Kokoro's native 24kHz to 48kHz, apply ITU-R BS.1770-4 two-pass loudness normalization via FFmpeg loudnorm filter, measure final LUFS, and produce normalized WAV files ready for muxing.

**Key functions to implement**: resample_audio, measure_lufs, normalize_loudness, process_segment_audio

---

## 5. ITU-R BS.1770-4 Loudness Measurement and Normalization


Maintaining consistent perceived loudness across dubbed audio segments ensures professional, "human-level high quality." The industry standard for this is ITU-R BS.1770-4, which measures audio in LUFS (Loudness Units relative to Full Scale) [cite: 37, 38].
*   **Target Levels**: Standard broadcast mandates `-23 LUFS` [cite: 37, 39]. Internet streaming (YouTube, Spotify) typically targets **-14 to -16 LUFS** [cite: 40]. High-quality speech dubbing should target **-16 LUFS** to sound present and intelligible on consumer devices.

## 6. Audio Manipulation with SciPy and Soundfile


Performing fine-grained, sample-level digital signal processing requires `numpy`, `scipy`, and `soundfile`.

## 10. Common Integration Pitfalls and Best Practices


A production pipeline typically fails not at the synthesis stage, but during integration. The following are the most pervasive pitfalls: