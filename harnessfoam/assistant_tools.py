"""Safe, repository-scoped tools exposed to the Web assistant."""
from __future__ import annotations
import difflib
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
    if not confirm:
        return {"status": "REQUIRES_CONFIRMATION", "path": path, "message": "Explicit confirmation is required before writing."}
    target = resolve_repo_path(path, repo_root)
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    diff = "".join(difflib.unified_diff(old.splitlines(True), content.splitlines(True), fromfile=path, tofile=path))
    return {"status": "APPLIED", "path": str(target), "diff": diff[:20000]}
