# Skill Creation Plan

**Task**: Multilingual video dubbing: parse SRT files, synthesize Japanese TTS audio fitted to time windows, normalize loudness per ITU-R BS.1770-4, mux dubbed audio into video, and generate a JSON report.

**Rationale**: The task has three distinct functional domains: (1) TTS synthesis with duration control, (2) audio processing including loudness normalization and resampling, and (3) video muxing and report generation. Combining audio processing with muxing keeps the pipeline simple while separating TTS synthesis (the most complex component) into its own skill.

**Number of skills**: 3

---

## Skill 1: evo-dubbing-tts-synthesis

**Description**: Synthesizes target-language speech from text using Kokoro TTS, with speed/duration control to fit precise time windows. Handles SRT parsing, text extraction, and produces WAV segments.

**Responsibility**: Parse SRT files (segments, source text, reference target text), read target language, synthesize TTS audio for each segment using Kokoro with speed adjustment to fit the time window, and save individual WAV segment files.

**Key functions**: `parse_srt_file`, `read_target_language`, `synthesize_segment`, `fit_audio_to_window`, `generate_tts_segments`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dubbing-tts-synthesis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-dubbing-audio-processing

**Description**: Handles audio resampling, loudness normalization per ITU-R BS.1770-4, and LUFS measurement for TTS segments to ensure broadcast-quality output.

**Responsibility**: Resample audio from Kokoro's native 24kHz to 48kHz, apply ITU-R BS.1770-4 two-pass loudness normalization via FFmpeg loudnorm filter, measure final LUFS, and produce normalized WAV files ready for muxing.

**Key functions**: `resample_audio`, `measure_lufs`, `normalize_loudness`, `process_segment_audio`

**Depends on**: evo-dubbing-tts-synthesis


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dubbing-audio-processing/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-dubbing-mux-report

**Description**: Muxes normalized TTS audio segments into the original video at precise time offsets using FFmpeg, and generates the JSON report with timing, drift, and loudness metadata.

**Responsibility**: Construct FFmpeg filter_complex commands with adelay to place audio segments at exact timestamps, mux with original video (copy video stream), enforce 48kHz mono AAC output, compute drift metrics, and write the structured JSON report.

**Key functions**: `build_ffmpeg_mux_command`, `mux_dubbed_video`, `calculate_drift`, `get_video_duration`, `generate_report_json`

**Depends on**: evo-dubbing-audio-processing


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dubbing-mux-report/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
