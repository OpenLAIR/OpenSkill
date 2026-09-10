# Domain Reference for evo-trivy-offline-audit

**Responsibility**: Complete end-to-end pipeline: configure and invoke Trivy CLI with correct offline flags, parse nested JSON output (including vendor-prioritized CVSS score extraction and missing FixedVersion handling), deduplicate results, and write formatted CSV output.

**Key functions to implement**: run_trivy_offline_scan, extract_best_cvss_score, parse_trivy_results, generate_csv_report

---

## 1. Trivy Command-Line Interface Configuration for Offline Environments


The Trivy CLI is highly configurable, offering multiple execution modes (`image`, `fs`, `k8s`, `sbom`) [cite: 1, 2]. To analyze an NPM project's dependencies without requiring a full container image, the filesystem (`fs`) subcommand is utilized [cite: 3, 4]. When operating in a restricted or offline environment, developers must provide an explicit set of flags to suppress Trivy's default behavior of updating its local databases over the internet [cite: 5, 6].

## 2. Offline Database Architecture and Cache Directory Structure


For Trivy to function in an offline capacity, the host machine must be pre-populated with the necessary vulnerability databases. Trivy relies on an OCI-compliant distribution mechanism, pulling these databases as artifacts from container registries [cite: 19].

When a pre-downloaded Trivy database is unzipped or mounted into the designated cache directory (e.g., `/root/.cache/trivy`), Trivy expects a strict hierarchical directory layout [cite: 10, 20].

## 3. Trivy JSON Output Schema and Data Representation


Executing `trivy fs --format json` yields a rich, deeply nested JSON document [cite: 1]. Understanding the exact schema is a prerequisite for robust Python parsing.

## 4. Extracting and Normalizing CVSS Scores


A critical requirement in vulnerability management pipelines is extracting the "best" available CVSS score. While NVD is traditionally the source of truth, NVD backlogs or ecosystem-specific realities often mean that GitHub Security Advisories (GHSA) possess more accurate or more rapidly available scoring for NPM dependencies [cite: 33]. 

Because Trivy returns a dictionary of vendors under the `CVSS` key, the Python parser must systematically fallback through preferred vendors if a specific vendor is missing.

## 5. Implementation: Python Automation and Data Pipeline


To programmatically execute Trivy, capture the output, handle edge cases (like the omitted `FixedVersion`), extract CVSS scores, and generate a sanitized CSV, Python's standard library provides all necessary modules (`subprocess`, `json`, `csv`).

## 6. Common Pitfalls and Edge Cases in Trivy Offline Scanning


Operating Trivy in automated, offline CI/CD pipelines exposes engineers to several architectural and ecosystem-specific pitfalls. Anticipating these issues is crucial for maintaining a reliable security posture.