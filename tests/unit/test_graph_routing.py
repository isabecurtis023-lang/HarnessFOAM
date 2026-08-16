import pytest
from unittest.mock import patch, MagicMock

from harnessfoam.agents.graph import should_review, end_node, create_workflow, SimulationState

def test_should_review_success():
    state = SimulationState(
        prompt="test",
        case_id="test",
        plan=[],
        status="SUCCESS",
        logs={},
        errors=0,
        max_errors=3
    )
    result = should_review(state)
    assert result == "visualize"

def test_should_review_retry():
    state = SimulationState(
        prompt="test",
        case_id="test",
        plan=[],
        status="FAILED",
        logs={},
        errors=1,
        max_errors=3
    )
    result = should_review(state)
    assert result == "review"

def test_should_review_max_errors():
    state = SimulationState(
        prompt="test",
        case_id="test",
        plan=[],
        status="FAILED",
        logs={},
        errors=3,
        max_errors=3
    )
    result = should_review(state)
    assert result == "fail"

def test_end_node():
    state = SimulationState(
        prompt="test",
        case_id="test",
        plan=[],
        status="SUCCESS",
        logs={},
        errors=0,
        max_errors=3
    )
    new_state = end_node(state)
    assert new_state["current_step"] == "end"

@patch("harnessfoam.agents.graph.architect_node")
@patch("harnessfoam.agents.graph.meshing_node")
@patch("harnessfoam.agents.graph.input_writer_node")
@patch("harnessfoam.agents.graph.runner_node")
@patch("harnessfoam.agents.graph.visualizer_node")
def test_create_workflow_compiles(mock_viz, mock_run, mock_input, mock_mesh, mock_arch):
    # Just verify that the workflow compiles without errors and returns a graph
    workflow = create_workflow()
    assert workflow is not None
