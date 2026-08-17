"""Portable JSON reports for interface and tutorial benchmark runs."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def write_benchmark_report(payload: dict[str, Any], path: str = "benchmark_report.json") -> str:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return str(target)
