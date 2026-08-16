from harnessfoam.telemetry import estimate_cost


def test_telemetry_reports_unpriced_usage_without_fabrication(monkeypatch):
    monkeypatch.delenv("LLM_INPUT_USD_PER_1M", raising=False)
    monkeypatch.delenv("LLM_OUTPUT_USD_PER_1M", raising=False)
    result = estimate_cost({"prompt_tokens": 100, "completion_tokens": 50}, "test-model")
    assert result["total_tokens"] == 150
    assert result["estimated_cost_usd"] is None
    assert result["cost_status"] == "UNPRICED"
