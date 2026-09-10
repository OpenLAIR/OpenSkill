# Domain Reference for evo-fuzz-env-runner

**Responsibility**: Create .venv in each library directory, install library dependencies and atheris, run fuzz.py with LibFuzzer flags (-max_total_time=10), and capture output to fuzz.log.

**Key functions to implement**: setup_venv_with_uv, install_dependencies, run_fuzzer_with_timeout, capture_fuzz_log

---

## 3. LibFuzzer Integration: Execution Engine and Configuration


Atheris operates as a proxy to LibFuzzer. When `atheris.Setup(sys.argv, TestOneInput)` is called, Atheris extracts LibFuzzer-specific flags from `sys.argv`, modifying the list in-place so that the Python application itself does not attempt to parse fuzzer flags [cite: 2, 3].

## 4. The OSS-Fuzz Base-Builder-Python Environment


OSS-Fuzz is Google's continuous fuzzing infrastructure for open-source software [cite: 20, 21]. Integrating a Python project into OSS-Fuzz revolves around Docker images, specifically `gcr.io/oss-fuzz-base/base-builder-python` [cite: 22].

## 9. Log Redirection and Fuzzing Artifact Management


Continuous fuzzing generates massive amounts of standard output (stdout) and standard error (stderr), detailing coverage metrics (cov, ft, corp), mutation strategies, and crash stack traces [cite: 16]. Managing this output is crucial for artifact archiving.