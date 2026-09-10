# Skill Creation Plan

**Task**: Perform speaker diarization on input.mp4 and generate RTTM diarization output, ASS subtitles with speaker-labeled transcripts, and a JSON report.

**Rationale**: The task has three distinct functional domains: (1) audio processing with VAD and speaker clustering for diarization, (2) ASR transcription aligned with diarization labels, and (3) output formatting for RTTM/ASS/JSON. Combining diarization and transcription alignment into one skill keeps the core pipeline cohesive, while output formatting is a separate concern.

**Number of skills**: 3

---

## Skill 1: evo-diarization-pipeline

**Description**: End-to-end speaker diarization pipeline: extracts audio from video via ffmpeg, runs Silero VAD for speech activity detection, extracts ECAPA-TDNN speaker embeddings via SpeechBrain, and clusters them using agglomerative clustering with cosine distance. Returns diarization segments with speaker labels.

**Responsibility**: Audio extraction, VAD, speaker embedding extraction, clustering, and producing diarization segment data (start, end, speaker label).

**Key functions**: `extract_audio_from_video`, `run_silero_vad`, `extract_speaker_embeddings`, `cluster_speakers`, `run_diarization_pipeline`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-diarization-pipeline/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-transcription-alignment

**Description**: Transcribes audio using OpenAI Whisper with word-level timestamps, then aligns each word to diarized speaker segments using overlap-based (IoU) assignment. Groups contiguous same-speaker words into coherent transcript lines.

**Responsibility**: ASR transcription via Whisper, word-to-speaker alignment using temporal overlap, and grouping words into speaker-attributed transcript segments.

**Key functions**: `transcribe_audio`, `assign_speaker_to_word`, `align_transcript_with_diarization`, `group_words_into_lines`

**Depends on**: evo-diarization-pipeline


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-transcription-alignment/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-output-formatting

**Description**: Handles all output file generation: writes RTTM files using pyannote.core Annotation, generates ASS subtitle files with proper header/timing/speaker labels, and creates the JSON report with pipeline metadata.

**Responsibility**: Formatting and writing RTTM diarization files, ASS subtitle files with centisecond time conversion and speaker labels, and JSON report generation.

**Key functions**: `export_rttm`, `format_ass_time`, `export_ass_subtitles`, `generate_report_json`

**Depends on**: evo-diarization-pipeline, evo-transcription-alignment


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-output-formatting/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
