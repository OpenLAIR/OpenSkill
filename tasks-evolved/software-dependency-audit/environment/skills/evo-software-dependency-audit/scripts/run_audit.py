#!/usr/bin/env python3
"""
Standalone script to run the full security audit pipeline.

Usage:
    python3 /root/.claude/skills/evo-software-dependency-audit/scripts/run_audit.py

This will scan /root/package-lock.json using Trivy's offline database
and write results to /root/security_audit.csv.
"""

import sys
import os

# Add scripts directory to path
scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, scripts_dir)

from utils import full_audit

def main():
    lockfile_path = '/root/package-lock.json'
    output_csv_path = '/root/security_audit.csv'

    if not os.path.exists(lockfile_path):
        print(f"ERROR: Lockfile not found at {lockfile_path}", file=sys.stderr)
        sys.exit(1)

    vulns = full_audit(lockfile_path, output_csv_path)
    print(f"\nAudit complete. Found {len(vulns)} HIGH/CRITICAL vulnerabilities.")
    print(f"Results written to {output_csv_path}")

    # Print summary
    for v in vulns:
        print(f"  {v['CVE_ID']} | {v['Package']}@{v['Version']} | "
              f"{v['Severity']} | CVSS:{v['CVSS_Score']} | Fixed:{v['Fixed_Version']}")

if __name__ == '__main__':
    main()