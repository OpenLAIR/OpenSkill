# Skill Creation Plan

**Task**: Count unique pedestrians in surveillance videos using VLM APIs and write results to an Excel file

**Rationale**: The task has three distinct concerns: (1) video frame extraction and encoding, (2) VLM-based pedestrian counting with de-duplication logic, and (3) Excel output formatting. However, since the VLM inference is tightly coupled with the frame preparation and the Excel output is simple, a 2-skill decomposition cleanly separates video/image processing from the VLM analysis + reporting pipeline.

**Number of skills**: 2

---

## Skill 1: evo-video-frame-extraction

**Description**: Extracts and encodes sampled frames from video files using MoviePy 2.1.2. Handles file discovery, temporal sampling, base64 JPEG encoding, and proper resource cleanup to prevent memory leaks.

**Responsibility**: Video file discovery, frame extraction at configurable intervals, NumPy-to-base64-JPEG conversion, and MoviePy resource management

**Key functions**: `discover_video_files`, `extract_sampled_frames`, `numpy_to_base64_jpeg`, `extract_and_encode_frames`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-video-frame-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-pedestrian-vlm-counting

**Description**: Sends extracted video frames to Vision LLM APIs (OpenAI GPT-4o or Google Gemini) with carefully engineered prompts for unique pedestrian counting, parses integer results robustly, and writes final counts to a properly formatted Excel file.

**Responsibility**: VLM API integration (OpenAI and Gemini), prompt engineering for unique pedestrian re-identification, response parsing with integer coercion, and Excel output generation with correct sheet/column structure

**Key functions**: `count_pedestrians_openai`, `count_pedestrians_gemini`, `parse_count_from_response`, `write_results_to_excel`, `run_pedestrian_counting_pipeline`

**Depends on**: evo-video-frame-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pedestrian-vlm-counting/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
