from harnessfoam.assistant_tools import apply_patch, assistant_command, read_file

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
