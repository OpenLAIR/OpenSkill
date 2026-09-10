#!/usr/bin/env python3
"""Generate Suricata 7.0 rules for HTTP exfil detection.

Detects data exfiltration hidden in HTTP telemetry traffic.
All 5 conditions must match simultaneously (logical AND):
1. HTTP POST request
2. Request path is exactly /telemetry/v2/report
3. Request header contains X-TLM-Mode: exfil
4. Body has blob= with Base64-looking value >= 80 chars (as a top-level parameter)
5. Body has sig= with exactly 64 hex chars (as a top-level parameter)

Key Suricata 7.0 considerations (from deep research):
- Sticky buffers must be declared BEFORE content matches
- http.request_body is NOT URL-decoded by default; use url_decode transform
- http.request_header uses |3a 20| (colon-space) as name-value separator
- PCRE R flag for relative matching after content anchors
- Parameter boundary checks via (?:^|&) to prevent substring false positives
- Use startswith/endswith on http.uri for exact path matching
"""

import subprocess
import os
import json
import glob


def build_exfil_rule_variants(sid=1000001, rev=1):
    """Build multiple Suricata rule variants to test for best detection.

    Returns a dict of {variant_name: rule_string}.

    We generate variants because:
    - The body may or may not be URL-encoded (url_decode vs no url_decode)
    - Header matching can use http.header or http.request_header
    - Different PCRE boundary strategies may work better
    """
    variants = {}

    # --- Variant A: http.header + url_decode on body ---
    # Uses http.header (concatenated headers buffer) with CRLF anchoring
    # and url_decode transform on request body
    variants['header_urldecode'] = _build_rule(
        sid=sid, rev=rev,
        use_request_header=False,
        use_url_decode=True,
    )

    # --- Variant B: http.request_header + url_decode on body ---
    # Uses http.request_header (individual header buffer) with |3a 20| separator
    # and url_decode transform on request body
    variants['reqheader_urldecode'] = _build_rule(
        sid=sid, rev=rev,
        use_request_header=True,
        use_url_decode=True,
    )

    # --- Variant C: http.header + NO url_decode on body ---
    # For cases where body is not form-urlencoded (raw POST)
    variants['header_raw'] = _build_rule(
        sid=sid, rev=rev,
        use_request_header=False,
        use_url_decode=False,
    )

    # --- Variant D: http.request_header + NO url_decode on body ---
    variants['reqheader_raw'] = _build_rule(
        sid=sid, rev=rev,
        use_request_header=True,
        use_url_decode=False,
    )

    # --- Variant E: http.header + url_decode, relaxed sig boundary ---
    # Uses (?:&|$|\s) instead of (?:[^0-9a-fA-F]|$) for sig termination
    variants['header_urldecode_relaxed'] = _build_rule(
        sid=sid, rev=rev,
        use_request_header=False,
        use_url_decode=True,
        relaxed_sig_boundary=True,
    )

    # --- Variant F: http.header + NO url_decode, relaxed sig boundary ---
    variants['header_raw_relaxed'] = _build_rule(
        sid=sid, rev=rev,
        use_request_header=False,
        use_url_decode=False,
        relaxed_sig_boundary=True,
    )

    # --- Variant G: Minimal - http.header, no url_decode, simpler pcre ---
    # Uses a single combined pcre for each body param instead of content+R
    variants['minimal_combined'] = _build_rule_minimal(sid=sid, rev=rev)

    return variants


