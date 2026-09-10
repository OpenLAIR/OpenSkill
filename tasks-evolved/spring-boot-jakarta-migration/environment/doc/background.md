# Comprehensive Guide for Migrating a Java Spring Boot 2.7 Microservice to Spring Boot 3.2 with Java 21

### Key Points
*   **Major Paradigm Shift**: The transition from Spring Boot 2.7 to 3.2 represents a foundational shift, largely driven by the mandatory upgrade from Java EE to Jakarta EE [cite: 1, 2].
*   **Security Architecture Overhaul**: Spring Security 6 removes legacy configuration adapters, leaning heavily toward component-based, Lambda DSL configurations [cite: 3, 4].
*   **Persistence Mechanics**: Hibernate 6, included by default, introduces stricter query parsing and alters default ID generation strategies [cite: 5, 6].
*   **Modernized HTTP Clients**: The introduction of `RestClient` provides a fluent, modern alternative to the aging `RestTemplate` [cite: 7, 8].
*   **Routing Logic Adjustments**: Trailing slash matching is disabled by default, which may necessitate updates to API routing or client calls [cite: 9, 10].

### Executive Summary
The migration of enterprise microservices from Spring Boot 2.7 (running on Java 8) to Spring Boot 3.2 (running on Java 21) is a multifaceted engineering endeavor. Evidence suggests that this upgrade is not merely a version bump but rather a comprehensive architectural alignment with modern Java standards. The migration touches almost every layer of a typical application, from the underlying build tools to the HTTP routing mechanisms. This report synthesizes best practices, architectural changes, and code-level transformations required to execute this migration successfully. It seems likely that teams will encounter the most friction in security configurations, namespace updates, and third-party library compatibility—particularly regarding JSON Web Token (JWT) implementations.

### Scope of the Migration
Migrating to Spring Boot 3.2 requires addressing deprecated APIs, updating package namespaces, and adopting new framework defaults. Research suggests that a methodical, layer-by-layer approach minimizes integration regressions [cite: 11, 12]. The Spring framework ecosystem has introduced `spring-boot-properties-migrator` to assist with property renames, while tools like OpenRewrite can automate parts of the namespace migration [cite: 13, 14]. However, complex domains like custom authentication filters, Hibernate dialects, and integration testing require explicit manual refactoring. This guide provides an exhaustive blueprint for each of these critical domains.

---

## 1. Maven POM Dependency Changes

The foundation of the migration begins in the `pom.xml`. Spring Boot 3.2 requires a minimum of Java 17, but adopting Java 21 is highly recommended to leverage advanced features like Virtual Threads (Project Loom) [cite: 15, 16]. It appears that dependency management must be updated to reflect the new baseline, alongside updates to essential third-party libraries.

### Spring Boot Dependencies and Coordinates
Spring Boot 3.2.x relies on the `spring-boot-starter-parent` to manage the versions of standard dependencies [cite: 17]. When upgrading, the parent POM version must be updated, which automatically propagates compatible versions to `spring-boot-starter-web`, `spring-boot-starter-security`, `spring-boot-starter-data-jpa`, `spring-boot-starter-validation`, and `spring-boot-starter-test`.

### Java 21 Compiler Configuration
Historically, developers used `maven.compiler.source` and `maven.compiler.target` to define the Java version. However, research suggests that for modern Java versions (Java 9 and above), using the `<maven.compiler.release>` property is the academically and technically correct approach [cite: 18]. This ensures that the compiler strictly validates against the designated Java SE release API, preventing accidental usage of newer APIs when compiling for an older target. The `maven-compiler-plugin` should be upgraded to version `3.11.0` or higher (e.g., `3.13.0` or `3.15.0`) to ensure full compatibility with Java 21 features [cite: 19, 20].

### JJWT Library Upgrade
The popular `io.jsonwebtoken` (JJWT) library must be significantly upgraded. Version `0.9.1` relies heavily on `javax.xml.bind.DatatypeConverter`, which was removed in Java 11 and completely breaks in Java 21 [cite: 21]. The migration path dictates updating to the `0.12.x` branch (e.g., `0.12.5` or `0.12.6`), which introduces a more secure, immutable API and fully supports modern Java environments [cite: 22, 23].

### Exact Before/After Code Examples

**Before (Spring Boot 2.7 / Java 8 / JJWT 0.9.1):**
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.7.18</version>
    <relativePath/>
</parent>

<properties>
    <java.version>1.8</java.version>
    <maven.compiler.source>1.8</maven.compiler.source>
    <maven.compiler.target>1.8</maven.compiler.target>
</properties>

<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <!-- Other starters omitted for brevity -->
    
    <!-- Old JJWT Dependency -->
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt</artifactId>
        <version>0.9.1</version>
    </dependency>
</dependencies>

<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <version>3.8.1</version>
        </plugin>
    </plugins>
