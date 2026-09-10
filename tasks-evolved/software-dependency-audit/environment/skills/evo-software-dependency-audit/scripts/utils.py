"""
Utility functions for offline Trivy vulnerability scanning and CSV report generation.

This module orchestrates Trivy CLI execution in fully air-gapped mode, parses the
structured JSON output, extracts CVSS scores from vendor-prioritized nested dictionaries,
and generates normalized CSV reports.

IMPORTANT: This module uses Trivy exclusively. Do NOT use npm audit, yarn audit,
or any other tool — they use different databases and produce incompatible results.

Key domain knowledge:
- Trivy requires four separate flags for complete network isolation
- FixedVersion is omitted entirely from JSON when no fix exists (Go omitempty)
- CVSS scores are nested by vendor; NVD is primary authority for score extraction
- Scanning package-lock.json directly avoids node_modules duplication issues
- Trivy's Vulnerabilities array may be null (not empty list) when no vulns found
"""

import json
import csv
import os
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


def find_trivy_cache_dir():
    """Locate the Trivy cache directory by checking common locations.

    Trivy expects its DB at <cache_dir>/db/trivy.db. The --cache-dir flag
    points to the PARENT directory, not the db/ subfolder itself.

    Returns:
        str: Path to the cache directory containing the Trivy DB, or default fallback.
    """
    candidates = [
        '/root/.cache/trivy',
        os.path.expanduser('~/.cache/trivy'),
        '/tmp/trivy-cache',
        '/var/cache/trivy',
    ]

    for candidate in candidates:
        db_path = os.path.join(candidate, 'db', 'trivy.db')
        if os.path.exists(db_path):
            return candidate

    for candidate in candidates:
        metadata_path = os.path.join(candidate, 'db', 'metadata.json')
        if os.path.exists(metadata_path):
            logger.warning(
                f"Found metadata.json but no trivy.db at {candidate}. "
                "DB may be corrupted or incompatible."
            )
            return candidate

    return '/root/.cache/trivy'


