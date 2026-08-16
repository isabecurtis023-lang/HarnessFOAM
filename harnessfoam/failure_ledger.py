"""Read-only summaries of bounded retry trajectories."""
import json
from pathlib import Path
from typing import Dict


def summarize_failure_ledger(case_dir: str) -> Dict[str, object]:
    path = Path(case_dir) / ".harnessfoam" / "failure_ledger.jsonl"
    if not path.is_file():
        return {"available": False, "attempts": 0, "files": []}
    attempts = 0
    suggestions = 0
    latest_error = ""
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            attempts += 1
            suggestions += len(item.get("suggestions", []))
            latest_error = str(item.get("error", ""))[-500:]
    except (OSError, json.JSONDecodeError):
        return {"available": False, "attempts": attempts, "files": []}
    return {"available": True, "attempts": attempts, "suggestions": suggestions, "latest_error": latest_error, "file": str(path)}
