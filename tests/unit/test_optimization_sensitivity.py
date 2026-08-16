from harnessfoam.optimization import analyze_sensitivity


def test_sensitivity_groups_completed_runs():
    runs = [
        {"status": "PASSED", "parameters": {"deltaT": 0.001}, "objective": 1.0},
        {"status": "PASSED", "parameters": {"deltaT": 0.002}, "objective": 2.0},
        {"status": "FAILED", "parameters": {"deltaT": 0.003}, "objective": None},
    ]
    result = analyze_sensitivity(runs, [{"key": "deltaT", "values": [0.001, 0.002]}])
    assert result["parameters"]["deltaT"]["range"] == 1.0
    assert result["parameters"]["deltaT"]["most_influential_value"] == "0.002"
