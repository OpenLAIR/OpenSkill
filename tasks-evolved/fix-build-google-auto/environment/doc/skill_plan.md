# Skill Creation Plan

**Task**: Diagnose and fix Java Maven build failures by analyzing error logs, generating diff patches, and applying them to the repository

**Rationale**: The task has three distinct functional domains: (1) running Maven builds and parsing error output to diagnose failures, (2) generating correct unified diff patches for the identified fixes, and (3) applying those patches. These map cleanly to two skills: one for build diagnosis/error parsing and one for patch generation/application, since patch generation and application are tightly coupled.

**Number of skills**: 2

---

## Skill 1: evo-maven-build-diagnosis

**Description**: Executes Maven builds, captures output, and parses error logs to identify the root cause of build failures. Handles compilation errors, dependency resolution failures, POM configuration issues, and JDK version incompatibilities.

**Responsibility**: Run Maven builds via subprocess, parse stdout/stderr for error patterns using regex, classify errors (compilation, dependency, POM, version), extract file paths/line numbers/error messages, and write diagnostic analysis to failed_reasons.txt

**Key functions**: `execute_maven_build`, `parse_compilation_errors`, `parse_dependency_errors`, `parse_plugin_errors`, `parse_version_incompatibilities`, `detect_java_version_from_pom`, `classify_build_failure`, `write_diagnosis_report`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-maven-build-diagnosis/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-maven-patch-generation

**Description**: Generates GNU-compatible unified diff patches for proposed code or POM fixes, writes them to numbered patch files, and applies them to the repository using git apply or patch command.

**Responsibility**: Generate unified diff content using difflib with proper handling of trailing newlines and 'No newline at end of file' markers, write patch files in standard diff format, and apply patches via subprocess (git apply or patch)

**Key functions**: `generate_unified_diff`, `make_strict_patch`, `write_patch_file`, `apply_patch_via_git`, `apply_patch_via_patch_command`, `modify_java_source`, `modify_pom_xml`

**Depends on**: evo-maven-build-diagnosis


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-maven-patch-generation/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
