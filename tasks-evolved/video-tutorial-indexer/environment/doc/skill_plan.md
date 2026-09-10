# Skill Creation Plan

**Task**: Transcribe a 23-minute Blender tutorial video using Whisper and detect timestamps for 29 predefined chapter titles, outputting results as a structured JSON file.

**Rationale**: The task requires two distinct functional domains: (1) audio extraction and transcription via FFmpeg/Whisper, and (2) chapter timestamp detection via transcript analysis and fuzzy matching, followed by JSON output generation. These naturally separate into a transcription skill and a chapter detection/output skill.

**Number of skills**: 2

---

## Skill 1: evo-audio-transcription

**Description**: Extracts audio from MP4 video files using FFmpeg and transcribes them using OpenAI Whisper with word-level timestamps. Provides utilities for audio preprocessing and robust transcription with hallucination mitigation.

**Responsibility**: Audio extraction from video containers (FFmpeg subprocess), Whisper model loading and transcription with optimal parameters (word_timestamps, condition_on_previous_text, language, no_speech_threshold), returning structured transcript data with word-level timestamps.

**Key functions**: `extract_audio_from_video`, `transcribe_audio`, `get_all_words_with_timestamps`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-audio-transcription/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-chapter-detection

**Description**: Maps predefined chapter titles to timestamps in a Whisper transcript using sliding window fuzzy string matching, then generates the final structured JSON output with video metadata and chapter timestamps.

**Responsibility**: Fuzzy string matching of chapter titles against transcript words using sliding windows, enforcing monotonic ordering and boundary constraints, and writing the final tutorial_index.json output file in the required format.

**Key functions**: `find_chapter_timestamp`, `detect_all_chapters`, `enforce_monotonic_timestamps`, `generate_tutorial_index_json`

**Depends on**: evo-audio-transcription


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-chapter-detection/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
