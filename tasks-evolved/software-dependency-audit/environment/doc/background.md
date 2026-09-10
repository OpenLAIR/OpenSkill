# Comprehensive Analysis of Offline Vulnerability Scanning using Trivy: Methodologies, Data Parsing, and Automation

**Key Points**
*   **Offline Capability**: Trivy supports fully air-gapped vulnerability scanning via locally cached databases, requiring specific flags like `--skip-db-update` and `--offline-scan` to prevent network calls.
*   **Target Specificity**: Scanning a `package-lock.json` directly using `trivy fs` provides deterministic dependency resolution, avoiding the redundancy and parsing complexities of analyzing a fully installed `node_modules` directory.
*   **Data Representation**: Trivy's JSON output encapsulates findings in a structured schema (`Results[].Vulnerabilities[]`), wherein CVSS scores are nested by vendor, and empty or non-existent patches result in omitted `FixedVersion` keys.
*   **Automation Patterns**: Automating Trivy via Python requires robust handling of sub-processes and JSON parsing, specifically navigating hierarchical vendor-specific CVSS dictionaries and graceful degradation when metadata is absent.
*   **Ecosystem Nuances**: NPM vulnerabilities are frequently assigned GitHub Security Advisory (GHSA) identifiers instead of traditional CVEs, necessitating pipeline logic that accommodates diverse vulnerability ID schemas.

**Context and Operational Prerequisites**
The integration of vulnerability scanning into Continuous Integration and Continuous Deployment (CI/CD) pipelines is a foundational element of DevSecOps. In secure, highly regulated, or air-gapped environments, the inability to dynamically fetch real-time vulnerability intelligence mandates the use of offline scanners. Trivy, an industry-standard open-source vulnerability scanner, provides robust offline capabilities. 

**Architectural Nuances of Offline Scanning**
Operating Trivy without network access demands precise cache management. The tool relies on a dual-database architecture: a primary vulnerability database (`trivy.db`) and a Java-specific index (`trivy-java.db`). Pre-populating these databases into specific directory structures ensures that Trivy can correlate locally resolved package versions against known vulnerabilities.

**Analytical Pipeline Integration**
Extracting actionable intelligence from Trivy requires parsing its raw JSON output. Security engineering teams often utilize Python to orchestrate the Trivy Command Line Interface (CLI), capture its standard output, and normalize the findings into tabular formats like CSV. This requires navigating complex JSON schemas, prioritizing CVSS scores from various authorities (e.g., NVD vs. GHSA), and handling edge cases such as unpatched vulnerabilities or duplicated dependency trees.

***

## 1. Trivy Command-Line Interface Configuration for Offline Environments

The Trivy CLI is highly configurable, offering multiple execution modes (`image`, `fs`, `k8s`, `sbom`) [cite: 1, 2]. To analyze an NPM project's dependencies without requiring a full container image, the filesystem (`fs`) subcommand is utilized [cite: 3, 4]. When operating in a restricted or offline environment, developers must provide an explicit set of flags to suppress Trivy's default behavior of updating its local databases over the internet [cite: 5, 6].

### 1.1 Command and Flag Specifications

To execute an offline scan specifically targeting a `package-lock.json` file, the following command structure is employed:

```bash
trivy fs \
  --cache-dir /root/.cache/trivy \
  --skip-db-update \
  --skip-java-db-update \
  --skip-check-update \
  --offline-scan \
  --scanners vuln \
  --severity HIGH,CRITICAL \
  --format json \
  package-lock.json
```

**Detailed Analysis of Flags:**

*   **Targeting the Lockfile (`package-lock.json`)**: By passing the explicit path `package-lock.json` to the `trivy fs` command, Trivy is instructed to parse the NPM lockfile directly [cite: 2, 7]. This is significantly more efficient and accurate than scanning the entire working directory or the `node_modules` folder, as the lockfile provides a fully resolved, deterministic dependency tree.
*   **`--cache-dir /root/.cache/trivy`**: This flag explicitly defines the path where Trivy should look for its vulnerability databases and cache [cite: 8, 9]. By default, Trivy uses `~/.cache/trivy` [cite: 10], but in CI/CD runners or containerized environments, specifying an absolute path ensures predictable behavior [cite: 11].
*   **`--skip-db-update`**: This is a critical flag for air-gapped environments. It prevents Trivy from attempting to reach GitHub Container Registry (GHCR) to download the latest primary vulnerability database (`trivy.db`) [cite: 5, 12].
*   **`--skip-java-db-update`**: Similar to the primary DB, Trivy maintains a separate database for indexing Java artifacts. Even when scanning an NPM project, Trivy may attempt to update this database upon startup unless explicitly instructed not to [cite: 5, 6].
*   **`--skip-check-update`**: This prevents Trivy from attempting to download the latest misconfiguration policies (Rego checks), which are used for Infrastructure as Code (IaC) scanning [cite: 5, 13].
*   **`--offline-scan`**: While the `--skip-*-update` flags prevent database downloads, Trivy may still attempt to issue outbound API requests during the scan to resolve specific dependency metadata (particularly for certain package managers). The `--offline-scan` flag explicitly suppresses these API calls, ensuring a strictly local execution [cite: 6, 12].
*   **`--scanners vuln`**: Trivy is a multifaceted tool capable of scanning for vulnerabilities, exposed secrets, misconfigurations, and licensing issues [cite: 3, 14]. Using `--scanners vuln` restricts the scan entirely to CVE/GHSA vulnerability detection, significantly reducing execution time and preventing the JSON output from being cluttered with unrelated findings [cite: 3].
*   **`--severity HIGH,CRITICAL`**: This filters the output, causing Trivy to report only vulnerabilities that meet or exceed the specified CVSS threshold severity [cite: 15, 16].
*   **`--format json`**: Instructs Trivy to output the results as a structured JSON object rather than its default human-readable tabular format, enabling programmatic ingestion by scripts [cite: 1, 17].
*   **`--list-all-pkgs`**: By default, Trivy only outputs packages that contain known vulnerabilities [cite: 18]. If the `--list-all-pkgs` flag is appended, Trivy will include the entire Software Bill of Materials (SBOM) in the output—listing every discovered dependency, regardless of whether it is vulnerable [cite: 4]. For purely vulnerability-focused extraction, omitting this flag is preferable to minimize JSON payload size.

