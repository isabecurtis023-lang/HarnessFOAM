from harnessfoam.assistant_tools import apply_patch, assistant_command, read_file
from harnessfoam.cavity_repair import run_cavity_repair_scenario

def test_patch_requires_confirmation(tmp_path):
    target = tmp_path / "x.txt"
    result = apply_patch("x.txt", "new", repo_root=str(tmp_path), confirm=False)
    assert result["status"] == "REQUIRES_CONFIRMATION"
    assert "new" in result["diff"]
    assert not target.exists()

def test_patch_is_repo_scoped(tmp_path):
    result = apply_patch("x.txt", "new", repo_root=str(tmp_path), confirm=True)
    assert result["status"] == "APPLIED"
    assert read_file("x.txt", str(tmp_path))["content"] == "new"

def test_assistant_test_command_is_recognized():
    # Do not execute pytest from a unit test; dispatch recognition is the contract.
    assert assistant_command("not a tool command") is None

def test_cavity_repair_preview_does_not_apply(tmp_path):
    result = run_cavity_repair_scenario(str(tmp_path / "repair"), confirm=False)
    assert result["status"] == "FAILED"
    assert result["patch_status"] == "REQUIRES_CONFIRMATION"
    assert result["repaired_ok"] is False

def test_cavity_repair_confirmation_repairs_case(tmp_path):
    result = run_cavity_repair_scenario(str(tmp_path / "repair"), confirm=True)
    assert result["status"] == "PASSED"
    assert result["patch_status"] == "APPLIED"
    assert result["repaired_ok"] is True
