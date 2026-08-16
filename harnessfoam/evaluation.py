"""Reproducible evaluation summaries for benchmark and optimization runs."""
from collections import Counter
from typing import Dict, List


def summarize_runs(runs: List[Dict[str, object]]) -> Dict[str, object]:
    total = len(runs)
    passed = [run for run in runs if run.get("status") == "PASSED"]
    failed = [run for run in runs if run.get("status") != "PASSED"]
    objectives = [float(run["objective"]) for run in passed if run.get("objective") is not None]
    failure_types = Counter()
    for run in failed:
        for error in run.get("errors", []) or []:
            failure_types[str(error).split(":", 1)[0]] += 1
    return {
        "total": total,
        "passed": len(passed),
        "failed": len(failed),
        "success_rate": len(passed) / total if total else 0.0,
        "objective_min": min(objectives) if objectives else None,
        "objective_max": max(objectives) if objectives else None,
        "failure_types": dict(failure_types),
    }
