import json
from harnessfoam.benchmark_report import write_benchmark_report

def test_write_benchmark_report(tmp_path):
    path = write_benchmark_report({"status": "PASSED"}, str(tmp_path / "benchmark_report.json"))
    assert json.loads(open(path, encoding="utf-8").read())["status"] == "PASSED"
