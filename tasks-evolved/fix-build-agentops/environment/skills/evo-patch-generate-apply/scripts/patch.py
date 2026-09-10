import difflib
import os
import subprocess
import glob
from typing import List, Optional, Tuple


def generate_unified_diff(original_text: str, modified_text: str, file_path: str) -> str:
    a = original_text.splitlines(keepends=True)
    b = modified_text.splitlines(keepends=True)
    from_file = f"a/{file_path}"
    to_file = f"b/{file_path}"
    diff_lines = list(difflib.unified_diff(a, b, fromfile=from_file, tofile=to_file, n=3))
    if not diff_lines:
        return ""
    diff_lines = handle_no_newline_at_eof(diff_lines, a, b)
    return "".join(diff_lines)


def handle_no_newline_at_eof(diff_lines: List[str], original: List[str], modified: List[str]) -> List[str]:
    result = []
    for i, line in enumerate(diff_lines):
        result.append(line)
        if not line.endswith("\n"):
            if not line.startswith("\\\\"): 
                result[-1] = line + "\n"
                result.append("\\ No newline at end of file\n")
    if original and not original[-1].endswith("\n"):
        new_result = []
        for i, line in enumerate(result):
            new_result.append(line)
            if line.startswith("-") and not line.startswith("---"):
                stripped = line[1:]
                if original and stripped.rstrip("\n") == original[-1].rstrip("\n"):
                    if i + 1 >= len(result) or not result[i + 1].startswith("\\\\"):
                        pass
        result = new_result if new_result else result
    return result


def write_patch_file(diff_content: str, output_dir: str, index: int = 1) -> str:
    os.makedirs(output_dir, exist_ok=True)
    patch_path = os.path.join(output_dir, f"patch_{index}.diff")
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(diff_content)
    return patch_path


def apply_patch(patch_path: str, target_dir: str) -> Tuple[bool, str]:
    strategies = [
        ["git", "apply", "--whitespace=fix", patch_path],
        ["git", "apply", "--3way", "--whitespace=fix", patch_path],
        ["git", "apply", "--reject", "--whitespace=fix", patch_path],
        ["patch", "-p1", "-i", patch_path],
    ]
    for cmd in strategies:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=target_dir, timeout=30
            )
            if proc.returncode == 0:
                return True, f"Applied with: {' '.join(cmd)}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return False, "All patch strategies failed"


def validate_patch_applied(file_path: str, expected_content: str) -> bool:
    if not os.path.exists(file_path):
        return False
    with open(file_path, "r", encoding="utf-8") as f:
        actual = f.read()
    return actual == expected_content


def apply_all_patches(patch_dir: str, target_dir: str) -> List[dict]:
    results = []
    patches = sorted(glob.glob(os.path.join(patch_dir, "patch_*.diff")))
    for p in patches:
        success, msg = apply_patch(p, target_dir)
        results.append({"patch": os.path.basename(p), "success": success, "message": msg})
    return results


def create_and_apply_fix(original_text: str, modified_text: str, file_path: str,
                         repo_dir: str, output_dir: str = None, index: int = 1) -> dict:
    if output_dir is None:
        output_dir = repo_dir
    diff = generate_unified_diff(original_text, modified_text, file_path)
    if not diff:
        return {"success": False, "message": "No differences found"}
    patch_path = write_patch_file(diff, output_dir, index)
    success, msg = apply_patch(patch_path, repo_dir)
    return {"success": success, "message": msg, "patch_path": patch_path, "diff": diff}


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        patch_dir = sys.argv[1]
        target = sys.argv[2]
        results = apply_all_patches(patch_dir, target)
        for r in results:
            status = "OK" if r["success"] else "FAIL"
            print(f"[{status}] {r['patch']}: {r['message']}")
