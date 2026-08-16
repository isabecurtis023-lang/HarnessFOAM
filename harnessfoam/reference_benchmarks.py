"""Small, versioned reference gates for reproducible OpenFOAM cases."""
from typing import Dict, List, Tuple


def evaluate_reference_case(prompt: str, runtime: Dict[str, object], physics: Dict[str, object], benchmark: str = "") -> Tuple[bool, Dict[str, object], List[str]]:
    """Score known smoke cases without pretending to replace validation data."""
    text = (prompt or "").lower()
    if benchmark != "cavity" and "cavity" not in text and "lid driven" not in text and "lid-driven" not in text:
        return True, {"status": "SKIPPED", "benchmark": "none"}, []
    checks = {
        "openfoam13_final_time": float(runtime.get("last_time") or 0) >= 0.5,
        "courant_below_0.2": (runtime.get("max_courant") is None or float(runtime["max_courant"]) <= 0.2),
        "continuity_below_1e-6": (runtime.get("max_abs_continuity_error") is None or float(runtime["max_abs_continuity_error"]) <= 1e-6),
        "finite_velocity": physics.get("status") in ("CHECKED", "SKIPPED") and physics.get("U_max") is not None,
        "moving_lid_velocity_reached": (physics.get("U_max") is not None and 0.5 <= float(physics["U_max"]) <= 2.0),
    }
    passed = sum(bool(value) for value in checks.values())
    score = passed / len(checks)
    errors = [name for name, value in checks.items() if not value]
    result = {"status": "PASSED" if score == 1.0 else "FAILED", "benchmark": "cavity", "score": score, "checks": checks}
    return score == 1.0, result, errors