def _build_rule(sid=1000001, rev=1, use_request_header=False,
                use_url_decode=True, relaxed_sig_boundary=False):
    """Build a single Suricata rule string with configurable options.

    Args:
        sid: Signature ID
        rev: Rule revision
        use_request_header: If True, use http.request_header with |3a 20|;
                           if False, use http.header with content matching
        use_url_decode: If True, apply url_decode transform to http.request_body
        relaxed_sig_boundary: If True, use looser sig= termination pattern
    """
    header = 'alert http any any -> any any'
    options = []

    options.append('msg:"DATA EXFIL via telemetry POST"')
    options.append('flow:established,to_server')

    # Condition 1: HTTP POST method
    # Sticky buffer declared before content match (Suricata 7.0 syntax)
    options.append('http.method; content:"POST"')

    # Condition 2: Exact request path /telemetry/v2/report
    # startswith + endswith ensures no partial matches like /telemetry/v2/report/extra
    # or /telemetry/v2/report?param=1 (endswith blocks query strings too)
    options.append('http.uri; content:"/telemetry/v2/report"; startswith; endswith')

    # Condition 3: Header X-TLM-Mode: exfil
    if use_request_header:
        # http.request_header isolates individual headers
        # Name and value joined by |3a 20| (colon-space) per Suricata normalization
        # nocase handles case-insensitive header names per RFC 7230
        options.append('http.request_header; content:"X-TLM-Mode|3a 20|exfil"; nocase')
    else:
        # http.header contains all headers concatenated with CRLF
        # Match header name then value within same buffer
        # nocase for case-insensitive header name matching
        options.append('http.header; content:"X-TLM-Mode"; nocase; content:"exfil"')

    # Condition 4 & 5: Body parameters
    # Declare the sticky buffer once; all subsequent content/pcre apply to it
    if use_url_decode:
        # url_decode transform: decodes %HH sequences and + to space
        # CRITICAL: http.request_body is NOT URL-decoded by default
        # Without this, %3D (=) and %2B (+) in form-urlencoded bodies won't match
        options.append('http.request_body; url_decode')
    else:
        options.append('http.request_body')

    # Condition 4: blob= with Base64 value >= 80 chars
    # Strategy:
    #   content:"blob=" — fast pattern pre-filter (MPM optimization)
    #   pcre with R flag — validates value starts with 80+ base64 chars
    #   pcre without R — validates blob= is a top-level parameter (not substring)
    # Base64 charset: A-Z, a-z, 0-9, +, /, = (padding)
    # Forward slash escaped in PCRE: \\/
    options.append('content:"blob="; pcre:"/^[A-Za-z0-9+\\/=]{80,}/R"; pcre:"/(?:^|&)blob=/"')

    # Condition 5: sig= with exactly 64 hex chars
    # The negative character class or $ ensures exactly 64 (not 65+) hex chars
    if relaxed_sig_boundary:
        sig_pcre = 'pcre:"/^[0-9a-fA-F]{64}(?:[^0-9a-fA-F]|$)/R"'
    else:
        sig_pcre = 'pcre:"/^[0-9a-fA-F]{64}(?:[^0-9a-fA-F]|$)/R"'
    options.append(f'content:"sig="; {sig_pcre}; pcre:"/(?:^|&)sig=/"')

    # Metadata
    options.append(f'sid:{sid}; rev:{rev}')

    options_str = '; '.join(options) + ';'
    rule = f'{header} ({options_str})'
    return rule


def _build_rule_minimal(sid=1000001, rev=1):
    """Build a minimal rule variant using combined pcre patterns.

    This variant uses fewer content matches and relies more on PCRE,
    which may be slower but handles edge cases differently.
    """
    header = 'alert http any any -> any any'
    options = []

    options.append('msg:"DATA EXFIL via telemetry POST"')
    options.append('flow:established,to_server')

    # Method
    options.append('http.method; content:"POST"')

    # Exact URI
    options.append('http.uri; content:"/telemetry/v2/report"; startswith; endswith')

    # Header - use http.header with nocase
    options.append('http.header; content:"X-TLM-Mode"; nocase; content:"exfil"')

    # Body - no url_decode, use combined pcre
    options.append('http.request_body; content:"blob="; pcre:"/(?:^|&)blob=[A-Za-z0-9+\\/=]{80,}/"; content:"sig="; pcre:"/(?:^|&)sig=[0-9a-fA-F]{64}(?:[^0-9a-fA-F]|$)/"')

    options.append(f'sid:{sid}; rev:{rev}')

    options_str = '; '.join(options) + ';'
    rule = f'{header} ({options_str})'
    return rule


def build_exfil_rule(sid=1000001, rev=1):
    """Build the default Suricata rule string for exfil detection.

    Uses the most robust configuration:
    - http.header for broad header matching
    - No url_decode (handles raw bodies; most common in custom exfil)
    - Parameter boundary awareness via (?:^|&)
    - PCRE R flag for value validation after content anchors

    Returns:
        str: Complete Suricata rule line
    """
    return _build_rule(
        sid=sid, rev=rev,
        use_request_header=False,
        use_url_decode=False,
        relaxed_sig_boundary=False,
    )


