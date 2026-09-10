# Skill Creation Plan

**Task**: Extract keyframes from a Super Mario gameplay video, convert to grayscale, count coins/enemies/turtles via template matching, and output results to CSV

**Rationale**: The task follows a linear pipeline with three distinct functional concerns: (1) video frame extraction and grayscale conversion, (2) template-based object counting with NMS, and (3) CSV result generation. However, since these are tightly coupled steps in a single pipeline and the task is straightforward, decomposing into 2 skills—one for video/image processing and one for template matching and counting—provides clean separation without over-decomposition.

**Number of skills**: 2

---

## Skill 1: evo-video-keyframe-extraction

**Description**: Extracts keyframes from an MP4 video at uniform temporal intervals using OpenCV VideoCapture, saves them with sequential naming (keyframes_001.png, keyframes_002.png, etc.), and converts them in-place from RGB/BGR to grayscale.

**Responsibility**: Video decoding, metadata extraction (FPS, frame count), uniform temporal sampling for keyframe selection, saving keyframes to disk with zero-padded naming, and in-place grayscale conversion of saved frames.

**Key functions**: `extract_keyframes`, `convert_frames_to_grayscale`, `get_video_metadata`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-video-keyframe-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-template-matching-counter

**Description**: Counts occurrences of template objects (coins, enemies, turtles) in grayscale keyframe images using OpenCV matchTemplate with TM_CCOEFF_NORMED and Non-Maximum Suppression, then aggregates results into a CSV file via Pandas.

**Responsibility**: Loading grayscale template images, performing template matching against each keyframe, applying NMS to deduplicate detections, counting objects per frame per category, and writing the final CSV with columns frame_id/coins/enemies/turtles.

**Key functions**: `load_template`, `count_objects_in_frame`, `non_max_suppression`, `generate_results_csv`

**Depends on**: evo-video-keyframe-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-template-matching-counter/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
