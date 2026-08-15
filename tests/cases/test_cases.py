"""Test cases for HarnessFOAM."""

import pytest
from harnessfoam.agents.graph import create_workflow, SimulationState

def test_full_workflow():
    workflow = create_workflow()
    
    initial_state = SimulationState(
        prompt="Perform a 2D incompressible lid driven cavity flow with top wall moving at 1 m/s.",
        case_id="case_12345",
        plan=[],
        mesh_job_id=None,
        run_job_id=None,
        viz_job_id=None,
        status="PENDING",
        logs={},
        errors=0,
        max_errors=3
    )
    
    results = workflow.invoke(initial_state)
    
    assert results['status'] == 'SUCCESS'
    assert len(results['plan']) > 0
    assert results['mesh_job_id'] is not None
    assert results['run_job_id'] is not None
    assert results['viz_job_id'] is not None
    assert results['errors'] == 1 # Simulated one error that gets fixed

def test_hpc_slurm_case():
    workflow = create_workflow()
    
    initial_state = SimulationState(
        prompt="Do an incompressible 3D lid driven cavity flow... Perform an hpc run in perlmutter.",
        case_id="case_hpc",
        plan=[],
        mesh_job_id=None,
        run_job_id=None,
        viz_job_id=None,
        status="PENDING",
        logs={},
        errors=0,
        max_errors=3
    )
    
    results = workflow.invoke(initial_state)
    assert results['status'] == 'SUCCESS'
