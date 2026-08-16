"""OpenFOAM 13 official tutorial regression registry."""
import re
import shutil
import subprocess
from typing import Dict

from harnessfoam.validation import validate_runtime

TUTORIAL_REGISTRY = {
    "cavity": "incompressibleFluid/cavity",
    "pitzDaily": "incompressibleFluid/pitzDaily",
    "damBreak": "incompressibleVoF/damBreak",
    "shockTube": "fluid/shockTube",
}


def list_tutorial_regressions() -> Dict[str, str]:
    return dict(TUTORIAL_REGISTRY)


def run_tutorial_regression(name: str, timeout: int = 300) -> Dict[str, object]:
    relative = TUTORIAL_REGISTRY.get(name)
    if not relative:
        return {"status": "UNKNOWN", "error": f"Unknown tutorial regression: {name}"}
    if not shutil.which("wsl"):
        return {"status": "UNSUPPORTED", "tutorial": name, "error": "WSL is unavailable"}
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    destination = f"/tmp/harnessfoam-regression/{safe_name}"
    source = f"/opt/openfoam13/tutorials/{relative}"
    # Official RunFunctions-based tutorials write solver output to log.* files
    # rather than stdout, so append those logs to the captured stream.
    command = f"set -e; source /opt/openfoam13/etc/bashrc; rm -rf '{destination}'; mkdir -p /tmp/harnessfoam-regression; cp -a '{source}' '{destination}'; cd '{destination}'; if [ -f ./Allrun ]; then bash ./Allrun; else blockMesh; foamRun; fi; find . -maxdepth 1 -name 'log.*' -type f -exec cat {{}} +"
    try:
        result = subprocess.run(["wsl", "bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "tutorial": name, "source": source}
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    courant_limit = 10.0 if name == "pitzDaily" else (1.2 if name == "damBreak" else 1.0)
    runtime_ok, metrics, errors = validate_runtime(log, expected_version="13", max_courant=courant_limit)
    status = "PASSED" if result.returncode == 0 and runtime_ok else "FAILED"
    return {"status": status, "tutorial": name, "source": source, "returncode": result.returncode, "metrics": metrics, "errors": errors}
