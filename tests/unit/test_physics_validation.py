from harnessfoam.physics_validation import validate_physics


def test_physics_validation_reads_written_fields(tmp_path):
    final = tmp_path / "0.5"
    final.mkdir()
    (final / "U").write_text("internalField nonuniform List<vector> 2((1 0 0)(0.5 0 0));", encoding="utf-8")
    (final / "p").write_text("internalField nonuniform List<scalar> 2(0.1 -0.1);", encoding="utf-8")
    ok, metrics, errors = validate_physics(str(tmp_path), "2D lid driven cavity", "icoFoam")
    assert ok is True
    assert metrics["U_max"] == 1.0
    assert metrics["p_min"] == -0.1
    assert errors == []
