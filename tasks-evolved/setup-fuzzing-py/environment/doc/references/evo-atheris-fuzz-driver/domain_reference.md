# Domain Reference for evo-atheris-fuzz-driver

**Responsibility**: Generate fuzz.py harness files for each library with proper instrumentation, FuzzedDataProvider usage, and exception handling tailored to each library's API.

**Key functions to implement**: generate_fuzz_driver, get_driver_template, get_exception_handlers_for_lib, create_fuzz_driver_file

---

## 1. The Atheris Library: API, Instrumentation, and Usage


Atheris is a coverage-guided Python fuzzing engine that supports the fuzzing of pure Python code as well as native CPython extensions [cite: 2, 3]. Under the hood, Atheris is a native Python extension that utilizes libFuzzer to provide code coverage tracking and mutational input generation [cite: 4].

## 6. Fuzz Driver Architectural Patterns for Specific Library Typologies


Writing effective fuzz drivers requires tailoring the harness to the specific semantics of the target library [cite: 9, 33]. Below are deep-dive strategies for various software typologies.

## 7. Handling Common Pitfalls, Expected Exceptions, and Edge Cases

