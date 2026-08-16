"""Deterministic OpenFOAM preflight and runtime validation."""
import os
import re
from typing import Dict, List, Tuple


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def validate_case_files(case_dir: str, plan: List[Dict[str, str]]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    paths = [f"{item['folder']}/{item['file']}" for item in plan]
    required = ["system/controlDict", "system/fvSchemes", "system/fvSolution", "system/blockMeshDict", "constant/transportProperties", "0/U", "0/p"]
    for path in required:
        if path not in paths and not os.path.exists(os.path.join(case_dir, path)):
            errors.append(f"Missing required OpenFOAM file: {path}")
    for path in paths:
        full_path = os.path.join(case_dir, path)
        if not os.path.isfile(full_path):
            errors.append(f"Planned file was not written: {path}")
            continue
        content = _read(full_path)
        if "Mock OpenFOAM content" in content:
            errors.append(f"Placeholder content is not allowed: {path}")
        if "FoamFile" not in content:
            errors.append(f"Missing FoamFile header: {path}")

    control = os.path.join(case_dir, "system", "controlDict")
    solver = ""
    if os.path.isfile(control):
        match = re.search(r"\bapplication\s+([A-Za-z0-9_]+)\s*;", _read(control))
        if match:
            solver = match.group(1)
        else:
            errors.append("system/controlDict has no application entry")

    block_path = os.path.join(case_dir, "system", "blockMeshDict")
    patches = set()
    if os.path.isfile(block_path):
        block = _read(block_path)
        boundary_match = re.search(r"\bboundary\s*\((.*)\)\s*;", block, re.S)
        if boundary_match:
            patches = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\{", boundary_match.group(1)))
        else:
            errors.append("system/blockMeshDict has no parseable boundary section")

    for field in ("U", "p"):
        field_path = os.path.join(case_dir, "0", field)
        if not os.path.isfile(field_path):
            continue
        content = _read(field_path)
        boundary_match = re.search(r"\bboundaryField\s*\{(.*)\}", content, re.S)
        field_patches = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\{", boundary_match.group(1))) if boundary_match else set()
        if boundary_match and patches and patches != field_patches:
            errors.append(f"Patch mismatch for 0/{field}: mesh={sorted(patches)}, field={sorted(field_patches)}")

    if solver and not re.search(r"\bapplication\s+" + re.escape(solver) + r"\s*;", _read(control)):
        errors.append("Unable to confirm solver application")
    solver_requirements = {
        "simpleFoam": ["constant/turbulenceProperties"],
        "pimpleFoam": ["constant/turbulenceProperties"],
        "interFoam": ["0/alpha.water", "constant/g"],
        "buoyantBoussinesqPimpleFoam": ["0/T", "constant/g", "constant/thermophysicalProperties"],
        "buoyantSimpleFoam": ["0/T", "constant/g", "constant/thermophysicalProperties"],
        "reactingFoam": ["0/T", "constant/thermophysicalProperties", "constant/chemistryProperties"],
        "rhoCentralFoam": ["0/T", "constant/thermophysicalProperties"],
    }
    for required_path in solver_requirements.get(solver, []):
        if not os.path.isfile(os.path.join(case_dir, required_path)):
            errors.append(f"{solver} requires {required_path}")
    return not errors, errors


def parse_runtime_metrics(log: str) -> Dict[str, object]:
    residuals = [float(value) for value in re.findall(r"Final residual\s*=\s*([0-9.eE+-]+)", log or "")]
    continuity = [float(value) for value in re.findall(r"global\s*=\s*([0-9.eE+-]+)", log or "")]
    courant = [(float(mean), float(maximum)) for mean, maximum in re.findall(r"Courant Number mean:\s*([0-9.eE+-]+)\s+max:\s*([0-9.eE+-]+)", log or "")]
    times = re.findall(r"\bTime\s*=\s*([0-9.eE+-]+)", log or "")
    return {
        "final_residual": min(residuals) if residuals else None,
        "max_residual": max(residuals) if residuals else None,
        "max_abs_continuity_error": max((abs(x) for x in continuity), default=None),
        "max_courant_mean": max((pair[0] for pair in courant), default=None),
        "max_courant": max((pair[1] for pair in courant), default=None),
        "time_steps": len(times),
        "last_time": float(times[-1]) if times else None,
        "has_end_marker": bool(re.search(r"(?:\nEnd\s*$|Simulation complete!\s*$)", log or "", re.M)),
    }


def validate_runtime(log: str) -> Tuple[bool, Dict[str, object], List[str]]:
    metrics = parse_runtime_metrics(log)
    errors: List[str] = []
    if re.search(r"FOAM FATAL|FOAM FATAL IO ERROR|FOAM aborting", log or "", re.I):
        errors.append("OpenFOAM fatal error reported in solver log")
    if not metrics["has_end_marker"]:
        errors.append("Solver log has no completion marker")
    if metrics["time_steps"] == 0:
        errors.append("Solver log contains no time steps")
    if metrics["max_courant"] is not None and metrics["max_courant"] > 1.0:
        errors.append(f"Maximum Courant number is too high: {metrics['max_courant']}")
    return not errors, metrics, errors
