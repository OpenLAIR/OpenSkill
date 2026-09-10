# Domain Reference for evo-maven-patch-generation

**Responsibility**: Generate unified diff content using difflib with proper handling of trailing newlines and 'No newline at end of file' markers, write patch files in standard diff format, and apply patches via subprocess (git apply or patch)

**Key functions to implement**: generate_unified_diff, make_strict_patch, write_patch_file, apply_patch_via_git, apply_patch_via_patch_command, modify_java_source, modify_pom_xml

---

## 4. Parsing `pom.xml` via Python's `xml.etree.ElementTree`


The Project Object Model (POM) is an XML representation of a Maven project. Python's built-in `xml.etree.ElementTree` module is exceptionally capable of querying and modifying these structures [cite: 16, 17].

## 6. Common Java and Maven Build Failure Patterns and Fixes


To achieve programmatic remediation, a mapping between parsed errors and actionable patch instructions is required. This section delineates the frequent error patterns identified in Java/Maven builds and the logical steps necessary to correct them.

## 7. Programmatic Generation and Application of Unified Diff Patches


Directly overwriting files via Python string manipulation risks corrupting code and complicating version control history. A safer, academically sound paradigm is to generate **unified diff patches** reflecting the proposed changes in memory, and then apply these patches utilizing standard OS or Git tooling [cite: 31, 32].