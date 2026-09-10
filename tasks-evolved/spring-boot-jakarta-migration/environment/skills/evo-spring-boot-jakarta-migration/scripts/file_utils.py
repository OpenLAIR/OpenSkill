"""
Shared file I/O and scanning utilities for the migration skill.
"""
import os
import re
import glob


def read_file(path):
    """Read file content, returning None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def write_file(path, content):
    """Write content to a file, creating directories if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Updated: {path}")


def find_java_files(workspace):
    """Find all .java files under src/ in the workspace."""
    java_files = []
    src_dir = os.path.join(workspace, 'src')
    if os.path.exists(src_dir):
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith('.java'):
                    java_files.append(os.path.join(root, f))
    return java_files


def find_properties_files(workspace):
    """Find all .properties and .yml files under src/."""
    props = []
    src_dir = os.path.join(workspace, 'src')
    if os.path.exists(src_dir):
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith('.properties') or f.endswith('.yml') or f.endswith('.yaml'):
                    props.append(os.path.join(root, f))
    return props


def find_pom_file(workspace):
    """Locate pom.xml in the workspace root."""
    pom_path = os.path.join(workspace, 'pom.xml')
    return pom_path if os.path.exists(pom_path) else None


def backup_file(path):
    """Create a .bak backup of a file if it doesn't already exist."""
    bak = path + '.bak'
    if not os.path.exists(bak) and os.path.exists(path):
        import shutil
        shutil.copy2(path, bak)