# Domain Reference for evo-springboot3-pom-namespace

**Responsibility**: Update pom.xml for Spring Boot 3.2, Java 21, maven-compiler-plugin, JJWT 0.12.x split artifacts, and perform global javax.persistence/javax.validation/javax.servlet to jakarta.* import replacements in all .java files while preserving javax.crypto and other Java SE packages

**Key functions to implement**: upgrade_pom_xml, migrate_javax_to_jakarta_imports, update_jjwt_dependencies, update_compiler_settings

---

## 1. Maven POM Dependency Changes


The foundation of the migration begins in the `pom.xml`. Spring Boot 3.2 requires a minimum of Java 17, but adopting Java 21 is highly recommended to leverage advanced features like Virtual Threads (Project Loom) [cite: 15, 16]. It appears that dependency management must be updated to reflect the new baseline, alongside updates to essential third-party libraries.

## 2. Javax to Jakarta Namespace Migration


A critical architectural shift in Spring Boot 3 is the migration from Java EE to Jakarta EE 10. The `javax` package namespace, originally owned by Oracle, was transitioned to the Eclipse Foundation and rebranded as `jakarta` [cite: 1, 2]. This necessitates a comprehensive import refactoring across the codebase.