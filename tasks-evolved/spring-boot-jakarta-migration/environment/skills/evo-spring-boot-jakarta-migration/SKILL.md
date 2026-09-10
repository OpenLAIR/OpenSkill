---
name: evo-spring-boot-jakarta-migration
description: Migrate a Java 8/Spring Boot 2.7 project to Java 21/Spring Boot 3.2 with comprehensive handling of namespace changes, security config, Hibernate 6, JJWT 0.12.x, and RestClient migration.
---

# Spring Boot 2.7 → 3.2 Jakarta Migration Skill

## Purpose
Migrate a Java 8/Spring Boot 2.7 user management microservice to Java 21/Spring Boot 3.2, covering all layers of the application stack.

## Key Migration Areas
1. **pom.xml**: Update parent to 3.2.x, java.version to 21, maven-compiler-plugin with `-parameters`, replace jjwt 0.9.x with modular 0.12.x, remove jaxb-api
2. **Jakarta namespace**: Replace javax.persistence → jakarta.persistence, javax.validation → jakarta.validation, javax.servlet → jakarta.servlet. **Preserve** javax.crypto, javax.sql, javax.net (Java SE packages)
3. **Spring Security 6**: Remove WebSecurityConfigurerAdapter, use SecurityFilterChain bean, Lambda DSL, authorizeHttpRequests + requestMatchers, @EnableMethodSecurity
4. **JJWT 0.12.x API**: Migrate from `Jwts.parser().setSigningKey()` to `Jwts.parser().verifyWith().build().parseSignedClaims()`, from `Jwts.builder().signWith(SignatureAlgorithm.HS512, key)` to `Jwts.builder().signWith(key)`
5. **Hibernate 6**: Remove versioned dialect references, use GenerationType.IDENTITY explicitly, update H2Dialect to unversioned form
6. **RestTemplate → RestClient**: Migrate to fluent RestClient API
7. **Application properties**: Update hibernate dialect class names, remove deprecated properties

## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-spring-boot-jakarta-migration/scripts')
from migrate import run_migration
run_migration('/workspace')
```

## Scripts
- `scripts/migrate.py` — Main entry point orchestrating all migration steps
- `scripts/pom_migrator.py` — POM XML transformation (parent, java version, dependencies)
- `scripts/namespace_migrator.py` — javax → jakarta import replacement across all .java files
- `scripts/security_migrator.py` — Spring Security 6 config and JWT filter migration
- `scripts/jwt_migrator.py` — JJWT 0.9.x → 0.12.x API call migration
- `scripts/hibernate_migrator.py` — Hibernate 6 compatibility (dialects, ID generation)
- `scripts/restclient_migrator.py` — RestTemplate → RestClient migration
- `scripts/properties_migrator.py` — application.properties updates
- `scripts/file_utils.py` — Shared file I/O and scanning utilities

## Domain Knowledge References
- javax.crypto.* is Java SE, NOT Jakarta EE — never migrate these imports
- JJWT 0.12.x uses immutable builder: `Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload()`
- Spring Security 6: `.and()` chaining removed, use Lambda DSL exclusively
- Hibernate 6: `GenerationType.AUTO` creates per-entity sequences — use IDENTITY for MySQL/H2
- Spring Boot 3.2: trailing slash matching disabled by default
- `-parameters` compiler arg required for Spring MVC parameter name resolution