from harnessfoam.tutorial_regression import list_tutorial_regressions


def test_official_tutorial_registry_is_openfoam13():
    registry = list_tutorial_regressions()
    assert set(registry) == {"cavity", "pitzDaily", "damBreak", "shockTube"}
    assert all(path for path in registry.values())
