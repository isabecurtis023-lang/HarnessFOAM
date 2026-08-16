from pathlib import Path

from harnessfoam.case_manifest import parse_openfoam_version, read_manifest, write_manifest
from harnessfoam.knowledge import retrieve_multistage, retrieve_routed
from harnessfoam.postprocess import collect_postprocess_metrics


def test_manifest_and_openfoam_version(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "controlDict").write_text("application icoFoam;\n", encoding="utf-8")
    manifest = write_manifest(str(tmp_path))
    assert manifest["openfoam_version"] == "13"
    assert read_manifest(str(tmp_path))["solver"] == "icoFoam"
    assert parse_openfoam_version("Version: 13") == "13"


def test_structured_postprocess_reader(tmp_path):
    output = tmp_path / "postProcessing" / "forces" / "0"
    output.mkdir(parents=True)
    (output / "forceCoeffs.dat").write_text("# columns: time Cd Cl\n0 0.3 0.01\n", encoding="utf-8")
    result = collect_postprocess_metrics(str(tmp_path))
    assert result["available"] is True
    assert result["forceCoeffs"]["rows"][-1][1] == 0.3


def test_multistage_rag_hits_vendored_tutorial():
    keys = [chunk.key for chunk in retrieve_multistage("OpenFOAM 13 lid driven cavity icoFoam", k=5)]
    assert any("tutorial:" in key and "cavity" in key for key in keys)


def test_routed_rag_returns_file_context_for_input_writer():
    chunks = retrieve_routed("lid driven cavity", route="input_writer", k=5)
    assert any("fvSolution" in chunk.text or "controlDict" in chunk.text for chunk in chunks)
