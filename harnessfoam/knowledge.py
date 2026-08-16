"""Offline retrieval over HarnessFOAM guidance and vendored OpenFOAM tutorials."""
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class KnowledgeChunk:
    key: str
    text: str
    tags: tuple[str, ...]


CORPUS = (
    KnowledgeChunk("solver-icofoam", "icoFoam is transient incompressible laminar flow. It requires U, p, transportProperties, fvSchemes, fvSolution, controlDict and a mesh.", ("icofoam", "laminar", "incompressible")),
    KnowledgeChunk("mesh-2d", "A 2-D blockMesh case uses one cell in the thin direction and empty frontAndBack patches. Every boundary face must belong to exactly one patch.", ("2d", "blockmesh", "empty", "mesh")),
    KnowledgeChunk("boundary-consistency", "All patches in blockMeshDict must appear in every volField boundaryField. Vector U uses vector dimensions and scalar p uses pressure dimensions.", ("boundary", "patch", "field", "consistency")),
    KnowledgeChunk("pressure-reference", "In a closed incompressible cavity, fvSolution PISO needs pRefCell and pRefValue to set the pressure reference.", ("cavity", "piso", "pressure", "reference")),
    KnowledgeChunk("mesh-quality", "Run checkMesh after mesh generation. A case is not valid merely because blockMesh exits zero; inspect fatal errors, invalid cells and boundary topology.", ("checkmesh", "quality", "mesh")),
    KnowledgeChunk("run-metrics", "A converged run should record solver residuals, continuity errors, Courant number and the final written time. Treat FOAM FATAL ERROR and missing final time as failure.", ("residual", "continuity", "courant", "convergence")),
    KnowledgeChunk("review-loop", "Repair only the file named by the diagnostic, preserve user-declared parameters, back up the previous file and re-run deterministic validation before the solver.", ("review", "repair", "rollback")),
)

_TUTORIAL_FILES = {"controlDict", "blockMeshDict", "snappyHexMeshDict", "fvSchemes", "fvSolution", "transportProperties", "physicalProperties", "momentumTransport", "thermophysicalProperties", "phaseProperties", "g", "setFieldsDict", "decomposeParDict", "U", "p", "p_rgh", "T", "alpha.water", "Allrun", "Allclean"}
_tutorial_cache: Optional[List[KnowledgeChunk]] = None
_tutorial_stats = {"enabled": True, "files": 0, "chunks": 0, "roots": [], "version": "OpenFOAM-13"}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_+.-]*", (value or "").lower()))


def _tutorial_roots() -> List[Path]:
    project_root = Path(__file__).resolve().parents[1]
    candidates = [project_root / "assets" / "openfoam_tutorials"]
    for variable in ("FOAM_TUTORIALS", "WM_PROJECT_DIR"):
        value = os.getenv(variable, "").strip()
        if value:
            path = Path(value) / ("tutorials" if variable == "WM_PROJECT_DIR" else "")
            if path.is_dir():
                candidates.append(path)
    try:
        probe = subprocess.run(["wsl", "bash", "-lc", "if [ -n \"$FOAM_TUTORIALS\" ] && [ -d \"$FOAM_TUTORIALS\" ]; then printf %s \"$FOAM_TUTORIALS\"; elif [ -d /usr/share/openfoam/tutorials ]; then printf %s /usr/share/openfoam/tutorials; fi"], capture_output=True, text=True, timeout=5)
        if probe.returncode == 0 and probe.stdout.strip():
            path = Path(probe.stdout.strip())
            if path.is_dir():
                candidates.append(path)
    except (OSError, subprocess.SubprocessError):
        pass
    unique = []
    for root in candidates:
        if root.is_dir():
            root = root.resolve()
            if root not in unique:
                unique.append(root)
    return unique


def load_tutorial_chunks() -> List[KnowledgeChunk]:
    """Index selected OpenFOAM dictionary files once per process."""
    global _tutorial_cache, _tutorial_stats
    if _tutorial_cache is not None:
        return _tutorial_cache
    chunks: List[KnowledgeChunk] = []
    roots = _tutorial_roots()
    seen = set()
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.name not in _TUTORIAL_FILES or path in seen:
                continue
            try:
                if path.stat().st_size > 80_000:
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            seen.add(path)
            relative = path.relative_to(root).as_posix()
            excerpt = content[:6000]
            key = f"tutorial:{root.name}:{relative}"
            tags = tuple(sorted(_tokens(relative + " " + content[:15000])))
            chunks.append(KnowledgeChunk(key, f"Official tutorial file: {relative}\n{excerpt}", tags))
    chunks.sort(key=lambda chunk: chunk.key)
    _tutorial_cache = chunks
    _tutorial_stats = {"enabled": True, "files": len(seen), "chunks": len(chunks), "roots": [str(root) for root in roots], "version": "OpenFOAM-13"}
    return chunks


def official_tutorial_stats() -> dict:
    load_tutorial_chunks()
    return dict(_tutorial_stats)


def retrieve(query: str, k: int = 4) -> List[KnowledgeChunk]:
    query_tokens = _tokens(query)
    ranked = []
    for chunk in list(CORPUS) + load_tutorial_chunks():
        tag_hits = len(query_tokens.intersection(chunk.tags))
        text_hits = len(query_tokens.intersection(_tokens(chunk.text)))
        score = tag_hits * 4 + min(text_hits, 12)
        if score:
            ranked.append((score, chunk.key, chunk))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:k]]


def format_context(query: str, k: int = 4, max_chars: int = 2500) -> str:
    chunks = retrieve(query, k=k)
    if not chunks:
        return "No canonical OpenFOAM guidance matched this request."
    return "\n".join(f"[{chunk.key}] {chunk.text[:max_chars]}" for chunk in chunks)
