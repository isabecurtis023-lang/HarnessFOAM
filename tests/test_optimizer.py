import pytest
from unittest.mock import patch, MagicMock
from harnessfoam.agents.optimizer import OptSweepPlan, OptParameter, run_agentic_optimization

def test_opt_sweep_plan_schema():
    param = OptParameter(path="system/controlDict", key="deltaT", values=[0.001, 0.002])
    assert param.path == "system/controlDict"
    assert param.key == "deltaT"
    assert len(param.values) == 2

@patch("harnessfoam.agents.optimizer.generate_sweep_plan")
@patch("harnessfoam.agents.optimizer.run_parameter_sweep")
def test_run_agentic_optimization(mock_run_sweep, mock_generate_plan):
    # Mock the LLM generating a plan
    mock_plan = OptSweepPlan(
        parameters=[OptParameter(path="system/controlDict", key="deltaT", values=[0.01, 0.05])],
        objective="last_time",
        direction="max",
        reasoning="I want to find the largest stable time step."
    )
    mock_generate_plan.return_value = mock_plan
    
    # Mock the sweep engine execution
    mock_run_sweep.return_value = {
        "status": "COMPLETED",
        "best": {"objective": 0.05, "parameters": {"deltaT": 0.05}, "case_dir": "opt_agent_runs/case_001"},
        "evaluation": {"passed": 2, "total": 2, "success_rate": 1.0}
    }
    
    result = run_agentic_optimization("fake_base_case", "fake_output", "Maximize deltaT")
    
    assert result["status"] == "COMPLETED"
    assert "agent_reasoning" in result
    assert result["agent_reasoning"] == "I want to find the largest stable time step."
    assert "agent_plan" in result
    assert result["agent_plan"][0]["key"] == "deltaT"
    
    mock_generate_plan.assert_called_once_with("fake_base_case", "Maximize deltaT", None)
    mock_run_sweep.assert_called_once()
