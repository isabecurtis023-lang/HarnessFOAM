import pytest
from unittest.mock import patch, MagicMock
import argparse
from harnessfoam.cli import main, run_simulation

@patch("harnessfoam.api.server.start_server")
@patch("argparse.ArgumentParser.parse_args")
def test_cli_serve_command(mock_parse_args, mock_start_server):
    # Mock the args for "serve"
    mock_args = MagicMock()
    mock_args.command = "serve"
    mock_args.host = "127.0.0.1"
    mock_args.port = 8080
    mock_parse_args.return_value = mock_args

    # Dynamically patching start_server since it's imported locally
    with patch("harnessfoam.cli.start_server", mock_start_server, create=True):
        main()
    
    mock_start_server.assert_called_once_with(host="127.0.0.1", port=8080)

@patch("asyncio.run")
@patch("argparse.ArgumentParser.parse_args")
def test_cli_run_command(mock_parse_args, mock_asyncio_run):
    # Mock the args for "run"
    mock_args = MagicMock()
    mock_args.command = "run"
    mock_args.prompt = "Simulate cavity"
    mock_args.output = "test_dir"
    mock_parse_args.return_value = mock_args

    main()
    
    mock_asyncio_run.assert_called_once()
    # The actual coroutine argument is not trivial to assert directly without capturing it,
    # but asserting it was called is a good start for coverage.

@pytest.mark.asyncio
@patch("harnessfoam.cli.create_workflow")
async def test_run_simulation_coroutine(mock_create_workflow):
    mock_workflow = MagicMock()
    mock_create_workflow.return_value = mock_workflow
    
    # Mock the ainvoke method to return a dummy final state
    async def mock_ainvoke(initial_state):
        return {"file_plan": [{"folder": "system", "file": "controlDict"}]}
    
    mock_workflow.ainvoke = mock_ainvoke
    
    # Call the async function
    await run_simulation("test prompt", "output_test")
    
    mock_create_workflow.assert_called_once()