</build>
```

**After (Spring Boot 3.2 / Java 21 / JJWT 0.12.6):**
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.5</version> <!-- or latest 3.2.x -->
    <relativePath/>
</parent>

<properties>
    <java.version>21</java.version>
    <!-- Use 'release' instead of source/target for Java 9+ -->
    <maven.compiler.release>21</maven.compiler.release>
</properties>

<dependencies>
    <!-- Standard Spring Boot Starters (Versions auto-managed by parent) -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>

    <!-- Modernized JJWT Dependencies (0.12.x) -->
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-api</artifactId>
        <version>0.12.6</version>
    </dependency>
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-impl</artifactId>
        <version>0.12.6</version>
        <scope>runtime</scope>
    </dependency>
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-jackson</artifactId>
        <version>0.12.6</version>
        <scope>runtime</scope>
    </dependency>
</dependencies>

<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <version>3.13.0</version>
            <configuration>
                <release>21</release>
                <compilerArgs>
                    <!-- Preserves parameter names for Spring MVC -->
                    <arg>-parameters</arg>
                </compilerArgs>
            </configuration>
        </plugin>
        <plugin>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-maven-plugin</artifactId>
        </plugin>
    </plugins>
</build>
```
*Note: Spring Boot 3.2 no longer attempts to deduce parameter names by parsing bytecode; therefore, adding the `-parameters` compiler argument is highly recommended to avoid property binding issues [cite: 24, 25].*

---

## 2. Javax to Jakarta Namespace Migration

A critical architectural shift in Spring Boot 3 is the migration from Java EE to Jakarta EE 10. The `javax` package namespace, originally owned by Oracle, was transitioned to the Eclipse Foundation and rebranded as `jakarta` [cite: 1, 2]. This necessitates a comprehensive import refactoring across the codebase.

### Complete List of Migrated Packages
The following enterprise specifications must be updated:
*   **JPA (Jakarta Persistence)**: `javax.persistence.*` → `jakarta.persistence.*`. This encompasses `@Entity`, `@Table`, `@Id`, `@GeneratedValue`, `@Column`, `@ManyToOne`, `@OneToMany`, `@Enumerated`, `@Transient`, etc. [cite: 1].
*   **Validation (Jakarta Bean Validation)**: `javax.validation.*` → `jakarta.validation.*`. This includes all constraints like `@Valid`, `@NotNull`, `@NotBlank`, `@Email`, `@Size`, `@Pattern` [cite: 1, 2].
*   **Servlet (Jakarta Servlet)**: `javax.servlet.*` → `jakarta.servlet.*`. This is vital for custom security filters, requiring updates to `HttpServletRequest`, `HttpServletResponse`, `FilterChain`, `Filter`, `ServletException`, etc. [cite: 1, 2].
*   **Other common namespaces**: `javax.transaction.*` → `jakarta.transaction.*`, `javax.annotation.*` → `jakarta.annotation.*` (e.g., `@PostConstruct`, `@PreDestroy`).

### Exceptions: What NOT to Migrate
It is imperative to note that not all `javax` packages are affected. Packages that are part of the standard Java Standard Edition (Java SE) rather than Java EE remain unchanged. 
*   `javax.crypto.*` (Cryptography) **DOES NOT CHANGE**.
*   `javax.sql.*` (e.g., `DataSource`) **DOES NOT CHANGE** [cite: 2].
*   `javax.net.*` (e.g., `SSLContext`) **DOES NOT CHANGE**.
*   `javax.xml.*` (Standard XML parsers) **DOES NOT CHANGE**.

### Exact Before/After Code Examples

**Before (Spring Boot 2.7 / Java 8):**
```java
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.persistence.Column;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;
import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@Entity
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(max = 50)
    @Column(nullable = false)
    private String username;
    
    // Getters and Setters
}
```

**After (Spring Boot 3.2 / Java 21):**
```java
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Column;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Entity
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(max = 50)
    @Column(nullable = false)
    private String username;
    
    // Getters and Setters
}
```

---

## 3. Spring Security 6 Migration from Spring Security 5

Spring Security 6 introduces a major paradigm shift. The framework enforces a declarative, component-based architecture and mandates the use of Lambda DSLs for configuration [cite: 3, 4]. The long-standing `WebSecurityConfigurerAdapter` has been completely removed [cite: 3, 12].

### Architectural Changes
1.  **Removal of `WebSecurityConfigurerAdapter`**: Developers must now register a `SecurityFilterChain` bean [cite: 3, 26].
2.  **`authorizeRequests` to `authorizeHttpRequests`**: The older method is deprecated and removed. The new method integrates tightly with Lambda DSLs [cite: 4, 27].
3.  **`antMatchers` to `requestMatchers`**: Path matching APIs have been consolidated [cite: 4, 27].
4.  **Lambda DSL Enforcement**: Chaining configurations via `.and()` is no longer supported. Instead, each security component is configured using functional interfaces (lambdas), which enhances modularity and readability [cite: 3, 28].

### Custom JWT `OncePerRequestFilter` Configuration
JWT authentication relies on intercepting the request via `OncePerRequestFilter`. The transition requires updating to `jakarta.servlet` and handling the authentication context properly. 

### Exact Before/After Code Examples

**Before (Spring Boot 2.7 / Spring Security 5):**
```java
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    private final JwtAuthenticationFilter jwtAuthFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthFilter) {
        this.jwtAuthFilter = jwtAuthFilter;
    }

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .csrf().disable()
            .cors().and()
            .sessionManagement().sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            .and()
            .authorizeRequests()
                .antMatchers("/api/auth/**").permitAll()
                .antMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            .and()
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);
    }
}
```

**After (Spring Boot 3.2 / Spring Security 6):**
```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthFilter) {
        this.jwtAuthFilter = jwtAuthFilter;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            // 1. Lambda DSL for CSRF and CORS
            .csrf(AbstractHttpConfigurer::disable)
            // If custom CORS is needed: .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            
            // 2. Lambda DSL for Session Management
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            
            // 3. requestMatchers instead of antMatchers, authorizeHttpRequests instead of authorizeRequests
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            
            // 4. Add custom JWT filter
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
```

