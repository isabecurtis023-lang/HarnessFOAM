from harnessfoam.cavity_repair import run_cavity_repair_scenario

def test_cavity_repair_scenario(tmp_path):
    result = run_cavity_repair_scenario(str(tmp_path))
    assert result["status"] == "PASSED"
    assert result["initial_ok"] is False
    assert result["repaired_ok"] is True
    assert result["patch_status"] == "APPLIED"
    assert "0/U" in result["diff"]
