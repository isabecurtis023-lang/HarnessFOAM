"""Deterministic OpenFOAM dictionary dependency ordering."""
from typing import Dict, List

_ORDER = {
    "blockMeshDict": 10,
    "controlDict": 20,
    "physicalProperties": 30,
    "transportProperties": 30,
    "turbulenceProperties": 31,
    "thermophysicalProperties": 32,
    "g": 33,
    "fvSchemes": 40,
    "fvSolution": 50,
}


def order_plan(plan: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Order structural dictionaries before fields, preserving stable ties."""
    return sorted(
        list(plan or []),
        key=lambda item: (_ORDER.get(item.get("file", ""), 60 if item.get("folder") == "0" else 55), item.get("folder", ""), item.get("file", "")),
    )
