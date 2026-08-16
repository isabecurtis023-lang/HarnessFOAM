from harnessfoam.benchmark_matrix import run_interface_matrix

def test_interface_matrix_is_ready():
    result = run_interface_matrix()
    assert result["status"] == "PASSED"
    assert result["cli"]["registry"]["cavity"]
    assert result["web"]["knowledge"]["chunks"] > 0
    assert result["mcp"]["server"] == "FastMCP"
