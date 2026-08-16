"""Case provenance and runtime contract for OpenFOAM 13 cases."""
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional

EXPECTED_OPENFOAM_VERSION = "13"


def _solver(case_dir: str) -> str:
    path = Path(case_dir) / "system" / "controlDict"
    if not path.is_file():
        return ""
    match = re.search(r"\bapplication\s+([A-Za-z0-9_]+)\s*;", path.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1) if match else ""


def write_manifest(case_dir: str, *, runtime: str = "WSL", source: str = "HarnessFOAM") -> Dict[str, str]:
    """Write a small, inspectable provenance file and return its contents."""
    manifest = {
        "openfoam_version": EXPECTED_OPENFOAM_VERSION,
        "solver": _solver(case_dir),
        "runtime": runtime,
        "tutorial_source": "OpenFOAM-13" if (Path(case_dir).parent / "assets" / "openfoam_tutorials").exists() else "OpenFOAM-13",
        "source": source,
    }
    target = Path(case_dir) / ".harnessfoam" / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def read_manifest(case_dir: str) -> Optional[Dict[str, str]]:
    path = Path(case_dir) / ".harnessfoam" / "manifest.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def parse_openfoam_version(log: str) -> Optional[str]:
    match = re.search(r"\bVersion:\s*([0-9]+(?:\.[0-9]+)?)", log or "")
    return match.group(1) if match else None