### 1.2 The Necessity of Multiple Offline Flags

A common pitfall is assuming that `--skip-db-update` is sufficient to air-gap Trivy [cite: 13]. Evidence suggests that if only `--skip-db-update` is provided, Trivy may still attempt to connect to external endpoints to fetch Java indexes, misconfiguration checks, or query specific package APIs [cite: 6, 12]. Complete isolation requires the combination of `--skip-db-update`, `--skip-java-db-update`, `--skip-check-update`, and `--offline-scan` [cite: 5, 13].

## 2. Offline Database Architecture and Cache Directory Structure

For Trivy to function in an offline capacity, the host machine must be pre-populated with the necessary vulnerability databases. Trivy relies on an OCI-compliant distribution mechanism, pulling these databases as artifacts from container registries [cite: 19].

When a pre-downloaded Trivy database is unzipped or mounted into the designated cache directory (e.g., `/root/.cache/trivy`), Trivy expects a strict hierarchical directory layout [cite: 10, 20]. 

### 2.1 Expected Directory Layout

```text
/root/.cache/trivy/
├── db/
│   ├── trivy.db
│   └── metadata.json
├── java-db/
│   ├── trivy-java.db
│   └── metadata.json
```

*   **`db/trivy.db`**: This is the core vulnerability database, implemented as a BoltDB file [cite: 8, 21]. It contains the mappings of OS packages and application dependencies to known CVEs and GHSAs [cite: 20].
*   **`db/metadata.json`**: A critical file that dictates the temporal validity of the database. It contains timestamps (`"NextUpdate"`, `"UpdatedAt"`) that Trivy evaluates to determine if the database is obsolete [cite: 22, 23]. If this file is missing, Trivy will refuse to execute the scan or attempt a forced network update.
*   **`java-db/trivy-java.db`**: The specialized database used for identifying Java libraries (JAR/WAR/EAR). Though seemingly irrelevant for an NPM lockfile scan, Trivy's initialization sequence often verifies the presence of this database unless explicitly bypassed [cite: 19, 20].
*   **`java-db/metadata.json`**: The temporal metadata file for the Java index [cite: 24].

**Common Pitfall**: A frequent mistake among DevSecOps engineers is placing the `trivy.db` file directly into `/root/.cache/trivy/` instead of `/root/.cache/trivy/db/` [cite: 11]. If the `db` subdirectory is missing, Trivy will fail to locate the database and will abort the offline scan [cite: 11].

## 3. Trivy JSON Output Schema and Data Representation

Executing `trivy fs --format json` yields a rich, deeply nested JSON document [cite: 1]. Understanding the exact schema is a prerequisite for robust Python parsing.

### 3.1 JSON Hierarchy

At the highest level, the JSON object contains metadata about the scan and an array named `Results`. Because `trivy fs` can scan multiple targets (e.g., multiple lockfiles in a monorepo), each target occupies an element within the `Results` array [cite: 25].

```json
{
  "SchemaVersion": 2,
  "CreatedAt": "2023-10-25T10:00:00Z",
  "ArtifactName": "package-lock.json",
  "ArtifactType": "filesystem",
  "Results": [
    {
      "Target": "package-lock.json",
      "Class": "lang-pkgs",
      "Type": "npm",
      "Vulnerabilities": [
        {
          "VulnerabilityID": "CVE-2023-1234",
          "PkgName": "lodash",
          "InstalledVersion": "4.17.10",
          "FixedVersion": "4.17.11",
          "Severity": "HIGH",
          "CVSS": { ... },
          "Title": "Prototype pollution in utilities function",
          "Description": "A prototype pollution...",
          "PrimaryURL": "https://avd.aquasec.com/nvd/cve-2023-1234",
          "References": [ ... ]
        }
      ]
    }
  ]
}
```

