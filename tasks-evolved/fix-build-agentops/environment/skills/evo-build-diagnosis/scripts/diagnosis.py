import ast
import os
import sys
import glob
import subprocess
import importlib.util
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple


def find_repo_path(base_dirs: List[str] = None) -> Optional[str]:
    if base_dirs is None:
        base_dirs = [
            "/home/github/build/failed",
            "/home/travis/build/failed",
            "/home/travis/build",
            "/workspace",
            ".",
        ]
    for base in base_dirs:
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            if any(f in files for f in ["pyproject.toml", "setup.py", "setup.cfg"]):
                return root
            if ".git" in dirs:
                return root
    return None


def parse_syntax_errors(repo_path: str) -> List[Dict]:
    errors = []
    for py_file in glob.glob(os.path.join(repo_path, "**/*.py"), recursive=True):
        try:
            with open(py_file, "rb") as f:
                source = f.read()
            compile(source, py_file, "exec")
        except SyntaxError as e:
            errors.append({
                "type": "SyntaxError",
                "file": e.filename or py_file,
                "line": e.lineno,
                "offset": e.offset,
                "end_line": getattr(e, "end_lineno", None),
                "end_offset": getattr(e, "end_offset", None),
                "message": e.msg,
                "text": (e.text.strip() if e.text else ""),
            })
        except Exception:
            pass
    return errors


def check_import_availability(dependencies: List[str]) -> List[Dict]:
    results = []
    for dep in dependencies:
        mod_name = dep.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
        mod_name = mod_name.replace("-", "_")
        try:
            spec = importlib.util.find_spec(mod_name)
            available = spec is not None
        except (ModuleNotFoundError, ValueError):
            available = False
        results.append({"dependency": dep, "module": mod_name, "available": available})
    return results


def analyze_build_config(repo_path: str) -> Dict:
    config = {"backend": None, "build_requires": [], "dependencies": [], "errors": []}
    toml_path = os.path.join(repo_path, "pyproject.toml")
    if os.path.exists(toml_path):
        try:
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                try:
                    import tomli as tomllib
                except ImportError:
                    import tomllib
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            bs = data.get("build-system", {})
            config["backend"] = bs.get("build-backend", "unknown")
            config["build_requires"] = bs.get("requires", [])
            proj = data.get("project", {})
            config["dependencies"] = proj.get("dependencies", [])
        except Exception as e:
            config["errors"].append(f"pyproject.toml parse error: {e}")
    setup_py = os.path.join(repo_path, "setup.py")
    if os.path.exists(setup_py):
        config["has_setup_py"] = True
    setup_cfg = os.path.join(repo_path, "setup.cfg")
    if os.path.exists(setup_cfg):
        config["has_setup_cfg"] = True
    return config


def run_build_and_capture_errors(repo_path: str) -> Dict:
    result = {"exit_code": None, "stdout": "", "stderr": "", "errors": []}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "--no-deps", "--dry-run"],
            capture_output=True, text=True, cwd=repo_path, timeout=120
        )
        result["exit_code"] = proc.returncode
        result["stdout"] = proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout
        result["stderr"] = proc.stderr[-2000:] if len(proc.stderr) > 2000 else proc.stderr
        if proc.returncode != 0:
            for line in proc.stderr.splitlines():
                if "error" in line.lower() or "Error" in line:
                    result["errors"].append(line.strip())
    except Exception as e:
        result["errors"].append(str(e))
    return result


def run_tests_and_capture_failures(repo_path: str) -> List[Dict]:
    xml_path = os.path.join(repo_path, "_test_report.xml")
    failures = []
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--junitxml", xml_path, "--tb=long", "-q", "--no-header"],
            capture_output=True, text=True, cwd=repo_path, timeout=300
        )
        if proc.returncode in (1, 2) and os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            for tc in tree.getroot().iter("testcase"):
                fail = tc.find("failure")
                err = tc.find("error")
                node = fail if fail is not None else err
                if node is not None:
                    failures.append({
                        "test": tc.attrib.get("name", ""),
                        "file": tc.attrib.get("file", ""),
                        "line": tc.attrib.get("line", ""),
                        "message": node.attrib.get("message", "")[:500],
                        "traceback": (node.text or "")[:1000],
                    })
    except Exception as e:
        failures.append({"test": "_runner_", "message": str(e)})
    finally:
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
            except OSError:
                pass
    return failures


def write_diagnosis_report(findings: Dict, output_path: str) -> str:
    lines = ["# Build Diagnosis Report\n"]
    if findings.get("repo_path"):
        lines.append(f"Repository: {findings['repo_path']}\n")
    if findings.get("syntax_errors"):
        lines.append("\n## Syntax Errors\n")
        for e in findings["syntax_errors"]:
            lines.append(f"- {e['file']}:{e['line']} - {e['message']}")
            if e.get("text"):
                lines.append(f"  Code: {e['text']}")
    if findings.get("missing_deps"):
        lines.append("\n## Missing Dependencies\n")
        for d in findings["missing_deps"]:
            lines.append(f"- {d['dependency']} (module: {d['module']})")
    if findings.get("config"):
        c = findings["config"]
        if c.get("errors"):
            lines.append("\n## Config Errors\n")
            for e in c["errors"]:
                lines.append(f"- {e}")
    if findings.get("build_errors"):
        be = findings["build_errors"]
        if be.get("errors"):
            lines.append("\n## Build Errors\n")
            for e in be["errors"]:
                lines.append(f"- {e}")
    if findings.get("test_failures"):
        lines.append("\n## Test Failures\n")
        for t in findings["test_failures"]:
            lines.append(f"- {t.get('test','?')}: {t.get('message','')}")
    report = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report


def run_full_diagnosis(repo_path: str = None, output_path: str = "failed_reasons.txt") -> Dict:
    if repo_path is None:
        repo_path = find_repo_path()
    if repo_path is None:
        return {"error": "Repository not found"}
    findings = {"repo_path": repo_path}
    findings["syntax_errors"] = parse_syntax_errors(repo_path)
    findings["config"] = analyze_build_config(repo_path)
    deps = findings["config"].get("dependencies", [])
    if deps:
        import_results = check_import_availability(deps)
        findings["missing_deps"] = [r for r in import_results if not r["available"]]
    findings["build_errors"] = run_build_and_capture_errors(repo_path)
    findings["test_failures"] = run_tests_and_capture_failures(repo_path)
    write_diagnosis_report(findings, output_path)
    return findings


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else "failed_reasons.txt"
    results = run_full_diagnosis(repo, out)
    print(f"Diagnosis complete. Report: {out}")
