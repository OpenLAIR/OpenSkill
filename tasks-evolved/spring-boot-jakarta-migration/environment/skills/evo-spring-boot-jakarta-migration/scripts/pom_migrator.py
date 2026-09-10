"""
POM XML migration: Spring Boot 2.7 → 3.2, Java 8 → 21, JJWT 0.9.x → 0.12.x.

Key domain knowledge:
- Spring Boot 3.2 requires Java 17+ minimum; we target Java 21
- JJWT 0.9.1 depends on javax.xml.bind which is removed in Java 11+
- JJWT must be split into jjwt-api, jjwt-impl (runtime), jjwt-jackson (runtime)
- maven-compiler-plugin needs -parameters flag for Spring MVC parameter binding
- jaxb-api dependency must be removed (no longer needed with JJWT 0.12.x)
"""
import re
from file_utils import read_file, write_file


def migrate_pom(workspace):
    """Transform existing pom.xml for Spring Boot 3.2 / Java 21 compatibility."""
    import os
    pom_path = os.path.join(workspace, 'pom.xml')
    content = read_file(pom_path)

    if content is None:
        print("  WARNING: pom.xml not found, generating from template")
        content = _generate_pom_template()
        write_file(pom_path, content)
        return

    original = content

    # 1. Update Spring Boot parent version from 2.7.x to 3.2.0
    # Handle various 2.x version patterns
    content = re.sub(
        r'(<artifactId>spring-boot-starter-parent</artifactId>\s*<version>)2\.\d+\.\d+([^<]*)(</version>)',
        r'\g<1>3.2.0\3',
        content
    )

    # 2. Update java.version property to 21
    content = re.sub(
        r'(<java\.version>)\s*\d+\.?\d*\s*(</java\.version>)',
        r'\g<1>21\2',
        content
    )
    # Also handle 1.8 format
    content = re.sub(
        r'(<java\.version>)\s*1\.8\s*(</java\.version>)',
        r'\g<1>21\2',
        content
    )

    # 3. Update maven.compiler.source and maven.compiler.target if present
    content = re.sub(
        r'(<maven\.compiler\.source>)[^<]*(</maven\.compiler\.source>)',
        r'\g<1>21\2',
        content
    )
    content = re.sub(
        r'(<maven\.compiler\.target>)[^<]*(</maven\.compiler\.target>)',
        r'\g<1>21\2',
        content
    )

    # 4. Replace old monolithic jjwt dependency with modular 0.12.x
    # Remove old jjwt 0.9.x single artifact
    old_jjwt_pattern = re.compile(
        r'\s*<dependency>\s*'
        r'<groupId>io\.jsonwebtoken</groupId>\s*'
        r'<artifactId>jjwt</artifactId>\s*'
        r'<version>[^<]*</version>\s*'
        r'</dependency>',
        re.DOTALL
    )

    jjwt_replacement = '''
        <!-- JWT Support (modular JJWT 0.12.x for Java 21 compatibility) -->
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
        </dependency>'''

    if old_jjwt_pattern.search(content):
        content = old_jjwt_pattern.sub(jjwt_replacement, content)
    elif 'jjwt-api' not in content and 'io.jsonwebtoken' in content:
        # Edge case: some other jjwt artifact pattern
        pass
    elif 'jjwt-api' not in content:
        # No JJWT at all but might be needed — check if JWT classes exist
        pass

    # Also update any existing jjwt-api/impl/jackson to 0.12.6 if they exist at older versions
    content = re.sub(
        r'(<artifactId>jjwt-(?:api|impl|jackson)</artifactId>\s*<version>)0\.1[01]\.[^<]*(</version>)',
        r'\g<1>0.12.6\2',
        content
    )
    content = re.sub(
        r'(<artifactId>jjwt-(?:api|impl|jackson)</artifactId>\s*<version>)0\.12\.[0-5](</version>)',
        r'\g<1>0.12.6\2',
        content
    )

    # 5. Remove jaxb-api dependency (not needed with JJWT 0.12.x on Java 21)
    content = re.sub(
        r'\s*<dependency>\s*'
        r'<groupId>javax\.xml\.bind</groupId>\s*'
        r'<artifactId>jaxb-api</artifactId>\s*'
        r'(?:<version>[^<]*</version>\s*)?'
        r'</dependency>',
        '',
        content,
        flags=re.DOTALL
    )

    # 6. Update maven-compiler-plugin version and add -parameters flag
    # First check if maven-compiler-plugin exists
    if 'maven-compiler-plugin' in content:
        # Update version
        content = re.sub(
            r'(<artifactId>maven-compiler-plugin</artifactId>\s*<version>)[^<]*(</version>)',
            r'\g<1>3.13.0\2',
            content
        )
        # Add configuration with -parameters if not present
        if '-parameters' not in content:
            content = re.sub(
                r'(<artifactId>maven-compiler-plugin</artifactId>\s*<version>[^<]*</version>)\s*(</plugin>)',
                r'''\1
                <configuration>
                    <release>21</release>
                    <compilerArgs>
                        <arg>-parameters</arg>
                    </compilerArgs>
                </configuration>
            \2''',
                content
            )

    # 7. Ensure spring-security-test is present for test migration
    if 'spring-security-test' not in content:
        # Insert before </dependencies>
        security_test_dep = '''
        <dependency>
            <groupId>org.springframework.security</groupId>
            <artifactId>spring-security-test</artifactId>
            <scope>test</scope>
        </dependency>'''
        content = content.replace('</dependencies>', security_test_dep + '\n    </dependencies>', 1)

    if content != original:
        write_file(pom_path, content)
    else:
        print("  pom.xml: no changes needed")


def _generate_pom_template():
    """Fallback: generate a complete Spring Boot 3.2 pom.xml from scratch."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>userservice</artifactId>
    <version>1.0.0</version>
    <name>User Service</name>
    <description>User Management Microservice</description>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
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
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>
        <!-- JWT Support (modular JJWT 0.12.x for Java 21 compatibility) -->
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
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.security</groupId>
            <artifactId>spring-security-test</artifactId>
            <scope>test</scope>
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
</project>
'''