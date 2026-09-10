# Skill Creation Plan

**Task**: Analyze camera egomotion and detect dynamic objects in a video, outputting motion labels as JSON and binary masks as compressed NPZ in CSR format.

**Rationale**: The task has three distinct functional domains: (1) video I/O and frame sampling, (2) egomotion estimation and motion classification, and (3) dynamic object detection with CSR mask serialization. However, egomotion and dynamic detection share the same optical flow/feature tracking pipeline and are tightly coupled per frame-pair, so they belong together. Separating video I/O from the analysis logic and output formatting keeps concerns clean while avoiding over-decomposition.

**Number of skills**: 3

---

## Skill 1: evo-video-sampling

**Description**: Extracts frames from an MP4 video file at a specified target FPS using sequential reading to avoid seek unreliability. Returns sampled grayscale frames and their original frame indices.

**Responsibility**: Video decoding, FPS calculation, sequential frame sampling, BGR-to-grayscale conversion. No analysis logic.

**Key functions**: `sample_video_frames`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-video-sampling/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-egomotion-dynamic-analysis

**Description**: For consecutive sampled frame pairs, computes sparse optical flow, estimates camera egomotion via partial affine transform (classifying into Pan/Tilt/Dolly/Roll/Stay labels), and detects dynamic objects via homography-based motion compensation and frame differencing. Outputs motion labels and binary masks.

**Responsibility**: Feature detection, optical flow (Lucas-Kanade), affine partial 2D estimation for egomotion classification, homography estimation for motion compensation, frame differencing, morphological cleanup, and threshold-based motion label assignment.

**Key functions**: `compute_egomotion_labels`, `detect_dynamic_objects`, `analyze_frame_pairs`

**Depends on**: evo-video-sampling


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-egomotion-dynamic-analysis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-output-serialization

**Description**: Serializes egomotion labels to JSON with frame-interval keys and binary masks to NPZ in CSR sparse format using only NumPy (no SciPy dependency).

**Responsibility**: Manual dense-to-CSR conversion using NumPy, NPZ file writing with compressed sparse masks, JSON export with interval-keyed motion labels.

**Key functions**: `dense_to_csr_manual`, `save_csr_masks_npz`, `export_motion_labels_json`

**Depends on**: evo-egomotion-dynamic-analysis


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-output-serialization/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
