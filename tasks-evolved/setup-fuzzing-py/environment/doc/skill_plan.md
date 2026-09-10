# Skill Creation Plan

**Task**: Identify 5 Python libraries in /app/, analyze their functions, create Atheris fuzz drivers, set up virtual environments with dependencies, and run each fuzzer for 10 seconds with log capture.

**Rationale**: This task involves two distinct concerns: (1) discovering and analyzing Python libraries in the directory, and (2) setting up and executing coverage-guided fuzz testing with Atheris. Splitting into a discovery/analysis skill and a fuzzing execution skill provides clean separation while keeping the plan minimal.

**Number of skills**: 3

---

## Skill 1: evo-python-library-discovery

**Description**: Detects Python libraries/packages in a directory by checking for pyproject.toml, setup.py, setup.cfg, or other standard Python project markers. Provides utilities to list library paths and analyze their structure, entry points, and key functions for testing.

**Responsibility**: Identify Python library directories, list them to a file, and analyze each library's public API and important functions to produce notes_for_testing.txt files.

**Key functions**: `find_python_libraries`, `analyze_library_api`, `write_libraries_txt`, `write_testing_notes`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-python-library-discovery/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-atheris-fuzz-driver

**Description**: Creates Atheris-based coverage-guided fuzz drivers for Python libraries using FuzzedDataProvider for structured input generation. Includes templates and patterns for different library types (parsers, formatters, serializers, ML frameworks).

**Responsibility**: Generate fuzz.py harness files for each library with proper instrumentation, FuzzedDataProvider usage, and exception handling tailored to each library's API.

**Key functions**: `generate_fuzz_driver`, `get_driver_template`, `get_exception_handlers_for_lib`, `create_fuzz_driver_file`

**Depends on**: evo-python-library-discovery


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-atheris-fuzz-driver/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-fuzz-env-runner

**Description**: Sets up Python virtual environments using uv for each library, installs dependencies from project configuration files, and executes the fuzzer for a specified duration with proper log redirection.

**Responsibility**: Create .venv in each library directory, install library dependencies and atheris, run fuzz.py with LibFuzzer flags (-max_total_time=10), and capture output to fuzz.log.

**Key functions**: `setup_venv_with_uv`, `install_dependencies`, `run_fuzzer_with_timeout`, `capture_fuzz_log`

**Depends on**: evo-atheris-fuzz-driver


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-fuzz-env-runner/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