**JWT Filter Migration (`OncePerRequestFilter`):**
```java
// BEFORE (Spring Boot 2.7)
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.springframework.web.filter.OncePerRequestFilter;

public class JwtAuthenticationFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, java.io.IOException {
        // Validation logic
        filterChain.doFilter(request, response);
    }
}

// AFTER (Spring Boot 3.2)
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.lang.NonNull;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.stereotype.Component;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request, 
            @NonNull HttpServletResponse response, 
            @NonNull FilterChain filterChain) throws ServletException, java.io.IOException {
        
        final String authHeader = request.getHeader("Authorization");
        // JWT validation logic utilizing jjwt 0.12.x APIs...
        
        filterChain.doFilter(request, response);
    }
}
```

---

## 4. Hibernate 6 Compatibility with Spring Boot 3.2

Spring Boot 3.2 utilizes Hibernate 6.3 (and upgrades to 6.4 in later patch versions like 3.2.5) [cite: 29, 30]. Hibernate 6 brings a major redesign focusing on SQL dialect resolution, standard alignment, and ID generation performance optimizations [cite: 5, 6].

### ID Generation Strategies
In Hibernate 5, `GenerationType.AUTO` on MySQL often resulted in the creation of a single global table named `hibernate_sequence` to simulate sequences. In Hibernate 6, `GenerationType.AUTO` now provisions a discrete sequence or table per entity hierarchy (e.g., `EntityName_SEQ`) [cite: 6, 31]. This provides superior concurrency and batching performance but represents a profound breaking change during database migrations. It seems likely that developers relying on `GenerationType.AUTO` with existing schemas will encounter "Table 'database.EntityName_SEQ' doesn't exist" errors.

**Recommendation**: Change ID strategies to explicitly match the underlying database mechanics, such as `GenerationType.IDENTITY` for MySQL/PostgreSQL serials, or `GenerationType.SEQUENCE` for databases natively supporting sequences [cite: 32].

### Database Dialects
The manual specification of SQL dialects via `spring.jpa.properties.hibernate.dialect` is overwhelmingly discouraged in Hibernate 6. The framework now dynamically resolves the optimal dialect via the JDBC metadata [cite: 33, 34]. 

Legacy versioned dialects (e.g., `org.hibernate.dialect.PostgreSQL10Dialect` or `MySQL8Dialect`) have been deprecated and removed [cite: 33, 34]. If a dialect must be overridden, you must use the unversioned base class, such as `org.hibernate.dialect.PostgreSQLDialect` or `org.hibernate.dialect.H2Dialect` [cite: 35, 36].

### @Enumerated and @Column Changes
Annotations have become stricter. Hibernate 6 natively maps specific types more efficiently, and custom `@TypeDef` definitions are removed in favor of standard JPA converters or `@JdbcTypeCode` [cite: 35].

### Exact Before/After Code Examples

**Before (Spring Boot 2.7 / Hibernate 5):**
```properties
# application.properties
spring.jpa.database-platform=org.hibernate.dialect.PostgreSQL10Dialect
```
```java
import javax.persistence.*;

@Entity
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;

    @Column(columnDefinition = "jsonb")
    private String metadata;
}
```

**After (Spring Boot 3.2 / Hibernate 6):**
```properties
# application.properties
# REMOVE spring.jpa.database-platform entirely to rely on automatic JDBC resolution.
# If strictly necessary, use the base class:
# spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.PostgreSQLDialect
```
```java
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
public class Product {
    @Id
    // Moving away from AUTO to IDENTITY ensures compatibility with existing auto-increment columns
    @GeneratedValue(strategy = GenerationType.IDENTITY) 
    private Long id;

    // Use @JdbcTypeCode instead of raw columnDefinition for better portability
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata")
    private String metadata;
}
```

---

## 5. RestTemplate to RestClient Migration

Spring Boot 3.2, building upon Spring Framework 6.1, introduces `RestClient`. It is designed as a direct, modern replacement for `RestTemplate`, providing a fluent, functional API similar to `WebClient`, but operating synchronously [cite: 7, 37]. It pairs exceptionally well with Java 21's Virtual Threads [cite: 7, 15].

### Constructing and Using RestClient
`RestClient` is located at `org.springframework.web.client.RestClient`. It is recommended to define it as a Spring Bean using the auto-configured `RestClient.Builder` [cite: 7, 38].

### Exact Before/After Code Examples

**Before (RestTemplate):**
```java
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;

@Service
public class UserService {
    private final RestTemplate restTemplate;

    public UserService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public User getUser(Long id) {
        return restTemplate.getForObject("https://api.example.com/users/" + id, User.class);
    }

    public User createUser(User user) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer token");
        HttpEntity<User> request = new HttpEntity<>(user, headers);
        
        ResponseEntity<User> response = restTemplate.exchange(
            "https://api.example.com/users", 
            HttpMethod.POST, 
            request, 
            User.class
        );
        return response.getBody();
    }
}
```

**After (RestClient):**
```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.http.HttpStatusCode;

@Configuration
public class RestClientConfig {
    @Bean
    public RestClient restClient(RestClient.Builder builder) {
        return builder
            .baseUrl("https://api.example.com")
            .defaultHeader("Accept", "application/json")
            .build();
    }
}

@Service
public class UserService {
    private final RestClient restClient;

    public UserService(RestClient restClient) {
        this.restClient = restClient;
    }

    // GET Example
    public User getUser(Long id) {
        return restClient.get()
            .uri("/users/{id}", id)
            .retrieve()
            .onStatus(HttpStatusCode::is4xxClientError, (request, response) -> {
                throw new RuntimeException("Client Error: " + response.getStatusCode());
            })
            .body(User.class);
    }

    // POST Example
    public User createUser(User user) {
        return restClient.post()
            .uri("/users")
            .header("Authorization", "Bearer token")
            .body(user)
            .retrieve()
            .body(User.class);
    }
}
```

