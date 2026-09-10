"""
javax → jakarta namespace migration across all Java source files.

Critical domain knowledge:
- ONLY migrate Java EE (Jakarta EE) packages, NOT Java SE packages
- javax.persistence.* → jakarta.persistence.*
- javax.validation.* → jakarta.validation.*
- javax.servlet.* → jakarta.servlet.*
- javax.transaction.* → jakarta.transaction.*
- javax.annotation.PostConstruct/PreDestroy → jakarta.annotation.*
- javax.inject.* → jakarta.inject.*
- javax.ws.rs.* → jakarta.ws.rs.*

DO NOT MIGRATE (Java SE packages):
- javax.crypto.* — cryptography (used in JWT signing)
- javax.sql.* — DataSource etc.
- javax.net.* — SSL etc.
- javax.xml.* — standard XML parsers (but javax.xml.bind IS Jakarta)
- javax.security.auth.* — JAAS (Java SE)
- javax.naming.* — JNDI (Java SE)
"""
import re
from file_utils import find_java_files, read_file, write_file

# Packages that MUST be migrated (Java EE → Jakarta EE)
JAKARTA_MIGRATION_PREFIXES = [
    'javax.persistence',
    'javax.validation',
    'javax.servlet',
    'javax.transaction',
    'javax.annotation',
    'javax.inject',
    'javax.ws.rs',
    'javax.enterprise',
    'javax.faces',
    'javax.json',
    'javax.jms',
    'javax.mail',
    'javax.resource',
    'javax.security.enterprise',
    'javax.websocket',
    'javax.xml.bind',       # JAXB is Jakarta EE
    'javax.xml.ws',         # JAX-WS is Jakarta EE
    'javax.activation',
    'javax.batch',
    'javax.decorator',
    'javax.ejb',
    'javax.el',
    'javax.interceptor',
]

# Packages that must NOT be migrated (Java SE)
JAVA_SE_PREFIXES = [
    'javax.crypto',
    'javax.sql',
    'javax.net',
    'javax.xml.parsers',
    'javax.xml.transform',
    'javax.xml.stream',
    'javax.xml.validation',
    'javax.xml.xpath',
    'javax.xml.namespace',
    'javax.xml.datatype',
    'javax.security.auth',
    'javax.naming',
    'javax.management',
    'javax.imageio',
    'javax.sound',
    'javax.swing',
    'javax.tools',
    'javax.lang',
]


def _should_migrate_import(import_line):
    """
    Determine if a javax import line should be migrated to jakarta.
    Returns True only for Java EE packages, False for Java SE packages.
    """
    # Extract the package from the import statement
    match = re.search(r'import\s+(static\s+)?javax\.(\S+)', import_line)
    if not match:
        return False

    full_package = 'javax.' + match.group(2).rstrip(';')

    # Check if it's explicitly a Java SE package (do NOT migrate)
    for prefix in JAVA_SE_PREFIXES:
        if full_package.startswith(prefix):
            return False

    # Check if it matches a known Jakarta EE package (DO migrate)
    for prefix in JAKARTA_MIGRATION_PREFIXES:
        if full_package.startswith(prefix):
            return True

    # For any other javax.* package not in either list, be conservative
    # and don't migrate (safer default)
    return False


def migrate_javax_to_jakarta(workspace):
    """
    Replace javax.* → jakarta.* imports in all Java files,
    preserving Java SE javax packages (crypto, sql, net, etc.).
    """
    java_files = find_java_files(workspace)
    migrated_count = 0

    for fpath in java_files:
        content = read_file(fpath)
        if content is None:
            continue

        original = content

        # Process line by line for import statements
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if re.match(r'\s*import\s+(static\s+)?javax\.', line):
                if _should_migrate_import(line):
                    line = line.replace('javax.', 'jakarta.', 1)
            new_lines.append(line)

        content = '\n'.join(new_lines)

        # Also handle fully-qualified references in code (not just imports)
        # e.g., javax.persistence.EntityNotFoundException used inline
        for prefix in JAKARTA_MIGRATION_PREFIXES:
            jakarta_prefix = prefix.replace('javax.', 'jakarta.', 1)
            # Use word boundary to avoid partial matches
            # Match javax.persistence but not javax.crypto
            content = re.sub(
                r'(?<![a-zA-Z])' + re.escape(prefix) + r'(?=\.|\s|;)',
                jakarta_prefix,
                content
            )

        if content != original:
            write_file(fpath, content)
            migrated_count += 1

    print(f"  Migrated javax→jakarta in {migrated_count} file(s)")
    return migrated_count