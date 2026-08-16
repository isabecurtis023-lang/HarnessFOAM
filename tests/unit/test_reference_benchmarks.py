from harnessfoam.reference_benchmarks import evaluate_reference_case


def test_cavity_reference_gate_passes():
    ok, result, errors = evaluate_reference_case(
        "2D lid driven cavity",
        {"last_time": 0.5, "max_courant": 0.05, "max_abs_continuity_error": 1e-12},
        {"status": "CHECKED", "U_max": 1.0},
    )
    assert ok is True
    assert result["score"] == 1.0
    assert errors == []


def test_reference_gate_rejects_high_courant():
    ok, result, errors = evaluate_reference_case(
        "cavity", {"last_time": 0.5, "max_courant": 1.2, "max_abs_continuity_error": 1e-12}, {"status": "CHECKED", "U_max": 1.0}
    )
    assert ok is False
    assert "courant_below_0.2" in errors
