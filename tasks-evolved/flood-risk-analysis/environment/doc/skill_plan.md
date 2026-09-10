# Skill Creation Plan

**Task**: Detect USGS Michigan stations that experienced flooding (exceeded 90th percentile historical streamflow) during April 1-7, 2025, and output a CSV of station IDs with flood day counts.

**Rationale**: This task is a focused, single-domain pipeline (USGS NWIS data retrieval + percentile-based flood detection + CSV output). All components are tightly coupled around the dataretrieval API workflow, so a single comprehensive skill avoids artificial fragmentation.

**Number of skills**: 1

---

## Skill 1: evo-usgs-flood-detection

**Description**: Detects flooding events at USGS streamgages by comparing daily streamflow against historical 90th percentile thresholds using the dataretrieval package. Use when analyzing flood occurrences over a date range for a list of USGS station IDs.

**Responsibility**: End-to-end pipeline: parse station list file (preserving leading zeros), fetch daily values and historical statistics via dataretrieval.nwis, compute flood-day counts via percentile threshold comparison, and write filtered results to CSV.

**Key functions**: `load_stations`, `get_station_flood_thresholds`, `detect_floods_for_site`, `run_flood_detection_pipeline`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-usgs-flood-detection/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
