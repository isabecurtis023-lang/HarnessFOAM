"""Small structured readers for OpenFOAM post-processing outputs."""
import re
from pathlib import Path
from typing import Dict, List


def _latest_data_file(case_dir: str, name: str) -> Path | None:
    root = Path(case_dir) / "postProcessing"
    files = sorted(root.rglob(name)) if root.is_dir() else []
    return files[-1] if files else None


def read_table(case_dir: str, name: str) -> Dict[str, object]:
    path = _latest_data_file(case_dir, name)
    if not path:
        return {"available": False, "file": name, "rows": []}
    rows: List[List[float]] = []
    columns: List[str] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("#"):
                header = stripped.lstrip("#/ ")
                # OpenFOAM writes both '# columns: time Cd Cl' and '# Time Cd Cl'.
                header = re.sub(r"^columns?\s*:?\s*", "", header, flags=re.I)
                candidate = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]*", header)
                if len(candidate) >= 2 and any(token.lower() in {"time", "cd", "cl", "cm", "fx", "fy", "fz"} for token in candidate):
                    columns = candidate
                continue
            values = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", stripped)
            if values:
                rows.append([float(value) for value in values])
    except OSError:
        return {"available": False, "file": str(path), "rows": []}
    if rows and not columns:
        columns = ["value_" + str(index) for index in range(len(rows[-1]))]
    result = {"available": bool(rows), "file": str(path), "columns": columns, "rows": rows[-100:]}
    result["summary"] = summarize_table(result)
    return result


def summarize_table(table: Dict[str, object]) -> Dict[str, object]:
    """Convert a numeric table into latest/min/max/mean values."""
    rows = table.get("rows", []) or []
    columns = table.get("columns", []) or []
    if not rows:
        return {"latest": {}, "min": {}, "max": {}, "mean": {}}
    width = len(rows[0])
    if len(columns) != width:
        columns = ["value_" + str(index) for index in range(width)]
    values = {column: [float(row[index]) for row in rows if len(row) > index] for index, column in enumerate(columns)}
    return {
        "latest": {column: values[column][-1] for column in columns if values[column]},
        "min": {column: min(values[column]) for column in columns if values[column]},
        "max": {column: max(values[column]) for column in columns if values[column]},
        "mean": {column: sum(values[column]) / len(values[column]) for column in columns if values[column]},
    }


def collect_postprocess_metrics(case_dir: str) -> Dict[str, object]:
    """Return machine-readable metrics without requiring ParaView."""
    coefficient = read_table(case_dir, "coefficient.dat")
    if not coefficient["available"]:
        coefficient = read_table(case_dir, "forceCoeffs.dat")
    result = {"forceCoeffs": coefficient, "forces": read_table(case_dir, "forces.dat"), "probes": read_table(case_dir, "p")}
    result["available"] = any(value.get("available") for value in result.values() if isinstance(value, dict))
    return result
