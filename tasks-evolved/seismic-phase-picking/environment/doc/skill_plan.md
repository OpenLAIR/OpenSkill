# Skill Creation Plan

**Task**: Process 100 earthquake trace .npz files using SeisBench deep learning models to pick P and S wave arrival indices and output results to CSV

**Rationale**: The task is a single end-to-end pipeline with tightly coupled steps (load npz, convert to ObsPy, run SeisBench model, extract picks). Splitting into two skills: one for data I/O and preprocessing (npz loading, channel reordering, ObsPy conversion, resampling) and one for model inference and pick extraction (SeisBench model loading, classify, index conversion, CSV output). This separation allows clean boundaries between data preparation and ML inference.

**Number of skills**: 2

---

## Skill 1: evo-seismic-data-preprocessing

**Description**: Loads seismic waveform data from .npz files and converts them into ObsPy Stream objects ready for SeisBench model inference. Handles channel identification, reordering to Z/N/E convention, transposing, float32 conversion, detrending, and resampling to 100 Hz.

**Responsibility**: All data I/O from .npz files and transformation into properly formatted ObsPy Stream objects with correct channel ordering, sampling rate, and data types

**Key functions**: `load_npz_trace`, `build_obspy_stream`, `identify_channel_order`, `preprocess_stream`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-seismic-data-preprocessing/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-seismic-phase-picking

**Description**: Runs SeisBench pretrained PhaseNet model on ObsPy Streams to detect P and S wave arrivals, extracts pick indices mapped back to original sample coordinates, and writes results to CSV. Handles model loading, inference with classify(), pick extraction from ClassifyOutput, and index conversion accounting for resampling.

**Responsibility**: Model loading, inference execution, pick extraction from model output, index conversion from resampled to original coordinates, and CSV output generation

**Key functions**: `load_phasenet_model`, `run_phase_picking`, `extract_picks_to_dataframe`, `convert_pick_to_original_index`, `process_all_traces_to_csv`

**Depends on**: evo-seismic-data-preprocessing


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-seismic-phase-picking/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
