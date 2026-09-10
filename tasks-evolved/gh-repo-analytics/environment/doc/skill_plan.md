# Skill Creation Plan

**Task**: Fetch PR and issue data from cli/cli for December 2024 using gh CLI, compute metrics, and output a structured report.json

**Rationale**: The task has two distinct data domains (PRs and issues) but they share the same data fetching mechanism and output format. I decompose into: (1) a foundational skill for fetching GitHub data via gh CLI subprocess calls, and (2) a skill for computing metrics and assembling the final report. This keeps data I/O separate from business logic.

**Number of skills**: 2

---

## Skill 1: evo-gh-data-fetcher

**Description**: Fetches pull request and issue data from a GitHub repository using the gh CLI tool via Python subprocess. Handles JSON output parsing, pagination limits, date range filtering, and error handling.

**Responsibility**: Execute gh CLI commands to retrieve PR and issue data with proper flags (--search, --state, --json, --limit), parse JSON output, and return structured Python lists of dictionaries.

**Key functions**: `fetch_prs`, `fetch_issues`, `run_gh_command`, `parse_gh_timestamp`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-gh-data-fetcher/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-gh-report-generator

**Description**: Computes community pulse metrics from raw PR and issue data and writes a structured report.json file. Calculates PR counts by state, average time-to-merge, top contributor, bug issue counts, and resolved bugs.

**Responsibility**: Process fetched PR/issue data to compute all required metrics (total/merged/closed PRs, avg merge days, top contributor, total issues, bug count, resolved bugs) and serialize results to /app/report.json.

**Key functions**: `compute_pr_metrics`, `compute_issue_metrics`, `identify_top_contributor`, `generate_report`

**Depends on**: evo-gh-data-fetcher


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-gh-report-generator/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
