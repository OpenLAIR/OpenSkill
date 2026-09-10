# Domain Reference for evo-springboot3-security-jwt

**Responsibility**: Refactor SecurityConfig class to remove WebSecurityConfigurerAdapter, adopt Lambda DSL, update path matchers, and rewrite JWT token generation/parsing code to use JJWT 0.12.x immutable builder API

**Key functions to implement**: migrate_security_config, migrate_jwt_filter, migrate_jjwt_api_calls, update_password_encoder_config

---

## 3. Spring Security 6 Migration from Spring Security 5


Spring Security 6 introduces a major paradigm shift. The framework enforces a declarative, component-based architecture and mandates the use of Lambda DSLs for configuration [cite: 3, 4]. The long-standing `WebSecurityConfigurerAdapter` has been completely removed [cite: 3, 12].

## 8. Common Pitfalls and Breaking Changes

