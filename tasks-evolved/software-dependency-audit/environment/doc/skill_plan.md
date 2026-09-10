# Skill Creation Plan

**Task**: Run an offline Trivy scan on /root/package-lock.json to identify HIGH/CRITICAL vulnerabilities and write results to a CSV file.

**Rationale**: This task is a single end-to-end pipeline: run Trivy offline, parse JSON output, and write CSV. The background research provides a near-complete Python script. A single skill covering Trivy execution and CSV generation is sufficient, as the concerns are tightly coupled and splitting them would create unnecessary complexity.

**Number of skills**: 1

---

## Skill 1: evo-trivy-offline-audit

**Description**: Executes Trivy in offline mode against a package-lock.json file, parses the JSON output to extract HIGH/CRITICAL vulnerabilities with CVSS scores, and generates a CSV report with columns: Package, Version, CVE_ID, Severity, CVSS_Score, Fixed_Version, Title, Url.

**Responsibility**: Complete end-to-end pipeline: configure and invoke Trivy CLI with correct offline flags, parse nested JSON output (including vendor-prioritized CVSS score extraction and missing FixedVersion handling), deduplicate results, and write formatted CSV output.

**Key functions**: `run_trivy_offline_scan`, `extract_best_cvss_score`, `parse_trivy_results`, `generate_csv_report`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-trivy-offline-audit/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
