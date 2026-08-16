from harnessfoam.evaluation import summarize_runs


def test_evaluation_report_counts_success_and_failures():
    report = summarize_runs([
        {"status": "PASSED", "objective": 1.0},
        {"status": "FAILED", "objective": None, "errors": ["OpenFOAM runtime version 13 was not confirmed"]},
    ])
    assert report["success_rate"] == 0.5
    assert report["failure_types"]["OpenFOAM runtime version 13 was not confirmed"] == 1
