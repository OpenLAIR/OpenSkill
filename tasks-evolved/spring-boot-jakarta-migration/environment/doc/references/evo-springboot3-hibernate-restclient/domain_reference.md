# Domain Reference for evo-springboot3-hibernate-restclient

**Responsibility**: Update JPA entity ID generation strategies for Hibernate 6, remove deprecated dialect configurations, migrate RestTemplate usage to RestClient with fluent API, update application properties, and fix test configurations for Spring Security 6 compatibility

**Key functions to implement**: migrate_id_generation_strategy, remove_deprecated_dialects, migrate_resttemplate_to_restclient, update_application_properties, fix_test_configurations

---

## 4. Hibernate 6 Compatibility with Spring Boot 3.2


Spring Boot 3.2 utilizes Hibernate 6.3 (and upgrades to 6.4 in later patch versions like 3.2.5) [cite: 29, 30]. Hibernate 6 brings a major redesign focusing on SQL dialect resolution, standard alignment, and ID generation performance optimizations [cite: 5, 6].

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



## 5. RestTemplate to RestClient Migration


Spring Boot 3.2, building upon Spring Framework 6.1, introduces `RestClient`. It is designed as a direct, modern replacement for `RestTemplate`, providing a fluent, functional API similar to `WebClient`, but operating synchronously [cite: 7, 37]. It pairs exceptionally well with Java 21's Virtual Threads [cite: 7, 15].

## 6. application.properties / application.yml Changes


Configuration properties have been restructured between Spring Boot 2.7 and 3.2. To identify deprecated properties seamlessly, it is strongly recommended to temporarily include the `spring-boot-properties-migrator` module during the migration phase [cite: 13, 39].

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-properties-migrator</artifactId>
    <scope>runtime</scope>
</dependency>
```

## 7. Test Migration


JUnit 5 remains the standard testing framework. However, the migration to Spring Security 6 and Jakarta EE impacts integration testing heavily [cite: 40].

## 8. Common Pitfalls and Breaking Changes

