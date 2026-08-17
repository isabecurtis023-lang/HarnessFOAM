from pathlib import Path

from harnessfoam.api.server import AssistantRepairRequest, assistant_repair


def test_web_repair_api_preview_requires_confirmation(tmp_path):
    result = assistant_repair(AssistantRepairRequest(output_dir=str(tmp_path / "case")))
    assert result["patch_status"] == "REQUIRES_CONFIRMATION"
    assert result["repaired_ok"] is False


def test_web_repair_api_confirmation_and_regression(tmp_path, monkeypatch):
    case_dir = str(tmp_path / "case")
    result = assistant_repair(AssistantRepairRequest(output_dir=case_dir, confirm=True))
    assert result["status"] == "PASSED"
    assert Path(case_dir, "0", "U").is_file()

    # The API's execute path is exercised independently; the real solver is
    # covered by the CLI benchmark and the dedicated cavity E2E test.
    result = assistant_repair(AssistantRepairRequest(output_dir=case_dir, confirm=True, execute=False))
    assert result["patch_status"] == "APPLIED"