def write_rules_file(output_path='/root/local.rules', rule=None, sid=1000001, rev=1):
    """Write the complete local.rules file.

    Args:
        output_path: Path to write the rules file
        rule: Pre-built rule string. If None, generates default rule.
        sid: Signature ID (used only if rule is None)
        rev: Rule revision (used only if rule is None)

    Returns:
        str: The rule that was written
    """
    if rule is None:
        rule = build_exfil_rule(sid=sid, rev=rev)

    with open(output_path, 'w') as f:
        f.write('# Suricata rules for HTTP exfil detection\n')
        f.write(rule + '\n')

    return rule


def test_rule_with_suricata(pcap_path, rules_path='/root/local.rules',
                            config_path='/root/suricata.yaml',
                            log_dir='/tmp/suricata-test',
                            sid=1000001):
    """Run Suricata against a pcap and return alert count for the given SID.

    Args:
        pcap_path: Path to PCAP file
        rules_path: Path to rules file
        config_path: Path to suricata.yaml
        log_dir: Directory for Suricata output logs
        sid: Signature ID to count alerts for

    Returns:
        tuple: (alert_count, stderr_output)
    """
    if not os.path.exists(pcap_path):
        print(f"WARNING: PCAP file not found: {pcap_path}")
        return 0, f"PCAP not found: {pcap_path}"

    os.makedirs(log_dir, exist_ok=True)

    # Clean up previous log files to avoid stale results
    eve_path = os.path.join(log_dir, 'eve.json')
    fast_path = os.path.join(log_dir, 'fast.log')
    for path in [eve_path, fast_path]:
        if os.path.exists(path):
            os.remove(path)

    # Also clean any rotated eve files
    for f in glob.glob(os.path.join(log_dir, 'eve.json.*')):
        os.remove(f)

    cmd = [
        'suricata',
        '-c', config_path,
        '-S', rules_path,    # -S loads ONLY this rule file (isolated testing)
        '-r', pcap_path,     # Read from PCAP (offline mode)
        '-l', log_dir,       # Log output directory
        '-k', 'none',        # Disable checksum validation (critical for synthetic PCAPs)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print(f"WARNING: Suricata timed out processing {pcap_path}")
        return 0, "Suricata timeout"
    except FileNotFoundError:
        print("ERROR: Suricata binary not found. Is it installed?")
        return 0, "Suricata not found"

    # Parse eve.json for alerts matching our SID
    alert_count = 0
    if os.path.exists(eve_path):
        with open(eve_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get('event_type') == 'alert':
                        alert_obj = event.get('alert', {})
                        if alert_obj.get('signature_id') == sid:
                            alert_count += 1
                except json.JSONDecodeError:
                    # Partial writes or corrupted lines — skip
                    continue

    return alert_count, result.stderr


def auto_select_best_rule(pos_pcap='/root/pcaps/train_pos.pcap',
                          neg_pcap='/root/pcaps/train_neg.pcap',
                          output_path='/root/local.rules',
                          config_path='/root/suricata.yaml',
                          sid=1000001, rev=1):
    """Test all rule variants against training PCAPs and select the best one.

    Best = most positive alerts AND zero false positives.
    If no variant achieves zero FP, selects the one with fewest FP and most TP.

    Returns:
        str: The best rule string (also written to output_path)
    """
    variants = build_exfil_rule_variants(sid=sid, rev=rev)

    results = {}
    best_variant = None
    best_score = (-1, float('inf'))  # (tp, -fp) — maximize tp, minimize fp

    for name, rule in variants.items():
        print(f"\n--- Testing variant: {name} ---")
        print(f"Rule: {rule[:200]}...")

        # Write this variant's rule
        write_rules_file(output_path, rule=rule)

        # Test positive PCAP (should alert)
        tp = 0
        if os.path.exists(pos_pcap):
            log_dir_pos = f'/tmp/suri-test-{name}-pos'
            tp, stderr_pos = test_rule_with_suricata(
                pos_pcap, output_path, config_path, log_dir_pos, sid)
            print(f"  Positive alerts (TP): {tp}")
            if tp == 0 and stderr_pos:
                # Print last portion of stderr for debugging
                print(f"  Stderr (last 500): {stderr_pos[-500:]}")
        else:
            print(f"  WARNING: Positive PCAP not found: {pos_pcap}")

        # Test negative PCAP (should NOT alert)
        fp = 0
        if os.path.exists(neg_pcap):
            log_dir_neg = f'/tmp/suri-test-{name}-neg'
            fp, stderr_neg = test_rule_with_suricata(
                neg_pcap, output_path, config_path, log_dir_neg, sid)
            print(f"  False positives (FP): {fp}")
        else:
            print(f"  WARNING: Negative PCAP not found: {neg_pcap}")

        results[name] = {'tp': tp, 'fp': fp, 'rule': rule}

        # Score: prefer zero FP, then maximize TP
        score = (tp if fp == 0 else 0, -fp)
        if score > best_score:
            best_score = score
            best_variant = name

    # If no variant got zero FP with any TP, fall back to best TP with least FP
    if best_score[0] == 0:
        print("\nWARNING: No variant achieved TP>0 with FP=0. Selecting least-bad option.")
        best_variant = max(results.keys(),
                          key=lambda k: (results[k]['tp'], -results[k]['fp']))

    best_rule = results[best_variant]['rule']
    print(f"\n=== Selected variant: {best_variant} ===")
    print(f"  TP={results[best_variant]['tp']}, FP={results[best_variant]['fp']}")
    print(f"  Rule: {best_rule}")

    # Write the winning rule
    write_rules_file(output_path, rule=best_rule)

    return best_rule


def validate_rule_syntax(rule_string):
    """Basic syntactic validation of a Suricata rule string.

    Checks for common mistakes:
    - Missing parentheses
    - Missing sid
    - Missing semicolons
    - Legacy syntax usage

    Returns:
        tuple: (is_valid: bool, errors: list[str])
    """
    errors = []

    if not rule_string.startswith('alert '):
        errors.append("Rule must start with 'alert'")

    if '(' not in rule_string or ')' not in rule_string:
        errors.append("Rule must have options in parentheses")

    if 'sid:' not in rule_string:
        errors.append("Rule must contain sid")

    # Check for legacy syntax patterns
    legacy_patterns = [
        ('http_method', 'Use http.method; instead of http_method'),
        ('http_uri', 'Use http.uri; instead of http_uri'),
        ('http_client_body', 'Use http.request_body; instead of http_client_body'),
        ('uricontent', 'Use http.uri; content: instead of uricontent'),
    ]
    for pattern, msg in legacy_patterns:
        if pattern in rule_string:
            errors.append(f"Legacy syntax detected: {msg}")

    # Check PCRE has proper delimiters
    import re
    pcre_matches = re.findall(r'pcre:"([^"]*)"', rule_string)
    for pcre_val in pcre_matches:
        if not pcre_val.startswith('/'):
            errors.append(f"PCRE must start with /: {pcre_val}")
        # Find the closing / (accounting for flags after it)
        parts = pcre_val.rsplit('/', 1)
        if len(parts) < 2:
            errors.append(f"PCRE must have closing /: {pcre_val}")

    return len(errors) == 0, errors


if __name__ == '__main__':
    print("=" * 70)
    print("Suricata Exfil Rule Generator - evo-suricata-custom-exfil")
    print("=" * 70)

    # Check if training PCAPs exist for auto-selection
    pos_pcap = '/root/pcaps/train_pos.pcap'
    neg_pcap = '/root/pcaps/train_neg.pcap'

    if os.path.exists(pos_pcap) and os.path.exists(neg_pcap):
        print("\nTraining PCAPs found. Running auto-selection...")
        best_rule = auto_select_best_rule()
    else:
        print("\nTraining PCAPs not found. Using default rule.")
        best_rule = write_rules_file('/root/local.rules')
        print(f"Rule written to /root/local.rules:")
        print(best_rule)

    # Validate the final rule
    is_valid, errors = validate_rule_syntax(best_rule)
    if is_valid:
        print("\nRule syntax validation: PASSED")
    else:
        print(f"\nRule syntax validation: FAILED")
        for err in errors:
            print(f"  - {err}")

    # Final test against any available PCAPs
    print("\n--- Final verification ---")
    pcap_dir = '/root/pcaps'
    if os.path.isdir(pcap_dir):
        for pcap_file in sorted(os.listdir(pcap_dir)):
            if pcap_file.endswith('.pcap'):
                pcap_path = os.path.join(pcap_dir, pcap_file)
                log_dir = f'/tmp/suri-final-{pcap_file.replace(".pcap", "")}'
                count, _ = test_rule_with_suricata(pcap_path, log_dir=log_dir)
                label = "POS" if "pos" in pcap_file.lower() else "NEG" if "neg" in pcap_file.lower() else "???"
                status = "OK" if (label == "POS" and count > 0) or (label == "NEG" and count == 0) else "CHECK"
                print(f"  {pcap_file}: {count} alerts [{label}] [{status}]")