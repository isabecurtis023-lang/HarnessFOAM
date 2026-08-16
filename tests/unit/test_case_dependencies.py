from harnessfoam.case_dependencies import order_plan


def test_structural_dictionaries_precede_fields():
    plan = [{"folder": "0", "file": "U"}, {"folder": "system", "file": "fvSolution"}, {"folder": "system", "file": "blockMeshDict"}]
    ordered = order_plan(plan)
    assert [item["file"] for item in ordered] == ["blockMeshDict", "fvSolution", "U"]