---

## 6. application.properties / application.yml Changes

Configuration properties have been restructured between Spring Boot 2.7 and 3.2. To identify deprecated properties seamlessly, it is strongly recommended to temporarily include the `spring-boot-properties-migrator` module during the migration phase [cite: 13, 39].

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-properties-migrator</artifactId>
    <scope>runtime</scope>
</dependency>
```

### Notable Property Changes
*   **Redis**: `spring.redis.*` is migrated to `spring.data.redis.*` [cite: 13].
*   **Cassandra**: `spring.data.cassandra.*` is moved to `spring.cassandra.*` [cite: 13].
*   **Trailing Slash Matching**: The property `spring.mvc.pathmatch.matching-strategy` default has shifted due to `PathPatternParser` handling [cite: 9, 10].
*   **Hibernate DDL**: While `spring.jpa.hibernate.ddl-auto` remains consistent, implicit schema validation defaults are stricter in Hibernate 6.

---

## 7. Test Migration

JUnit 5 remains the standard testing framework. However, the migration to Spring Security 6 and Jakarta EE impacts integration testing heavily [cite: 40].

### Security Testing with MockMvc
The `SecurityMockMvcRequestPostProcessors` class resides in the `spring-security-test` library. Due to Spring Security 6 defaults, any endpoint interaction that involves state-altering HTTP methods (POST, PUT, DELETE) will face CSRF protection blocks unless properly disabled in the application logic or bypassed in the test utilizing `.with(csrf())` [cite: 41, 42].

When verifying endpoints guarded by JWT configurations, it is often more pragmatic to inject mock identities via `@WithMockUser` rather than generating signed tokens for unit tests [cite: 42, 43].

### Exact Before/After Code Examples

**Before (Spring Boot 2.7):**
```java
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserController.class)
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void testCreateUser() throws Exception {
        mockMvc.perform(post("/api/users")
                .contentType("application/json")
                .content("{\"name\":\"John\"}"))
               .andExpect(status().isOk());
    }
}
```

**After (Spring Boot 3.2):**
*Note: If Spring Security is present, a `@WebMvcTest` will intercept requests. CSRF injection is necessary if CSRF is not disabled globally.*
```java
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.security.test.context.support.WithMockUser;

// Required for CSRF and Security test utilities
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserController.class)
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @WithMockUser(username = "admin", roles = {"ADMIN"}) // Simulates JWT authentication
    void testCreateUser() throws Exception {
        mockMvc.perform(post("/api/users")
                .with(csrf()) // Injects valid CSRF token if your config demands it
                .contentType("application/json")
                .content("{\"name\":\"John\"}"))
               .andExpect(status().isOk());
    }
}
```

---

## 8. Common Pitfalls and Breaking Changes

### A. Trailing Slash Matching Configuration
One of the most disruptive changes in Spring Framework 6 (and thus Spring Boot 3) is the deprecation of transparent trailing slash matching. In previous versions using `AntPathMatcher`, a request to `/api/users/` would implicitly match the route `/api/users`. With the transition to the highly-performant `PathPatternParser` by default, this is no longer the case. A request to `/api/users/` will return a `404 Not Found` if the controller maps to `/api/users` [cite: 9, 10, 44].

**Resolution Strategy**:
Instead of re-enabling deprecated behavior, developers should explicitly declare trailing slashes in controllers if necessary, or enforce strict URL formats on the client-side:
```java
// Stop-gap fix
@GetMapping({"/users", "/users/"})
public ResponseEntity<?> getUsers() { ... }
```

### B. JJWT Library (0.9.x to 0.12.x) Migration
The migration of `io.jsonwebtoken` from `0.9.1` to `0.12.6` introduces significant API alterations [cite: 22, 45, 46]. The legacy `0.9.x` API relied on mutable parser instances and outdated JDK implementations. 

**Pitfall**: `Jwts.parser().setSigningKey(key).parseClaimsJws(token)` is heavily deprecated and will cause compilation failures.
**Migration Path**:
```java
// BEFORE (JJWT 0.9.1)
Claims claims = Jwts.parser()
    .setSigningKey(secretKey)
    .parseClaimsJws(token)
    .getBody();

// AFTER (JJWT 0.12.6)
import javax.crypto.SecretKey;
// Notice the transition to the immutable builder pattern
Claims claims = Jwts.parser()
    .verifyWith((SecretKey) secretKey) // Enforces strong cryptography keys
    .build()
    .parseSignedClaims(token)
    .getPayload();
