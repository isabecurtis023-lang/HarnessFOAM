import pytest
from harnessfoam.assistant_tools import read_file, apply_patch

def test_sensitive_files_are_blocked(tmp_path):
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    with pytest.raises(PermissionError):
        read_file(".env", str(tmp_path))
    with pytest.raises(PermissionError):
        apply_patch(".env", "SECRET=y", str(tmp_path), confirm=True)
