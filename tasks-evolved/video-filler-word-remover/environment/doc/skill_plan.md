# Skill Creation Plan

**Task**: Detect filler words in an interview video with timestamps, save annotations as JSON, and stitch filler word clips into a single output video.

**Rationale**: The task has three distinct concerns: (1) speech-to-text transcription with word-level timestamps, (2) filler word detection via text matching with normalization, and (3) video clip extraction and concatenation. Skills 1 and 2 are tightly coupled (transcription feeds directly into detection), so they can be combined. Video processing is a separate concern. This yields 2 skills with clear boundaries.

**Number of skills**: 2

---

## Skill 1: evo-speech-filler-detection

**Description**: Extracts audio from video, transcribes it using faster-whisper with word-level timestamps, and detects filler words/phrases using normalized text matching with sliding window logic. Outputs structured annotations as JSON.

**Responsibility**: Audio extraction from video via ffmpeg subprocess, speech-to-text transcription using faster-whisper with optimized CPU settings, text normalization (lowercasing, punctuation stripping, whitespace handling), single-word and multi-word filler phrase detection using n-gram sliding window, and JSON annotation output.

**Key functions**: `extract_audio_for_whisper`, `transcribe_with_word_timestamps`, `normalize_word`, `detect_filler_words`, `save_annotations_json`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-speech-filler-detection/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-video-clip-stitcher

**Description**: Extracts precise video clips at given timestamps from a source video using ffmpeg with re-encoding for sub-second accuracy, then concatenates all clips into a single output video using the concat demuxer.

**Responsibility**: Frame-accurate video clip extraction with re-encoding (libx264/aac), timestamp padding for acoustic continuity, temporary clip file management, concat demuxer list generation, and final video concatenation with stream copy.

**Key functions**: `extract_clip`, `concatenate_clips`, `build_filler_compilation`

**Depends on**: evo-speech-filler-detection


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-video-clip-stitcher/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
