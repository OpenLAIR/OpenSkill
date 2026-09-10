# Skill Creation Plan

**Task**: Load seismic waveform and station data, pick P/S phases using SeisBench deep learning models, associate picks into earthquake events, and output event catalog as CSV.

**Rationale**: The task has three distinct functional domains: (1) data loading and preparation, (2) deep learning phase picking with SeisBench, and (3) phase association to group picks into earthquake events. Combining picking and association into fewer skills risks unclear boundaries, while separating data I/O from computation keeps each skill focused and reusable.

**Number of skills**: 3

---

## Skill 1: evo-seismic-data-io

**Description**: Loads MiniSEED waveform data and CSV station metadata, groups traces by station for 3-component processing, and provides station coordinate lookups.

**Responsibility**: Reading waveform files with ObsPy, parsing station CSV with Pandas, grouping traces by network.station, and building station dictionaries/DataFrames for downstream use.

**Key functions**: `load_waveforms`, `load_stations`, `group_traces_by_station`, `get_station_dict`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-seismic-data-io/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-seismic-phase-picking

**Description**: Runs SeisBench deep learning models (PhaseNet/EQTransformer) on grouped station waveforms to produce P and S phase picks with timestamps and probabilities.

**Responsibility**: Loading pretrained SeisBench models, running classify() on per-station streams, extracting pick times/phases/probabilities into a structured DataFrame.

**Key functions**: `load_picker_model`, `pick_phases_for_stream`, `pick_all_stations`, `picks_to_dataframe`

**Depends on**: evo-seismic-data-io


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-seismic-phase-picking/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-seismic-phase-association

**Description**: Associates phase picks from multiple stations into earthquake events using temporal clustering (DBSCAN) and travel-time validation with a uniform velocity model, then outputs event catalog as CSV.

**Responsibility**: Clustering picks temporally, validating clusters against expected P/S travel times using station coordinates and velocity model (vp=6km/s, vs=vp/1.75), estimating event origin times, deduplicating events, and writing results CSV with ISO-formatted timestamps.

**Key functions**: `associate_picks`, `validate_cluster`, `estimate_origin_time`, `write_event_catalog`

**Depends on**: evo-seismic-data-io, evo-seismic-phase-picking


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-seismic-phase-association/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
