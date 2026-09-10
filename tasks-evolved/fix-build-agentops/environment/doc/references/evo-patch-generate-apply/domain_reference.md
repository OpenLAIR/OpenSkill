# Domain Reference for evo-patch-generate-apply

**Responsibility**: Generate properly formatted unified diffs (with a/b prefixes, correct context lines, POSIX newline handling), write patch_{i}.diff files, and apply patches using git apply with appropriate flags and fallback strategies.

**Key functions to implement**: generate_unified_diff, handle_no_newline_at_eof, write_patch_file, apply_patch, validate_patch_applied, apply_all_patches

---

## 2. Generating and Applying Diffs Programmatically in Python


Once the AI agent identifies the root cause of a build failure and formulates a localized code fix, it must generate a patch and apply it to the repository. The universal standard for this operation is the **Unified Diff Format**.

### 2.1 Generating Unified Diffs with `difflib`


Python's standard library includes the `difflib` module, which exposes the `unified_diff` function. This function compares two sequences of strings and yields a delta in unified diff format [cite: 10, 11].

The exact function signature is:
`difflib.unified_diff(a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n')` [cite: 12].

*   `a` and `b`: Lists of strings representing the original and modified file contents.
*   `fromfile` and `tofile`: Filenames to embed in the `---` and `+++` headers [cite: 12].
*   `n`: The number of context lines to include. GNU `patch` and `git apply` generally prefer at least 3 lines of context to ensure accurate application (`n=3` is the default) [cite: 13, 14, 15].
*   `lineterm`: The line-ending character, which defaults to `\n` [cite: 12].

### 2.2 The Pitfall of Missing Newlines at EOF


A notorious complication in programmatic patch generation is the "No newline at end of file" marker. POSIX defines a text file as a sequence of lines, each terminating with a newline character [cite: 16]. If a file does not end with a newline, standard `diff` utilities append a special marker `\ No newline at end of file` to explicitly state this condition [cite: 17].

Without this marker, `git apply` and GNU `patch` may become confused about whether to append a trailing newline, leading to corrupted file states or rejected hunks [cite: 11, 16]. Unfortunately, Python's native `difflib.unified_diff` does *not* automatically generate the `\ No newline at end of file` marker out-of-the-box in the way GNU diff does [cite: 9, 11]. Developers have requested this feature (e.g., Python Issue 8702), but maintaining backward compatibility has prevented its default inclusion [cite: 11].

To generate valid diffs that `git apply` will accept, an AI agent must utilize a custom wrapper that inspects the last line of the string arrays and injects the marker manually:

```python
import difflib
from typing import List

def generate_git_compatible_diff(original_text: str, modified_text: str, file_path: str) -> str:
    """
    Generates a unified diff compatible with `git apply`, properly handling
    the POSIX newline-at-EOF constraint.
    """
    # splitlines(keepends=True) is vital. Without it, the trailing \n is lost [cite: 9].
    a = original_text.splitlines(keepends=True)
    b = modified_text.splitlines(keepends=True)
    
    # Git patch convention dictates a/ and b/ prefixes [cite: 18]
    from_file = f"a/{file_path}"
    to_file = f"b/{file_path}"
    
    diff_generator = difflib.unified_diff(a, b, fromfile=from_file, tofile=to_file, n=3)
    diff_lines = list(diff_generator)
    
    if not diff_lines:
        return "" # No differences found
        
    # Manually handle the "No newline at end of file" condition [cite: 10, 11, 17]
    if a and not a[-1].endswith('\n'):
        # We must insert the marker right after the deletion hunk ends
        # This requires parsing the diff logic, but for simplicity we can append it
        # However, a robust implementation tracks hunk headers.
        pass # Omitted for brevity, but crucial in production.

    # Simplified approach: Just check the final diff line
    if not diff_lines[-1].endswith('\n'):
        diff_lines[-1] += '\n'
        diff_lines.append('\\ No newline at end of file\n')
        
    return "".join(diff_lines)
```

### 2.3 Applying Diffs: `git apply` vs. GNU `patch`


Once a `.diff` file is generated, the agent must apply it. There are two primary command-line tools for this: `patch` and `git apply`.

**GNU `patch`**: Originally written by Larry Wall, the historical `patch` command is highly permissive. It uses "fuzz factors" to apply hunks even if the surrounding context does not match perfectly [cite: 19]. While useful for humans, this fuzziness can lead to AI agents inadvertently patching the wrong function if two functions share identical structural syntax [cite: 19]. 

