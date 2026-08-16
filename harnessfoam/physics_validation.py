"""Low-cost physics sanity checks over written OpenFOAM fields.

These checks are intentionally conservative. They do not replace a benchmark
solution, but catch NaN/Inf fields, impossible magnitudes and broken cavity
smoke outputs after a numerically successful solver run.
"""
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple


def _numbers(text: str) -> List[float]:
    return [float(value) for value in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)]


def _field_values(path: Path, vector: bool = False) -> List[Tuple[float, ...]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"internalField\s+uniform\s+([^;]+);", text)
    if match:
        values = _numbers(match.group(1))
        return [tuple(values)] if values else []
    match = re.search(r"internalField\s+nonuniform\s+List<[^>]+>\s+\d+\s*\((.*?)\);", text, re.S)
    if not match:
        return []
    values = _numbers(match.group(1))
    width = 3 if vector else 1
    return [tuple(values[index:index + width]) for index in range(0, len(values), width) if len(values[index:index + width]) == width]


def _latest_time(case_dir: str) -> Path | None:
    root = Path(case_dir)
    times = []
    for child in root.iterdir() if root.is_dir() else []:
        try:
            if child.is_dir():
                times.append((float(child.name), child))
        except ValueError:
            continue
    return max(times, default=(0.0, root), key=lambda item: item[0])[1]


def validate_physics(case_dir: str, prompt: str = "", solver: str = "") -> Tuple[bool, Dict[str, object], List[str]]:
    time_dir = _latest_time(case_dir)
    if not time_dir or time_dir == Path(case_dir):
        return True, {"status": "SKIPPED", "reason": "No written numeric time directory"}, []
    metrics: Dict[str, object] = {"status": "CHECKED", "time": time_dir.name}
    errors: List[str] = []
    u_path, p_path = time_dir / "U", time_dir / "p"
    if u_path.is_file():
        vectors = _field_values(u_path, vector=True)
        magnitudes = [math.sqrt(sum(component * component for component in vector)) for vector in vectors]
        metrics["U_count"] = len(magnitudes)
        metrics["U_max"] = max(magnitudes, default=None)
        metrics["U_min"] = min(magnitudes, default=None)
        if not all(math.isfinite(value) for value in magnitudes):
            errors.append("Velocity field contains NaN or Inf")
        if any(value > 1e4 for value in magnitudes):
            errors.append("Velocity magnitude exceeds conservative sanity limit 1e4")
        if "cavity" in (prompt or "").lower() and solver == "icoFoam" and magnitudes and max(magnitudes) < 0.5:
            errors.append("Cavity velocity field never reaches 0.5 m/s despite a 1 m/s moving lid")
    if p_path.is_file():
        values = [value[0] for value in _field_values(p_path)]
        metrics["p_count"] = len(values)
        metrics["p_min"] = min(values, default=None)
        metrics["p_max"] = max(values, default=None)
        if not all(math.isfinite(value) for value in values):
            errors.append("Pressure field contains NaN or Inf")
    if not u_path.is_file() and not p_path.is_file():
        return True, {"status": "SKIPPED", "reason": "No U or p field in final time"}, []
    return not errors, metrics, errors
