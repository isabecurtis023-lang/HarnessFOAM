"""Safe, repository-scoped tools exposed to the Web assistant."""
from __future__ import annotations
import difflib
import re
import subprocess
import sys
from pathlib import Path

MAX_READ = 2 * 1024 * 1024

def resolve_repo_path(path: str, repo_root: str | None = None) -> Path:
    root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes the HarnessFOAM repository")
    return candidate

def read_file(path: str, repo_root: str | None = None) -> dict:
    target = resolve_repo_path(path, repo_root)
    if not target.is_file():
        raise FileNotFoundError(path)
    if target.stat().st_size > MAX_READ:
        raise ValueError("file exceeds the assistant read limit")
    return {"path": str(target), "content": target.read_text(encoding="utf-8"), "size": target.stat().st_size}

def search_files(query: str, repo_root: str | None = None) -> list[dict]:
    root = resolve_repo_path(".", repo_root)
    results = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in {".git", "__pycache__", ".venv"} for part in path.parts):
            continue
        try: text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if query.lower() in line.lower():
                results.append({"path": str(path.relative_to(root)), "line": line_no, "text": line[:500]})
                if len(results) >= 200: return results
    return results

def apply_patch(path: str, content: str, repo_root: str | None = None, *, confirm: bool = False) -> dict:
    target = resolve_repo_path(path, repo_root)
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    diff = "".join(difflib.unified_diff(old.splitlines(True), content.splitlines(True), fromfile=path, tofile=path))
    if not confirm:
        return {"status": "REQUIRES_CONFIRMATION", "path": path,
                "message": "Explicit confirmation is required before writing.", "diff": diff[:20000]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"status": "APPLIED", "path": str(target), "diff": diff[:20000]}

def run_unit_tests(repo_root: str | None = None) -> dict:
    root = resolve_repo_path(".", repo_root)
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-q"], cwd=root,
                            capture_output=True, text=True, timeout=180)
    return {"status": "PASSED" if result.returncode == 0 else "FAILED",
            "returncode": result.returncode, "output": (result.stdout + result.stderr)[-12000:]}

def run_cavity_benchmark(output_dir: str = "tmp_assistant_cavity") -> dict:
    from harnessfoam.benchmark import run_cavity_smoke
    return run_cavity_smoke(output_dir)

def analyze_log(path: str, repo_root: str | None = None) -> dict:
    data = read_file(path, repo_root)["content"]
    patterns = {
        "fatal_errors": r"(?im)^.*(?:FOAM FATAL|ERROR|SIGFPE).*$",
        "courant": r"(?im)^.*Courant Number.*$",
        "continuity": r"(?im)^.*time step continuity errors.*$",
    }
    return {"path": path, "matches": {key: re.findall(pattern, data)[-20:] for key, pattern in patterns.items()}}

def assistant_command(message: str, *, output_dir: str = "tmp_assistant_cavity") -> dict | None:
    """Handle safe deterministic commands before delegating explanatory chat to the LLM."""
    text = (message or "").strip()
    lower = text.lower()
    if lower in {"/test", "/tests", "运行测试", "run tests"}:
        return {"tool": "run_unit_tests", "result": run_unit_tests()}
    if lower in {"/benchmark cavity", "run cavity benchmark", "运行 cavity benchmark", "运行cavity算例"}:
        return {"tool": "run_cavity_benchmark", "result": run_cavity_benchmark(output_dir)}
    if lower.startswith("/search "):
        return {"tool": "search_files", "result": {"results": search_files(text[8:].strip())}}
    if lower.startswith("/read "):
        try: return {"tool": "read_file", "result": read_file(text[6:].strip())}
        except Exception as exc: return {"tool": "read_file", "result": {"error": str(exc)}}
    if lower.startswith("/log "):
        try: return {"tool": "analyze_log", "result": analyze_log(text[5:].strip())}
        except Exception as exc: return {"tool": "analyze_log", "result": {"error": str(exc)}}
    return None