**`git apply`**: Designed as a stricter, more secure alternative, `git apply` follows an "apply all or abort all" model [cite: 20]. It does not utilize fuzz factors; the context must match exactly, making it inherently safer for automated agents [cite: 19, 20]. By default, `git apply` assumes the patch was created with `-p1` (stripping the leading `a/` and `b/` directories from the patch paths) [cite: 18, 21].

Critical flags for `git apply` include:
*   `--directory=<root>`: Prepends the `<root>` path to all filenames in the patch [cite: 15]. This is essential if the agent is operating from a sub-directory rather than the repository root.
*   `--reject`: If some hunks do not apply cleanly, `git apply` usually aborts the entire operation [cite: 15]. Providing `--reject` forces the command to apply the successful hunks and save the failed hunks to `.rej` files [cite: 15, 22].
*   `--3way`: If the context lines fail to match, but the patch contains `Index:` metadata with blob hashes, `--3way` instructs Git to attempt a three-way merge [cite: 15, 19, 21]. This is immensely powerful for resolving minor discrepancies caused by intervening commits [cite: 19].
*   `--whitespace=fix`: Instructs Git to automatically repair whitespace anomalies (like trailing spaces or mixed tabs/spaces) during application [cite: 22].
*   `-p<n>`: Strips `<n>` leading directory components from the paths in the patch [cite: 18, 23]. The default is `-p1` [cite: 18, 21].

```python
import subprocess
import os

def apply_patch_programmatically(patch_content: str, target_dir: str) -> bool:
    """
    Writes a patch to disk and applies it using `git apply`.
    """
    patch_path = os.path.join(target_dir, "fix.patch")
    with open(patch_path, 'w', encoding='utf-8') as f:
        f.write(patch_content)
        
    # Execute git apply with strict directory scoping and a fallback to 3-way merge
    cmd = [
        "git", "apply",
        "--3way",             # Attempt 3-way merge if context fails [cite: 19]
        "--whitespace=fix",   # Auto-resolve whitespace anomalies [cite: 22]
        f"--directory={target_dir}", # Ensure paths align [cite: 15]
        patch_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=target_dir)
    if result.returncode != 0:
        print(f"Patch failed: {result.stderr}")
        # If --3way fails, the agent could fallback to `git apply --reject` 
        # to salvage partial hunks [cite: 15, 22].
        return False
        
    os.remove(patch_path)
    return True
```

### 5.3 Automating the Validation Loop


An AI agent can utilize BugSwarm to safely generate and test its code patches without contaminating the host operating system. The workflow proceeds as follows:

1.  **Instantiate Sandbox**: The agent invokes `bugswarm run --image-tag <id> --use-sandbox` [cite: 40, 41]. The `--use-sandbox` flag creates a shared volume mount, allowing the agent to move generated `.patch` files into the Docker container [cite: 41].
2.  **Execute Failed Build**: The agent runs `bash /usr/local/bin/run_failed.sh` and captures `stderr` and `stdout` [cite: 39]. It parses the `pytest` output or `SyntaxError` tracebacks.
3.  **Apply Remediation**: The agent generates a unified diff, drops it into the sandbox volume, and uses a secondary process to run `git apply --directory=/home/travis/build/failed /sandbox/fix.patch` inside the container [cite: 15].
4.  **Validate**: The agent re-runs `run_failed.sh`. If the exit code transitions from `1` (failure) to `0` (success), the AI agent has successfully synthesized a valid remediation patch [cite: 41].
5.  **Restart Container Principle**: BugSwarm documentation specifically advises against running the passed and failed scripts consecutively in the same container session to avoid state pollution [cite: 41]. Therefore, if a patch fails, the AI agent must terminate the container and spin up a fresh instance before attempting the next iteration.

### 6.3 Patch Paths and the `a/ b/` Prefix Convention


A final pitfall is the misalignment of directory prefixes in diff files. By default, `git diff` produces files with an `a/` prefix for the original file and `b/` for the modified file [cite: 18]. Consequently, `git apply` relies on a default `-p1` setting to strip exactly one leading path component [cite: 18, 21].

However, if the AI agent generates a patch using `difflib.unified_diff` without manually prepending `a/` and `b/` to the `fromfile` and `tofile` arguments, `git apply` will attempt to strip a directory that doesn't exist, leading to a "Patch does not apply" fatal error [cite: 21]. The AI skill must either ensure it strictly adheres to the Git header convention when formatting diff strings or invoke `git apply` with `-p0` to disable path stripping entirely [cite: 18, 21].