# Skill Creation Plan

**Task**: Migrate a Java 8/Spring Boot 2.7 user management microservice to Java 21/Spring Boot 3.2, updating all dependencies, namespaces, security config, Hibernate compatibility, and RestTemplate to RestClient

**Rationale**: The migration has three distinct concern areas: (1) build configuration and namespace changes that form the foundation, (2) security and JWT library migration which is a self-contained domain, and (3) Hibernate/JPA and RestClient changes plus remaining fixes. This decomposition follows dependency order and separates the most complex domains.

**Number of skills**: 3

---

## Skill 1: evo-springboot3-pom-namespace

**Description**: Handles Maven POM upgrades (Spring Boot parent, Java version, compiler plugin, JJWT library split) and the comprehensive javax-to-jakarta namespace migration across all Java source files. This is the foundational skill that must be applied first.

**Responsibility**: Update pom.xml for Spring Boot 3.2, Java 21, maven-compiler-plugin, JJWT 0.12.x split artifacts, and perform global javax.persistence/javax.validation/javax.servlet to jakarta.* import replacements in all .java files while preserving javax.crypto and other Java SE packages

**Key functions**: `upgrade_pom_xml`, `migrate_javax_to_jakarta_imports`, `update_jjwt_dependencies`, `update_compiler_settings`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-springboot3-pom-namespace/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-springboot3-security-jwt

**Description**: Migrates Spring Security configuration from WebSecurityConfigurerAdapter to SecurityFilterChain bean with Lambda DSL, updates antMatchers to requestMatchers, authorizeRequests to authorizeHttpRequests, and migrates JJWT API calls from 0.9.x to 0.12.x pattern (parser/builder/verifyWith/parseSignedClaims).

**Responsibility**: Refactor SecurityConfig class to remove WebSecurityConfigurerAdapter, adopt Lambda DSL, update path matchers, and rewrite JWT token generation/parsing code to use JJWT 0.12.x immutable builder API

**Key functions**: `migrate_security_config`, `migrate_jwt_filter`, `migrate_jjwt_api_calls`, `update_password_encoder_config`

**Depends on**: evo-springboot3-pom-namespace


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-springboot3-security-jwt/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-springboot3-hibernate-restclient

**Description**: Handles Hibernate 6 compatibility changes (ID generation strategy, dialect removal), RestTemplate to RestClient migration, application.properties updates, trailing slash handling, and test migration adjustments.

**Responsibility**: Update JPA entity ID generation strategies for Hibernate 6, remove deprecated dialect configurations, migrate RestTemplate usage to RestClient with fluent API, update application properties, and fix test configurations for Spring Security 6 compatibility

**Key functions**: `migrate_id_generation_strategy`, `remove_deprecated_dialects`, `migrate_resttemplate_to_restclient`, `update_application_properties`, `fix_test_configurations`

**Depends on**: evo-springboot3-pom-namespace


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-springboot3-hibernate-restclient/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
