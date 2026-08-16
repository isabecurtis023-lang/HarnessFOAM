"""Explicit-confirmation GitHub feedback bridge for the assistant."""
from __future__ import annotations
import shutil
import subprocess

def create_feedback(*, kind: str, title: str, body: str, confirm: bool = False,
                    base: str = "master") -> dict:
    kind = kind.lower().strip()
    if kind not in {"issue", "pr"}:
        return {"status": "ERROR", "error": "kind must be issue or pr"}
    if not confirm:
        return {"status": "REQUIRES_CONFIRMATION", "kind": kind, "title": title, "body": body}
    if not shutil.which("gh"):
        return {"status": "ERROR", "error": "GitHub CLI (gh) is not installed"}
    if kind == "issue":
        cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    else:
        cmd = ["gh", "pr", "create", "--base", base, "--title", title, "--body", body]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return {"status": "CREATED" if result.returncode == 0 else "ERROR",
            "output": (result.stdout or result.stderr).strip()}
