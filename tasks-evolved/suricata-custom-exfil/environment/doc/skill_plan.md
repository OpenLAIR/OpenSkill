# Skill Creation Plan

**Task**: Write a Suricata rule (sid:1000001) in /root/local.rules that detects HTTP POST exfiltration matching specific path, header, and body patterns while avoiding false positives.

**Rationale**: This is a focused task requiring one skill: writing a correct Suricata 7.0 rule with sticky buffers, exact URI matching, header inspection, and PCRE body matching. The background research provides all needed syntax details. A single skill covering Suricata rule construction is sufficient since there's no separate data processing or output formatting needed.

**Number of skills**: 1

---

## Skill 1: evo-suricata-http-exfil-rule

**Description**: Constructs and validates Suricata 7.0 rules for detecting HTTP-based data exfiltration patterns using sticky buffers, content matching, and PCRE. Covers HTTP method, URI exact matching, request header inspection, and request body pattern matching with url_decode transform.

**Responsibility**: Generate the correct Suricata rule syntax for /root/local.rules that matches HTTP POST to exact path /telemetry/v2/report with X-TLM-Mode: exfil header, base64 blob≥80 chars, and sig= with exactly 64 hex chars. Includes knowledge of sticky buffer ordering, http.method, http.uri with startswith/endswith, http.request_header with colon-space delimiter, http.request_body with url_decode transform, and PCRE boundary anchoring.

**Key functions**: `generate_exfil_detection_rule`, `validate_rule_syntax`, `write_local_rules_file`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-suricata-http-exfil-rule/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
