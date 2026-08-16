import asyncio
import os

from harnessfoam.core import mcp_server


def test_mcp_apply_fix_is_bounded_and_backed_up(tmp_path):
    case_id = "case_unit_fix"
    mcp_server._jobs[case_id] = {"case_id": case_id, "case_dir": str(tmp_path), "status": "CREATED", "logs": {}}
    result = asyncio.run(mcp_server.apply_fix(case_id, [{"path": "system/controlDict", "content": "FoamFile;"}]))
    assert result["status"] == "REQUIRES_WORKFLOW_RETRY"
    assert (tmp_path / "system" / "controlDict").is_file()
    rejected = asyncio.run(mcp_server.apply_fix(case_id, [{"path": "../../escape", "content": "bad"}]))
    assert rejected["status"] == "FAILED"
    assert not os.path.exists(tmp_path.parent.parent / "escape")
