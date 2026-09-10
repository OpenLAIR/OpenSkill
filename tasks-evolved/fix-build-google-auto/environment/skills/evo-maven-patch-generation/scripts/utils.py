import difflib
import os
import subprocess
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_unified_diff(original_text, modified_text, file_path):
    """Generate a unified diff between two text states of a file."""
    original_lines = original_text.splitlines(keepends=True)
    modified_lines = modified_text.splitlines(keepends=True)
    
    diff_generator = difflib.unified_diff(
        original_lines, modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=3
    )
    diff_lines = list(diff_generator)
    if not diff_lines:
        return ""
    return "".join(diff_lines)


def make_strict_patch(original_text, modified_text, file_path):
    """Generate a unified diff with proper 'No newline at end of file' markers."""
    original_lines = original_text.splitlines(keepends=True)
    modified_lines = modified_text.splitlines(keepends=True)
    
    diff_generator = difflib.unified_diff(
        original_lines, modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=3
    )
    
    NO_EOL_MARKER = "\\ No newline at end of file\n"
    strict_diff = []
    
    for line in diff_generator:
        strict_diff.append(line)
        if not line.endswith('\n'):
            strict_diff.append('\n' + NO_EOL_MARKER)
    
    return "".join(strict_diff)


def write_patch_file(patch_content, patch_path):
    """Write patch content to a file."""
    with open(patch_path, 'w', encoding='utf-8') as f:
        f.write(patch_content)
    logger.info(f"Patch written to {patch_path}")


def apply_patch_via_git(patch_path, project_dir):
    """Apply a patch using git apply."""
    try:
        result = subprocess.run(
            ['git', 'apply', patch_path],
            cwd=project_dir,
            capture_output=True, text=True, check=True
        )
        logger.info(f"Patch {patch_path} applied successfully via git apply")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"git apply failed: {e.stderr}")
        return False


def apply_patch_via_patch_command(patch_path, project_dir, strip=1):
    """Apply a patch using the patch command."""
    try:
        result = subprocess.run(
            ['patch', f'-p{strip}', '-i', patch_path],
            cwd=project_dir,
            capture_output=True, text=True, check=True
        )
        logger.info(f"Patch {patch_path} applied successfully via patch command")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"patch command failed: {e.stderr}")
        return False


def apply_patch(patch_path, project_dir):
    """Try git apply first, fall back to patch command."""
    if apply_patch_via_git(patch_path, project_dir):
        return True
    logger.info("Falling back to patch command...")
    return apply_patch_via_patch_command(patch_path, project_dir)


def modify_file_content(file_path, old_text, new_text):
    """Read a file, replace old_text with new_text, return (original, modified)."""
    with open(file_path, 'r', encoding='utf-8') as f:
        original = f.read()
    modified = original.replace(old_text, new_text)
    return original, modified


def modify_java_source(file_path, modifications):
    """Apply modifications to a Java source file.
    modifications is a list of (old_text, new_text) tuples.
    Returns (original_content, modified_content)."""
    with open(file_path, 'r', encoding='utf-8') as f:
        original = f.read()
    modified = original
    for old_text, new_text in modifications:
        modified = modified.replace(old_text, new_text)
    return original, modified


def modify_pom_xml(pom_path, property_changes=None, remove_dependencies=None):
    """Modify a pom.xml file.
    property_changes: dict of {property_name: new_value}
    remove_dependencies: list of (groupId, artifactId) tuples to remove
    Returns (original_content, modified_content)."""
    with open(pom_path, 'r', encoding='utf-8') as f:
        original = f.read()
    
    modified = original
    
    if property_changes:
        for prop_name, new_value in property_changes.items():
            # Match XML property tags
            pattern = re.compile(
                f'(<{re.escape(prop_name)}>)([^<]*)()',
                re.DOTALL
            )
            modified = pattern.sub(f'\\g<1>{new_value}\\g<3>', modified)
    
    return original, modified


def create_travis_fix_patch(travis_path, old_text, new_text, patch_path):
    """Create a patch to fix .travis.yml."""
    original, modified = modify_file_content(travis_path, old_text, new_text)
    if original == modified:
        logger.warning(f"No changes made to {travis_path}")
        return None
    
    rel_path = os.path.basename(travis_path)
    patch = make_strict_patch(original, modified, rel_path)
    write_patch_file(patch, patch_path)
    return patch
