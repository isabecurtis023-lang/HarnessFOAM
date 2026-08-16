"""Opt-in per-agent memory and deterministic self-improvement ledger."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

DEFAULT_TOKEN_LIMITS = {
    "architect": 2000, "meshing": 2000, "input_writer": 4000,
    "preflight": 2500, "runner": 2500, "reviewer": 3500,
    "visualizer": 2500, "assistant": 4000,
}

def normalize_limits(limits: Mapping[str, Any] | None = None) -> dict[str, int]:
    result = dict(DEFAULT_TOKEN_LIMITS)
    for name, value in (limits or {}).items():
        try:
            result[name] = max(256, min(20000, int(value)))
        except (TypeError, ValueError):
            pass
    return result

def _token_count(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))

def memory_path(case_dir: str | os.PathLike[str], agent: str) -> Path:
    safe = re.sub(r"[^a-z0-9_-]+", "_", agent.lower()).strip("_") or "agent"
    return Path(case_dir) / ".harnessfoam" / "memory" / f"{safe}.md"

def _compress(text: str, limit: int) -> str:
    if _token_count(text) <= limit:
        return text
    lines = [line for line in text.splitlines() if line.strip()]
    tail = lines[-max(8, limit // 80):]
    compact = "\n".join(lines[:2] + ["\n> [自动压缩] 旧记录已折叠，仅保留近期经验。\n"] + tail)
    return " ".join(compact.split()[:limit])

def read_memory(case_dir: str, agent: str, *, enabled: bool = False,
                limits: Mapping[str, Any] | None = None) -> str:
    if not enabled:
        return ""
    path = memory_path(case_dir, agent)
    if not path.exists():
        return ""
    return _compress(path.read_text(encoding="utf-8"), normalize_limits(limits).get(agent, 2000))

def prompt_context(case_dir: str | None, agent: str, *, enabled: bool = False,
                   limits: Mapping[str, Any] | None = None) -> str:
    """Return a bounded prompt block; disabled memory contributes no text."""
    if not case_dir or not enabled:
        return ""
    text = read_memory(case_dir, agent, enabled=True, limits=limits)
    return f"\n\nAgent memory for {agent} (use as lessons, verify against current files):\n{text}\n" if text else ""

def record_event(case_dir: str, agent: str, *, outcome: str, details: str = "",
                 enabled: bool = False, limits: Mapping[str, Any] | None = None) -> str:
    if not enabled:
        return ""
    path = memory_path(case_dir, agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {agent} Agent Memory\n\n", encoding="utf-8")
    event = f"\n## {outcome.upper()}\n- details: {(details or '').strip()[-2500:]}\n"
    text = _compress(path.read_text(encoding="utf-8") + event,
                     normalize_limits(limits).get(agent, 2000))
    path.write_text(text, encoding="utf-8")
    return str(path)

def record_self_improvement(case_dir: str, *, agent: str, error: str,
                            fix: str = "", outcome: str = "recovered",
                            enabled: bool = False,
                            limits: Mapping[str, Any] | None = None) -> str:
    return record_event(case_dir, agent, outcome=outcome,
                        details=f"Observed error: {error[-1000:]}\nRecommended fix: {fix[-1000:]}",
                        enabled=enabled, limits=limits)

def memory_snapshot(case_dir: str, *, enabled: bool = False,
                    limits: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not enabled:
        return {"enabled": False, "agents": {}}
    result = {}
    for agent in DEFAULT_TOKEN_LIMITS:
        text = read_memory(case_dir, agent, enabled=True, limits=limits)
        result[agent] = {"path": str(memory_path(case_dir, agent)),
                         "tokens": _token_count(text) if text else 0,
                         "limit": normalize_limits(limits).get(agent, DEFAULT_TOKEN_LIMITS[agent]),
                         "content": text}
    return {"enabled": True, "agents": result}

def clear_memory(case_dir: str, agent: str | None = None, *, confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {"status": "REQUIRES_CONFIRMATION"}
    targets = [agent] if agent else list(DEFAULT_TOKEN_LIMITS)
    removed = []
    for name in targets:
        path = memory_path(case_dir, name)
        if path.exists():
            path.unlink()
            removed.append(str(path))
    return {"status": "CLEARED", "removed": removed}

def memory_config(enabled: bool = False, limits: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"enabled": bool(enabled), "limits": normalize_limits(limits)}

def initialize_memory(case_dir: str, *, enabled: bool = False,
                      limits: Mapping[str, Any] | None = None) -> list[str]:
    """Create a stable memory document for every graph agent when opted in."""
    if not enabled:
        return []
    paths = []
    for agent in DEFAULT_TOKEN_LIMITS:
        path = memory_path(case_dir, agent)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(f"# {agent} Agent Memory\n\n<!-- local, opt-in, auto-compressed -->\n", encoding="utf-8")
        paths.append(str(path))
    return paths
