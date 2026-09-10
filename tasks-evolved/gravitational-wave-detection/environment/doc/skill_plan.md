# Skill Creation Plan

**Task**: Detect gravitational wave signal from binary black hole merger using matched filtering with PyCBC, scanning mass parameters across three approximants and reporting best SNR results.

**Rationale**: The task has a clear linear pipeline: (1) data I/O and conditioning, (2) matched filtering with grid search over mass parameters and approximants, and (3) result aggregation and CSV output. Since the pipeline is tightly coupled and the background document provides a complete working example, two skills suffice: one for the core GW data processing and matched filtering engine, and one for orchestrating the grid search and output formatting.

**Number of skills**: 2

---

## Skill 1: evo-gw-matched-filter-engine

**Description**: Core utility for reading GWF frame files, conditioning gravitational wave detector data (highpass filtering, resampling, cropping, PSD estimation), generating waveform templates for various approximants, and performing matched filtering to extract peak SNR values.

**Responsibility**: Handles all PyCBC-specific operations: frame file reading, data conditioning pipeline (highpass, resample, crop, PSD estimation with Welch's method, interpolation, inverse spectrum truncation), waveform template generation (get_td_waveform for SEOBNRv4_opt, IMRPhenomD, TaylorT4), template resizing/cyclic shifting, matched filtering execution, SNR extraction with edge cropping.

**Key functions**: `read_and_condition_data`, `estimate_psd`, `generate_template`, `compute_matched_filter_snr`, `find_peak_snr`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-gw-matched-filter-engine/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-gw-grid-search-output

**Description**: Orchestrates the mass parameter grid search across approximants, tracks best SNR per approximant, handles error cases (e.g., TaylorT4 failures for high masses), manages memory during large loops, and formats/writes the final CSV output.

**Responsibility**: Manages the grid search loop over mass1, mass2 (10-40 solar masses, integer steps) and three approximants, calls the matched filter engine for each combination, tracks the maximum SNR and corresponding total mass per approximant, handles exceptions gracefully, performs memory cleanup between iterations, and writes the results CSV to /root/detection_results.csv in the required format.

**Key functions**: `run_grid_search`, `extract_best_per_approximant`, `write_detection_results_csv`

**Depends on**: evo-gw-matched-filter-engine


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-gw-grid-search-output/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