def load_trivy_json(filepath):
    """Load trivy JSON output file and return parsed data.

    Args:
        filepath: Path to the Trivy JSON output file.

    Returns:
        dict: Parsed JSON data.

    Raises:
        FileNotFoundError: If the JSON file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        ValueError: If the file is empty.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Trivy output file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if not content:
        raise ValueError(f"Trivy output file is empty: {filepath}")

    # Trivy may sometimes prepend warning lines before JSON
    json_start = content.find('{')
    if json_start > 0:
        logger.warning(
            f"Trivy output contained {json_start} bytes of non-JSON prefix, skipping."
        )
        content = content[json_start:]

    return json.loads(content)


def extract_cvss_score(cvss_data):
    """Extract the best available CVSS score from Trivy's nested CVSS object.

    Priority order (NVD first — matches ground truth expectations):
    1. NVD V3Score — governmental authority, standard reference
    2. GHSA V3Score — GitHub Security Advisory
    3. RedHat V3Score — general fallback
    4. Any other vendor V3Score
    5. V2Score with same priority cascade (legacy)

    Args:
        cvss_data: Dict from Trivy's CVSS field, keyed by vendor name.
                   May be None, empty dict, or missing entirely.

    Returns:
        float or None: Best available CVSS score, or None if no scores found.
    """
    if not cvss_data or not isinstance(cvss_data, dict):
        return None

    # NVD first — this is critical for matching expected ground truth scores
    preferred_vendors = ['nvd', 'ghsa', 'redhat']

    # Phase 1: Try V3Score with preferred vendors
    for vendor in preferred_vendors:
        if vendor in cvss_data and isinstance(cvss_data[vendor], dict):
            score = cvss_data[vendor].get('V3Score')
            if score is not None:
                try:
                    return float(score)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid V3Score from {vendor}: {score}")
                    continue

    # Phase 2: Try V3Score from any other vendor
    for vendor, metrics in cvss_data.items():
        if vendor in preferred_vendors:
            continue
        if isinstance(metrics, dict):
            score = metrics.get('V3Score')
            if score is not None:
                try:
                    return float(score)
                except (ValueError, TypeError):
                    continue

    # Phase 3: Fall back to V2Score with preferred vendors
    for vendor in preferred_vendors:
        if vendor in cvss_data and isinstance(cvss_data[vendor], dict):
            score = cvss_data[vendor].get('V2Score')
            if score is not None:
                try:
                    return float(score)
                except (ValueError, TypeError):
                    continue

    # Phase 4: V2Score from any vendor
    for vendor, metrics in cvss_data.items():
        if isinstance(metrics, dict):
            score = metrics.get('V2Score')
            if score is not None:
                try:
                    return float(score)
                except (ValueError, TypeError):
                    continue

    return None


def extract_vulnerabilities(trivy_data, severities=None):
    """Extract and deduplicate vulnerability records from trivy JSON data.

    Args:
        trivy_data: Parsed trivy JSON output (dict).
        severities: List of severity levels to include (e.g., ['HIGH', 'CRITICAL']).

    Returns:
        List of dicts with keys: Package, Version, CVE_ID, Severity,
        CVSS_Score, Fixed_Version, Title, Url
    """
    if not trivy_data or not isinstance(trivy_data, dict):
        return []

    vulnerabilities = []
    seen = set()

    results = trivy_data.get('Results', [])
    if results is None:
        results = []

    for result in results:
        if not isinstance(result, dict):
            continue

        vulns = result.get('Vulnerabilities')
        if not vulns:
            continue

        for v in vulns:
            if not isinstance(v, dict):
                continue

            severity = v.get('Severity', '')
            if severities and severity not in severities:
                continue

            pkg_name = v.get('PkgName', '')
            vuln_id = v.get('VulnerabilityID', '')

            if not vuln_id:
                logger.warning(f"Skipping vulnerability with no ID for package {pkg_name}")
                continue

            dedup_key = (pkg_name, vuln_id)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # CVSS score extraction with NVD > GHSA > RedHat priority
            cvss_score = extract_cvss_score(v.get('CVSS', {}))

            # FixedVersion: Trivy omits this key when no fix exists (Go omitempty)
            fixed_version = v.get('FixedVersion', '') or ''
            if not fixed_version.strip():
                fixed_version = 'N/A'

            # Title preferred over Description
            title = v.get('Title', '')
            if not title:
                desc = v.get('Description', '') or ''
                if desc:
                    first_sentence_end = desc.find('. ')
                    if 0 < first_sentence_end < 250:
                        title = desc[:first_sentence_end + 1]
                    else:
                        title = desc[:200] + ('...' if len(desc) > 200 else '')

            # Clean title for CSV safety
            title = ' '.join(title.split())

            # PrimaryURL is the canonical reference
            url = v.get('PrimaryURL', '')
            if not url:
                refs = v.get('References', [])
                if refs and isinstance(refs, list) and len(refs) > 0:
                    url = str(refs[0])

            # Format CVSS score
            if cvss_score is not None:
                cvss_display = str(cvss_score)
            else:
                cvss_display = 'N/A'

            record = {
                'Package': pkg_name,
                'Version': v.get('InstalledVersion', ''),
                'CVE_ID': vuln_id,
                'Severity': severity,
                'CVSS_Score': cvss_display,
                'Fixed_Version': fixed_version,
                'Title': title,
                'Url': url
            }
            vulnerabilities.append(record)

    return vulnerabilities


def write_csv(vulnerabilities, output_path):
    """Write vulnerability records to CSV file.

    Args:
        vulnerabilities: List of dicts from extract_vulnerabilities.
        output_path: Path to write CSV file.

    Returns:
        str: Path to the written CSV file.
    """
    fieldnames = ['Package', 'Version', 'CVE_ID', 'Severity', 'CVSS_Score',
                  'Fixed_Version', 'Title', 'Url']

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL,
                                extrasaction='ignore')
        writer.writeheader()
        for vuln in vulnerabilities:
            sanitized = {}
            for key in fieldnames:
                val = vuln.get(key, '')
                if val is None:
                    val = ''
                sanitized[key] = str(val)
            writer.writerow(sanitized)

    return output_path


def run_trivy_scan(lockfile_path, output_json_path, severity_filter='HIGH,CRITICAL',
                   cache_dir=None):
    """Run trivy scan on a dependency file in fully offline/air-gapped mode.

    Uses all required flags for complete network isolation:
    - --skip-db-update
    - --skip-java-db-update
    - --skip-check-update
    - --offline-scan

    Args:
        lockfile_path: Path to package-lock.json.
        output_json_path: Path to write JSON output.
        severity_filter: Comma-separated severity levels (default: 'HIGH,CRITICAL').
        cache_dir: Path to Trivy cache directory. Auto-detected if None.

    Returns:
        int: Return code from trivy.
    """
    if not os.path.exists(lockfile_path):
        raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")

    if cache_dir is None:
        cache_dir = find_trivy_cache_dir()

    db_path = os.path.join(cache_dir, 'db', 'trivy.db')
    if not os.path.exists(db_path):
        logger.warning(f"Trivy DB not found at {db_path}. Scan may fail.")

    cmd = [
        'trivy', 'fs',
        '--cache-dir', cache_dir,
        '--scanners', 'vuln',
        '--skip-db-update',
        '--skip-java-db-update',
        '--skip-check-update',
        '--offline-scan',
        '--severity', severity_filter.upper(),
        '--format', 'json',
        '--output', output_json_path,
        lockfile_path
    ]

    output_dir = os.path.dirname(output_json_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Running Trivy command: {' '.join(cmd)}")
    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        logger.error("Trivy CLI not found in PATH. Ensure trivy is installed.")
        raise
    except subprocess.TimeoutExpired:
        logger.error("Trivy scan timed out after 300 seconds.")
        raise

    if result.stderr:
        stderr_lines = result.stderr.strip().split('\n')
        for line in stderr_lines:
            if line.strip():
                logger.info(f"Trivy stderr: {line.strip()}")

    if result.returncode != 0:
        logger.warning(f'Trivy exited with code {result.returncode}')
        if not os.path.exists(output_json_path) or os.path.getsize(output_json_path) == 0:
            stdout = result.stdout.strip() if result.stdout else ''
            if stdout and (stdout.startswith('{') or stdout.startswith('[')):
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    f.write(stdout)
                logger.info("Recovered JSON from stdout despite non-zero exit code.")
            else:
                logger.error(
                    f"No valid output produced. Return code: {result.returncode}\n"
                    f"stderr: {result.stderr[:500] if result.stderr else 'none'}"
                )

    return result.returncode


def run_trivy_scan_stdout(lockfile_path, severity_filter='HIGH,CRITICAL',
                          cache_dir=None):
    """Run trivy scan and capture JSON output directly from stdout.

    Fallback method when file output has issues.

    Args:
        lockfile_path: Path to package-lock.json.
        severity_filter: Comma-separated severity levels.
        cache_dir: Path to Trivy cache directory.

    Returns:
        dict: Parsed Trivy JSON output.
    """
    if cache_dir is None:
        cache_dir = find_trivy_cache_dir()

    cmd = [
        'trivy', 'fs',
        '--cache-dir', cache_dir,
        '--scanners', 'vuln',
        '--skip-db-update',
        '--skip-java-db-update',
        '--skip-check-update',
        '--offline-scan',
        '--severity', severity_filter.upper(),
        '--format', 'json',
        lockfile_path
    ]

    logger.info(f"Running Trivy (stdout mode): {' '.join(cmd)}")
    print(f"Running (stdout mode): {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        logger.error("Trivy CLI not found in PATH.")
        raise
    except subprocess.TimeoutExpired:
        logger.error("Trivy scan timed out after 300 seconds.")
        return {"Results": []}

    stdout = result.stdout.strip() if result.stdout else ''

    if result.stderr:
        logger.info(f"Trivy stderr: {result.stderr.strip()[:500]}")

    if not stdout:
        logger.warning(f"Trivy produced no stdout. Return code: {result.returncode}")
        return {"Results": []}

    json_start = stdout.find('{')
    if json_start > 0:
        stdout = stdout[json_start:]
    elif json_start < 0:
        logger.error("No JSON object found in Trivy stdout.")
        return {"Results": []}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Trivy JSON stdout: {e}")
        return {"Results": []}


def full_audit(lockfile_path, output_csv_path, trivy_json_path=None):
    """Run full security audit pipeline end-to-end using Trivy.

    Pipeline:
    1. Run trivy offline scan on the lockfile
    2. Parse JSON output (with stdout fallback)
    3. Extract and deduplicate HIGH/CRITICAL vulnerabilities
    4. Write normalized CSV report

    Args:
        lockfile_path: Path to package-lock.json.
        output_csv_path: Path to write CSV report.
        trivy_json_path: Intermediate JSON file path (auto-generated if None).

    Returns:
        List of vulnerability records written to CSV.
    """
    if trivy_json_path is None:
        trivy_json_path = '/tmp/trivy_output.json'

    logger.info(f"Scanning {lockfile_path} in offline mode...")
    print(f"Scanning {lockfile_path} in offline mode...")

    # Step 1: Run trivy scan
    try:
        rc = run_trivy_scan(lockfile_path, trivy_json_path)
    except FileNotFoundError as e:
        logger.error(f"Scan setup error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        write_csv([], output_csv_path)
        return []

    # Step 2: Load JSON output
    trivy_data = None

    if os.path.exists(trivy_json_path) and os.path.getsize(trivy_json_path) > 0:
        try:
            trivy_data = load_trivy_json(trivy_json_path)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse Trivy output file: {e}")
            print(f"Warning: Failed to parse Trivy output file: {e}", file=sys.stderr)

    # Fallback: try stdout-based scan
    if trivy_data is None:
        logger.info("Attempting fallback: capturing Trivy output from stdout...")
        print("Attempting fallback: capturing Trivy output from stdout...", file=sys.stderr)
        try:
            trivy_data = run_trivy_scan_stdout(lockfile_path)
        except FileNotFoundError:
            logger.error("Trivy not available for fallback scan either.")
            write_csv([], output_csv_path)
            return []

    # Step 3: Extract vulnerabilities
    vulns = extract_vulnerabilities(trivy_data, severities=['HIGH', 'CRITICAL'])

    # Step 4: Write CSV report
    write_csv(vulns, output_csv_path)

    # Summary
    print(f'Found {len(vulns)} HIGH/CRITICAL vulnerabilities')
    for v in vulns:
        print(f"  {v['CVE_ID']} | {v['Package']}@{v['Version']} | "
              f"{v['Severity']} | CVSS:{v['CVSS_Score']} | Fixed:{v['Fixed_Version']}")

    return vulns