### 3.2 Exact Field Names and their Behavior

*   **Package Name**: `PkgName` represents the specific NPM dependency (e.g., `lodash`, `express`) [cite: 26].
*   **Installed Version**: `InstalledVersion` indicates the exact version parsed from the lockfile [cite: 1].
*   **Vulnerability ID**: `VulnerabilityID` provides the CVE number (e.g., `CVE-2021-3711`) or a GitHub Security Advisory ID (e.g., `GHSA-cxm3-wv7p-598c`) [cite: 26, 27].
*   **Severity**: `Severity` provides the categorical impact (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`) [cite: 14, 25]. Trivy determines this by favoring vendor severity ratings over NVD base severities where applicable [cite: 28].
*   **Fixed Version**: `FixedVersion` displays the package version containing the patch [cite: 29]. **Crucially, if a vulnerability has no known fix, the `FixedVersion` key is entirely omitted from the JSON object** [cite: 21, 30]. It is not represented as an empty string `""` or `null`; it simply does not exist due to the `omitempty` struct tag in Trivy's Go source code [cite: 21, 30]. Parsers utilizing strict key access (e.g., `vuln["FixedVersion"]`) will encounter `KeyError` exceptions [cite: 30].
*   **Title and Description**: `Title` is a short summary, while `Description` provides the verbose advisory text [cite: 15, 29].
*   **References**: `PrimaryURL` is typically a link to Aqua Security's vulnerability database, while `References` is a list of strings pointing to external advisories (NVD, GitHub, vendor notices) [cite: 15, 31].

### 3.3 Representation of CVSS Scores

The Common Vulnerability Scoring System (CVSS) data is stored within a nested dictionary keyed by `CVSS` [cite: 32]. Trivy aggregates CVSS scores from multiple upstream data providers (e.g., NVD, RedHat, GHSA) [cite: 1, 17, 26].

```json
"CVSS": {
  "nvd": {
    "V2Vector": "AV:N/AC:L/Au:N/C:P/I:P/A:P",
    "V3Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "V2Score": 7.5,
    "V3Score": 9.8
  },
  "ghsa": {
    "V3Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "V3Score": 9.8
  },
  "redhat": {
    "V3Vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:L",
    "V3Score": 3.7
  }
}
```

*   **Nesting Structure**: `CVSS -> <vendor_id> -> V3Score`.
*   **Vendors**: Common keys include `nvd`, `ghsa`, `redhat`, `alpine`, and `ubuntu` [cite: 17, 26, 32]. For NPM packages, `nvd` and `ghsa` are the primary providers [cite: 33].
*   **Data Types**: The `V3Score` is stored as a native JSON floating-point number (e.g., `9.8`, `5.3`), not a string [cite: 25, 32]. The `V3Vector` is stored as a string [cite: 26, 32].

## 4. Extracting and Normalizing CVSS Scores

A critical requirement in vulnerability management pipelines is extracting the "best" available CVSS score. While NVD is traditionally the source of truth, NVD backlogs or ecosystem-specific realities often mean that GitHub Security Advisories (GHSA) possess more accurate or more rapidly available scoring for NPM dependencies [cite: 33]. 

Because Trivy returns a dictionary of vendors under the `CVSS` key, the Python parser must systematically fallback through preferred vendors if a specific vendor is missing.

### 4.1 Vendor Fallback Logic

When parsing an NPM lockfile, the logical order of precedence for CVSS v3 score extraction is typically:
1.  **NVD**: The standard governmental authority for CVEs [cite: 33].
2.  **GHSA**: Highly relevant for the JavaScript/NPM ecosystem [cite: 33].
3.  **RedHat / Others**: General fallback.

If no `CVSS` dictionary exists, or if no `V3Score` is found, the parser must gracefully assign a default value (e.g., `0.0` or empty) to prevent pipeline failures [cite: 25].

## 5. Implementation: Python Automation and Data Pipeline

To programmatically execute Trivy, capture the output, handle edge cases (like the omitted `FixedVersion`), extract CVSS scores, and generate a sanitized CSV, Python's standard library provides all necessary modules (`subprocess`, `json`, `csv`).

### 5.1 Python Code Pattern

The following Python script embodies a production-ready pattern for orchestrating Trivy in an offline context:

```python
import subprocess
import json
import csv
import sys
from typing import Dict, Any, List

def extract_best_cvss_score(cvss_data: Dict[str, Any]) -> float:
    """
    Extracts the best available CVSS V3 score from Trivy's nested CVSS object.
    Prefers NVD, falls back to GHSA, then RedHat, then any available.
    """
    if not cvss_data:
        return 0.0

    # Define vendor preference order
    preferred_vendors = ["nvd", "ghsa", "redhat"]

    # 1. Check preferred vendors in order
    for vendor in preferred_vendors:
        if vendor in cvss_data:
            score = cvss_data[vendor].get("V3Score")
            if score is not None:
                return float(score)

    # 2. Fallback to any other vendor that has a V3Score
    for vendor, metrics in cvss_data.items():
        score = metrics.get("V3Score")
        if score is not None:
            return float(score)

    return 0.0

def run_trivy_offline_scan(target_file: str, cache_dir: str) -> List[Dict[str, Any]]:
    """
    Executes Trivy CLI as a subprocess and parses the JSON output.
    """
    cmd = [
        "trivy", "fs",
        "--cache-dir", cache_dir,
        "--skip-db-update",
        "--skip-java-db-update",
        "--skip-check-update",
        "--offline-scan",
        "--scanners", "vuln",
        "--severity", "HIGH,CRITICAL",
        "--format", "json",
        target_file
    ]

    try:
        # Execute Trivy. Note: Trivy may exit with 0 or a non-zero code depending 
        # on configuration, so we do not enforce check=True here.
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse standard output as JSON
        trivy_output = json.loads(result.stdout)
        
    except FileNotFoundError:
        print("Error: Trivy CLI not found in PATH.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error parsing Trivy JSON output. Stderr: {result.stderr}")
        sys.exit(1)

    extracted_vulns = []
    
    # Safely navigate the Results array
    results_array = trivy_output.get("Results", [])
    for result_set in results_array:
        vulnerabilities = result_set.get("Vulnerabilities", [])
        
        for vuln in vulnerabilities:
            # Handle duplicate CVEs by maintaining a unique set if required,
            # though here we process sequentially.
            extracted_vulns.append(vuln)
            
    return extracted_vulns

def generate_csv_report(vulnerabilities: List[Dict[str, Any]], output_file: str):
    """
    Writes extracted vulnerabilities to a CSV file.
    """
    # Define required columns
    headers = [
        "Package", "Version", "CVE_ID", "Severity", 
        "CVSS_Score", "Fixed_Version", "Title", "Url"
    ]

    # Use csv.writer with QUOTE_MINIMAL to safely handle commas in Titles/URLs
    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()

        # Track seen vulnerabilities to avoid duplicates (Package + CVE)
        seen = set()

        for vuln in vulnerabilities:
            pkg_name = vuln.get("PkgName", "Unknown")
            cve_id = vuln.get("VulnerabilityID", "Unknown")
            
            # Deduplication key
            dedup_key = f"{pkg_name}-{cve_id}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Edge Case Handling: Missing FixedVersion [cite: 21, 30]
            fixed_version = vuln.get("FixedVersion", "")
            
            # Edge Case Handling: CVSS extraction [cite: 25]
            cvss_score = extract_best_cvss_score(vuln.get("CVSS", {}))

            row = {
                "Package": pkg_name,
                "Version": vuln.get("InstalledVersion", ""),
                "CVE_ID": cve_id,
                "Severity": vuln.get("Severity", ""),
                "CVSS_Score": cvss_score,
                "Fixed_Version": fixed_version,
                "Title": vuln.get("Title", ""),
                "Url": vuln.get("PrimaryURL", "")
            }
            writer.writerow(row)

if __name__ == "__main__":
    TARGET_LOCKFILE = "package-lock.json"
    CACHE_DIRECTORY = "/root/.cache/trivy"
    CSV_OUTPUT = "vulnerability_report.csv"

    print(f"Scanning {TARGET_LOCKFILE} in offline mode...")
    vulns = run_trivy_offline_scan(TARGET_LOCKFILE, CACHE_DIRECTORY)
    
    if vulns:
        print(f"Found {len(vulns)} HIGH/CRITICAL vulnerabilities. Writing to CSV.")
        generate_csv_report(vulns, CSV_OUTPUT)
    else:
        print("No HIGH or CRITICAL vulnerabilities found.")
```

## 6. Common Pitfalls and Edge Cases in Trivy Offline Scanning

Operating Trivy in automated, offline CI/CD pipelines exposes engineers to several architectural and ecosystem-specific pitfalls. Anticipating these issues is crucial for maintaining a reliable security posture.

### 6.1 `node_modules` vs `package-lock.json` Scans

A highly common operational error occurs when engineers instruct Trivy to scan an entire project directory (e.g., `trivy fs .`) rather than isolating the `package-lock.json`. 
*   **Duplication**: If both `package-lock.json` and a fully installed `node_modules` directory exist, scanning the root directory forces Trivy to parse the lockfile and recursively discover `.json` files within `node_modules` [cite: 18]. Historically, this generated duplicate findings [cite: 34]. The Trivy maintainers have implemented logic where `trivy fs` prefers the lockfile and skips `node_modules` to prevent redundant data [cite: 18], but explicit targeting (e.g., `trivy fs package-lock.json`) is the safest practice [cite: 2].
*   **Parsing Errors**: If a `package-lock.json` contains non-standard metadata—such as legacy packages declaring licenses as JSON arrays rather than strings—Trivy's JSON unmarshaler may crash, resulting in a silent failure where the file is skipped entirely, and zero vulnerabilities are reported [cite: 23, 35]. Explicitly capturing `stderr` in Python is necessary to alert on these `Walk error` anomalies [cite: 23, 35].

### 6.2 The Proliferation of GHSA IDs over CVEs

Historically, vulnerabilities were exclusively tracked via MITRE's CVE IDs. However, in the NPM ecosystem, many security flaws (particularly malware, typosquatting, and supply chain attacks) are discovered and remediated by GitHub without ever being assigned a CVE [cite: 27, 33]. 
*   **Behavior**: Trivy relies heavily on the GitHub Advisory Database (GHSA) for NPM packages [cite: 33]. Therefore, the `VulnerabilityID` field will frequently contain identifiers starting with `GHSA-` (e.g., `GHSA-cxm3-wv7p-598c`) [cite: 27, 33].
*   **Handling**: Security pipelines must not assume that `VulnerabilityID` adheres to the `CVE-YYYY-NNNN` regex. Database schemas and SIEM ingestors must be relaxed to accept GHSA formats.

### 6.3 Multiple Findings for the Same Vulnerability

When parsing the JSON output, it is entirely possible to see the same `VulnerabilityID` reported multiple times. This occurs when an NPM package is included multiple times in the `package-lock.json` at different dependency paths (e.g., `Package A -> lodash`, and `Package B -> lodash`).
*   **Handling**: The Python script provided in Section 5 demonstrates the use of a deduplication `set()`, tracking the unique combination of `PkgName` and `VulnerabilityID` to ensure the CSV report is not artificially inflated.

### 6.4 Missing `FixedVersion` and Remediation Challenges

As established, when no patch exists for a vulnerability, the `FixedVersion` key is omitted from the JSON [cite: 21, 30]. While Python's `dict.get()` handles the `KeyError` seamlessly, this scenario presents a workflow challenge: if an image fails a pipeline build due to a CRITICAL vulnerability, but no `FixedVersion` exists, developers cannot resolve the issue through updates. Advanced implementations often parse the `FixedVersion` and only break the build if a fix is actually available (sometimes handled natively by Trivy via the `--ignore-unfixed` flag) [cite: 15, 36].

### 6.5 Trivy Version Instability in Unpinned CI/CD

When installing Trivy via APT repositories (`https://aquasecurity.github.io/trivy-repo/deb`) in Dockerfiles or CI/CD runners, utilizing `apt-get install trivy` without specifying a version pulls the `latest` binary [cite: 37, 38].
*   **Pitfall**: Because Trivy updates frequently, unpinned installations risk introducing sudden breaking changes to the JSON schema or CLI flag behaviors.
*   **Security Risk**: Furthermore, as demonstrated in early 2024, CI/CD pipelines pulling `latest` or unpinned Trivy GitHub Actions were compromised in a supply chain attack (GHSA-69fq-xp46-6x23), resulting in malicious binaries executing in customer environments [cite: 27, 39]. Strict version pinning (e.g., `apt-get install trivy=0.50.1`) and verifying binary checksums are mandatory DevSecOps practices [cite: 25, 40].

## Conclusion

Conducting offline vulnerability scans on NPM dependencies using Trivy requires precision in CLI configuration and robust JSON parsing. By fully isolating Trivy from the network using the suite of `--skip-*-update` and `--offline-scan` flags [cite: 5, 6], organizations can maintain absolute control over their security assessments in air-gapped environments. Coupling this tightly controlled execution with resilient Python automation—capable of traversing nested CVSS vendor hierarchies [cite: 25, 26] and gracefully managing the volatile nature of ecosystem metadata like GHSA identifiers and unpatched flaws [cite: 30, 33]—yields a highly reliable, deterministic, and actionable security pipeline.

**Sources:**
1. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGd98VVXnKOVDwW-sjKllYLrAwpzCxxpBuzOAsCaW5kC39-rrKuKhUyrJH1OAQms897eSRrzD3h7PCEFcRypyrncnWDkT2FDOtkoAVJPA4Z4iiWH7cYBNG4yFt7LDyJ0TNx0n2WMpA-YngefwM=)
2. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHeq1OEALW4PCedGU1TOWNoRhyY1A771lc81teLyXHFPKQP4V0vxRdjLZ9DASz9P1ySU4CwzBcGGXnqGnCqp25pcJw_-yNo2VLFJOzMd2-hRRd2poUVCeLl5AhKjF38dBOiZVoB4atOUEnx9RImT0-NT3AqV6qu8fvJ4l3y1BZ-zxcw-KPxAGI=)
3. [stephane-robert.info](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF0WH4u7DccWxHXIR4TuDtBtgQBkAnUHpWc1QUeConRdv1bottIhc7qelqx-7U7gG5Lj_XTGsaLGrXDiohv8AU-WRjuExI-g-XvaeuA6PyZCwoJZ8-qIkYr8mN2IohFdvWfLoAqzxDXnXbnXS_KZzlvNIH10g==)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWm2xBoae4X97hoCNto0xcwyovQskecg5l3VXSuQoBKeeO-tyodbV9G6bbdPM4SBl7P4f2IFd8Y5kv_00WmRkkXXgeQ1rexkpvxwgsvu_hbn4iOar_mDBkCJ5YcQOoMxTQcLX5EB3kbc_EzFQ=)
5. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQITeTJo-ktt4JFoLXHK7OJQJNrL_zzHvLi7T9I5J8gxwfc2G2UvlkD3E342mEVRdNfmVMpi2m2_waY13TccG3IWf94x-L2Mt-6tFIJgd3H2vs87fm1gFgX-Aw4rUoBeDa3_c8YFi3VAZU)
6. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGuyMpMK1ASTvh33ZkpmDNddmwcYGEWKXRBOxvCBnZts6oidatOQkSGP_4u_th_vjhEVX2utxPVD-U87-9d95w9cAOCERglav3T89iITIZNS4us5wo0qT50ILScuwzOkbEDhyAe)
7. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHhSnIHOecGnlcUEkzYIVGxMxRlRN28tEovELFjlsGOxU_SCgNCL1eEZ9-KEP0dqEm_taXQuHhb_7kA8AjUR4KhbW0ueOb4VYO_eDE6sQBRyZr9uZY_t_XQuZAMcvHMIfjcUDQ3-Ys7reOu4l9bcEpNeuS3liyidbnEq_UBvDgy8A_nZS4A1GCzS2ytpejBXVstTpGXy4ih65TmaYCsFPo5Ywy764=)
8. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqbV_nf6i9zeVjkLYRP9-BRnSDZP2z5_GXc5gtU3DjFhEhyeLI5T8oQKZnDlDu0w-_XpBwi6OKvwU_1jWIolHoaLX30HB5hSewvh8tEMx3cTfOvgBuVwuY1BmdhlLFAR8m2dtrAgoq0Q==)
9. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGQ-pORH_hPby9oiJ1CfhnWoBUVgnD_PKJMFBz0jV9PLV6kdJ8XJlMaPznCTpq-sVQOcgc8E6pvhU5Ipl5BBfERjvx-9TF1W4ipGYc9pZJfxmcBTCIbtyGlwBYSu9iz80qy70Mb4kHaD3JXXe4m)
10. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgN914Go7KIS_bYFEriiSTfBRJb0klgKewGMvaFBkzXUIKJ5Q5m0FrAf4iuYfD6-99clbqtIoT_bMtNycQ3Dd_8xun6u7d2XGT6J8E9GP9kmB0YFFrglJdnM-TbwDDe1DXeDt_)
11. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHvFy5XIeY1zdNrAdiXTGxyzwWWR09R7Jjogz6tCVM06HqDNSqA3HstLGzcJSixWKDAYOP-OboA5cdsVwoeOsOKM9ieeooqHiUgeTf_tTTNcyY-oZPYZ2PZ38t5hTKdlcI7vgwgUADdOB0ysCzD5nB7Gi193tk9Grvp2CiXTcgyhdIOisntvotYDA-kyugsRuBipLPoVA9v)
12. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHLiJhH3-hGxIgQN8wX30V7cerVtusz0cGVuvyZ8M4Jtn8U-dmEEIqQ7E3Yqdp97wasN9GHqA80lDrtbpn53L-OYSdtzn9PouK_0CpZC30KPkbTYZAZ54OApycas2vXsxiQ_rEaPrPPiRossmpk7hgXx4AnJtn0BLP5DwwsbfqO)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEculB3ivTb0e9uMD_qjpyjQkWsGAEiL7CMEyF9014iYshLDFzEr7ANMJJsZ5SfwrbYRVSxYoOcsHXWdP9vNQg11W0rGKcyeOsQbWdq3m3cmmlRsPVGkSYO1N9b8vcmp-hfRzb-yGBdMTMSeg=)
14. [ox.security](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEsY0vmUfNK8KEhzcWv4yTzGZqmS_yrike65F66DltEBeYkLHt7LxPhKKNgelVM6o-M59qCciHG7z_xHwgYLGduxR73tMLeiJP9E9Xv5XYvrqgyMjE7EW4DQxD1tWq1gj-4AGxariOCs0Yf_bDiJ7EuxA==)
15. [hackmd.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4y2KrdLaXYrsNRrae4bJGNwnAqylfgI_zpbdeolQbNs0XWeHAYztY7hXVrEvNcDf3fs1dscYeNVJVWJbRjGGY75Cnab6SNIoai_5g7fAfvl5mzq1uyu-Yd5N5Q9TsPQSqWbsh71PLbb4=)
16. [securecodebox.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_vsk9X1FCVPZbRp8YvuO4JswlQ0ZLBHNGd6fF4uHaiDPqClHADvKNJF-IXAuZOMWKFoFaTsDOqzt7hKTw6AlpGiGiGjnMcOOpYZJNZCQ-MGm7ju85aQDm2OefURbKQCdKmX9y-p8=)
17. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFOTusjphCiJ5iyZme39mvSRIgpRvireO5ypyV33aXDHQMD-_X-LKHeT92PXXrrD2eJc4d9jdo2f528faEKPPfLaYubXzV_OnpObnQygPwbIbsyjooGvBvo0oXa1Ah3Lv3jQtinHg==)
18. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHfg8jllGvWwLTxD-kDYTJ2yR-GqwZLs3CjENoYogx4A9sl9dkbJnZUzrcCl1y1yP4_6cmJ3EiXE_coEdLwsugBRw_ii022CSowqjCa3Fm5Rlst701VncbQVyzhjOGnxjp-H8mrYGFY)
19. [broadcom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHQT2Tq3-7gpmGP5C_xEeFarmHDNZtfecQPawhk0m0SpwHORkY0IkwFrwnn8kro4SPgvZLJrgQ_eHy6Ew8akn57JRDWsONlcZOwze5uQerVrTp8rtk5NhRC-IJci-r8ZmnFKoYSl8R3Sk_oubItGGa_4tdzf5h97ZbvuikzNkO7DuYLCoRIp9zyHQi_N7DjS_PGpa9z3VR3vbnqn8WNKQXKK91zknvBYFpXO-WvCB0Th5MLruXppv5UEaLQPUEo_rJclSgM7rWFCaxZ)
20. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgz1-n5rCQxH6M4st9oa96GLw1Rs01PvKZdxqx00IOvj8B_hwOV62P3CeqAMtfv55PVp1cYPX81Jly-tj-rwWiOHO-0KncwwJMpkNu2PfAbtcFf9DQC51Wr1iVJsUnvzhIpe3pecbeY2mPrQ==)
21. [go.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESJSoNnPiXZvsgX29CaDMEFg4Q8SWQgGyJeKiWsnRYmKh4UfLPpCnkKeMq9P5nfWdXTDKch_ul-5riGl5V-jh7Zj5OpcIZOR4sgAM6HyoQzt1WYQBozmuYbOyqOrZzxEzt5_dbUdyPzh3RCyAAEgrDnUR3)
22. [artifacthub.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHSkpB15fJYv4Q5ex7599c_3Hy3j80I23txMw7RP_M02aOObxygC6u9_b5yWYHrB9L4dxAk8g-JTv7oKdTP8XRQcdrR4t0ZewiWoB4o67p_qqBABmlIfmtpwktL6tusKpiQJIL0kO2KWznPkV9kxq9NS6AL)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFdm184KbmCmNHarqbz8JtujhafTWLPMviwAUDOSwlzkLEbcXdN_bAafkCvfvVSqx-CYiV2Z2JQr6eSF_bciKSjKQUGt37-GoTCqaosx4aJ-ZpNHyrX8llqrgVT3ZGmBZzJsD8mkJDCn0LVLzO)
24. [broadcom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHv3gWUmxdLdUbdy46qHV9_01PNa91z82tubkxysePT_l64f9Gwigdl22wU2ulUfAGXFWZMjTm-97YIjttOEMPHmj4cUs1lTGkNnIPqRlJ_kNvEhm-WUfg_0LUsUEGWWyBqPGaoMUFWTKn6b-FVXJNwPrMQbPZ66TdTFqXCShnDkp6hcflWsg9boR_rwxTcOaVISOLQVVjZ6rg=)
25. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwM29jSPmfRZ5JUjBoVWF3BRgePThwIR2CeqP1oRbZMFjoQ2aPVN_mKcUJI4lIQl5GBH6eJT4Wqc21wp3VVQg3BB94AqooE2vHRG5ORSNzYqPsIgYkTafUny3CbT_mmTdVHtsmd90P0UM58RRXjrwZ882Ulu_YA3zytwnkXedQbHOOaTQjBOKNnQmpWeXKO8Hod8PfLWOrymROmE6EXvum-Q==)
26. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF58s2dONdETXO5RbUlpbwlW_WZBLPCohwrEDLUnZHSQej8wRg8e1qcNQGqGbP3iaqZ7ka1beEbfN-E-kuBsmC1cyx3fp7qerSgtBcWPKJNmaQTXwJgpDLGhUkmSckoDDoyp3QfRfFfQ2AANrc=)
27. [phoenix.security](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGZkK1ZohMXFIUDtwovoaoLZvldExfxCRVG74WhgaP7aWwQGYmzA7pg8azeW3PXp3J7YJyfd8z_iZ9Esv62AjP4iKwIl_ml-QcNIpfPndCq7ZfPCBkp5PVvYyr5DljJy8pKQgZdtgchs6F5J5fOnIbvY7MZQ1eJv4Cj8NEaj5L33het_8jPzvQcrkDa1BKXki9dOg0BwRPb)
28. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGQxQzk0d79W7ShYHtJgqVMvj2RJmG1dVgplND_Qii-dbor_mBIzqe-PesCuKR3GMhjb74eMyHItAPyZ9Ll18nO50KPZde1KiLba11GYxYzXygeJL6LSi7f74TR3B8EOmCPUm6Uw0Z_QMrcGYeLrqc=)
29. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUgRXgCh1ou-k6jiQyvsE0gLh0eoFJd6HsJP-Eijp8a5Mfe5FF4qDjIMQnFoWQGk8Q6POAjrFg9rNSlpuXwbcmz8OJ63SpE28sQuIWJT_EKTfmeQMhc1csipRNCMEgkeGiBH1kDyCu)
30. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF47VuMELD2yGA5jZzwq5GrHjjZXi1Kg6_b9DvO7QQjLjHSmBSt6oS18sw1oYBDzqQmwUZykg_IdGJpbNLVNic9Fntz7C2AVTKK2X7sVeWc-i4CTa-vL16Q-HtOW-GoJyXEfLAYewtL)
31. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECREBme2f2GLspJgecQC1Ua2vancuXM8LVW2XYf5li6jBMrcehKwcXkPMS6mRk8ijImxDHlrmgrXRZ_A__Mv5eY2yrz6swNi571lekUc7-SlTAQ5SC-oEWJfISeeXjzSgvHhUi_9JcYujI9iQ=)
32. [jsonformatter.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6KCVCU2cvN__Yj7jwbQNXzWQOr0RZJS89h2wrQS8IPs4Qp1VImOWlrwbPbih0pm4a525d59INJwH38-h47E6O7RqyGgYWhDGez6cZStLHEVgd0Y3aI2o7b-fiVUTyekHT82I1wc13sIeOup04LsD7)
33. [codecentric.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGCFDvMVYtm4y4i7eZ8moaUTF9-1MT4GdUJTK6zpaw5Q8i-CFJ6I53drKdjLHgkPGjAKrGm2ZdHE_u9ekjIQgks8SdEprwYYyPXaz91R0PDq6x1nNEouVR721qmg-khuI23rxDWyTvsqMkdq3pYNB-m_I8Ngh6GhswxdWSBsXw28NG6YHrU9hks5SHzCvLpPGdZTl-zYc5KJx18NnIL525oRufTylU7vr0_0X4wB2iL)
34. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFKtHCDpsXP6Hak-lahEsH2fKie1Pq_yUHq8H8WYR_kufSh7oYoBTDTJwRMIUXhSTaJ7FakufoNgbZj_N0ecYce0dUfkvqFhavgZJLo0QCTvGC_dB6rypT_51P1MLHhAcU6mfGYLIFMkimXPzk=)
35. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_NyiLzn7aloxUUv1xN84ftoqqXpjy57lpt2s9MwHGN6vttgdJdwme73hM3gQ4AVtOfARlPrFMG0ibChfYpQ9baLhNjQBfkk703A_aEGa2ny0ITVQuLFfnebb_xGmNbkQ21c_aFEbIk1Q7ODzT)
36. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmymMV57HcV9JYhl0o6PVxutWCskEnfS83HxVDrYTQYJHjBkmO72463jOn-QcnMX0IgAzS3BKrkbewTtWcbd7EJKvkAfX3lhVMm3NMSJZqBpCRs_KfyRhMotSGKKI8SUdZ46FRO0u80BN6tYk=)
37. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4TnaGmpnDwoETo1RnQrensR2sSNijKHNAN_i1tWEAUfzhH_GSjecO0t4ePIyf9CF29H0oDyLsdc0ItIuu-mbXdlHhDaZVfwUdnCPEbUssYOTP1HGGmoZft-fcAPNiYgbnzmpFpkP1rDbL)
38. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGzEbAw2pvq3c7IO-KHSHDMmysug6WjX5kVFJf3v7vcsWQlavePuHX0DyIvMe1DfRmlP6uETOpIGYYrGXV_DbcToEaicKdp0J-OLfS37gcUmencoQLIaLu-AX3ZMte44yc=)
39. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFKdpu_39g_tskFQKJaZK7dMYfLl0AU6ZKwv7TX_-8L1COZIYk3GJAWSuqM6jJb4fgaymsvAztI2HILc-Dx6T2igmrBSKN6hpNT9GCDlSjVLi1Old06ba48oUAcon9IISI98TcpU5m8x5uznpnAGpIZhYidEGo0iPsNHg6eIP87CO7jvovxaPz9zxTbOlIl0Kc1hyw=)
40. [trivy.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6lTGKem_DneA3N6PMNiIpzmYsS9PJ9Hs_woO9yZmypS18yswE4BB95YiY9L_xNrnNfO29WrpKz7DPg0WTTguDh0q6iFNABjEy042_JMAwuZchVWu0miMMDdD-5aMceSyrnCtvYd1BwectENzrcVJD)
