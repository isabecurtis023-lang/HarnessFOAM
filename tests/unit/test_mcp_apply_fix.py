import asyncio
import os

from harnessfoam.core import mcp_server
from harnessfoam.core.database import init_db, create_run

def test_mcp_apply_fix_is_bounded_and_backed_up(tmp_path):
    init_db()
    case_id = "case_unit_fix"
    create_run(case_id, str(tmp_path), "test prompt", {"case_id": case_id, "case_dir": str(tmp_path), "status": "CREATED", "logs": {}})
    
    result = asyncio.run(mcp_server.apply_fix(case_id, [{"path": "system/controlDict", "content": "FoamFile;"}]))
    assert result["status"] == "REQUIRES_WORKFLOW_RETRY"
    assert (tmp_path / "system" / "controlDict").is_file()
    
    rejected = asyncio.run(mcp_server.apply_fix(case_id, [{"path": "../../escape", "content": "bad"}]))
    assert rejected["status"] == "FAILED"
    assert not os.path.exists(tmp_path.parent.parent / "escape")
