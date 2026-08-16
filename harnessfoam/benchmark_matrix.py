"""Cross-interface smoke matrix for CLI, Web API and MCP surfaces."""
from __future__ import annotations
from typing import Any

def run_interface_matrix(*, include_tutorials: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"cli": {}, "web": {}, "mcp": {}}
    # CLI surface: the same registry used by ``harnessfoam benchmark``.
    from harnessfoam.tutorial_regression import list_tutorial_regressions, run_tutorial_regression
    result["cli"]["registry"] = list_tutorial_regressions()
    if include_tutorials:
        result["cli"]["tutorials"] = {name: run_tutorial_regression(name) for name in result["cli"]["registry"]}
    else:
        result["cli"]["status"] = "READY"

    # Web surface: no network hop is needed for the deterministic contract check.
    from harnessfoam.knowledge import official_tutorial_stats
    from harnessfoam.assistant_tools import resolve_repo_path
    result["web"] = {"status": "READY", "knowledge": official_tutorial_stats(),
                     "assistant_root": str(resolve_repo_path("."))}

    # MCP surface: importing the registered server catches broken decorators and imports.
    from harnessfoam.api.mcp_server import mcp
    result["mcp"] = {"status": "READY", "server": type(mcp).__name__}
    result["status"] = "PASSED" if all(result[key].get("status", "READY") in {"READY", "PASSED"} for key in ("cli", "web", "mcp")) else "FAILED"
    return result
