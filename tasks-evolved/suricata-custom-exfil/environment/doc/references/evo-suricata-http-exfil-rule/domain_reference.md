# Domain Reference for evo-suricata-http-exfil-rule

**Responsibility**: Generate the correct Suricata rule syntax for /root/local.rules that matches HTTP POST to exact path /telemetry/v2/report with X-TLM-Mode: exfil header, base64 blob≥80 chars, and sig= with exactly 64 hex chars. Includes knowledge of sticky buffer ordering, http.method, http.uri with startswith/endswith, http.request_header with colon-space delimiter, http.request_body with url_decode transform, and PCRE boundary anchoring.

**Key functions to implement**: generate_exfil_detection_rule, validate_rule_syntax, write_local_rules_file

---

## 1. Suricata 7.0.x HTTP Rule Keywords: Exact Syntax and Semantics


To programmatically generate and validate Suricata rules via a Python utility, the generator must enforce the strict syntactical rules governing Suricata 7.0.x sticky buffers. The legacy Snort-compatible content modifiers (e.g., `http_method`, `http_uri`, `http_client_body`) are deprecated; utilizing them in modern deployments is highly discouraged [cite: 1, 2].

## 2. PCRE in Suricata Rules: Syntax for Body Matching


Perl Compatible Regular Expressions (PCRE) provide powerful pattern-matching capabilities, relying on the underlying C-based PCRE/PCRE2 libraries [cite: 10, 11, 12]. While PCRE allows for immense flexibility, it is computationally expensive. Suricata mitigates this via the Multi-Pattern Matcher (MPM), which evaluates fast patterns (fixed strings) before executing PCRE [cite: 13].

## 3. Combining Multiple Match Conditions in a Single Rule



## 4. Rule Structure and Syntax


A valid Suricata rule consists of three core components: Action, Header, and Options [cite: 16, 18].

## 5. Critical Pitfalls and Edge Cases


Developing a Python utility to write Suricata rules mandates strict programmatic guardrails to prevent common logical errors that lead to false positives (FP) or false negatives (FN).

## 6. Command-Line Execution and PCAP Analysis


For testing the generated rules, the Python utility should interface with Suricata's command-line interface and subsequently parse the output telemetry.