# Domain Reference for evo-maven-build-diagnosis

**Responsibility**: Run Maven builds via subprocess, parse stdout/stderr for error patterns using regex, classify errors (compilation, dependency, POM, version), extract file paths/line numbers/error messages, and write diagnostic analysis to failed_reasons.txt

**Key functions to implement**: execute_maven_build, parse_compilation_errors, parse_dependency_errors, parse_plugin_errors, parse_version_incompatibilities, detect_java_version_from_pom, classify_build_failure, write_diagnosis_report

---

## 2. Python Subprocess Execution Patterns for Maven Builds


The foundation of analyzing Maven builds programmatically is executing them deterministically. The Python `subprocess` module is the recommended interface for spawning new processes, connecting to their input/output/error pipes, and obtaining their return codes [cite: 1].

## 3. Java and JDK Version Management in CI Environments


Maven projects are often highly sensitive to the JDK version executing the build. An automated remediation tool must be capable of diagnosing version incompatibilities and switching the JDK context on the fly.

## 4. Parsing `pom.xml` via Python's `xml.etree.ElementTree`


The Project Object Model (POM) is an XML representation of a Maven project. Python's built-in `xml.etree.ElementTree` module is exceptionally capable of querying and modifying these structures [cite: 16, 17].

## 5. Maven Build Error Parsing and Information Extraction


Once a build terminates with a non-zero exit status, the Python utility must parse the consolidated standard output log. Maven logs, particularly when output in batch mode, follow semi-structured textual patterns that are highly amenable to Regular Expression (Regex) extraction [cite: 19, 20]. Using Python's `re` module, exceptions like `re.error` should be handled correctly, utilizing raw strings (`r'...'`) to prevent escape sequence conflicts [cite: 21].

## 6. Common Java and Maven Build Failure Patterns and Fixes


To achieve programmatic remediation, a mapping between parsed errors and actionable patch instructions is required. This section delineates the frequent error patterns identified in Java/Maven builds and the logical steps necessary to correct them.

## 8. Edge Cases, Pitfalls, and Complex Project Topologies


Architecting a Python diagnosis engine requires anticipating the eccentricities of the Java ecosystem.