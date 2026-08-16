"""Reproducible, LLM-free OpenFOAM 13 smoke benchmark."""
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict

from harnessfoam.case_manifest import write_manifest
from harnessfoam.cases.cavity import cavity_files
from harnessfoam.validation import validate_runtime


def run_cavity_smoke(output_dir: str) -> Dict[str, object]:
    """Generate and run the deterministic cavity case through OpenFOAM 13."""
    case_dir = Path(output_dir).resolve()
    for relative, content in cavity_files().items():
        target = case_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    write_manifest(str(case_dir), runtime="WSL" if shutil.which("wsl") else "Native", source="cavity-smoke-benchmark")
    allrun = """#!/bin/bash
set -e
. /opt/openfoam13/etc/bashrc
blockMesh
checkMesh
icoFoam
echo 'Simulation complete!'
"""
    with open(case_dir / "Allrun", "w", encoding="utf-8", newline="") as handle:
        handle.write(allrun)
    if not shutil.which("wsl"):
        return {"status": "UNSUPPORTED", "error": "OpenFOAM 13 smoke benchmark requires WSL on Windows"}
    case_path = str(case_dir).replace("\\", "/")
    case_path = re.sub(r"^([A-Za-z]):", lambda match: "/mnt/" + match.group(1).lower(), case_path)
    result = subprocess.run(["wsl", "bash", "-lc", f"cd '{case_path}' && bash ./Allrun"], capture_output=True, text=True, timeout=300)
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    ok, metrics, errors = validate_runtime(log, expected_version="13")
    return {"status": "PASSED" if result.returncode == 0 and ok else "FAILED", "metrics": metrics, "errors": errors, "returncode": result.returncode}
