# Skill Creation Plan

**Task**: Diagnose and fix Python build failures in a BugSwarm-reproduced AgentOps-AI/agentops repository by analyzing errors, generating diff patches, and applying them.

**Rationale**: The task has three distinct phases: (1) diagnosing the build failure by analyzing code, logs, and configuration, (2) generating correct unified diff patches, and (3) applying those patches. Diagnosis and patch generation are the two core competencies, while patch application is straightforward enough to fold into the patch generation skill.

**Number of skills**: 2

---

## Skill 1: evo-build-diagnosis

**Description**: Analyzes a Python repository to identify the root causes of build failures, including syntax errors, import errors, test failures, and build configuration issues. Writes a structured analysis to a findings file.

**Responsibility**: Scan repository files for syntax errors (via ast.parse/compile), parse pytest output and CI logs, check build configuration files (pyproject.toml, setup.py, setup.cfg), identify missing dependencies, and produce a structured diagnosis report in failed_reasons.txt.

**Key functions**: `find_repo_path`, `parse_syntax_errors`, `run_build_and_capture_errors`, `run_tests_and_capture_failures`, `analyze_build_config`, `check_import_availability`, `write_diagnosis_report`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-build-diagnosis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-patch-generate-apply

**Description**: Generates git-compatible unified diff patches from original and modified file contents, writes them to numbered patch files, and applies them to the repository using git apply or GNU patch.

**Responsibility**: Generate properly formatted unified diffs (with a/b prefixes, correct context lines, POSIX newline handling), write patch_{i}.diff files, and apply patches using git apply with appropriate flags and fallback strategies.

**Key functions**: `generate_unified_diff`, `handle_no_newline_at_eof`, `write_patch_file`, `apply_patch`, `validate_patch_applied`, `apply_all_patches`

**Depends on**: evo-build-diagnosis


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-patch-generate-apply/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
