# Skill Creation Plan

**Task**: Fix CVE-2025-32433 in Erlang/OTP SSH server by adding authentication check to ssh_connection.erl to block pre-auth connection protocol messages

**Rationale**: This is a single well-defined code patch task: inserting one pattern-matching clause into one Erlang source file. The vulnerability, fix location, and exact code change are precisely documented. A single skill covering vulnerability identification and patching is sufficient.

**Number of skills**: 1

---

## Skill 1: evo-erlang-ssh-cve-patch

**Description**: Identifies and patches CVE-2025-32433 in Erlang/OTP SSH server source code by inserting an authentication-state check in ssh_connection.erl that rejects connection protocol messages (IDs >= 80) received before authentication is complete. The fix adds a pattern-matching clause for handle_msg/4 that matches unauthenticated server connections and returns a disconnect tuple.

**Responsibility**: Locate lib/ssh/src/ssh_connection.erl in the OTP source tree, find the handle_msg/4 function clauses, verify the vulnerability exists (no authenticated=false guard), and insert the correct catch-all clause after the ssh_msg_disconnect handler but before any channel/connection message handlers.

**Key functions**: `find_ssh_connection_erl`, `check_if_already_patched`, `apply_cve_2025_32433_patch`, `validate_patch_applied`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-erlang-ssh-cve-patch/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
