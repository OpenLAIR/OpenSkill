---
name: evo-software-dependency-audit
description: Security audit skill for scanning dependency files (e.g., package-lock.json) using Trivy offline scanner to identify HIGH/CRITICAL vulnerabilities and produce CSV reports.
---

# evo-software-dependency-audit

## CRITICAL: You MUST Use Trivy (Not npm audit)

**DO NOT use `npm audit`, `yarn audit`, `snyk`, or any other tool.** The ONLY correct tool for this task is **Trivy** with its pre-built offline vulnerability database. Using any other tool will produce incorrect results because different tools use different vulnerability databases with different CVE mappings, CVSS scores, and fixed version information.

Trivy is already installed and its offline database is pre-loaded. You do not need internet access.

## Quickest Path to Solution

A complete, ready-to-run Python script is provided. Simply execute it:

```bash
python3 /root/.claude/skills/evo-software-dependency-audit/scripts/run_audit.py
```

This will:
1. Run Trivy offline scan on `/root/package-lock.json`
2. Parse the JSON output
3. Extract HIGH and CRITICAL vulnerabilities
4. Write `/root/security_audit.csv` with the correct format

**That single command is all you need.** Do not modify the script. Do not use npm audit. Do not try alternative approaches.

## Alternative: Use as a Python Library

```python
import sys
sys.path.insert(0, '/root/.claude/skills/evo-software-dependency-audit/scripts')
from utils import full_audit

vulns = full_audit('/root/package-lock.json', '/root/security_audit.csv')
print(f"Found {len(vulns)} vulnerabilities")
```

## Why Trivy and Not npm audit

- `npm audit` uses GitHub's live advisory database (GHSA IDs, different CVSS scores, different fixed versions)
- Trivy's offline DB uses NVD as primary source with specific CVE IDs, NVD CVSS scores, and comprehensive fixed version lists
- The expected output format requires Trivy-specific data (e.g., comma-separated fixed versions like "7.5.2, 6.3.1, 5.7.2")
- `npm audit` reports many more vulnerabilities than the offline Trivy DB for the same lockfile

## Technical Details

### Trivy Offline Scanning Flags
All four flags are required for air-gapped operation:
- `--skip-db-update` — prevents fetching primary vuln DB
- `--skip-java-db-update` — prevents fetching Java artifact index  
- `--skip-check-update` — prevents fetching misconfiguration policies
- `--offline-scan` — suppresses any remaining outbound API calls

### CVSS Score Extraction Priority
For extracting CVSS scores from Trivy's nested CVSS object, use this vendor precedence:
1. NVD V3Score — governmental authority, standard reference (matches ground truth)
2. GHSA V3Score — GitHub Security Advisory
3. RedHat V3Score — general fallback
4. Any other vendor V3Score
5. V2Score with same priority cascade (legacy)

### CSV Output Format
Columns: `Package,Version,CVE_ID,Severity,CVSS_Score,Fixed_Version,Title,Url`
- Fixed_Version: Use "N/A" when no fix is available
- CVSS_Score: Numeric float (e.g., 7.5, 9.8)
- Title: From Trivy's Title field
- Url: PrimaryURL from Trivy (typically avd.aquasec.com)

### FixedVersion Handling
- Trivy omits the FixedVersion key entirely when no fix exists (Go's `json:",omitempty"`)
- Must use `dict.get('FixedVersion', '')` to avoid KeyError
- Map missing/empty to "N/A" in CSV output

### Deduplication
- Deduplicate by `(PkgName, VulnerabilityID)` tuple
- Same CVE can appear multiple times due to transitive dependency resolution

## Functions in scripts/utils.py

- `find_trivy_cache_dir()` - Locate Trivy cache directory
- `run_trivy_scan(lockfile_path, output_json_path, ...)` - Run trivy offline scan
- `load_trivy_json(filepath)` - Load trivy JSON output
- `extract_cvss_score(cvss_data)` - Extract best CVSS score with NVD>GHSA>RedHat priority
- `extract_vulnerabilities(trivy_data, severities)` - Parse and deduplicate vulnerabilities
- `write_csv(vulnerabilities, output_path)` - Write CSV report
- `full_audit(lockfile_path, output_csv_path)` - Complete end-to-end pipeline