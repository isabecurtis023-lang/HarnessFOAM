"""Deterministic failure-injection scenario for the Assistant repair loop."""
from __future__ import annotations
from pathlib import Path
from harnessfoam.cases.cavity import cavity_files
from harnessfoam.validation import validate_case_files
from harnessfoam.agents.reviewer import deterministic_suggestions
from harnessfoam.assistant_tools import apply_patch

def _plan():
    return [{"folder": path.split("/", 1)[0], "file": path.split("/", 1)[1]} for path in cavity_files()]

def run_cavity_repair_scenario(output_dir: str, *, execute: bool = False, confirm: bool = True) -> dict:
    root = Path(output_dir).resolve()
    files = cavity_files()
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    broken = root / "0" / "U"
    broken.write_text(files["0/U"].replace(" fixedWalls { type fixedValue; value uniform (0 0 0); }", ""), encoding="utf-8")
    initial_ok, initial_errors = validate_case_files(str(root), _plan())
    suggestions = deterministic_suggestions("\n".join(initial_errors))
    target_suggestion = next((item for item in suggestions if item.get("file") == "U"), None)
    if not target_suggestion:
        return {"status": "FAILED", "stage": "locate", "errors": initial_errors, "suggestions": suggestions}

    preview = apply_patch("0/U", files["0/U"], str(root), confirm=False)
    applied = apply_patch("0/U", files["0/U"], str(root), confirm=confirm)
    repaired_ok, repaired_errors = validate_case_files(str(root), _plan()) if confirm else (False, ["Repair not confirmed yet"])
    result = {"status": "PASSED" if (not initial_ok and repaired_ok) else "FAILED",
              "initial_ok": initial_ok, "initial_errors": initial_errors,
              "suggestions": suggestions, "diff": preview.get("diff", ""),
              "patch_status": applied.get("status"), "repaired_ok": repaired_ok,
              "repaired_errors": repaired_errors}
    if execute and repaired_ok:
        from harnessfoam.benchmark import run_cavity_smoke
        result["benchmark"] = run_cavity_smoke(str(root))
    return result
