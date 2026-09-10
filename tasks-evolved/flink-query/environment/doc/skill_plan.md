# Skill Creation Plan

**Task**: Implement a Flink job that reads Google cluster trace data, identifies job stages based on SUBMIT event sessions (10-min inactivity gap), and outputs the largest stage size per job.

**Rationale**: This task involves three distinct concerns: (1) understanding the existing project structure and AppBase pattern to correctly scaffold data types and integrate with the skeleton, (2) implementing the core Flink pipeline logic including CSV parsing, event-time session windows, and aggregation, and (3) handling file I/O (reading gzipped CSVs and writing output in the correct format). These are tightly coupled enough that 2 skills suffice: one for data model/schema setup and one for the complete Flink pipeline implementation.

**Number of skills**: 2

---

## Skill 1: evo-cluster-data-model

**Description**: Provides guidance and utility patterns for defining Flink-compatible POJO data types (TaskEvent, JobEvent) based on the Google Cluster Trace 2011 v2 schema, including CSV parsing logic with proper field indexing and type handling for gzipped headerless CSVs.

**Responsibility**: Define the TaskEvent and JobEvent data type classes under clusterdata.datatypes, ensuring they meet Flink POJO serialization requirements (public fields, no-arg constructor). Provide CSV line parsing logic with correct column indices, handling of empty/missing fields, and microsecond timestamp semantics.

**Key functions**: `parse_task_event_from_csv`, `parse_job_event_from_csv`, `get_event_type_constants`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-cluster-data-model/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-flink-session-window-pipeline

**Description**: Provides complete implementation guidance for the LongestSessionPerJob Flink job: reading gzipped CSV sources, assigning event-time watermarks with microsecond-to-millisecond conversion, filtering SUBMIT events, applying session windows with 10-minute gap, counting tasks per session via AggregateFunction, finding the max session per job via reduce, and writing output as (jobId,count) tuples to a local file using FileSink or writeAsText.

**Responsibility**: Implement the full Flink DataStream pipeline in LongestSessionPerJob.java: FileSource/readTextFile for gzipped input, WatermarkStrategy with bounded out-of-orderness and timestamp extraction, filter for event type 0 (SUBMIT), keyBy jobId, EventTimeSessionWindows with Duration.ofMinutes(10), aggregate+process window for counting, reduce for max session per job, and sink output in the required tuple format.

**Key functions**: `build_flink_pipeline`, `configure_watermark_strategy`, `session_window_aggregation`, `find_max_session_per_job`, `configure_output_sink`

**Depends on**: evo-cluster-data-model


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-flink-session-window-pipeline/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
