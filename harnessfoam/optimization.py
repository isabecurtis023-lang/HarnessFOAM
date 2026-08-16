"""Safe, reproducible parameter sweeps for OpenFOAM 13 cases."""
import itertools
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List

from harnessfoam.validation import validate_runtime
from harnessfoam.evaluation import summarize_runs


def expand_parameter_grid(parameters: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Expand [{path, key, values}, ...] into deterministic combinations."""
    if not parameters:
        return [{}]
    names = [str(item["key"]) for item in parameters]
    values = [list(item.get("values", [])) for item in parameters]
    if any(not options for options in values):
        raise ValueError("Every optimization parameter needs at least one value")
    return [dict(zip(names, combination)) for combination in itertools.product(*values)]


def _inject(case_dir: Path, parameters: List[Dict[str, object]], values: Dict[str, object]) -> None:
    for parameter in parameters:
        relative = str(parameter["path"])
        key = str(parameter["key"])
        target = (case_dir / relative).resolve()
        if os.path.commonpath([str(case_dir.resolve()), str(target)]) != str(case_dir.resolve()):
            raise ValueError(f"Parameter path escapes case directory: {relative}")
        content = target.read_text(encoding="utf-8", errors="ignore")
        pattern = rf"(\b{re.escape(key)}\s+)[^;]+(;)"
        updated, count = re.subn(pattern, lambda match: match.group(1) + str(values[key]) + match.group(2), content, count=1)
        if count != 1:
            raise ValueError(f"Could not locate parameter {key} in {relative}")
        with open(target, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)


def analyze_sensitivity(runs: List[Dict[str, object]], parameters: List[Dict[str, object]], objective: str = "last_time") -> Dict[str, object]:
    """Estimate one-at-a-time parameter influence from completed runs."""
    result = {}
    valid = [run for run in runs if run.get("status") == "PASSED" and run.get("objective") is not None]
    for parameter in parameters:
        key = str(parameter["key"])
        groups = {}
        for run in valid:
            if key in run.get("parameters", {}):
                groups.setdefault(str(run["parameters"][key]), []).append(float(run["objective"]))
        means = {value: sum(values) / len(values) for value, values in groups.items() if values}
        if means:
            result[key] = {"means": means, "range": max(means.values()) - min(means.values()), "most_influential_value": max(means, key=means.get)}
        else:
            result[key] = {"means": {}, "range": 0.0, "most_influential_value": None}
    return {"objective": objective, "parameters": result}


def run_parameter_sweep(base_case: str, output_root: str, parameters: List[Dict[str, object]], objective: str = "last_time", direction: str = "max") -> Dict[str, object]:
    """Run a bounded grid of independent cases through the OpenFOAM 13 gate."""
    source = Path(base_case).resolve()
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    combinations = expand_parameter_grid(parameters)
    runs = []
    for index, values in enumerate(combinations):
        candidate = root / f"case_{index:03d}"
        if candidate.exists():
            shutil.rmtree(candidate)
        shutil.copytree(source, candidate, ignore=shutil.ignore_patterns(".harnessfoam", "postProcessing", "*.log"))
        _inject(candidate, parameters, values)
        case_path = str(candidate).replace("\\", "/")
        if re.match(r"^[A-Za-z]:", case_path):
            case_path = "/mnt/" + case_path[0].lower() + case_path[2:]
        result = subprocess.run(["wsl", "bash", "-lc", f"cd '{case_path}' && bash ./Allrun"], capture_output=True, text=True, timeout=300) if shutil.which("wsl") else None
        log = ((result.stdout if result else "") or "") + "\n" + ((result.stderr if result else "") or "")
        ok, metrics, errors = validate_runtime(log, expected_version="13") if result else (False, {}, ["WSL is unavailable"])
        runs.append({"index": index, "parameters": values, "status": "PASSED" if result and result.returncode == 0 and ok else "FAILED", "objective": metrics.get(objective), "metrics": metrics, "errors": errors, "case_dir": str(candidate)})
    valid = [run for run in runs if run["status"] == "PASSED" and run["objective"] is not None]
    if direction not in {"max", "min"}:
        raise ValueError("direction must be 'max' or 'min'")
    best = (max if direction == "max" else min)(valid, key=lambda run: run["objective"]) if valid else None
    return {"status": "COMPLETED", "objective": objective, "direction": direction, "count": len(runs), "best": best, "evaluation": summarize_runs(runs), "sensitivity": analyze_sensitivity(runs, parameters, objective), "runs": runs}