```
*Note: Ensure the secret key utilized is cryptographically strong (e.g., HMAC-SHA256 requires at least a 256-bit key). Weak keys will throw `WeakKeyException` in JJWT 0.12.x [cite: 47].*

### C. Bean Definition Overriding
By default, Spring Boot actively prevents bean overriding to avoid unintended contextual collisions. If your application relies on overwriting definitions (often seen in legacy test environments), you must explicitly enable it:
```properties
spring.main.allow-bean-definition-overriding=true
```

### D. Java 21 Virtual Threads
To gain the monumental performance scalability benefits of Java 21, Virtual Threads must be explicitly toggled on in your configuration. Without this property, Tomcat will continue utilizing standard OS-level platform threads [cite: 7, 15].
```properties
spring.threads.virtual.enabled=true
```

## Conclusion

The jump from Spring Boot 2.7 to 3.2 is an exercise in modernization. By adhering to the `jakarta.*` namespace requirements, leveraging the Lambda DSL for Spring Security, updating database identity generation schemas to match Hibernate 6 paradigms, and harnessing the `RestClient` alongside Java 21 Virtual Threads, enterprise microservices will be positioned to operate with maximum efficiency, enhanced security, and extended support lifecycles. Ensure all dependency scopes, particularly the Maven compiler release flags and test configurations, align tightly with the new paradigms to prevent runtime regressions.

**Sources:**
1. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEfrMtLmLSO1BLcNpJQuHxaVOr4V24sHOa5vi3gzYSVaFLzycnhjrGfeMXcYZwD8TbKU_3YWK6rmaE8h-rvYEpGVIPAV5gfQ4cT-rWcTnPqW3qcnhWGL_RLFN-MkofEgvcaav8yRimMG8JK8srkGXiGRUdw_HZ6wwr9BDjhAy4z5FOGmQPrpODgRdYu)
2. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGzmGB4EJ1woZ4lwEU5JtSvlW8HwYRXcVQRMfwwK48JxmOJXjg2-tOWpc6lhEn2eghqabISTpot8RifULvxxClKdcnvzk7iv-6d84SroJXLCplf2D921Ad-BZlb8575nHUiAvnDyEJ4qX1HUugSqALSrnBX7Y7b8G9y_DbAEaChrQFdqbDSQWU1XG3weaVQTvRk1brLkbxZhHE=)
3. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH-nHZ2YW3KeUUncQun-OULpTd-Kw9bGbFFpdKz9ekHGJDO0c1Z95WYqHC4D6B1Qe8KqAdt88JFYrOkP9pxG3BSv6kWqUXMEFBwYWJBL8VoovuB149bD3LdXRxRLoSN36yraZJy0ZG5ENgm25pRw44UuO2xzlU7Zvoh1n3tks0hMS5EKcSRojKB2a-mz5S8r-_lYfdehDAyFOrWZk4fO0IyoH47C8zeJAXk)
4. [osintteam.blog](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlePUTn_6QvSjnLI5ayXXCD6lZZUeyv_NuRuCOCT7fQuHdVvDotVbyZUbUeka8XlgwflJ5y3BvYk1zsJNkzjWaLEYxtA6bV0-m1FzMOJnAjS4NZAKHim7z7vKBruS9pbGECgz5sNjMKfg-Y10LWaGLFphzGB6tLwgvGFfackw08lov6xYk)
5. [hibernate.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHONlYajmgkBe29Ci2-MhFOwE6ZLQdIuN5MS5i2blpgi3wJZ9k8XmQRshWgE1I6LDe40ad7mXlzGZ1A0x7RNyDHmuXBeHsxKCK1Y7I9wu1aR97OChUNY3qM1Ya0kj2cD2iZ7z9tygsZIxaLa2BB97QXKw==)
6. [thorben-janssen.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxBMMRSdoaqqdLyXBL2_V671dXpJA_GRPw4_jCcDqoxBjz9g-tEdxHiG8p6WEB9F3F-HcVLeEerXNmGdsy2XBYfz3z61f1YYEFVQVGWdJfTQgOwweOPg7A5qBvv38OfzLP0IkdMjiaPaBulPZK9YMuPOdDCirJjZrVt3Q=)
7. [devgenius.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGsRevEvW6vEZcA2xKOnDhnQVHOKy9ZX1AoZHEbjfgax27Li35aKcHASAwWa6uttD37Jllan4g5-oHI8NnZdL16KgRilqGSa9JMgE8veaU3V1nn0GPWLeNJ3tjGpOH2czjz4YM9LGpVLE8T_U-pjDLEpj0AaNdmYLByZZ7h_I_F8NDrms7Wyf4ewKNye5Vk7Ip8HRYBIhj_ZmXewOa3c-_ysgpqKU0O9_WvWnSs)
8. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEIA95W4Gm9CkRqW7wjKpn5Gu2wffhruNRLmIUTlweLVm154o_PtULDJlltyxTUIKaj7FAdydrPlYMkcPl0A2sjYqa0UQlQeNLjSMCAXm0uAmN03CHaSSQ56nFcBNdPo6hDu0x25sOykHmkAuR1ZWjCMyewTW0BABS8jfJuc55i0mzKYVtTEiQDeIVHOMEijuSQafTFrA==)
9. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGo8f87D3QEbtOtYQYibWP5IKWRyzXRBL3sFXc8uiSV_I9vSxmwg6i2vJvIQF1Ulw7iudc2dGg37nEnf2xwC8LKDSK106t1zf6eLY04OHI0PVQPnH7f9ALPCUTPaut1P9M3D4qQHRXjMzFVU9Pmu3Ph2ZhQsE7MUuCGttFl0nw5LyyfW3653ccFEsRfGE_2n6G74pH-Zn-HficzxIa658oljYgG-Uy8wTfQ)
10. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGAtksIehU_ekJEIAVm3tH8bvzEBDwTrJubWXterxexKE6O_BVwXyYbCOgFoJZbnRjnzsdYiBX6mj3ZH01CjmV4XvO1EeMBRiz47dMLzpIGjNr_C_ZXTxtwIe-ELUYJ3aDYD1a_wMRku_fFFWG4hlFeIWsnLncyjSjEDi1HoUwz2IOFDMkTYnzrs0Tm6LoLV4nGwGWigKwluC4=)
11. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_L4lbAE3FtNXDyZ97DBJtPceBu723hauZfZPAKOQ388sb-R_Md8mZkPz9LoL1vhImZ1kkvOS4lhx-heN2gGACDPx-F8tpPGg3LyHAZpFyl5TO8Wqj1Db4lPGQf83Ww35rnVNjkoA1-dZH5Bx3euZxNv8s3J-vDegtEEoWkfPrb5GgHDqEp7IPc6VXtjnECOOG-HYbwIK9pLaAffPFOX81CJiv0EgNpjItbG_HuXHJz4BCxTaIl48Dcyr54AhtgrxngxVZoK8=)
12. [baeldung.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUJRZfvfpGn_Fio8-Bnn7dfvmfx8DpOs-UKyz7u6Xc8tRGvPfS9gy3VDfZl3yZ_h-MFae7WQmGm9di5j-h2Ula4_YoGdkhez4C2Zp13DM8J-lvdyxUKsvPTWOLD-HHPBKaUAuRcj5uNkci5Fg=)
13. [baeldung.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEDNmV3W0MK17_VSKHnOO7INErYwOeSNBDyilZlWlV1J8fcgfIq2oGI-VTbfqgy27K90Y2jSyMq0nxL0tfvhHD4b-b077OzSrHY4qnhMREUVG3fVfgeu7POZpPYSr5gz5HnVNd90A==)
14. [moderne.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaxGYua72XMrD3FEIHsLRZFOHcjaN86ObZa9BnHSea-k9o5d_T5uzoVuaxfc5AEei3cnS-TNxYRZ7ox6UeGWWcRTqiZLsdNL7CWNiHu0ZdxQc0W0Fc7Oh50lnUQnZP1fn59lU2N6MEWLAV6nS3tfkoWygonbVJCXlUfTmOEsszn-LfDu0UgTBzgFFgdyNB)
15. [digma.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGLxryPgldLG6yPaYhfD_xzwoB0OI0oFfyZrqbqVRmRBddXMHU-SAxMWujQA_pLHLBUD-LJ86rr-5ycCCR3MSlGDddp_ii_opoguDOeUe_RJF6gz_rBOakR48ZYMx_x3gGeHHQMTA2G-Igy6WAC)
16. [bell-sw.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQXwK-XnTOheg9rFFwrwHnOUKFX6496063sPLuvZWYn91CQlHWSunAMowBzVJufl9sFvrSaYqKOcN_oUgIJXMylElPdtXWmq_xQkxZkKwrINUEbdjBul4d418JhIz4WWehWT2jQVZX_mM=)
17. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGM-m3J9rys9_EJ6LW8aCmwW60m3q3stXp3MJ6-mZeClPagholmjDiY92aRSoCb_gc8xGRJDgeMLbuwb1ko5yTPW5UVbkCfnmeEh9JMJ_46vz6ow9JahPJAmozqN9-e6rBaoKIcNGOKV6ApYi9zfB6Zm5csAkpyjZlUOu82MLT-NXDjDHanzY_R61afwDJkvvSz1S3BuPtkRKJ9HaUBCZxXrpbVp2vf9TQTwcQzoqUuEwxvgWQ=)
18. [apache.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjMP1xzKy8JnBalGcM5-6tpjcOPDZ6tg-4v1uEkxg3QYyxa80j4IiisbGhABftgu9vu7Aa6Ov-bKDPHSeZhyHHLuHJc0yXQsXY-I-CMDcGONT5momZzdmRjUuF48yZvuKKSCSNLEajt9OzQZY=)
19. [mvnrepository.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGZXU3DsXxt3l5H3AASE1t18W_YZfeXKyk7QIA7QdPomvyw3VpCXRUDXZ3ddl5NgQ9Hy1AfkMX_FSey9PwnRY07kU3QytO-RFPR_qwmyQfeYwq4U6KZDHdRwrVntoDTsmBvvMIdqQjVGBShPirXigpF8zs16OCVbBlocXKJ8al63b5pKClJ6w==)
20. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_mtWT2XuHshf6sS_5A6Y0Je62mk1cE0k1X3xADVCdDUErNrE3_O6g9JxgspYpT2MsjrAxTq2M_yQ4IwRwP47ciIcJ_3KWKcUG5PEGUXsHrZXYeAy5AOP2QnpM1BKUMhtuRdHhVigM3r5qJ3o6vvgb6j-Lr1UDFaIVx1FieMHni8Gbeg==)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGiCt2uTS1sAtxIBoBTL3-1GiRJHExVLFr4P14ATzmhDvnTW4sBsJkHwUdP9p3Hs7fHk2XniC1IXJfAtAnkxf1EJGFLKyqDxJCRhJqFq-pSf8L56dMgMO-B1FWUTg==)
22. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGvMnMzbG-TscyIeIOgKQzn-tTieifZmM5ZGbfiKrfwrJ8cilPMHUNRhL7Cgs5-vilLRtg3tbRwCyxL7zguEtAn7A9nh7yic_H9EDEKdzOQhR_sXb2zyxor4Qb9zRN6OJ7sbHkIf6_ExLMP)
23. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElx3f9BB9dZ2XcQyFC8EGCQ4CbOBzBcU9-N9SBqM8ry0IoCrebdzwygUhxUsSsH-sWbJCBhX6Bbm96EjXcqgDRAM4lVjJ6fqaMNWSjpdeA7Kx3rB52Cs53nkpPZFXgfCiagSwdnbGLX79cLnGE4V2hAIcBGoSVSatsf_84WyqKlBU2hSeENfxq977_JVftsgDi23Q6T_NtpOCGjw==)
24. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFmKU56ZL7lh-qijd92no5LhbgnZgaRTVpiwZbKRsb0Cj9QD-DSNepk_y4svMzj6Nu4Ihw_1kA60thXmIb5MP5vh0D1_CphF9hojzD0u74AAoZ9nH48GTVd1ML3fBD_24lKxdjdDrmQinTdBu6D_aWRU08fR3W-ZdBmXv2f0KXtLs8Oa4qH5A==)
25. [tistory.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjk3vt9W0pwjWsIB3n3NEcG7lO_KtCO1BV9iL7zmNgz9uJXEmln7OZTdai71g0qGwA05vCJHBLsVxeWCWhBvWtoJRLJZb_17ejdzdJsMZcDxSQUDTj)
26. [javacodegeeks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGIV6FRhE05YV-NHwBcTSrnf-EmObDnMxBUDTSrnn2hiq8tnkCQD2DiafL35BkBWj1ZslkdBgasX1T0W6XgzXQAuslB70KAKlEigY4B9aRo_7SCsD9w_x2NYcpbk3xAKDzPq09WklIilArLo97nJKusRRUVNxhPba9-rJ706K6mt3pgl5bZPkpba18M72vyobkx1MkCbDc8_nXt2rw=)
27. [danvega.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAvKsNezFpHXfLo4c0B_QpZhPKjbYZ9z0oDGmgS14QK9F9B_0q2lcKQT3GoSB15tC1636YVNI816YYrYTIJq3R-8reKqMJLH9G_p7Jmr4u7K-kshi48LdCjc0MRZP0gfj-26c=)
28. [openrewrite.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGgvF1YI8TdfU8U1nAMcCn5f22sJZIjxrhIszpfzNLdCf9uMgQXvF957ALuVkLn0rEAcumFfEf_qjY5iHH1iowhxP36KehWHYmgtV72hjaoN_gH8KrhNNovDRFHpiDRfJGFC71v_a5m5iGx9q6C2N2KmMmMLMLoSPUZNdARkUmSZ8wXITk=)
29. [infoq.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_0yHwoaScowFn_YZBr4tHQBe1adJpaCIvA3dBdFGyffTdktiM8-3oecOsbd5PGjR5o5ec9Jq-a-FqK20u-Y_URViTGLf3_fX0tan0aTg8m1SuRooZTcDkgosNUvkwma-NkCdMg5TzXBb7mWcM_C8=)
30. [herodevs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFLneSix3TilZv7PU-xeiu21huseVtS2axjo32KarHXzhlVT2qk4liP-Ku9SL_Ycie5fnCQ_U3IqBcGIi6LlWwgdDTF8FMtDJF7bbanYIS-rmnXBh9tiBOsaiEtS5b4RKFZRfjXnYZiD-vt1x3yjl4oKDYvWZ5PkKDtUyy6cTAX4AkK6VuGoYJKyaRX41SVceLoVCSBRgc=)
31. [hibernate.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH5QxBPbZBUU0SeFStcgvsnbm4mPWv4uGwM7AhsX4AgyvlyPQkxI74a1S2IR07YkIbP-dMwLKklmubQYwK5zg1l1K7Zx2BRHxfuiCIm3A-efsajUkPnJV4Ox8GrfS92ZcAQ5x2p088OqvlYQ_Y2t0pdbHmGXD051aQG)
32. [stackademic.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBTi_6H4w-RM4DNzz5zE6kWkIl0wUo77dRzjEwvBURJFL5gdANKA7yLWJOj34kIZYddL6NvxEM06i15hU7VpOP4cRYAA-osJhBDvp4h9Rt50WPrdHwuPG4j-VxOS3EOTfTnCKjyqRUd7evCudCQCddB70JcjrUPm-7kUGCC7RQH1dwfddlR-s6q2x-sHCgn4OZN8534RYo1PhtYQ==)
33. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwSn-JXp64yE2YHsv2FFw0D6zjajpdKozY83G8AyVs5tbC4H7cw5Jple8YqJ2l9VpsgXruScqowjvCtKz7m4jZ3R7cnkytzBISC2yZACZyn8T8MpUDCfvSfvy1JhJdTiotip3oRCTo_tdPJbjDgATU3171G5SW3j9gmNdqYEqsskzhr46PlEkBt7MDcjHmIV2rEWW9AtzX)
34. [hibernate.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJJMCSDkY00epUtsF7nDaCRTHkIbXkHT9Hc8nl6ENwBR-e7SF7iQegGaKI7w9E9T4fH4IZ4LEmOZcTEGpJpSPoWM7wsErkMTN2CvY67MXqFsly58nv0PldC-mM0cgIoqudqtePDSpK9MABrjmWT1nWHEnsA3zFztTEHsMlDuUvNHUwqg==)
35. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFIhi9kYgqn4QYJIzDd6fiIHI4WAI1YQcqLPcoIsRrGA3ZE4lw8k8_C74GowlhKO3nsas2_8kQOTTIYeNlCODGsy8X9llBS_8oUQuckcqnEFK7ZqwqEpxgZ9iDGvmWY3KFIt9_eDXOEa8kiag9gUx79rVnSNdWvUbfk39if_gnB4KlVEMFjEGkn3fKwikhzDIeEUqu9EujaOTYAbe72d_BHcfRKU8W2ozck9TdNRFdjtou3tjuSj2Vp5DiobEI=)
36. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3-GrLwxLZmVG9TiouxShSIC2R5Y6l7qXSNGie7hTTY_R11Iu4wBfZHB-CY659hhoQBpjW7ybdX0vVu2EjFAjTC2ecHtmHiPUTZPs_31kVDLb2WZFhMCdEC9TK-NZmhIFxpUFDyeBQ29Ekm2EBQfFDjAioeiEKaT4DALEJTYshZoEC4nXygYySBG-E-Z9HGksDpnTb_syk)
37. [dzone.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBOD87jg9DHABaIb_aBD6Ko7-oynkEzzZ5p2RFvobqy02RE-4AgMLECVpR7NBgamsUtRiezdhtoMU-QS0Ime5ec7wkC3dqEDmlL7yv-yIkvZh5T-AdW23AQGPZkANIij6vTfI3tuogyAx7LTT7UMAs1guED_IKy5XIzXR60ri1dAfn)
38. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFMo4twVYxouOvCkUXitIa8cTUyLDZraHZKWNFfDjqeEhe62-0o43uqWhV3_qFGTRw2xU2zIiKThqPd2Z87gx7uu0VPmcDwCB4k3t5IaVEIoM094-jfsq1VEwlRko_gDqJ1WM6DImJTFbbdAlGTIge6NiX7GnpmK-Yu_ZWECmPJo10eYEI)
39. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG9VzkMbYzv-ZWzfr_qjFV_RNR9s9MetR0cvAVFIKv_P0YiKMATCcngmhzfE5fRO4aeQJ68SOe371ymC7nRty9USBrfMyL0LkS8n86Klj4ufPrnBBbN7FxMCOlZ6PS-DN__iS73PKhFdlPksZEOmsKSfm7lgyJIcYcU9e5-_yoCAmh4lWnzVHg5)
40. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHW7Ibyp4l1GWaZNi38lAFkPrELRpjkoIzrjJxtuTZJOIeOq1ORSCpMd-l4KLp1hH2Cex_Y1kYQskswRDyQ0q9Gv0izDh7V3hNIc6ck_A7P46Xyt9aWtcCO51X5nziCejREXpQ4q2IdJdLjAzlYpaF0ogg2zmQjef4MfZ53pO6fGITmK1BFqmYLqETBNsfUWFHRbuCxiMaDdWLVUxwnorz29XnKbuFRsftziGU3Ig==)
41. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQnkSg2kSHzl0nugw7ZNifvEM-nJyy2x8p-2z3vMDdvoIoPInsfca6X3Kx8aZf_qrzbGJp7htIJvnjCbfA8wvGNI5lDNQAPqoPNgxKGA3lFoHjMqtfiA8arcOLOPBPlV6d8UZmDiWYfvT_Yo9Sr-ivgEPGtPyWG8Yxkoe9S_8ruW5PiLttAr38mCaMxCAHfzLYSXig)
42. [spring.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmJfQJ3gwJaIdNLUAe-NmNb0OwbmwnYuZhFBRKSkbnX_yGoW4YtbPrDBEGeAVMVV0mBXQAFHKM3MKPrHezK6vlK0o0fUSmfTkRqn0pCsW09jiE58j-qv_7jwvegz3F8iwCA5AlC-X-jMiea-Z0QkMAqcNaKezjUuNSwRdoaAdcP1jjZ0LU08Iu9hqmAHzDUk2ljutJ)
43. [diffblue.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECzQDW4jpmCQzD8b_IWW7B86w6eBh6HqwVMuGgGEi7Y-4p1ay29tPUfgmbNNZnLpQ6Kaw6l3Bd_f83Sns-iWKk9n6VKIKqpS7lDXR43pH06Q3wDzD4kuyhuRGkV1q7lUOnDEnse7PzQmkTqGFcgajF5ZScGDHHH2FfdOXFs-VpL16zenDf0MBChKjyKytAIvxUC4I=)
44. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8FmPVarAgHUwKpOKotoEq1A7qj65IjiNnC8KEVZRVlIO_5ZZxAUJwuZc1fedHPMvYR2YK-Lv8VzYPvVYOqDbUnWYDwAP-LacFXAb8DqYtpJN1XexIdN8oUlptxWDYHb7PY5FHBNseB-5KplQOOaPOqAatNfvORS95UANP8SxH1GsI247IKpJETse3d-87P4c1gC-ToERqYdJ52pE5rQ==)
45. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVzZ3QLmNgD4jFdyCDKd7vFqR62U6rTyTggZMjuVhu1FoMu6pqNjMT8-yysAw-Uo49Y5AC4EMlmfwCG0nUhsqsIPLDOYZo70iwmYb9MMzV0C-zopIzoPe0YRXQZ-nV2lLp88kdYZ2YokxAMED59vGcKTuzcmYS70doYkdsmQsOGtcH_ie60rZJUqYo6fCK26ZD2KXdg6Ai_mWVso_wOdjikD7lDg==)
46. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUaG06jN9cKY6OX2m58CJWZ7P82lliuktNG_eKrVuVnG7vIVjabmHOWAhEzOM1KlWEKCTQdUWSf9mU6T3Nz9041fSgajjEqd3pR8Xl1-mbXEf4rRDCCIZ9PBNW_oesYYwe)
47. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyA6utTnMjdVSEnkyG1kY6pVGym3L11o49tsnMKl_Ieuw2Ubzm9sos8OVTxK4g3Q1h1LGtGNKNGxhhF9vEldlVQOp_hqORbvLGtfADUDao2nm1atQM_ObjWoDJ_w==)
