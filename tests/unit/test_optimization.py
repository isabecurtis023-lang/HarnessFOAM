from harnessfoam.optimization import expand_parameter_grid


def test_parameter_grid_is_deterministic():
    result = expand_parameter_grid([
        {"key": "deltaT", "values": [0.001, 0.002]},
        {"key": "writeInterval", "values": [10, 20]},
    ])
    assert result == [
        {"deltaT": 0.001, "writeInterval": 10},
        {"deltaT": 0.001, "writeInterval": 20},
        {"deltaT": 0.002, "writeInterval": 10},
        {"deltaT": 0.002, "writeInterval": 20},
    ]
